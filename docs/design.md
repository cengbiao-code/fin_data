# 财务报告数据提取系统设计

日期：2026-05-31

## 目标

为个人投资者构建一个本地、高可信的财务报告数据提取系统。首版处理本地文本型 PDF 报告，提取合并三大财务主表和关键财报附注明细表。系统必须优先保证准确性、来源追踪、校验、人工修正，以及面向 AI 的可信数据访问。

## 已确认的产品决策

- 首版只处理本地 PDF 文件。
- 首版只支持文本型 PDF。扫描版 PDF 直接拒绝或标记为不支持。
- 支持市场：A 股、港股、美股。
- 支持报告类型：A 股年报、半年报、季报；港股/美股年报和最新财报。
- 主表口径从合并报表开始。
- 数据库 schema 按多口径设计：`consolidated`、`parent`、`company`、`segment`、`unknown`。
- 抽取期间口径忠实跟随报告披露。如果报告只有累计值，就存累计值；如果同时披露累计值和单季值，就两者都存。MVP 不自动推算报告中未披露的单季值。
- 三大主表要求高可信：自动进入可信库必须满足抽取器一致、单位明确、校验通过。否则必须人工确认。
- 附注表纳入系统，但按优先级分批实现：
  1. 营收 / 成本 / 毛利；
  2. 资产质量；
  3. 投资与金融资产；
  4. 费用与研发。
- 标准化采取保守策略。只有高置信度别名自动映射；未知或有歧义的标签保留原文并进入 review。
- 校验失败绝不自动改写财务数字。
- 人工修正保留完整历史。
- AI 默认只读取 verified 或 manually confirmed 数据。debug 模式可以暴露原始抽取、失败记录和修正历史。
- 首版 review 流程是命令行 + Excel 修正 + HTML 摘要报告，而不是完整 Web App。
- 首版验收样本集应包含 6-9 份 PDF，覆盖 A 股、港股、美股。
- 每个市场都有可编辑规则包。
- 单位同时保存原始单位和标准化值。单位不明确会阻止进入可信状态。
- `source_type = xbrl | html` 只是 MVP schema 预留；首版不实现 XBRL/SEC ingest。
- 相同 PDF hash 复用同一个 `report_id`；每次重新解析生成新的 `extraction_run`。
- MVP 中，可信查询读取显式激活的 trusted version。未来可以演进到字段级 trusted version。
- 核心校验规则写在 Python 代码中并配套测试；市场差异和别名放在 YAML 中。
- 校验同时使用绝对容差和相对容差，并区分完全通过和四舍五入通过。

## 相关规格

- [MVP 数据 Schema 规格](specs/data-schema.md)
- [MVP 规则包与校验接口规格](specs/rule-packs.md)
- [MVP Review Workbook 规格](specs/review-workbook.md)

## 架构

```text
data/raw_pdfs
  -> Importer
  -> PDF Profiler
  -> Extractor Orchestrator
       -> pdfplumber extractor
       -> Camelot extractor
       -> PyMuPDF locator/renderer
  -> Table Candidate Store
  -> Statement and Note Classifier
  -> Normalizer
  -> Unit Resolver
  -> Validation Engine
  -> Review Exporter
  -> Correction Importer
  -> Trusted Version Publisher
  -> SQLite Audit DB
  -> DuckDB Analytics DB
  -> AI Query Layer
```

## 组件职责

### Importer

登记 PDF 文件并计算内容 hash。如果 hash 已存在，则复用已有 `report_id`，并创建新的 `extraction_run`。

职责：

- 检测重复 PDF；
- 收集基础元数据；
- 在 MVP 中拒绝扫描版或 image-only PDF；
- 创建 extraction run 记录，保存抽取器版本和规则包版本。

### PDF Profiler

检查 PDF 是否有可用文本层，并抽取页面级元数据。

职责：

- 页数；
- 页面尺寸；
- 文本密度；
- 可能的语言/文字系统；
- 包含报表关键词的候选页面。

### Extractor Orchestrator

运行抽取器，并保存原始输出，不抹平不同抽取器之间的差异。

MVP 行为：

- 三大主表：运行 `pdfplumber` 和 `Camelot`。
- 附注表：先运行主抽取器，初始为 `pdfplumber`；当表格质量较弱时，可选用 Camelot 做对比。
- 使用 `PyMuPDF` 做页面渲染、页面截图和未来的裁剪图。

