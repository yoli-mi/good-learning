"""Compile self-contained TeX into PDF using an ASCII build name.

Some Windows TeX installations cannot create log files whose names contain
Chinese characters. Build as study.tex in a temporary directory while keeping
the delivered TeX and PDF names descriptive.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

GRAPHICS = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")


def collect_images(tex: Path) -> list[Path]:
    """Figures referenced by the TeX, resolved next to it.

    The build happens in a temporary directory, so every referenced file has to
    be copied along.  A Chinese *directory* is fine (only the bare file name is
    written into the TeX), but a Chinese *file name* still trips some TeX
    installations, so it is rejected here with an actionable message instead of
    failing inside the compiler.
    """
    text = tex.read_text(encoding="utf-8", errors="replace")
    found: list[Path] = []
    for name in sorted({Path(n).name for n in GRAPHICS.findall(text)}):
        if not name.isascii():
            raise SystemExit(
                f"图片文件名需要是 ASCII：{name} —— 请改成 sheet-error-1.png 这类名字后再编译"
            )
        candidate = tex.parent / name
        if not candidate.is_file():
            raise SystemExit(f"图片缺失：{candidate}")
        found.append(candidate)
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Self-contained TeX source")
    parser.add_argument("output", type=Path, help="Final PDF file")
    parser.add_argument("--compiler", choices=["xelatex", "lualatex"], default="xelatex")
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if compiler is None:
        raise SystemExit(f"{args.compiler} is unavailable; PDF was not created")
    if args.source.suffix.lower() != ".tex" or args.output.suffix.lower() != ".pdf":
        raise SystemExit("Expected a .tex source and .pdf output")

    images = collect_images(args.source)

    with tempfile.TemporaryDirectory(prefix="good-learning-") as directory:
        build = Path(directory)
        tex = build / "study.tex"
        shutil.copyfile(args.source, tex)
        for image in images:
            shutil.copyfile(image, build / image.name)
        command = [compiler, "-interaction=nonstopmode", "-halt-on-error", tex.name]
        for pass_number in (1, 2):
            result = subprocess.run(
                command, cwd=build, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", check=False,
            )
            if result.returncode:
                raise SystemExit(
                    f"{args.compiler} pass {pass_number} failed:\n"
                    + "\n".join(result.stdout.splitlines()[-30:])
                )
        pdf = build / "study.pdf"
        if not pdf.is_file() or pdf.stat().st_size == 0:
            raise SystemExit("Compiler finished without producing a PDF")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pdf, args.output)
        print(f"Compiled {args.output} with {args.compiler} (2 passes)")


if __name__ == "__main__":
    main()
