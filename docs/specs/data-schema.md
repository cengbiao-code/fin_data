# MVP 数据 Schema 规格

日期：2026-05-31

## 目标

定义首版系统的 SQLite 审计库和 DuckDB 分析库 schema。SQLite 负责来源、抽取运行、原始数据、校验、人工修正和可信版本状态；DuckDB 负责面向投资分析和 AI 查询的可信事实表与宽表视图。

## 设计原则

- 原始抽取记录 immutable：任何 correction 都不能覆盖 `raw_*` 字段。
- 同一 PDF 由内容 hash 去重，同一报告可以有多次 `extraction_run`。
- 可信数据必须显式发布为 active trusted version。
- 默认 AI 查询只读取 trusted 数据。
- Debug 查询可以读取 raw extraction、validation failures 和 correction history。
- SQLite 是审计账本，DuckDB 是分析仓库。

## SQLite 审计库

建议文件路径：

```text
data/db/audit.sqlite
```

### reports

记录 PDF 报告实体。相同文件内容 hash 只保留一条 report。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `report_id` | TEXT | primary key | UUID |
| `file_sha256` | TEXT | unique, not null | PDF 内容 hash |
| `original_filename` | TEXT | not null | 导入时文件名 |
| `stored_pdf_path` | TEXT | not null | 本地归档路径 |
| `market` | TEXT | not null | `a_share`、`hk`、`us`、`unknown` |
| `company_id` | TEXT | nullable | 股票代码、CIK 或自定义 ID |
| `company_name` | TEXT | nullable | 公司名称 |
| `fiscal_year` | INTEGER | nullable | 财年 |
| `report_type` | TEXT | nullable | `annual`、`semiannual`、`quarterly`、`latest`、`unknown` |
| `source_type` | TEXT | not null | MVP 默认 `pdf`，预留 `xbrl`、`html`、`manual` |
| `page_count` | INTEGER | nullable | 页数 |
| `is_text_pdf` | INTEGER | not null | 1 表示文本型 PDF |
| `unsupported_reason` | TEXT | nullable | 扫描版等拒绝原因 |
| `created_at` | TEXT | not null | ISO 时间 |

索引：

- unique index: `file_sha256`
- index: `(market, company_id, fiscal_year, report_type)`

### extraction_runs

记录每次解析运行。重复导入同一 PDF 时复用 `report_id`，创建新的 `extraction_run_id`。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `extraction_run_id` | TEXT | primary key | UUID |
| `report_id` | TEXT | foreign key | 关联 `reports.report_id` |
| `run_started_at` | TEXT | not null | 开始时间 |
| `run_finished_at` | TEXT | nullable | 结束时间 |
| `status` | TEXT | not null | `running`、`succeeded`、`failed`、`needs_review` |
| `pipeline_version` | TEXT | not null | 本项目版本 |
| `rule_pack_version` | TEXT | not null | 规则包版本 hash |
| `extractor_versions_json` | TEXT | not null | pdfplumber/Camelot/PyMuPDF 版本 |
| `error_message` | TEXT | nullable | 失败原因 |

索引：

- index: `report_id`
- index: `(report_id, run_started_at)`

### pdf_pages

保存页面级 profile 信息。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `page_id` | TEXT | primary key | UUID |
| `report_id` | TEXT | foreign key | 报告 |
| `page_number` | INTEGER | not null | 1-based 页码 |
| `width` | REAL | nullable | PDF 坐标宽度 |
| `height` | REAL | nullable | PDF 坐标高度 |
| `text_char_count` | INTEGER | not null | 字符数量 |
| `text_density` | REAL | nullable | 文本密度 |
| `has_statement_keywords` | INTEGER | not null | 是否含报表关键词 |
| `page_text_sample` | TEXT | nullable | 页面文本片段 |

唯一约束：

- unique: `(report_id, page_number)`

### raw_tables

