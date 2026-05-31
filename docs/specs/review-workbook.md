# MVP Review Workbook 规格

日期：2026-05-31

## 目标

定义首版人工修正 Excel workbook 的结构、列、可编辑范围和导入规则。该 workbook 用于连接自动抽取/校验系统和人工确认流程。

## 设计原则

- 每份报告生成一个 review workbook。
- workbook 同时包含失败清单和原始整表上下文。
- 原始抽取字段不可修改。
- 人工只能修改明确允许的 correction 字段。
- 每次导入产生 append-only correction history。
- 导入后必须重新运行校验。

## 文件路径

导出路径建议：

```text
data/review_exports/{company_id}_{fiscal_year}_{report_type}_{extraction_run_id}.xlsx
data/review_exports/{company_id}_{fiscal_year}_{report_type}_{extraction_run_id}.html
```

导入路径建议：

```text
data/review_imports/{company_id}_{fiscal_year}_{report_type}_{extraction_run_id}_corrected.xlsx
```

## Workbook Sheets

首版 workbook 包含：

- `summary`
- `validation_failures`
- `balance_sheet_raw`
- `income_statement_raw`
- `cash_flow_raw`
- `notes_revenue_raw`
- `corrections`
- `_metadata`

`_metadata` 可以隐藏，但不应依赖隐藏保护来保证安全；导入程序必须重新校验所有字段。

## summary

用于给用户快速了解报告状态。

| 列名 | 可编辑 | 说明 |
|---|---|---|
| `field` | 否 | 元数据字段 |
| `value` | 否 | 元数据值 |

建议内容：

```text
report_id
extraction_run_id
company_id
company_name
market
fiscal_year
report_type
original_filename
pdf_path
run_started_at
rule_pack_version
overall_status
failed_validation_count
blocked_unit_unknown_count
blocked_extractor_conflict_count
requires_manual_review_count
```

## validation_failures

列出所有校验失败、单位不明、抽取器冲突、需要人工 review 的规则结果。

| 列名 | 可编辑 | 说明 |
|---|---|---|
| `validation_result_id` | 否 | 校验结果 ID |
| `rule_id` | 否 | 规则 ID |
| `severity` | 否 | `error` 或 `warning` |
| `status` | 否 | `failed`、`blocked_unit_unknown` 等 |
| `message` | 否 | 人类可读说明 |
| `involved_fact_ids` | 否 | JSON 或逗号分隔 fact IDs |
| `lhs_value` | 否 | 左侧值 |
| `rhs_value` | 否 | 右侧值 |
| `difference_value` | 否 | 差异 |
| `source_pages` | 否 | 涉及页码 |
| `suggested_action` | 否 | 系统建议 |

`suggested_action` 示例：

- `检查单位`
- `检查抽取器冲突`
- `检查缺失科目`
- `在 corrections sheet 填写修正值`

## *_raw sheets

用于展示原始整表上下文。首版包括：

- `balance_sheet_raw`
- `income_statement_raw`
- `cash_flow_raw`
- `notes_revenue_raw`

### 固定列

每个 raw sheet 前置以下固定列：

| 列名 | 可编辑 | 说明 |
|---|---|---|
| `fact_id` | 否 | fact ID |
| `raw_table_id` | 否 | 来源表 ID |
| `raw_cell_id` | 否 | 来源单元格 ID |
| `extractor_name` | 否 | 抽取器 |
| `page_number` | 否 | 页码 |
| `table_index_on_page` | 否 | 页面内表格序号 |
| `row_index` | 否 | 行号 |
| `column_index` | 否 | 列号 |
| `cell_bbox_json` | 否 | 单元格坐标 |
| `table_role` | 否 | 表格角色 |
| `statement_scope` | 否 | 报表口径 |
| `period_basis` | 否 | 期间口径 |
| `period_start` | 否 | 期间开始 |
| `period_end` | 否 | 期间结束 |
| `instant_date` | 否 | 时点日期 |
| `raw_label` | 否 | 原始标签 |
| `normalized_concept_id` | 否 | 当前标准 concept |
| `raw_value` | 否 | 原始值 |
| `raw_unit` | 否 | 原始单位 |
| `currency` | 否 | 币种 |
| `scale_factor` | 否 | 缩放 |
| `normalized_value` | 否 | 标准化值 |
| `validation_status` | 否 | 校验状态 |
| `review_hint` | 否 | review 提示 |

### 原始表格展示

除了固定列，raw sheet 可以附加 `display_col_1`、`display_col_2`、... 来展示原始表格行。它们仅用于阅读上下文，不参与导入。

## corrections

唯一允许用户编辑并导入修正的 sheet。

### 必填列

| 列名 | 可编辑 | 说明 |
|---|---|---|
| `fact_id` | 是 | 被修正 fact，必须来自 raw sheet |
| `correction_action` | 是 | `confirm`、`correct`、`remap`、`ignore` |
| `corrected_value` | 是 | 修正后的数值，可为空 |
| `corrected_unit` | 是 | 修正后的单位，可为空 |
| `normalized_concept_id` | 是 | 修正后的 concept，可为空 |
| `period_basis` | 是 | 修正后的期间口径，可为空 |
| `statement_scope` | 是 | 修正后的报表口径，可为空 |
| `table_role` | 是 | 修正后的表格角色，可为空 |
| `correction_reason` | 是 | 必填，说明原因 |

