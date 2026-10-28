# Good Learning

一个用于 AI agent 的学习与备考 skill：根据考纲、教材、真题和可用时间建立知识清单、备考计划与每日课程，再依据真实作答整理错题并调整后续安排

## 能做什么

- 分别制作知识清单和备考计划，保留知识点编号、验收标准及来源
- 按零基础或复习模式生成自成体系的每日课程，包括例题、变式、混合练习与逐步答案
- 根据用户的实际作答制作错题本；演示错误会标为模拟，不计入真实掌握状态
- 把单道错题渲染成一张对照图（PNG）：左边是学习者自己的过程、从出错那一步起标红，右边是订正后的正解，页面顶部先给错误诊断——《错题重做纸》适合手机查看、群聊讲解和打印，和错题本 PDF 互补：图片既可单独发送，也可用 Markdown 图片语法嵌进错题本 PDF
- 为当日复盘绘制 SVG 思维导图，可选生成 PNG 预览
- 通过 XeLaTeX 或 LuaLaTeX 编译课程、清单、计划和错题本 PDF；科目目录存放知识清单和备考计划 PDF，每日课程按日期独立成夹；各文件夹顶层只放最终 PDF，Markdown、`.tex` 和其他源文件放在对应的 `源文件` 子目录

## 输出目录

```text
科目或比赛/
├── 知识清单.pdf
├── 备考计划.pdf
├── 源文件/
└── 每日学习/
    └── D001-YYYY-MM-DD/
        ├── D001-紧凑排版型.pdf
        ├── D001-宽松排版型.pdf
        └── 源文件/  课程文本、LaTeX、配置与当日学习记录
```

后续课程按真实学习进度逐日建立，用户提交作答或错题后更新对应日期的记录，并调整尚未完成的学习任务

## 安装

以codex为示例：把仓库克隆或复制为 Codex skills 目录下的 `good-learning` 文件夹，重启 Codex 或重新加载 skills 后即可使用

```text
~/.codex/skills/good-learning/SKILL.md
```

示例请求：

```text
我准备参加一项数学竞赛，每天能学三小时，请帮我制定知识清单和备考计划
我是零基础，开始今天的学习
这里是我的作答，请核对并制作错题本
根据今天的知识和错题绘制总结思维导图
```

## 运行环境

- Python 3.10 或更新版本
- PDF：XeLaTeX 或 LuaLaTeX，以及 `ctex`、`amsmath`、`tikz` 等常用 LaTeX 宏包
- 总结图 PNG：Pillow，使用 `pip install -r requirements.txt` 安装
- 总结图 SVG：只需 Python 标准库
- 生成 PNG 时需提供中文字体；脚本可自动查找常见字体，也可用 `--font` 和 `--bold-font` 指定

## 脚本

```text
scripts/render_study_pdf.py      常用 Markdown → LaTeX
scripts/compile_study_pdf.py     LaTeX → PDF
scripts/render_summary_map.py    JSON → SVG，可选 PNG
scripts/render_mistake_sheet.py  JSON → 错题重做纸 PNG（左：学习者过程标红，右：正解），可加 --pdf 出 A4 PDF
```

总结图输入为 JSON，包含 `eyebrow`、`title`、`subtitle`、`status`、`description`、`core_label`、`core_title`、`core_subtitle`、`core_foot`、`workload`、`error_count`、`legend`、`note_legend`、`footer`，以及 4—6 个 `branches`；每个分支填写 `side`、`category`、`title`、`rule`、`detail`，如有错题再填写 `error.number`、`error.label`、`error.mistake`、`error.fix`；无错题时填写 `check` 与 `check_fix`

```text
python scripts/render_summary_map.py examples/summary-map.json summary.svg --png summary.png
```

错题重做纸的输入是单道错题的 JSON，包含 `title`、`diagnosis`、`my_steps`、`error_from`、`correct_steps`、`pitfalls`、`knowledge_point`；`error_from` 是从 0 数起的第一处错误行号（填 `-1` 不标红）。一页放不下时自动拆成两页：第 1 页错误记录、第 2 页正解

```text
python scripts/render_mistake_sheet.py examples/mistake-sheet.json sheet.png
```

实现：脚本不依赖 LaTeX，自带一套轻量数学排版。每行先解析成文本、上标下标、分数三类节点，逐个量出宽度和基线上下高度，再排到 38px 的基线网格上——普通行占一格，含分数的行占两格并垂直居中；分数线不压在文字基线上，而是抬到约 0.3 字高的“数学轴”，所以分数和同一行的等号、数字是对齐的。整页按 A4（1240×1754，`--dpi` 可放大）用 Pillow 画到方格纸上：左栏「错误诊断 + 我的过程」，右栏「易错点 / 考察重点 + 正解」，两栏各自独立向下排；`error_from` 及其之后的行用红色，前面正确的部分保持墨色。排版前先在一张空白页上试排，任一侧溢出就自动改出两页版（第 1 页错误记录、第 2 页正解）。

要印进错题本 PDF 时：`render_study_pdf.py` 把单独成行的 `![说明](图.png)` 转成 `\includegraphics`（宽度撑满正文、高度上限 0.86 页，附图注）；`compile_study_pdf.py` 在编译前扫描 `.tex` 里的图片引用，把文件复制进临时编译目录——它本来就在临时目录里编译，不复制会找不到图。缺图或非 ASCII 文件名会在编译前直接报错。

具体工作流程见 [SKILL.md](SKILL.md)，设计与资料检索规则见 [references](references)

## 内容边界

仓库只包含 skill 指令和生成脚本，不包含教材、历年试卷、用户作答或生成的个人学习文件；使用资料时请核对来源与授权

## 许可证

[MIT](LICENSE)
