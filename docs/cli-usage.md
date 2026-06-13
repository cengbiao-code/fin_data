# CLI 使用说明

## 快速上手：一键导出三张报表

如果你只想从一份 PDF 快速导出三张财务报表，使用 `export-pdf-statements` 命令：

```powershell
python -m fin_report_extractor.cli export-pdf-statements `
  data/raw_pdfs/格力电器：2025年一季度报告.pdf `
  --market a_share `
  --company-id 000651 `
  --company-name 格力电器 `
  --fiscal-year 2025 `
  --report-type quarterly `
  --output data/review_exports/格力电器_2025Q1_三张报表.xlsx
```

命令完成后会打印输出的 Excel 文件路径。

## 固定部分 vs 替换部分

**固定部分**（每次使用保持不变的命令结构）：

```text
python -m fin_report_extractor.cli export-pdf-statements <pdf路径> --market ...
```

**需要替换的字符串**（不同 PDF 需要修改）：

| 参数              | 说明             | 示例                                    |
|-------------------|------------------|----------------------------------------|
| `<pdf路径>`      | PDF 文件路径     | `data/raw_pdfs/格力电器：2025年一季度报告.pdf` |
| `--market`        | 市场             | `a_share`、`hk`、`us`                 |
| `--company-id`    | 公司代码         | `000651`（A股）、`0700.HK`（港股）、`AAPL`（美股） |
| `--company-name`  | 公司名称         | `格力电器`                              |
| `--fiscal-year`   | 财年             | `2025`                                  |
| `--report-type`   | 报告类型         | 见下方表格                              |
| `--output`        | 输出路径（可选） | `data/review_exports/格力电器_2025Q1.xlsx` |

### 报告类型（`--report-type`）

| 值           | 说明                         |
|-------------|------------------------------|
| `annual`    | 年报                         |
| `semiannual`| 半年报                       |
| `quarterly` | 季报                         |
| `latest`    | 最新财报（港股/美股适用）    |

### 省略 `--output`

如果不指定 `--output`，系统会自动生成默认路径：

```text
data/review_exports/{company_id}_{fiscal_year}_{report_type}_{extraction_run_id}_statements.xlsx
```

## 一键命令内部流程

`export-pdf-statements` 一键执行以下步骤：

1. `init-db` — 初始化数据库
2. `import-pdf` — 注册 PDF
3. `profile-pdf` — PDF 文本分析
4. `extract-tables` — 提取表格（自动尝试 PdfPlumber→PyMuPDF 回退）
5. `classify-tables` — 分类三张主表
6. `export-statements` — 生成 Excel

### 提取器回退逻辑

当 PdfPlumber 找不到表格或表格碎片化严重时，系统自动回退到 PyMuPDF：

1. **PdfPlumber** 优先（基于边框检测，适合 A 股等有线表格）
2. **PyMuPDF** 回退（基于坐标聚类，适合港股等无线表格）

Camelot 提取器（stream 模式）已实现，但需安装 `camelot-py[cv]` 后手动使用。

## 完整示例

### A 股：格力电器 2025 年一季报

```powershell
python -m fin_report_extractor.cli export-pdf-statements `
  "data/raw_pdfs/格力电器：2025年一季度报告.pdf" `
  --market a_share `
  --company-id 000651 `
  --company-name 格力电器 `
  --fiscal-year 2025 `
  --report-type quarterly
```

### 港股：腾讯 2025 年度业绩

```powershell
python -m fin_report_extractor.cli export-pdf-statements `
  "data/raw_pdfs/Tencent_2025_Annual_Results.pdf" `
  --market hk `
  --company-id 0700.HK `
  --company-name "Tencent" `
  --fiscal-year 2025 `
  --report-type annual
```

### 美股：Apple 2025 年 10-K

```powershell
python -m fin_report_extractor.cli export-pdf-statements `
  "data/raw_pdfs/AAPL-2025-09-27-10-K-....pdf" `
  --market us `
  --company-id AAPL `
  --company-name "Apple Inc." `
  --fiscal-year 2025 `
  --report-type annual