保存抽取器发现的候选表格。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `raw_table_id` | TEXT | primary key | UUID |
| `extraction_run_id` | TEXT | foreign key | 抽取运行 |
| `report_id` | TEXT | foreign key | 报告 |
| `extractor_name` | TEXT | not null | `pdfplumber`、`camelot`、`pymupdf` |
| `extractor_table_id` | TEXT | nullable | 抽取器内部 ID |
| `page_number` | INTEGER | not null | 页码 |
| `table_index_on_page` | INTEGER | not null | 页面内表格序号 |
| `bbox_json` | TEXT | nullable | `[x0, top, x1, bottom]` |
| `row_count` | INTEGER | nullable | 行数 |
| `column_count` | INTEGER | nullable | 列数 |
| `quality_json` | TEXT | nullable | Camelot accuracy/whitespace 等 |
| `raw_table_text` | TEXT | nullable | 表格原始文本 |
| `created_at` | TEXT | not null | 创建时间 |

索引：

- index: `(extraction_run_id, page_number)`
- index: `(report_id, page_number)`

### raw_cells

保存原始单元格。该表是最重要的不可变来源表。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `raw_cell_id` | TEXT | primary key | UUID |
| `raw_table_id` | TEXT | foreign key | 表格 |
| `extraction_run_id` | TEXT | foreign key | 抽取运行 |
| `report_id` | TEXT | foreign key | 报告 |
| `row_index` | INTEGER | not null | 0-based 行号 |
| `column_index` | INTEGER | not null | 0-based 列号 |
| `raw_text` | TEXT | nullable | 单元格文本 |
| `normalized_text` | TEXT | nullable | 轻量清洗文本，不改变事实 |
| `bbox_json` | TEXT | nullable | 单元格坐标 |
| `page_number` | INTEGER | not null | 页码 |
| `is_header_candidate` | INTEGER | not null | 是否表头候选 |
| `created_at` | TEXT | not null | 创建时间 |

不可变字段：

- `raw_text`
- `bbox_json`
- `page_number`
- `row_index`
- `column_index`
- `raw_table_id`
- `extractor_name` 通过 `raw_tables` 间接确定

### classified_tables

保存候选表格分类结果。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `classified_table_id` | TEXT | primary key | UUID |
| `raw_table_id` | TEXT | foreign key | 原始表格 |
| `extraction_run_id` | TEXT | foreign key | 抽取运行 |
| `table_role` | TEXT | not null | `statement.balance_sheet` 等 |
| `statement_scope` | TEXT | not null | `consolidated`、`parent`、`unknown` |
| `classification_confidence` | REAL | not null | 0-1 |
| `classification_rule_id` | TEXT | nullable | 命中规则 |
| `requires_review` | INTEGER | not null | 是否需人工确认 |
| `created_at` | TEXT | not null | 创建时间 |

### extracted_facts

保存从单元格或单元格组合中抽取出的候选财务事实。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `fact_id` | TEXT | primary key | UUID |
| `extraction_run_id` | TEXT | foreign key | 抽取运行 |
| `report_id` | TEXT | foreign key | 报告 |
| `raw_table_id` | TEXT | foreign key | 来源表 |
| `raw_cell_id` | TEXT | nullable | 来源单元格 |
| `source_type` | TEXT | not null | `pdf`、`xbrl`、`html`、`manual` |
| `market` | TEXT | not null | 市场 |
| `company_id` | TEXT | nullable | 公司 ID |
| `fiscal_year` | INTEGER | nullable | 财年 |
| `report_type` | TEXT | nullable | 报告类型 |
| `statement_scope` | TEXT | not null | 报表口径 |
| `statement_type` | TEXT | nullable | `balance_sheet`、`income_statement`、`cash_flow` |
| `table_role` | TEXT | not null | 表格角色 |
| `period_basis` | TEXT | not null | `point_in_time`、`cumulative`、`single_period`、`comparative`、`unknown` |
| `period_start` | TEXT | nullable | 期间开始 |
| `period_end` | TEXT | nullable | 期间结束 |
| `instant_date` | TEXT | nullable | 时点日期 |
| `raw_label` | TEXT | not null | 原始科目/行名 |
| `normalized_concept_id` | TEXT | nullable | 标准科目 ID |
| `mapping_confidence` | REAL | not null | 映射置信度 |
| `mapping_rule_id` | TEXT | nullable | 映射规则 |
| `raw_value` | TEXT | nullable | 原始值文本 |
| `parsed_decimal` | TEXT | nullable | Decimal 字符串 |
| `raw_unit` | TEXT | nullable | 原始单位 |
| `currency` | TEXT | nullable | `CNY`、`HKD`、`USD` 等 |
| `scale_factor` | TEXT | nullable | Decimal 字符串，如 10000 |
| `normalized_value` | TEXT | nullable | 标准化金额 Decimal 字符串 |
| `unit_confidence` | REAL | not null | 单位置信度 |
| `row_label` | TEXT | nullable | 行标签 |
| `column_label` | TEXT | nullable | 列标签 |
| `page_number` | INTEGER | not null | 页码 |
| `cell_bbox_json` | TEXT | nullable | 单元格坐标 |
| `extractor_name` | TEXT | not null | 抽取器 |
| `extractor_confidence` | REAL | nullable | 抽取器置信度 |
| `fact_status` | TEXT | not null | `raw`、`normalized`、`validated`、`needs_review` |
| `created_at` | TEXT | not null | 创建时间 |