### Table Candidate Store

保存每一张候选表格及其来源证据。

每张表应包含：

- `report_id`
- `extraction_run_id`
- `extractor_name`
- `page_number`
- `table_index_on_page`
- `table_bbox`
- 行/列网格
- 原始单元格文本
- 可用时保存 cell bbox
- parser 质量指标

### Statement and Note Classifier

将表格分类为具体角色，例如：

- `statement.balance_sheet`
- `statement.income_statement`
- `statement.cash_flow`
- `note.revenue_by_product`
- `note.revenue_by_region`
- `note.customer_concentration`
- `note.receivables_aging`
- `note.inventory`
- `note.goodwill`
- `note.financial_assets`
- `note.investment_income`
- `note.expense_breakdown`
- `unknown`

分类应使用市场专属 YAML 规则：

```text
rules/
  a_share/
    table_titles.yml
    concept_aliases.yml
    unit_patterns.yml
    note_roles.yml
  hk/
    table_titles.yml
    concept_aliases.yml
    unit_patterns.yml
    note_roles.yml
  us/
    table_titles.yml
    concept_aliases.yml
    unit_patterns.yml
    note_roles.yml
```

### Normalizer

只在置信度足够高时，将原始标签映射到标准 concept ID。

同时保存：

- `raw_label`
- `normalized_concept_id`
- `mapping_confidence`
- `mapping_rule_id`
- `requires_review`

有歧义的标签在 review 前保持未映射状态。

### Unit Resolver

从报告级、页面级、表格级和表头级文本中识别币种和缩放单位。

保存：

- `raw_value`
- `raw_unit`
- `currency`
- `scale_factor`
- `normalized_value`
- `unit_confidence`

如果单位未知，该 fact 不能进入可信库。

### Validation Engine

验证财务勾稽关系，但不修改数值。

MVP 核心规则：

- 资产负债表：资产 = 负债 + 权益。
- 资产负债表小计：流动资产、非流动资产、流动负债、非流动负债，在可用时校验。
- 利润表：校验营业利润、利润总额、净利润、EPS 相关项目等可识别小计关系。
- 现金流量表：经营/投资/筹资活动现金流小计，以及现金及现金等价物变动关系。

状态：

- `verified`
- `verified_with_rounding`
- `failed`
- `blocked_unit_unknown`
- `blocked_extractor_conflict`
- `requires_manual_review`
- `manually_confirmed`

校验使用：

- 以披露单位计的绝对容差；
- 相对容差；
- 市场/报告专属规则设置；
- 严重程度：`error` 或 `warning`。

### Review Exporter

当报告需要 review 时，为每份报告生成一个 Excel workbook。

Sheet：

- `summary`
- `validation_failures`
- `balance_sheet_raw`
- `income_statement_raw`
- `cash_flow_raw`
- `notes_revenue_raw`
- `corrections`

workbook 展示失败上下文和原始整表上下文。原始抽取字段在导入时应被视为不可变。

### Correction Importer

导入人工修正后的 Excel 文件，并写入修正记录，不修改原始抽取。

允许修正的字段：

- `corrected_value`
- `corrected_unit`
- `normalized_concept_id`
- `period_basis`
- `statement_scope`
- `table_role`
- `correction_reason`

不可变原始字段：

- `raw_value`
- `raw_text`
- `pdf_page`
- `bbox`
- `extractor_name`
- `extracted_at`

每次修正都创建一条新的修正历史记录。

### Trusted Version Publisher

发布显式激活的可信数据版本。

MVP 规则：

- 可信查询只读取某份报告/某张表/某次 run 的 active trusted version。
- 未来可以扩展为 fact 级 active version。

### AI Query Layer

提供两种模式：

- Trusted mode：只包含 `verified`、`verified_with_rounding` 或 `manually_confirmed` facts。
- Debug mode：包含原始抽取、校验失败、修正历史和来源坐标。

默认使用 trusted mode。

## 存储设计

### SQLite Audit Database

SQLite 保存来源、工作流状态和审计历史。

核心表：