### 只读辅助列

导出时可以带出以下辅助列，但导入时不信任这些列：

| 列名 | 可编辑 | 说明 |
|---|---|---|
| `raw_label` | 否 | 便于人工判断 |
| `raw_value` | 否 | 便于人工判断 |
| `page_number` | 否 | 便于回 PDF 定位 |
| `cell_bbox_json` | 否 | 便于回 PDF 定位 |
| `validation_status` | 否 | 当前状态 |

### correction_action 含义

`confirm`：

- 表示用户确认原始抽取值正确。
- 可以不填 `corrected_value`。
- 导入后可将相关 fact 标记为 `manually_confirmed`，前提是单位和概念可确定。

`correct`：

- 表示数值或单位需要修正。
- 至少填写 `corrected_value` 或 `corrected_unit`。
- 必须填写 `correction_reason`。

`remap`：

- 表示科目、期间、口径或表格角色需要修正。
- 至少填写 `normalized_concept_id`、`period_basis`、`statement_scope` 或 `table_role` 中一个。
- 必须填写 `correction_reason`。

`ignore`：

- 表示该 fact 不应进入可信数据。
- 必须填写 `correction_reason`。

## _metadata

用于导入校验。

| 列名 | 可编辑 | 说明 |
|---|---|---|
| `key` | 否 | key |
| `value` | 否 | value |

必须包含：

```text
workbook_schema_version
report_id
extraction_run_id
review_export_id
rule_pack_version
exported_at
```

导入时必须检查：

- `workbook_schema_version` 是否支持；
- `report_id` 是否存在；
- `extraction_run_id` 是否存在且属于该 report；
- `review_export_id` 是否存在；
- 该 workbook 是否已被导入过。

## 样式和可用性要求

首版不需要复杂 UI，但 workbook 应易读：

- 冻结首行。
- raw sheet 前置关键定位列。
- `validation_status` 使用颜色标记：
  - `failed`：红色
  - `blocked_unit_unknown`：橙色
  - `blocked_extractor_conflict`：紫色
  - `requires_manual_review`：黄色
  - `verified_with_rounding`：蓝色
  - `verified`：绿色
- `corrections` sheet 中 `correction_action` 应使用数据验证下拉框。
- 必填但为空的 correction 字段在导入错误报告中列出。

## 导入规则

导入程序只读取：

- `_metadata`
- `corrections`

导入程序不得信任 raw sheet 中被用户修改的任何内容。

导入步骤：

```text
1. 读取 _metadata 并验证 workbook 身份
2. 检查 review_export 是否未被导入或未被 superseded
3. 读取 corrections sheet
4. 对每行校验 fact_id 是否存在且属于 extraction_run
5. 校验 correction_action
6. 校验 correction_reason 非空
7. 校验只修改允许字段
8. 写入 correction_batches
9. 逐字段写入 corrections append-only 记录
10. 重新计算 corrected fact view
11. 重新运行 validation
12. 如果校验通过或人工确认充分，允许发布 trusted version
```

## 错误处理

导入错误应生成一份 import error report，而不是静默失败。

建议路径：

```text
data/review_imports/errors/{correction_batch_id}_errors.xlsx
```

错误列：

| 列名 | 说明 |
|---|---|
| `row_number` | corrections sheet 行号 |
| `fact_id` | fact ID |
| `field` | 出错字段 |
| `error_code` | 错误代码 |
| `message` | 人类可读说明 |

错误代码：

- `UNKNOWN_FACT_ID`
- `FACT_NOT_IN_EXTRACTION_RUN`
- `INVALID_ACTION`
- `MISSING_REASON`
- `MISSING_CORRECTED_VALUE`
- `INVALID_DECIMAL`
- `INVALID_UNIT`
- `IMMUTABLE_FIELD_MODIFIED`
- `DUPLICATE_CORRECTION_ROW`

## 导入后的状态更新

导入 corrections 后：

- `confirm` 可使 fact 进入 `manually_confirmed` 候选状态。
- `correct` 生成 corrected effective value，并重新校验。
- `remap` 更新 corrected concept/period/scope/table role，并重新校验。
- `ignore` 将 fact 排除出 trusted 发布候选。

只有当报告或表格范围内的必要规则满足以下之一时，才能发布 trusted version：

- `verified`
- `verified_with_rounding`
- `manually_confirmed`

## 最小测试场景

必须测试：

- 导入一个只包含 `confirm` 的 corrections sheet。
- 导入一个修正数值的 `correct` 行。
- 导入一个修正 concept 的 `remap` 行。
- 导入一个 `ignore` 行。
- 导入缺少 `correction_reason` 的文件应失败。
- 导入未知 `fact_id` 应失败。
- 用户修改 raw sheet 不应影响导入结果。
- 同一个 workbook 重复导入应被拒绝或标记为重复。

