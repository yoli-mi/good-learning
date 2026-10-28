#!/usr/bin/env python3
"""Render one wrong-answer sheet as an image: the learner's own work on the left
with the broken step highlighted in red, the corrected solution on the right.

    python scripts/render_mistake_sheet.py examples/mistake-sheet.json out/sheet.png
    python scripts/render_mistake_sheet.py in.json out/sheet.png --dpi 300

Input is a JSON object (see references/mistake-sheet.md):

    {
      "title": "第 2 题 · 隐函数求导",
      "diagnosis": "错因：概念混淆 + 符号错误。……",
      "my_steps": ["e^y + xy = e", "...", "y''(0) = 2/e^2"],
      "error_from": 9,
      "correct_steps": ["e^y + xy = e", "...", "y''(0) = 1/e^2"],
      "pitfalls": ["……", "……"],
      "knowledge_point": "隐函数求导与二阶导数"
    }

`error_from` is the zero-based index of the first wrong line (-1 disables the
red highlight). If the content does not fit on one page the sheet is split into
page 1 (diagnosis + learner's work) and page 2 (pitfalls + solution).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── geometry: A4 at 150dpi, scaled at runtime by --dpi ───────────────────────
BASE_DPI = 150
_A4 = (1240, 1754)          # 210mm × 297mm at 150dpi

W, H = _A4
MARGIN = 58
GUTTER = 36
COL_W = (W - 2 * MARGIN - GUTTER) // 2
COL_X = [MARGIN, MARGIN + COL_W + GUTTER]
TOP = MARGIN + 92
BOTTOM = H - MARGIN - 20

ROW_H = 38            # baseline grid: one text row; fractions take two
BODY = 22             # body size (≈10.5pt at 150dpi)
SMALL = 15            # superscript / subscript
HEAD = 20             # section heading
TITLE = 30
SUP_RISE = 8
SUB_DROP = 7
BAR_GAP = 5           # gap between the fraction rule and numerator/denominator
BAR_PAD = 6
MATH_AXIS = 7         # fractions sit on the math axis, not on the baseline
SCALE = 1.0           # set by --dpi

INK = (38, 42, 48)
RED = (198, 44, 44)
BLUE = (34, 84, 150)
GREY = (120, 128, 136)
GRID_COLOR = (228, 231, 235)
PAPER = (253, 253, 251)


def apply_dpi(dpi: int) -> None:
    """Scale every layout constant so the same layout renders at another dpi."""
    global W, H, MARGIN, GUTTER, COL_W, COL_X, TOP, BOTTOM, ROW_H
    global BODY, SMALL, HEAD, TITLE, SUP_RISE, SUB_DROP, BAR_GAP, BAR_PAD, MATH_AXIS, SCALE
    k = dpi / BASE_DPI
    SCALE = k
    W = int(round(_A4[0] * k))
    H = int(round(_A4[1] * k))
    MARGIN = int(round(58 * k))
    GUTTER = int(round(36 * k))
    COL_W = (W - 2 * MARGIN - GUTTER) // 2
    COL_X = [MARGIN, MARGIN + COL_W + GUTTER]
    TOP = MARGIN + int(round(92 * k))
    BOTTOM = H - MARGIN - int(round(20 * k))
    ROW_H = int(round(38 * k))
    BODY = int(round(22 * k))
    SMALL = int(round(15 * k))
    HEAD = int(round(20 * k))
    TITLE = int(round(30 * k))
    SUP_RISE = int(round(8 * k))
    SUB_DROP = int(round(7 * k))
    BAR_GAP = int(round(5 * k))
    BAR_PAD = int(round(6 * k))
    MATH_AXIS = int(round(7 * k))


def pen(width: int) -> int:
    return max(1, int(round(width * SCALE)))


def find_font(explicit: Path | None, bold: bool = False) -> Path:
    candidates = [
        explicit,
        Path(os.environ["GOOD_LEARNING_FONT"]) if os.environ.get("GOOD_LEARNING_FONT") else None,
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
        Path("C:/Windows/Fonts/Deng.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    ]
    for path in candidates:
        if path and path.is_file():
            return path
    raise RuntimeError("No Chinese font found; supply --font for PNG output")


# ── math markup ─────────────────────────────────────────────────────────────
SUP_CHARS = "⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ⁺⁻ⁱˣ"
_SUP = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6",
        "⁷": "7", "⁸": "8", "⁹": "9", "ⁿ": "n", "⁺": "+", "⁻": "-", "ⁱ": "i", "ˣ": "x"}
_SUB = {"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4", "₅": "5", "₆": "6",
        "₇": "7", "₈": "8", "₉": "9", "ₙ": "n", "ₓ": "x", "₊": "+", "₋": "-"}

TOKEN = r"[A-Za-z0-9_]+(?:[" + SUP_CHARS + r"]+|\^\{[^{}\n]*\}|\^[A-Za-z0-9])?"
FRACTIONS = [
    re.compile(r"((?:sin|cos|tan|cot|sec|csc|ln|log|exp)\s+" + TOKEN + r")\s*/\s*(\([^()\n]{1,24}\)|" + TOKEN + r")"),
    re.compile(r"(\([^()\n]{1,24}\))\s*/\s*(\([^()\n]{1,24}\))"),
    re.compile(r"(\([^()\n]{1,24}\))\s*/\s*(" + TOKEN + r")"),
    re.compile(r"(?<![\w./])(-?" + TOKEN + r")\s*/\s*(\([^()\n]{1,24}\))"),
    re.compile(r"(?<![\w./])(-?" + TOKEN + r")\s*/\s*(" + TOKEN + r")(?![\w./" + SUP_CHARS + r"\x00])"),
]
MATH_HINT = re.compile(r"[=→≈≤≥≠^∑∫√]|lim|ln|sin|cos|tan|log|frac")
FUNC_TAIL = re.compile(r"(?:sin|cos|tan|cot|sec|csc|ln|log|exp|lim|arcsin|arccos|arctan)\s*$")
CJK = re.compile(r"[\u4e00-\u9fa5]")

GREEK = {
    "\\to": "→", "\\infty": "∞", "\\pi": "π", "\\cdot": "·", "\\approx": "≈",
    "\\neq": "≠", "\\leq": "≤", "\\geq": "≥", "\\times": "×", "\\Delta": "Δ",
    "\\alpha": "α", "\\beta": "β", "\\theta": "θ", "\\lim": "lim", "\\int": "∫",
    "\\sum": "∑", "\\ln": "ln", "\\sin": "sin", "\\cos": "cos", "\\tan": "tan",
    "\\left": "", "\\right": "", "\\,": " ", "\\;": " ",
    "✓": "√", "✔": "√", "✗": "×", "✘": "×", "✅": "√", "❌": "×",
}


def normalize_scripts(text: str) -> str:
    """Unicode superscripts/subscripts → ^{} / _{} so they can be typeset."""
    out: list[str] = []
    buf, kind = "", None

    def flush() -> None:
        nonlocal buf, kind
        if buf:
            out.append(("^" if kind == "s" else "_") + "{" + buf + "}")
            buf = ""

    for ch in text:
        if ch in _SUP:
            if kind != "s":
                flush()
                kind = "s"
            buf += _SUP[ch]
        elif ch in _SUB:
            if kind != "b":
                flush()
                kind = "b"
            buf += _SUB[ch]
        else:
            flush()
            out.append(ch)
    flush()
    return "".join(out)


def auto_fractions(text: str) -> str:
    """Turn a/b, (x+1)/(2y) … into \\frac so plain slashes still typeset.

    Only touches lines that look like formulas: URLs, CJK glued to a slash, and
    prose lines (six or more CJK characters) are left alone.
    """
    s = text
    if "://" in s or not MATH_HINT.search(s):
        return s
    if re.search(r"[\u4e00-\u9fa5]\s*/|/\s*[\u4e00-\u9fa5]", s):
        return s
    if len(CJK.findall(s)) >= 6:
        return s

    protected: list[str] = []

    def protect(m: re.Match) -> str:
        protected.append(m.group(0))
        return "\x00%d\x00" % (len(protected) - 1)

    s = re.sub(r"[\^_]\s*(?:\{[^{}]*\}|\([^()]*\)|\w)", protect, s)
    for pattern in FRACTIONS:
        def rep(m: re.Match, _s: str = s) -> str:
            if FUNC_TAIL.search(_s[max(0, m.start(1) - 6):m.start(1)]):
                return m.group(0)
            return "\\frac{" + m.group(1) + "}{" + m.group(2) + "}"
        s = pattern.sub(rep, s)
    if protected:
        s = re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], s)
    return s


def prettify(text: str, frac: bool = True) -> str:
    text = auto_fractions(text) if frac else text
    text = normalize_scripts(text)

    def sqrt(m: re.Match) -> str:
        inner = m.group(1).strip()
        return f"√{inner}" if re.fullmatch(r"[\w\u4e00-\u9fa5]+", inner) else f"√({inner})"

    text = re.sub(r"\\sqrt\{([^{}]*)\}", sqrt, text)
    for k, v in GREEK.items():
        text = text.replace(k, v)
    return text


# ── layout nodes ────────────────────────────────────────────────────────────
class Txt:
    __slots__ = ("text", "kind")

    def __init__(self, text: str, kind: str = "n") -> None:
        self.text = text
        self.kind = kind


class Frac:
    __slots__ = ("num", "den")

    def __init__(self, num: list, den: list) -> None:
        self.num = num
        self.den = den


def _match_brace(s: str, i: int) -> int:
    depth = 0
    for k in range(i, len(s)):
        if s[k] == "{":
            depth += 1
        elif s[k] == "}":
            depth -= 1
            if depth == 0:
                return k
    return -1


def parse_nodes(text: str) -> list:
    out: list = []
    buf = ""
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        m = re.match(r"\\(?:d)?frac\s*\{", text[i:])
        if m:
            lb = i + m.end() - 1
            rb = _match_brace(text, lb)
            if rb > 0:
                j = rb + 1
                while j < n and text[j] == " ":
                    j += 1
                if j < n and text[j] == "{":
                    rb2 = _match_brace(text, j)
                    if rb2 > 0:
                        if buf:
                            out.append(Txt(buf))
                            buf = ""
                        out.append(Frac(parse_nodes(text[lb + 1:rb]), parse_nodes(text[j + 1:rb2])))
                        i = rb2 + 1
                        continue
            buf += ch
            i += 1
            continue
        if ch in "^_" and i + 1 < n:
            kind = "sup" if ch == "^" else "sub"
            j = i + 1
            inner, end = None, j
            if text[j] == "{":
                k = _match_brace(text, j)
                if k > 0:
                    inner, end = text[j + 1:k], k + 1
            elif text[j] == "(":
                k = text.find(")", j + 1)
                if k > 0:
                    inner, end = text[j + 1:k], k + 1
            else:
                inner, end = text[j], j + 1
            if inner is not None:
                if buf:
                    out.append(Txt(buf))
                    buf = ""
                out.append(Txt(inner, kind))
                i = end
                continue
            buf += ch
            i += 1
            continue
        buf += ch
        i += 1
    if buf:
        out.append(Txt(buf))
    return out


class Fonts:
    def __init__(self, regular: Path, bold: Path) -> None:
        self.n = ImageFont.truetype(str(regular), BODY)
        self.s = ImageFont.truetype(str(regular), SMALL)
        self.head = ImageFont.truetype(str(bold), HEAD)
        self.title = ImageFont.truetype(str(bold), TITLE)
        self.tiny = ImageFont.truetype(str(regular), max(10, int(15 * SCALE)))
        self.asc_n, self.desc_n = self.n.getmetrics()
        self.asc_s, self.desc_s = self.s.getmetrics()


def measure(nodes: list, F: Fonts) -> tuple[float, int, int]:
    w, up, down = 0.0, 0, 0
    for nd in nodes:
        nw, nu, nd_ = measure_one(nd, F)
        w += nw
        up = max(up, nu)
        down = max(down, nd_)
    return w, up, down


def measure_one(nd, F: Fonts) -> tuple[float, int, int]:
    if isinstance(nd, Txt):
        if nd.kind == "sup":
            return F.s.getlength(nd.text), F.asc_s + SUP_RISE, max(0, F.desc_s - SUP_RISE)
        if nd.kind == "sub":
            return F.s.getlength(nd.text), F.asc_s, F.desc_s + SUB_DROP
        return F.n.getlength(nd.text), F.asc_n, F.desc_n
    nw, nu, ndown = measure(nd.num, F)
    dw, du, dd = measure(nd.den, F)
    width = max(nw, dw) + 2 * BAR_PAD
    return width, nu + ndown + BAR_GAP + MATH_AXIS, max(0, du + dd + BAR_GAP - MATH_AXIS)


def draw_nodes(draw: ImageDraw.ImageDraw, x: float, baseline: float, nodes: list,
               F: Fonts, fill) -> None:
    cx = x
    for nd in nodes:
        nw = measure_one(nd, F)[0]
        if isinstance(nd, Txt):
            if nd.kind == "sup":
                draw.text((cx, baseline - SUP_RISE - F.asc_s), nd.text, font=F.s, fill=fill)
            elif nd.kind == "sub":
                draw.text((cx, baseline + SUB_DROP - F.asc_s), nd.text, font=F.s, fill=fill)
            else:
                draw.text((cx, baseline - F.asc_n), nd.text, font=F.n, fill=fill)
        else:
            nw2, _nu2, nd2 = measure(nd.num, F)
            dw2, du2, _dd2 = measure(nd.den, F)
            bar_y = baseline - MATH_AXIS
            draw_nodes(draw, cx + (nw - nw2) / 2, bar_y - BAR_GAP - nd2, nd.num, F, fill)
            draw.line([(cx, bar_y), (cx + nw, bar_y)], fill=fill, width=pen(2))
            draw_nodes(draw, cx + (nw - dw2) / 2, bar_y + BAR_GAP + du2, nd.den, F, fill)
        cx += nw


def wrap_nodes(nodes: list, F: Fonts, max_w: float) -> list[list]:
    """Greedy wrap. Long text runs are split by character, preferring spaces;
    superscripts/subscripts never start a line on their own."""
    lines: list[list] = []
    cur: list = []
    cur_w = 0.0

    def commit(upto: int) -> None:
        """Push cur[:upto] as a finished line, keep the rest in cur."""
        nonlocal cur, cur_w
        head, tail = cur[:upto], cur[upto:]
        if head:
            lines.append(head)
        cur = tail
        cur_w = sum(measure_one(x, F)[0] for x in cur)

    for nd in nodes:
        nw = measure_one(nd, F)[0]
        # 1) try to break at the last space when the node does not fit
        if cur and cur_w + nw > max_w:
            cut = -1
            for idx in range(len(cur) - 1, -1, -1):
                nd2 = cur[idx]
                if isinstance(nd2, Txt) and nd2.kind == "n" and nd2.text.endswith(" "):
                    cut = idx
                    break
            if cut >= 0:
                cur[cut] = Txt(cur[cut].text.rstrip(" "))
                commit(cut + 1)
        # 2) place the node, splitting long text by character
        if isinstance(nd, Txt) and nd.kind == "n":
            base_w = cur_w
            piece = ""
            for ch in nd.text:
                if base_w + F.n.getlength(piece + ch) <= max_w or (not cur and not piece):
                    piece += ch
                else:
                    cur.append(Txt(piece))
                    lines.append(cur)
                    cur, base_w, piece = [], 0.0, ch
            if piece:
                cur.append(Txt(piece))
                cur_w = base_w + F.n.getlength(piece)
        else:
            if cur and cur_w + nw > max_w and isinstance(nd, Txt) and nd.kind in ("sup", "sub"):
                base = cur.pop()
                base_w = measure_one(base, F)[0]
                cur_w = sum(measure_one(x, F)[0] for x in cur)
                if cur:
                    lines.append(cur)
                cur = [base, nd]
                cur_w = base_w + nw
            else:
                cur.append(nd)
                cur_w += nw
    if cur:
        lines.append(cur)
    return lines


def line_units(nodes: list, F: Fonts) -> int:
    if not nodes:
        return 1
    _, up, down = measure(nodes, F)
    return max(1, min(3, int(math.ceil((up + down) / float(ROW_H)))))


class Painter:
    """Draws blocks of content into one column on a fixed baseline grid."""

    def __init__(self, draw: ImageDraw.ImageDraw, F: Fonts) -> None:
        self.d = draw
        self.F = F

    def items(self, text: str, width: float, color, frac: bool = True):
        line = prettify(str(text).rstrip(), frac=frac)
        if not line.strip():
            return [("blank", [], color)]
        indent = len(line) - len(line.lstrip(" "))
        t = "　" * max(0, indent // 2) + line.strip()
        return [("line", piece, color) for piece in wrap_nodes(parse_nodes(t), self.F, width)]

    def band(self, nodes: list) -> int:
        return line_units(nodes, self.F) * ROW_H

    def draw_line(self, x: float, y_top: float, nodes: list, color) -> None:
        h = self.band(nodes)
        _, up, down = measure(nodes, self.F)
        baseline = y_top + (h - (up + down)) / 2.0 + up
        draw_nodes(self.d, x, baseline, nodes, self.F, color)

    def lines(self, items: list, x: float, y: float, y_max: float, draw: bool = True):
        for kind, nodes, color in items:
            h = self.band(nodes)
            if y + h > y_max:
                return y, True
            if draw and kind == "line" and nodes:
                self.draw_line(x, y, nodes, color)
            y += h
        return y, False

    def blocks(self, blocks: list, x: float, y: float, y_max: float, width: float,
               draw: bool = True):
        over = False
        for kind, *rest in blocks:
            if kind == "head":
                text, color = rest
                if y + ROW_H > y_max:
                    return y, True
                if draw:
                    self.d.text((x, y + 4), text, font=self.F.head, fill=color)
                y += ROW_H
            elif kind == "colored":
                y, o = self.lines(rest[0], x, y, y_max, draw)
                over = over or o
                y += ROW_H
            else:
                texts, color = rest
                items = []
                for t in texts:
                    items.extend(self.items(t, width, color, frac=(kind != "plain")))
                y, o = self.lines(items, x, y, y_max, draw)
                over = over or o
                y += ROW_H
        return y, over


def draw_grid(draw: ImageDraw.ImageDraw) -> None:
    step = ROW_H
    y = MARGIN - step
    while y < H - MARGIN:
        draw.line([(MARGIN - 4, y), (W - MARGIN + 4, y)], fill=GRID_COLOR, width=pen(1))
        y += step
    x = MARGIN - 4
    while x < W - MARGIN + step:
        draw.line([(x, MARGIN - 4), (x, H - MARGIN + 4)], fill=GRID_COLOR, width=pen(1))
        x += step
    mid = COL_X[1] - GUTTER // 2
    for yy in range(TOP, BOTTOM, 2 * step):
        draw.line([(mid, yy), (mid, yy + step)], fill=(206, 211, 217), width=pen(1))


def split_blocks(data: dict, F: Fonts) -> tuple[list, list]:
    diag = data.get("diagnosis") or []
    my_steps = data.get("my_steps") or []
    correct = data.get("correct_steps") or []
    pitfalls = data.get("pitfalls") or []
    kp = str(data.get("knowledge_point") or "").strip()
    error_from = int(data.get("error_from", -1))

    if isinstance(diag, str):
        diag = diag.splitlines()
    if isinstance(my_steps, str):
        my_steps = my_steps.splitlines()
    if isinstance(correct, str):
        correct = correct.splitlines()
    if isinstance(pitfalls, str):
        pitfalls = [p for p in pitfalls.splitlines() if p.strip()]

    colored: list[tuple[str, list, tuple]] = []
    for idx, raw in enumerate(my_steps):
        color = RED if 0 <= error_from <= idx else INK
        line = prettify(str(raw).rstrip())
        if not line.strip():
            colored.append(("blank", [], color))
            continue
        indent = len(line) - len(line.lstrip(" "))
        text = "　" * max(0, indent // 2) + line.strip()
        for piece in wrap_nodes(parse_nodes(text), F, COL_W):
            colored.append(("line", piece, color))

    left: list = []
    if diag:
        left += [("head", "错误诊断", RED), ("plain", diag, INK)]
    left += [("head", "我的过程（红色 = 从错的那一步开始）", RED), ("colored", colored)]

    right: list = []
    if pitfalls or kp:
        right.append(("head", "易错点 / 考察重点", BLUE))
        if pitfalls:
            right.append(("lines", [f"· {p}" for p in pitfalls], BLUE))
        if kp:
            right.append(("lines", [f"本题考点：{kp}"], BLUE))
    right.append(("head", "正解", BLUE))
    right.append(("lines", correct, INK))
    return left, right


def render(data: dict, output: Path, font: Path | None, bold_font: Path | None) -> list[Path]:
    regular = find_font(font)
    bold = find_font(bold_font or font, bold=True)
    F = Fonts(regular, bold)
    title = str(data.get("title") or "错题重做").strip()
    left_blocks, right_blocks = split_blocks(data, F)

    def blank_page():
        img = Image.new("RGB", (W, H), PAPER)
        d = ImageDraw.Draw(img)
        draw_grid(d)
        return img, d

    def head(d, page_no: int, total: int) -> None:
        d.text((MARGIN, MARGIN - 6), title, font=F.title, fill=(52, 58, 64))
        d.line([(MARGIN, MARGIN + 52), (W - MARGIN, MARGIN + 52)], fill=(176, 184, 192), width=pen(2))
        d.text((W - MARGIN - int(90 * SCALE), MARGIN + int(12 * SCALE)),
               f"{page_no} / {total}", font=F.tiny, fill=GREY)

    def foot(d, text: str) -> None:
        d.text((MARGIN, H - MARGIN + int(2 * SCALE)), text, font=F.tiny, fill=(152, 158, 164))

    probe, pd = blank_page()
    P = Painter(pd, F)
    _, over_l = P.blocks(left_blocks, COL_X[0], TOP, BOTTOM, COL_W, draw=False)
    _, over_r = P.blocks(right_blocks, COL_X[1], TOP, BOTTOM, COL_W, draw=False)
    single = not (over_l or over_r)

    pages: list[Image.Image] = []
    if single:
        img, d = blank_page()
        head(d, 1, 1)
        P = Painter(d, F)
        P.blocks(left_blocks, COL_X[0], TOP, BOTTOM, COL_W)
        P.blocks(right_blocks, COL_X[1], TOP, BOTTOM, COL_W)
        foot(d, "错题重做 · 左：我的过程（红=从错那步起）  右：易错点 + 正解")
        pages.append(img)
    else:
        img1, d1 = blank_page()
        head(d1, 1, 2)
        P1 = Painter(d1, F)
        intro = [b for b in left_blocks if b[0] in ("head", "plain") and b[1] != "我的过程（红色 = 从错的那一步开始）"]
        steps = [b for b in left_blocks if b[0] == "colored"]
        y, _ = P1.blocks(intro, MARGIN, TOP, BOTTOM, W - 2 * MARGIN)
        y = P1.blocks([("head", "我的过程（红色 = 从错的那一步开始）", RED)],
                      MARGIN, y, BOTTOM, W - 2 * MARGIN)[0]
        items = steps[0][1] if steps else []
        _y, over = P1.lines(items, COL_X[0], y, BOTTOM)
        if over:
            used, yy = 0, y
            for _kind, nodes, _color in items:
                h = P1.band(nodes)
                if yy + h > BOTTOM:
                    break
                yy += h
                used += 1
            P1.lines(items[used:], COL_X[1], y, BOTTOM)
        foot(d1, "错题重做 · 第 1 页：错误记录（第 2 页是正解）")
        pages.append(img1)

        img2, d2 = blank_page()
        head(d2, 2, 2)
        P2 = Painter(d2, F)
        P2.blocks(right_blocks, MARGIN, TOP, BOTTOM, W - 2 * MARGIN)
        foot(d2, "错题重做 · 第 2 页：正解")
        pages.append(img2)

    output.parent.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for i, img in enumerate(pages, start=1):
        path = output if i == 1 else output.with_name(f"{output.stem}-{i}{output.suffix or '.png'}")
        img.save(path, optimize=True)
        out.append(path)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, help="PNG path; extra pages get -2, -3 suffixes")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--bold-font", type=Path)
    parser.add_argument("--dpi", type=int, default=150, help="150 default; 300 for print quality")
    parser.add_argument("--pdf", type=Path,
                        help="also write the sheet as an A4 PDF (to embed in other PDFs)")
    args = parser.parse_args()
    apply_dpi(max(72, args.dpi))
    data = json.loads(args.source.read_text(encoding="utf-8-sig"))
    paths = render(data, args.output, args.font, args.bold_font)
    for path in paths:
        print(path)
    if args.pdf:
        args.pdf.parent.mkdir(parents=True, exist_ok=True)
        pages = [Image.open(p).convert("RGB") for p in paths]
        pages[0].save(args.pdf, "PDF", resolution=args.dpi,
                      save_all=len(pages) > 1, append_images=pages[1:])
        print(args.pdf)


if __name__ == "__main__":
    main()