- `reports`
- `extraction_runs`
- `pdf_pages`
- `raw_tables`
- `raw_cells`
- `classified_tables`
- `extracted_facts`
- `validation_runs`
- `validation_results`
- `review_exports`
- `correction_batches`
- `corrections`
- `trusted_versions`
- `rule_pack_versions`

### DuckDB Analytics Database

DuckDB 保存可信 facts 和便于分析的视图。

核心表/视图：

- `trusted_facts`
- `trusted_statement_lines`
- `trusted_note_facts`
- `company_period_summary`
- `statement_wide_balance_sheet`
- `statement_wide_income_statement`
- `statement_wide_cash_flow`
- `ai_trusted_facts_view`
- `debug_extraction_facts_view`

## 数据模型要点

每个 fact 应携带：

- `fact_id`
- `report_id`
- `extraction_run_id`
- `source_type`
- `market`
- `company_id`
- `fiscal_year`
- `report_type`
- `statement_scope`
- `statement_type`
- `table_role`
- `period_basis`
- `period_start`
- `period_end`
- `instant_date`
- `raw_label`
- `normalized_concept_id`
- `raw_value`
- `raw_unit`
- `currency`
- `scale_factor`
- `normalized_value`
- `page_number`
- `table_index_on_page`
- `row_label`
- `column_label`
- `cell_bbox`
- `extractor_name`
- `extractor_confidence`
- `validation_status`
- `trusted_status`

## MVP 工作流

```text
1. 将 PDF 放入 data/raw_pdfs/
2. 运行导入命令
3. 系统 profile PDF，并拒绝扫描版 PDF
4. 系统抽取候选表格
5. 系统分类三大主表和第一优先级附注表
6. 系统标准化高置信度科目
7. 系统解析单位
8. 系统校验三大主表
9. 如果可信条件通过，发布 trusted version
10. 如果未通过，导出 review workbook 和 HTML 摘要
11. 用户在 Excel 中编辑允许修正的字段
12. 系统导入修正并记录修正历史
13. 系统重新运行校验
14. 用户标记 active trusted version
15. DuckDB 分析视图更新，供 AI 使用
```

## MVP 验收标准

使用固定的 6-9 份本地文本型 PDF：

- 2-3 份 A 股报告；
- 2-3 份港股报告；
- 2-3 份美股报告。

验收标准：

- 每份 PDF 都用稳定 hash 注册为 `report_id`。
- 重复导入同一 PDF 会创建新的 `extraction_run`，不会创建重复 report。
- 能找到合并资产负债表、利润表、现金流量表；找不到时进入 review。
- 三大主表只有在抽取器一致、单位明确、校验通过时，才自动进入可信状态。
- 校验失败能定位到报告、页码、表格、行/列和 cell bbox。
- Review workbook 导出失败清单和完整原始表格上下文。
- Correction import 保留不可变原始抽取记录。
- 修正历史完整。
- DuckDB trusted views 只包含 verified、verified-with-rounding 或 manually confirmed 数据。
- Debug views 单独暴露原始数据和失败数据。

## MVP 非目标

- 自动下载 PDF。
- 扫描版 PDF OCR。
- 完整本地 Web review UI。
- 用 LLM 作为可信数据抽取器。
- 自动修正失败的财务勾稽关系。
- 完整 XBRL/SEC ingest。
- 当报告未披露单季值时，自动推算季度单季值。
- 默认抽取母公司报表作为可信主线。

## 组件采用决策

立即使用：

- `pdfplumber`
- `Camelot`
- `PyMuPDF`
- SQLite
- DuckDB
- pandas
- openpyxl 或 xlsxwriter
- PyYAML
- Pydantic

保持 adapter-ready：

- Docling
- Arelle
- EdgarTools
- tabula-py

## 主要风险

1. 不同市场的表格结构差异大。
2. 单位歧义和表格局部单位变化。
3. 多期间列，以及累计/单季口径混杂。
4. 报表分类误判。
5. 科目标准化过于激进。
6. 人工修正工作流复杂。
7. AI 访问边界没有严格限制到可信数据。

## 风险控制

- 三大主表使用多抽取器一致性检查。
- 保守科目映射。
- 单位未知会阻止可信发布。
- 校验规则绝不修改 facts。
- 原始抽取记录不可变。
- 修正记录 append-only。
- Active trusted version 必须显式指定。
- 市场专属规则包可编辑。
- Debug views 与 AI trusted views 分离。
