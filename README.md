# Good Learning

一个用于 AI agent 的学习与备考 skill：根据考纲、教材、真题和可用时间建立知识清单、备考计划与每日课程，再依据真实作答整理错题并调整后续安排

## 能做什么

- 分别制作知识清单和备考计划，保留知识点编号、验收标准及来源
- 按零基础或复习模式生成自成体系的每日课程，包括例题、变式、混合练习与逐步答案
- 根据用户的实际作答制作错题本；演示错误会标为模拟，不计入真实掌握状态
- 为当日复盘绘制 SVG 思维导图，可选生成 PNG 预览
- 通过 XeLaTeX 或 LuaLaTeX 编译课程、清单、计划和错题本 PDF；科目目录存放知识清单、备考计划和每日课程 PDF；每日课程的 Markdown、`.tex` 与学习记录按日期放在 `源文件` 下的独立子目录

## 输出目录

```text
科目-课程
├── 知识清单.pdf
├── 备考计划.pdf
├── D001-科目简称-课程.pdf
└── 源文件/
    └── D001-YYYY-MM-DD源文件/  课程文本、LaTeX 与所需配置与当日学习记录
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
```

总结图输入为 JSON，包含 `eyebrow`、`title`、`subtitle`、`status`、`description`、`core_label`、`core_title`、`core_subtitle`、`core_foot`、`workload`、`error_count`、`legend`、`note_legend`、`footer`，以及 4—6 个 `branches`；每个分支填写 `side`、`category`、`title`、`rule`、`detail`，如有错题再填写 `error.number`、`error.label`、`error.mistake`、`error.fix`；无错题时填写 `check` 与 `check_fix`

```text
python scripts/render_summary_map.py examples/summary-map.json summary.svg --png summary.png
```

具体工作流程见 [SKILL.md](SKILL.md)，设计与资料检索规则见 [references](references)

## 内容边界

仓库只包含 skill 指令和生成脚本，不包含教材、历年试卷、用户作答或生成的个人学习文件；使用资料时请核对来源与授权

## 许可证

[MIT](LICENSE)
