# GitHub 组件调研：本地财务报告数据提取系统

日期：2026-05-31

## 调研问题

是否存在一个成熟的 GitHub 项目，可以直接复用来构建一个本地财务报告数据提取系统，并同时支持：

- 本地文本型 PDF 输入
- A 股、港股、美股报告
- 优先处理合并三大主表
- 提取关键财报附注明细表
- 通过财务勾稽关系进行高准确率验证
- 将数据来源追溯到 PDF 的页码、表格、行、列、单元格坐标
- 人工修正，同时保持原始抽取记录不可变
- SQLite 审计库 + DuckDB 分析库
- AI 默认只能访问可信数据，并提供单独的 debug 模式

## 简短结论

目前没有看到一个成熟开源项目可以完整满足上述需求。更现实的路线是：复用成熟的文档解析、表格抽取、XBRL/SEC 工具作为基础设施，然后在本项目中自研财务领域层。

这个系统真正的核心价值应当是：

1. 财务主表和附注表分类；
2. 保守的科目标准化；
3. 单位和币种处理；
4. 财务勾稽校验；
5. PDF 坐标级来源追踪；
6. 不可变原始抽取记录 + 完整人工修正历史；
7. 面向 AI 的可信分析视图。

## 推荐组件组合

### 主要 PDF 抽取组件

建议组合使用 `pdfplumber`、`Camelot` 和 `PyMuPDF`。

- `pdfplumber`：适合字符级、线条级、坐标级抽取。它尤其适合机器生成的文本型 PDF，并能暴露字符、矩形、线条、裁剪区域、bbox 操作和可视化调试能力。它非常契合“每个数字都要追溯到 PDF 坐标”的需求。
- `Camelot`：适合把 PDF 表格确定性地抽取为 pandas DataFrame。它提供表格质量指标，比如 accuracy 和 whitespace，支持多种解析模式，并可导出 CSV、JSON、Excel、HTML、Markdown 和 SQLite。
- `PyMuPDF`：适合快速读取 PDF 页面、渲染页面图像、抽取富文本块、通过 `find_tables()` 定位表格，以及为未来校对界面生成页面截图和单元格裁剪图。

采用建议：

- 三大主表抽取应运行两个抽取器，首选 `pdfplumber` + `Camelot`。
- `PyMuPDF` 主要用于页面渲染、截图/裁剪支持，也可作为第三个诊断性抽取器。
- 三大主表只有在抽取器结果一致、单位明确、勾稽校验通过时，才能自动进入可信库。

来源：

- https://github.com/jsvine/pdfplumber
- https://github.com/camelot-dev/camelot
- https://github.com/pymupdf/PyMuPDF

### 复杂版式 fallback

可以后续评估 `Docling`，但不建议作为 MVP 第一依赖。

Docling 支持高级 PDF 理解、阅读顺序、表格结构、无损 JSON 导出、本地运行、OCR 和 XBRL 解析。它能力很强，但覆盖面比 MVP 更大，可能在确定性抽取/校验闭环跑通之前增加复杂度。

采用建议：

- 不把 Docling 作为第一条抽取路径的必需组件。
- 设计抽取器适配器接口，让 Docling 未来可以接入，用于复杂表格和交叉验证。

来源：

- https://github.com/docling-project/docling

### 美股 XBRL / SEC 路线

美股公司的长期主表数据应优先考虑 XBRL/SEC 数据，而不是 PDF 抽取。

候选组件：

- `EdgarTools`：Python SEC filings 库，支持 10-K、10-Q、8-K、XBRL financials、标准化标签、pandas 输出和跨公司对比。
- `Arelle`：成熟的开源 XBRL 平台，支持 CLI、GUI、Python API、Web service API、Inline XBRL、验证处理器认证和 SEC filing validation。
- SEC 官方 APIs：company submissions、company facts、company concept、frames 等接口提供 JSON 格式和 XBRL 派生事实，无需 API key。

采用建议：

- MVP 仍然保持本地 PDF 兼容，符合当前需求。
- 数据库 schema 必须包含 `source_type = pdf | xbrl | html | manual`。
- 未来美股流水线应使用 SEC XBRL 处理主表，用 PDF/HTML 处理附注、MD&A 和来源复核。

来源：

- https://github.com/dgunning/edgartools
- https://github.com/Arelle/Arelle
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces

### Tabula / tabula-py

`tabula-py` 是 `tabula-java` 的 Python wrapper，可以将 PDF 表格转换为 pandas DataFrame、CSV、TSV 或 JSON。

采用建议：

