"""Turn the learning skill's Markdown into a XeLaTeX-ready document.

The PDF is compiled separately with xelatex.  A single Markdown lesson can be
rendered in compact or print-writing layout without changing its content.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TOKEN = re.compile(r"(\$\$[\s\S]*?\$\$|\$[^$\n]+?\$|\*\*[^*]+?\*\*|\[[^\]]+\]\([^)]*\))")
QUESTION = re.compile(r"^\*\*((?:[A-Z]\d+|题\s*\d+|练习\s*\d+|\d+))[.．:：]\*\*\s*(.*)$")
HEADING = re.compile(r"^(#{1,3})\s+(.*)$")
ORDERED = re.compile(r"^\d+\.\s+(.*)$")
# ![替代文字](文件名.png) —— 单独成行的图片引用，用于把错题重做纸放进 PDF
IMAGE = re.compile(r'^!\[([^\]]*)\]\(([^)\s]+)\)\s*$')


def escape_tex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "①": r"{\circledfont ①}",
        "②": r"{\circledfont ②}",
        "③": r"{\circledfont ③}",
        "④": r"{\circledfont ④}",
        "⑤": r"{\circledfont ⑤}",
    }
    return "".join(replacements.get(char, char) for char in text)


def inline(text: str) -> str:
    result: list[str] = []
    end = 0
    for match in TOKEN.finditer(text):
        result.append(escape_tex(text[end : match.start()]))
        token = match.group()
        if token.startswith("$$"):
            result.append(r"\[" + token[2:-2].strip() + r"\]")
        elif token.startswith("$"):
            result.append(token)
        elif token.startswith("**"):
            result.append(r"\textbf{" + inline(token[2:-2]) + "}")
        else:
            link = re.fullmatch(r"\[([^\]]+)\]\(([^)]*)\)", token)
            assert link
            result.append(r"\href{" + link.group(2) + "}{" + inline(link.group(1)) + "}")
        end = match.end()
    result.append(escape_tex(text[end:]))
    return "".join(result)


def image_tex(name: str, alt: str = "") -> str:
    """A standalone `![说明](图.png)` line becomes a full-width figure.

    Only the file name is written into the TeX: compile_study_pdf.py copies that
    file into the build directory, so directories with Chinese characters never
    reach the LaTeX engine.
    """
    file = Path(name).name
    caption = escape_tex(alt.strip())
    body = (
        r"\begin{figure}[htbp]\centering"
        r"\includegraphics[width=\linewidth,height=0.86\textheight,keepaspectratio]{" + file + r"}"
    )
    if caption:
        body += r"\par\smallskip{\small " + caption + "}"
    return body + r"\end{figure}"


def table_tex(lines: list[str], kind: str) -> str:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    if len(rows) < 2 or not all(re.fullmatch(r":?-+:?", cell) for cell in rows[1]):
        raise ValueError("Malformed Markdown table")
    headers, data = rows[0], rows[2:]
    count = len(headers)
    if count == 4 and kind == "knowledge":
        widths = [.08, .40, .29, .16]
    elif count == 4:
        widths = [.14, .17, .31, .31]
    elif count == 3:
        widths = [.17, .48, .28]
    elif count == 2:
        widths = [.12, .82]
    else:
        widths = [0.94 / count] * count
    columns = "".join(f"P{{{width:.2f}\\linewidth}}" for width in widths)
    def row(cells: list[str]) -> str:
        if len(cells) != count:
            raise ValueError(f"Expected {count} table cells, got {len(cells)}: {cells}")
        return " & ".join(inline(cell) for cell in cells) + r" \\"
    stretch = "1.22" if kind == "knowledge" else "1.38"
    row_gap = ".15em" if kind == "knowledge" else ".35em"
    out = [rf"{{\small\renewcommand{{\arraystretch}}{{{stretch}}}\setlength{{\tabcolsep}}{{3.5pt}}",
           r"\begin{longtable}{" + columns + "}",
           r"\toprule", r"\bfseries " + row(headers).replace(" & ", r" & \bfseries "),
           r"\midrule", r"\endfirsthead", r"\toprule",
           r"\bfseries " + row(headers).replace(" & ", r" & \bfseries "),
           r"\midrule", r"\endhead"]
    for cells in data:
        out.extend([row(cells), rf"\addlinespace[{row_gap}]"])
    out.extend([r"\bottomrule", r"\end{longtable}", "}"])
    return "\n".join(out)


def question_space(number: str) -> int:
    values = {
        "R1": 42, "R2": 38, "R3": 42, "R4": 42, "R5": 44,
        "V1": 30, "V2": 42, "V3": 34, "V4": 40,
        "V5": 29, "V6": 39, "V7": 39, "V8": 42,
        "V9": 34, "V10": 42, "V11": 34, "V12": 43,
        "M1": 40, "M2": 34, "M3": 34, "M4": 38,
        "M5": 43, "M6": 43, "M7": 45, "M8": 45,
        "A1": 23, "A2": 26, "A3": 34,
        "B1": 24, "B2": 34, "B3": 34, "B4": 42,
        "C1": 27, "C2": 35, "C3": 38, "C4": 38,
        "D1": 32, "D2": 32, "D3": 32, "D4": 32, "D5": 34,
    }
    return values.get(number, 35)


def body_tex(markdown: str, kind: str, layout: str) -> str:
    lines = markdown.lstrip("\ufeff").splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    list_kind: str | None = None
    in_exercises = False
    error_seen = False

    def flush_paragraph() -> None:
        if paragraph:
            out.append(inline(" ".join(paragraph)) + "\n")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            out.append(r"\end{" + list_kind + "}")
            list_kind = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            flush_paragraph()
            i += 1
            continue
        if line.startswith("|"):
            flush_paragraph()
            close_list()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            out.append(table_tex(rows, kind))
            continue
        image = IMAGE.match(line)
        if image:
            flush_paragraph()
            close_list()
            out.append(image_tex(image.group(2), image.group(1)))
            i += 1
            continue
        if line.startswith("$$"):
            flush_paragraph()
            close_list()
            math = [line]
            while len(math) == 1 and math[0].count("$$") == 1 or (len(math) > 1 and not math[-1].endswith("$$")):
                i += 1
                if i >= len(lines):
                    raise ValueError("Unclosed display math")
                math.append(lines[i].strip())
            expr = "\n".join(math).removeprefix("$$").removesuffix("$$").strip()
            out.append(r"\[" + expr + r"\]")
            i += 1
            continue
        heading = HEADING.match(line)
        if heading:
            flush_paragraph()
            close_list()
            level, title = len(heading.group(1)), heading.group(2)
            if kind in ("day", "errors"):
                if level == 2 and re.match(r"单元\s*\d", title):
                    out.append(r"\clearpage")
                    in_exercises = False
                elif kind == "errors" and level == 2 and re.match(r"错题\s*\d", title):
                    if error_seen:
                        out.append(r"\clearpage")
                    error_seen = True
                    in_exercises = False
                elif level == 3 and "举一反三" in title:
                    in_exercises = True
                elif kind == "errors" and level == 3 and "再做一题" in title:
                    in_exercises = True
                elif level == 2 and re.search(r"独立练习|练习题|自主练习|巩固练习", title):
                    out.append(r"\clearpage")
                    in_exercises = True
                elif level == 2 and "答案" in title:
                    in_exercises = False
                    out.append(r"\clearpage")
                elif level == 3 and "混合题答案" in title:
                    out.append(r"\clearpage")
                elif level == 2:
                    in_exercises = False
            command = {1: "chaptertitle", 2: "section", 3: "subsection"}[level]
            out.append("\\" + command + "{" + inline(title) + "}")
            i += 1
            continue
        if in_exercises and kind in ("day", "errors"):
            question = QUESTION.match(line)
            if question:
                flush_paragraph()
                close_list()
                label, prompt = question.groups()
                suffix = "Colon" if kind == "errors" else ""
                if layout == "loose":
                    out.append(r"\PracticeQuestion" + suffix + "{" + inline(label) + "}{" + inline(prompt) + "}{" + str(question_space(label)) + "}")
                else:
                    out.append(r"\CompactQuestion" + suffix + "{" + inline(label) + "}{" + inline(prompt) + "}")
                i += 1
                continue
            plain_question = ORDERED.match(line)
            if plain_question:
                flush_paragraph()
                close_list()
                label = line.split(".", 1)[0]
                prompt = plain_question.group(1)
                if layout == "loose":
                    out.append(r"\PracticeQuestion{" + label + "}{" + inline(prompt) + "}{35}")
                else:
                    out.append(r"\CompactQuestion{" + label + "}{" + inline(prompt) + "}")
                i += 1
                continue
        bullet = line.startswith("- ")
        numbered = ORDERED.match(line)
        if bullet or numbered:
            flush_paragraph()
            target = "itemize" if bullet else "enumerate"
            if list_kind != target:
                close_list()
                out.append(r"\begin{" + target + "}")
                list_kind = target
            item = line[2:] if bullet else numbered.group(1)
            out.append(r"\item " + inline(item))
            i += 1
            continue
        close_list()
        paragraph.append(line)
        i += 1
    flush_paragraph()
    close_list()
    return "\n".join(out)


def map_header(info: dict, kind: str) -> list[str]:
    caption = info.get("caption", {"knowledge": "知识结构", "plan": "备考路径", "day": "每日课程"}[kind])
    return [
        r"\thispagestyle{empty}",
        r"\noindent{\sffamily\footnotesize " + escape_tex(caption) + r"}\hfill{\sffamily\footnotesize 学习导图}\par",
        r"\vspace{7mm}",
        r"\noindent{\sffamily\fontsize{25}{30}\selectfont\bfseries " + escape_tex(info["title"]) + r"}\par",
        r"\vspace{4mm}\noindent\rule{\linewidth}{.85pt}\par\vspace{6mm}",
        r"\begin{center}",
        r"\begin{tikzpicture}[x=1cm,y=1cm,>=stealth,every node/.style={font=\sffamily}]",
    ]


def map_knowledge(info: dict) -> list[str]:
    nodes = info["nodes"]
    out = [r"\path[use as bounding box] (-8.1,-18.7) rectangle (8.1,.4);",
           r"\node[font=\sffamily\Large\bfseries] at (0,-.65) {" + escape_tex(info.get("headline", info["title"])) + "};",
           r"\node[font=\sffamily\small,text=black!55] at (0,-1.35) {" + escape_tex(info.get("tagline", "按模块学习并检验掌握")) + "};",
           r"\draw[line width=.85pt] (0,-1.9) -- (0,-2.45);",
           r"\draw[line width=.85pt] (-4,-2.45) -- (4,-2.45);",
           r"\draw[line width=.85pt] (-4,-2.45) -- (-4,-2.8);",
           r"\draw[line width=.85pt] (4,-2.45) -- (4,-2.8);",
           r"\node[font=\sffamily\bfseries] at (-4,-3.15) {" + escape_tex(info.get("groups", ["基础模块", "进阶模块"])[0]) + "};",
           r"\node[font=\sffamily\bfseries] at (4,-3.15) {" + escape_tex(info.get("groups", ["基础模块", "进阶模块"])[1]) + "};"]
    for i, node in enumerate(nodes):
        col = 0 if i < 3 else 1
        x = -7.4 if col == 0 else .8
        row = i if col == 0 else i - 3
        y = -4.3 - 4.1 * row
        out.extend([
            rf"\node[anchor=north west,font=\sffamily\fontsize{{22}}{{24}}\selectfont\bfseries,text=black!50] at ({x},{y}) {{{i+1:02d}}};",
            rf"\node[anchor=north west,text width=5.9cm,align=left,font=\sffamily\large\bfseries] at ({x+1.15},{y+.02}) " + "{" + escape_tex(node["title"]) + "};",
            rf"\node[anchor=north west,text width=5.9cm,align=left,font=\sffamily\small] at ({x+1.15},{y-.75}) " + "{" + r"\\[.25em]".join(escape_tex(t) for t in node["lines"][:2]) + "};",
            rf"\node[anchor=west,font=\sffamily\footnotesize,text=black!60] at ({x+1.15},{y-2.05}) " + "{" + escape_tex(node["lines"][-1]) + "};",
            rf"\draw[black!35,line width=.4pt] ({x},{y-2.35}) -- ({x+7.15},{y-2.35});",
        ])
    out.append(r"\node[font=\sffamily\small,text=black!55] at (0,-17.95) {" + escape_tex(info.get("footnote", "按编号复习 · 用能力验证检验掌握")) + "};")
    return out


def map_plan(info: dict) -> list[str]:
    nodes = info["nodes"]
    out = [r"\path[use as bounding box] (-8.1,-19.3) rectangle (8.1,.4);",
           r"\node[anchor=west,font=\sffamily\Large\bfseries] at (-7.5,-.55) {" + escape_tex(info.get("headline", info["title"])) + "};",
           r"\node[anchor=east,font=\sffamily\small,text=black!55] at (7.5,-.55) {" + escape_tex(info.get("date_range", "")) + "};",
           r"\draw[black!45,line width=.7pt] (-6.65,-1.75) -- (-6.65,-16.65);"]
    for i, node in enumerate(nodes[:5]):
        y = -2.25 - 3.35 * i
        date = node["lines"][0]
        details = node["lines"][1:]
        out.extend([
            rf"\node[circle,draw=black,line width=.7pt,minimum size=9mm,fill=white,font=\sffamily\small\bfseries] at (-6.65,{y}) {{{i+1:02d}}};",
            rf"\node[anchor=west,font=\sffamily\large\bfseries] at (-5.75,{y+.45}) " + "{" + escape_tex(node["title"]) + "};",
            rf"\node[anchor=east,font=\sffamily\small,text=black!55] at (7.45,{y+.45}) " + "{" + escape_tex(date) + "};",
            rf"\node[anchor=north west,text width=12.8cm,align=left,font=\sffamily\small] at (-5.75,{y-.15}) " + "{" + r"\quad{}·\quad{}".join(escape_tex(t) for t in details) + "};",
            rf"\draw[black!25,line width=.4pt] (-5.75,{y-1.35}) -- (7.45,{y-1.35});",
        ])
    feedback = nodes[5]
    out.extend([
        r"\draw[black!45,line width=.7pt] (-7.5,-18.35) -- (7.5,-18.35);",
        r"\node[anchor=west,font=\sffamily\bfseries] at (-7.4,-18.8) {" + escape_tex(feedback["title"]) + "};",
        r"\node[anchor=east,font=\sffamily\small] at (7.4,-18.8) {" + "  →  ".join(escape_tex(t) for t in feedback["lines"]) + "};",
    ])
    return out


def map_day(info: dict) -> list[str]:
    nodes = info["nodes"]
    out = [r"\path[use as bounding box] (-8.1,-18.7) rectangle (8.1,.4);",
           r"\node[font=\sffamily\Large\bfseries] at (0,-.6) {" + escape_tex(info.get("headline", info["title"])) + "};",
           r"\node[font=\sffamily\small,text=black!55] at (0,-1.25) {" + escape_tex(info.get("tagline", "从概念走向独立练习")) + "};"]
    positions = [(-7.35,-2.35), (.85,-2.35), (.85,-7.7), (-7.35,-7.7), (-7.35,-13.05), (.85,-13.05)]
    for i, (x, y) in enumerate(positions):
        node = nodes[i]
        out.extend([
            rf"\node[anchor=north west,font=\sffamily\fontsize{{22}}{{24}}\selectfont\bfseries,text=black!50] at ({x},{y}) {{{i+1:02d}}};",
            rf"\node[anchor=north west,text width=5.8cm,align=left,font=\sffamily\large\bfseries] at ({x+1.15},{y+.03}) " + "{" + escape_tex(node["title"]) + "};",
            rf"\node[anchor=north west,text width=5.9cm,align=left,font=\sffamily\small] at ({x+1.15},{y-.72}) " + "{" + r"\\[.25em]".join(escape_tex(t) for t in node["lines"]) + "};",
            rf"\draw[black!35,line width=.4pt] ({x},{y-2.7}) -- ({x+7.05},{y-2.7});",
        ])
    out.extend([
        r"\draw[->,black!55,line width=.8pt] (-.12,-3.7) -- (.55,-3.7);",
        r"\draw[->,black!55,line width=.8pt] (7.85,-5.45) -- (7.85,-7.2);",
        r"\draw[->,black!55,line width=.8pt] (.52,-9.05) -- (-.15,-9.05);",
        r"\draw[->,black!55,line width=.8pt] (-7.85,-10.8) -- (-7.85,-12.55);",
        r"\draw[->,black!55,line width=.8pt] (-.12,-14.4) -- (.55,-14.4);",
        r"\node[font=\sffamily\small,text=black!55] at (0,-18.1) {" + escape_tex(info.get("footnote", "概念 → 例题 → 独立练习 → 核对答案")) + "};",
    ])
    return out


def map_tex(info: dict, kind: str) -> str:
    if len(info["nodes"]) != 6:
        raise ValueError("Mindmap needs exactly six nodes")
    out = map_header(info, kind)
    out.extend({"knowledge": map_knowledge, "plan": map_plan, "day": map_day}[kind](info))
    out.extend([r"\end{tikzpicture}", r"\end{center}", r"\clearpage"])
    return "\n".join(out)


PREAMBLE = r"""\documentclass[UTF8,a4paper,11pt]{ctexart}
\usepackage[margin=22mm,headheight=14pt,footskip=12mm]{geometry}
\usepackage{amsmath,amssymb,array,longtable,booktabs,tikz,needspace,enumitem,fancyhdr,hyperref,graphicx}
\usepackage{microtype}
\hypersetup{colorlinks=false,pdfborder={0 0 0},pdfauthor={Good Learning},bookmarks=false}
\newfontfamily\circledfont{Segoe UI Symbol}
\newcolumntype{P}[1]{>{\raggedright\arraybackslash}p{#1}}
\setlength{\LTleft}{0pt}\setlength{\LTright}{0pt}
\setlength{\parindent}{0pt}\setlength{\parskip}{.65em}
\linespread{1.18}
\raggedbottom
\setcounter{secnumdepth}{0}
\setlist{leftmargin=2.2em,itemsep=.4em,topsep=.5em}
\ctexset{section={format=\Large\bfseries\sffamily,beforeskip=1.35em,afterskip=.65em},
subsection={format=\large\bfseries\sffamily,beforeskip=1em,afterskip=.45em}}
\newcommand{\chaptertitle}[1]{\Needspace{8\baselineskip}\noindent{\LARGE\bfseries\sffamily #1}\par\vspace{4mm}\hrule\vspace{6mm}}
\newcommand{\CompactQuestion}[2]{\par\noindent\textbf{#1.}\ #2\par\vspace{.8em}}
\newcommand{\PracticeQuestion}[3]{\par\Needspace{4\baselineskip}\noindent\begin{minipage}{\linewidth}\textbf{#1.}\ #2\par\noindent\rule{0pt}{#3mm}\par\end{minipage}\par}
\newcommand{\CompactQuestionColon}[2]{\par\noindent\textbf{#1：}\ #2\par\vspace{.8em}}
\newcommand{\PracticeQuestionColon}[3]{\par\Needspace{4\baselineskip}\noindent\begin{minipage}{\linewidth}\textbf{#1：}\ #2\par\noindent\rule{0pt}{#3mm}\par\end{minipage}\par}
\pagestyle{fancy}\fancyhf{}\fancyfoot[C]{\thepage}\renewcommand{\headrulewidth}{0pt}
\begin{document}
"""


def render(source: Path, output: Path, kind: str, layout: str, map_info: dict) -> None:
    markdown = source.read_text(encoding="utf-8")
    cover = dict(map_info)
    if kind == "day":
        cover["title"] += "（宽松排版型）" if layout == "loose" else "（紧凑排版型）"
    list_style = r"\setlist[enumerate]{label=\arabic*）}" if kind == "errors" else ""
    cover_tex = "" if kind == "errors" else map_tex(cover, kind) + "\n"
    tex = PREAMBLE + cover_tex + list_style + "\n" + body_tex(markdown, kind, layout) + "\n\\end{document}\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(tex, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--kind", choices=["knowledge", "plan", "day", "errors"], required=True)
    parser.add_argument("--layout", choices=["compact", "loose"], default="compact")
    parser.add_argument("--map-config", type=Path)
    args = parser.parse_args()
    config = json.loads(args.map_config.read_text(encoding="utf-8")) if args.map_config else {}
    if args.kind != "errors" and args.kind not in config:
        parser.error("--map-config must contain the selected document kind")
    render(args.source, args.output, args.kind, args.layout, config.get(args.kind, {}))


if __name__ == "__main__":
    main()