```

## 调试/审计：逐步执行命令

如果需要查看中间结果或调试，可以逐步执行每个步骤：

### 1. 初始化数据库

```powershell
python -m fin_report_extractor.cli init-db `
  --audit-db data/db/audit.sqlite `
  --analytics-db data/db/analytics.duckdb
```

### 2. 导入 PDF

```powershell
python -m fin_report_extractor.cli import-pdf `
  "data/raw_pdfs/格力电器：2025年一季度报告.pdf" `
  --audit-db data/db/audit.sqlite `
  --stored-pdf-path data/raw_pdfs/格力电器：2025年一季度报告.pdf `
  --market a_share `
  --company-id 000651 `
  --company-name 格力电器 `
  --fiscal-year 2025 `
  --report-type quarterly
```

输出 `report_id`（UUID），后续步骤需要用到。

### 3. PDF 分析

```powershell
python -m fin_report_extractor.cli profile-pdf <report_id> `
  --audit-db data/db/audit.sqlite
```

### 4. 提取表格

```powershell
python -m fin_report_extractor.cli extract-tables <report_id> `
  --audit-db data/db/audit.sqlite
```

输出 `extraction_run_id`，后续步骤需要用到。

### 5. 分类表格

```powershell
python -m fin_report_extractor.cli classify-tables <extraction_run_id> `
  --audit-db data/db/audit.sqlite `
  --rules-root rules
```

### 6. 导出 Excel 报表

```powershell
python -m fin_report_extractor.cli export-statements <extraction_run_id> `
  --audit-db data/db/audit.sqlite `
  --output data/review_exports/格力电器_2025Q1_三张报表.xlsx
```

### 7. 额外：抽取关键财务事实（可选）

```powershell
python -m fin_report_extractor.cli extract-facts <extraction_run_id> `
  --audit-db data/db/audit.sqlite `
  --rules-root rules
```

### 8. 额外：校验（可选）

```powershell
python -m fin_report_extractor.cli validate-run <extraction_run_id> `
  --audit-db data/db/audit.sqlite `
  --rules-root rules
```

### 9. 发布可信数据到 DuckDB（可选）

```powershell
python -m fin_report_extractor.cli publish-trusted <extraction_run_id> `
  --audit-db data/db/audit.sqlite `
  --analytics-db data/db/analytics.duckdb `
  --notes "首次发布"
```

输出 `trusted_version_id`（UUID）。此命令将提取的已校验事实写入 DuckDB 分析库，
并创建宽表视图（`statement_wide_balance_sheet`、`statement_wide_income_statement`、`statement_wide_cash_flow`）。

## 生成的 Excel 工作簿结构

| 工作表         | 内容                              |
|---------------|----------------------------------|
| `资产负债表`   | 项目、期末余额、期初余额、来源页    |
| `利润表`       | 项目、本期发生额、上期发生额、来源页 |
| `现金流量表`   | 项目、本期发生额、上期发生额、来源页 |
| `说明`         | 来源 PDF、数据来源、完整性检查结果、表格来源 |

## 常见错误及处理

### "报表不完整，无法导出"

表示某张主表缺失或缺少关键科目。错误信息会列出具体缺失的内容。

常见原因：
- PDF 为扫描版（无文本层），提取不到表格数据
- PDF 中的表格标题与规则包中的关键词不匹配
- 表格分类错误（可在数据库中查看 `classified_tables` 表排查）
- 20-F 文件引用并入年报附件，实际财报不在本 PDF 中

### "no such file"

PDF 路径不存在。请检查文件路径是否正确。

### 导入同一 PDF 两次

系统通过文件 hash 去重，同一份 PDF 导入多次不会创建重复记录。每次重新提取会创建新的 `extraction_run`。

## 支持的数据库路径

所有命令的默认数据库路径：

- 审计库：`data/db/audit.sqlite`
- 分析库：`data/db/analytics.duckdb`

可通过 `--audit-db` 和 `--analytics-db` 参数自定义。