索引：

- index: `(report_id, extraction_run_id)`
- index: `(normalized_concept_id, period_end)`
- index: `(table_role, statement_scope)`

### validation_runs

记录一次校验运行。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `validation_run_id` | TEXT | primary key | UUID |
| `extraction_run_id` | TEXT | foreign key | 抽取运行 |
| `rule_pack_version` | TEXT | not null | 规则包版本 |
| `started_at` | TEXT | not null | 开始时间 |
| `finished_at` | TEXT | nullable | 结束时间 |
| `status` | TEXT | not null | `succeeded`、`failed` |

### validation_results

保存每条规则的结果。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `validation_result_id` | TEXT | primary key | UUID |
| `validation_run_id` | TEXT | foreign key | 校验运行 |
| `extraction_run_id` | TEXT | foreign key | 抽取运行 |
| `rule_id` | TEXT | not null | 规则 ID |
| `rule_name` | TEXT | not null | 规则名 |
| `severity` | TEXT | not null | `error`、`warning` |
| `status` | TEXT | not null | `verified`、`verified_with_rounding`、`failed`、`blocked_unit_unknown`、`blocked_extractor_conflict`、`requires_manual_review` |
| `lhs_value` | TEXT | nullable | 左侧 Decimal 字符串 |
| `rhs_value` | TEXT | nullable | 右侧 Decimal 字符串 |
| `difference_value` | TEXT | nullable | 差异 |
| `absolute_tolerance` | TEXT | nullable | 绝对容差 |
| `relative_tolerance` | TEXT | nullable | 相对容差 |
| `involved_fact_ids_json` | TEXT | not null | 相关 fact IDs |
| `message` | TEXT | not null | 人类可读信息 |
| `created_at` | TEXT | not null | 创建时间 |

### review_exports

记录导出的 Excel/HTML review 文件。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `review_export_id` | TEXT | primary key | UUID |
| `report_id` | TEXT | foreign key | 报告 |
| `extraction_run_id` | TEXT | foreign key | 抽取运行 |
| `validation_run_id` | TEXT | nullable | 校验运行 |
| `workbook_path` | TEXT | not null | Excel 路径 |
| `html_summary_path` | TEXT | nullable | HTML 摘要路径 |
| `status` | TEXT | not null | `exported`、`imported`、`superseded` |
| `created_at` | TEXT | not null | 创建时间 |

### correction_batches

记录一次人工修正导入。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `correction_batch_id` | TEXT | primary key | UUID |
| `review_export_id` | TEXT | foreign key | 来源 review export |
| `report_id` | TEXT | foreign key | 报告 |
| `extraction_run_id` | TEXT | foreign key | 抽取运行 |
| `imported_workbook_path` | TEXT | not null | 导入文件 |
| `operator` | TEXT | nullable | 操作者，个人版可为空 |
| `imported_at` | TEXT | not null | 导入时间 |
| `status` | TEXT | not null | `accepted`、`rejected`、`partial` |
| `error_message` | TEXT | nullable | 错误信息 |

### corrections

保存 append-only 修正历史。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `correction_id` | TEXT | primary key | UUID |
| `correction_batch_id` | TEXT | foreign key | 修正批次 |
| `fact_id` | TEXT | foreign key | 被修正 fact |
| `field_name` | TEXT | not null | 被修正字段 |
| `old_value` | TEXT | nullable | 修正前值 |
| `new_value` | TEXT | nullable | 修正后值 |
| `correction_reason` | TEXT | not null | 修正原因 |
| `created_at` | TEXT | not null | 创建时间 |