- 仅作为可选 fallback。
- 它要求 Java 8+，会增加 Windows 本地环境配置成本。
- MVP 阶段优先使用 `Camelot` 和 `pdfplumber`。

来源：

- https://github.com/chezou/tabula-py

## 与目标接近的项目

### FinTable

仓库：https://github.com/lazyaccountant/FinTable

功能：

- 从 PDF 年报中抽取财务状况表、损益表和现金流量表。
- 使用 Camelot、PyMuPDF、pandas、regex 和 CustomTkinter GUI。
- 导出结构化 CSV 文件。

不建议作为核心依赖的原因：

- 项目体量较小：调研时为 5 stars、0 forks、16 commits、无 releases。
- 工作流较窄，缺少本系统要求的审计数据库、校验引擎、多市场规则包、不可变修正记录和 AI 可信查询层。

可借鉴之处：

- 页码检测、报表关键词匹配、轻量 GUI 思路。
- 不适合作为核心依赖或架构基础。

### Annualreport_tools

仓库：https://github.com/legeling/Annualreport_tools

功能：

- 爬取并下载巨潮资讯 A 股年报 PDF。
- 将 PDF 转为 TXT。
- 做关键词分析并导出 Excel 结果。

不建议作为核心依赖的原因：

- 项目重点是爬取、文本转换和关键词分析，不是高准确率财务表格抽取。
- 不包含校验、修正历史、坐标级事实模型或可信分析 schema。

可借鉴之处：

- A 股报告组织方式和巨潮批处理流程。
- 下载不在 MVP 范围内，因为首版只处理本地 PDF。

### financial-report-parser

包地址：https://pypi.org/project/financial-report-parser/

功能：

- 使用 `pdfplumber` 解析 PDF 财务报告。
- 识别资产负债表、利润表和现金流量表。
- 抽取关键财务指标。
- 输出 JSON，并包含基础数据质量检查。

不建议作为核心依赖的原因：

- 更像是早期 parser package，而不是完整高可信数据系统。
- 不覆盖人工修正闭环、多抽取器一致性、active trusted version、SQLite/DuckDB 双层存储或 AI 查询边界。

可借鉴之处：

- 实现阶段可以参考其中的中文报表术语列表和简单标准化思路。
- 应作为参考，而不是系统地基。

## 采用 / 暂缓 / 避免 决策

采用：

- `pdfplumber`：用于原始 PDF 对象抽取和坐标追踪。
- `Camelot`：用于表格抽取和 parser 质量指标。
- `PyMuPDF`：用于渲染、截图、页面图像和辅助表格抽取诊断。
- `openpyxl` 或 `xlsxwriter`：用于 review workbook。
- SQLite：用于审计、来源追踪、抽取运行、校验和修正历史。
- DuckDB：用于可信分析事实表和 AI 可读视图。

暂缓：

- `Docling`：等确定性 MVP 跑通后再接入。
- `Arelle`：等实现 XBRL ingest 时再接入。
- `EdgarTools`：等实现美股 SEC ingest 时再接入。
- `tabula-py`：只有当 Camelot/pdfplumber 在重要样本上失败时再考虑。

避免作为核心依赖：

- 缺乏审计能力和 active versioning 的小型一次性财报 parser。
- 用 LLM 作为可信主数据抽取器的服务。
- MVP 阶段的 OCR 扫描版 PDF 抽取。

## MVP 依赖建议

MVP 应安装并使用：

- `pdfplumber`
- `camelot-py`
- `pymupdf`
- `pandas`
- `openpyxl`
- `duckdb`
- Python 标准库 `sqlite3`
- `pydantic`，用于 typed extraction 和 validation models
- `pyyaml`，用于市场规则包

MVP 不应要求：

- OCR 引擎
- Java / Tabula
- 大型 ML 表格模型
- LLM APIs
- SEC 网络访问

## 对系统设计的影响

系统不应被设计成一个单一 parser，而应设计成一条证据流水线：

```text
PDF -> extractor candidates -> table candidates -> classified tables
    -> normalized facts -> validation results -> review queue
    -> manual corrections -> trusted fact version -> DuckDB analytics views
```

每一个抽取出来的数字，都必须携带足够证据来回答：

- 它来自哪个 PDF 文件？
- 哪次 extraction run 产生了它？
- 哪个 extractor 产生了它？
- 它来自哪一页、哪张表、哪一行、哪一列、哪个 bbox？
- 原始文本是什么？
- 应用了什么单位和 scale？
- 哪些校验规则通过或失败？
- 它是机器校验通过、四舍五入校验通过，还是人工确认？

