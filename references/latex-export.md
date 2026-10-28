# LaTeX 导出

本 skill 产出的**每一份 PDF**，不论学科或是否有公式，均须先生成 `.tex`，再用 XeLaTeX 或 LuaLaTeX 实际编译。知识清单、备考计划等主文件的最终 PDF 放在科目或比赛文件夹顶层；每日课程 PDF 放在各自的 `每日学习/D001-YYYY-MM-DD` 文件夹。对应 `.tex` 放在同级 `源文件` 子目录，保持同名以便重编译。公式直接保留 LaTeX 数学模式；不得使用网页打印、Word 导出、ReportLab 等其他方式替代编译。若编译器不可用，先排查或安装，仍不可用时明确告知 PDF 尚未完成，不输出来源不明的 PDF。

工作区的 [`scripts/render_study_pdf.py`](../scripts/render_study_pdf.py) 可把本 skill 常用的 Markdown（标题、段落、列表、表格、粗体、链接和 `$...$`／`$$...$$` 公式）转成黑白 XeLaTeX 文档。它从一个 JSON 文件读取导图信息：顶层分别以 `knowledge`、`plan`、`day` 为键，每项有 `title`、`center` 和六个 `nodes`；每个节点有 `title` 与 `lines`。如果材料含脚本未支持的 Markdown，先扩展转换逻辑或直接编写 `.tex`，不得丢失正文。

```text
python scripts/render_study_pdf.py 科目/每日学习/D001-YYYY-MM-DD/源文件/今日课程.md 科目/每日学习/D001-YYYY-MM-DD/源文件/今日课程-紧凑.tex --kind day --layout compact --map-config 科目/每日学习/D001-YYYY-MM-DD/源文件/导图.json
python scripts/render_study_pdf.py 科目/每日学习/D001-YYYY-MM-DD/源文件/今日课程.md 科目/每日学习/D001-YYYY-MM-DD/源文件/今日课程-宽松.tex --kind day --layout loose --map-config 科目/每日学习/D001-YYYY-MM-DD/源文件/导图.json
python scripts/compile_study_pdf.py 科目/每日学习/D001-YYYY-MM-DD/源文件/今日课程-紧凑.tex 科目/每日学习/D001-YYYY-MM-DD/今日课程-紧凑.pdf
python scripts/compile_study_pdf.py 科目/每日学习/D001-YYYY-MM-DD/源文件/今日课程-宽松.tex 科目/每日学习/D001-YYYY-MM-DD/今日课程-宽松.pdf
```

对知识清单和备考计划分别使用 `--kind knowledge`、`--kind plan`。每日课程每个核心方法用 `## 单元 N...` 标题，脚本使单元另起一页；单元包含一题完整例题和其举一反三。将独立填步题、变式题放在 `### 举一反三` 下，混合题放在 `## 独立练习` 下，使用 `**A1.**` 一类题号；脚本只给这些题目留作答空白，例题不留白。若某题需要长证明或作图，按实际解答量调整空白高度。答案应有单独的二级标题，并位于全部独立练习之后。

错题本用 --kind errors 渲染，不需要导图 JSON；不制作思维导图、独立封面或其他非正题内容，首页直接进入第一条错题。每条错题采用“错题 N”二级标题，第二条起另起一页；复做题置于“再做一题”三级标题下，答案集中放在后部的二级标题。复做记录用 LaTeX 数学模式的 `$\square$` 表示可手写勾选的空方框，每个日期提供独立做对、订正后做对、未做对等选项；不要预勾选模拟记录。若需要打印作答区，使用 --layout loose。正文排版采用黑白、宽页边距、较舒展的行距和段距；表格优先不用竖线，留足行高。核心例题和错题记录都不要在同页堆叠，题干与步骤保持在一起，避免标题落在页尾。紧凑版也保留阅读所需空白；两个版本只在独立题的作答区有差异。编译器源文件应能在本机重新编译成同一内容的 PDF。

编译脚本实际调用 XeLaTeX 两遍，用临时 ASCII 文件名避开 Windows 上中文日志文件名写入失败；若要使用 LuaLaTeX，可传 --compiler lualatex。源文件应为自包含的 LaTeX 文档。检查日志中的缺字与越界警告，渲染 PDF 的每一页检查中文、公式、导图、表格和作答空白。紧凑版和宽松版必须出自同一份课程文本，核对题目及答案完整一致。

错题本可以把[错题重做纸](mistake-sheet.md)的 PNG 一起印进 PDF：在对应错题小节里**单独一行**写 `![错题重做纸：第 N 题](sheet-error-N.png)`，脚本会把它转成通栏插图（`\includegraphics` + 图注），宽度撑满正文、高度不超过 0.86 页。图片要和该 `.tex` 放在同一个 `源文件` 目录，**文件名用 ASCII**（`sheet-error-1.png`）；`compile_study_pdf.py` 会把被引用的图片一起复制进临时编译目录，所以目录名里有中文也没关系，缺图或中文文件名会在编译前给出明确报错。插图属于正题内容，放在该错题的订正之后、“再做一题”之前，不单独成页、不加封面说明。