允许修正字段：

- `corrected_value`
- `corrected_unit`
- `normalized_concept_id`
- `period_basis`
- `statement_scope`
- `table_role`
- `correction_reason`

禁止修正字段：

- `raw_value`
- `raw_text`
- `pdf_page`
- `bbox`
- `extractor_name`
- `extracted_at`

### trusted_versions

记录被发布为可信版本的数据范围。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `trusted_version_id` | TEXT | primary key | UUID |
| `report_id` | TEXT | foreign key | 报告 |
| `extraction_run_id` | TEXT | foreign key | 抽取运行 |
| `scope` | TEXT | not null | `report`、`statement`、`table` |
| `scope_key` | TEXT | nullable | 如 `statement.balance_sheet` |
| `status` | TEXT | not null | `active`、`inactive`、`superseded` |
| `published_at` | TEXT | not null | 发布时间 |
| `published_by` | TEXT | nullable | 发布者 |
| `notes` | TEXT | nullable | 说明 |

唯一约束：

- 对同一 `(report_id, scope, scope_key)` 只能有一个 `active` 版本。SQLite 可通过 partial unique index 实现。

### rule_pack_versions

记录规则包版本。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `rule_pack_version` | TEXT | primary key | 规则包内容 hash |
| `market` | TEXT | not null | 市场 |
| `rules_path` | TEXT | not null | 规则目录 |
| `created_at` | TEXT | not null | 记录时间 |

## DuckDB 分析库

建议文件路径：

```text
data/db/analytics.duckdb
```

DuckDB 可以从 SQLite 发布流程中写入，也可以由命令重建。

### trusted_facts

可信事实表，只包含：

- `verified`
- `verified_with_rounding`
- `manually_confirmed`

字段与 `extracted_facts` 近似，但应加入：

| 字段 | 类型 | 说明 |
|---|---|---|
| `trusted_version_id` | VARCHAR | 来源可信版本 |
| `trusted_status` | VARCHAR | `verified`、`verified_with_rounding`、`manually_confirmed` |
| `effective_value` | DECIMAL | 最终可信金额 |
| `effective_unit` | VARCHAR | 最终可信单位 |
| `effective_concept_id` | VARCHAR | 最终可信 concept |

### trusted_statement_lines

三大主表长表视图。

核心字段：

- `company_id`
- `company_name`
- `market`
- `fiscal_year`
- `report_type`
- `statement_scope`
- `statement_type`
- `period_basis`
- `period_end`
- `concept_id`
- `raw_label`
- `effective_value`
- `currency`
- `source_page`
- `trusted_status`

### trusted_note_facts

附注明细长表视图。

核心字段：

- `company_id`
- `market`
- `fiscal_year`
- `report_type`
- `table_role`
- `dimension_name`
- `dimension_value`
- `concept_id`
- `raw_label`
- `effective_value`
- `currency`
- `period_basis`
- `period_end`
- `source_page`
- `trusted_status`

### 宽表视图

首版建议生成三张宽表视图：

- `statement_wide_balance_sheet`
- `statement_wide_income_statement`
- `statement_wide_cash_flow`

宽表字段只包含高置信度标准 concept。未知 concept 保留在长表，不强行进入宽表。

### AI 视图

`ai_trusted_facts_view`：

- 只读 trusted 数据。
- 不暴露未确认 raw facts。
- 包含足够来源字段：`report_id`、`source_page`、`raw_label`、`trusted_status`。

`debug_extraction_facts_view`：

- 暴露 raw facts、validation failures、corrections。
- 仅用于排查，不作为默认 AI 分析入口。

## 状态流转

```text
raw extraction
  -> normalized
  -> validated
      -> verified
      -> verified_with_rounding
      -> failed
      -> blocked_unit_unknown
      -> blocked_extractor_conflict
      -> requires_manual_review
  -> manual correction
  -> manually_confirmed
  -> active trusted version
```

## 需要测试的 Schema 行为

- 相同 `file_sha256` 不创建第二个 report。
- 相同 report 可创建多次 extraction run。
- raw extraction 字段不可被 correction import 修改。
- correction 是 append-only。
- 同一 report/scope/scope_key 同时只能有一个 active trusted version。
- DuckDB trusted views 不包含 failed、blocked、requires_review facts。

