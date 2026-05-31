# MVP 规则包与校验接口规格

日期：2026-05-31

## 目标

定义首版系统如何用市场规则包识别表格、科目、单位、期间和附注角色，并定义核心财务勾稽规则的代码接口。规则包应可人工编辑，但核心校验逻辑应写在 Python 中并有测试覆盖。

## 规则分层

规则分为两层：

1. YAML 规则包：市场差异、关键词、别名、单位模式、表格角色、期间列模式。
2. Python 核心规则：三大主表勾稽关系、容差计算、状态判定、错误定位。

原则：

- YAML 负责“识别和映射”。
- Python 负责“计算和裁决”。
- YAML 不直接修改事实值。
- Python 校验规则不自动修正事实值。

## 目录结构

```text
rules/
  a_share/
    table_titles.yml
    concept_aliases.yml
    unit_patterns.yml
    period_patterns.yml
    note_roles.yml
    validation_overrides.yml
  hk/
    table_titles.yml
    concept_aliases.yml
    unit_patterns.yml
    period_patterns.yml
    note_roles.yml
    validation_overrides.yml
  us/
    table_titles.yml
    concept_aliases.yml
    unit_patterns.yml
    period_patterns.yml
    note_roles.yml
    validation_overrides.yml
```

每个规则包目录的内容 hash 形成 `rule_pack_version`，写入 `extraction_runs` 和 `validation_runs`。

## table_titles.yml

用于识别三大主表和排除母公司报表。

### A 股示例

```yaml
market: a_share
statement_titles:
  statement.balance_sheet:
    include:
      - 合并资产负债表
      - 资产负债表
    prefer:
      - 合并资产负债表
    exclude:
      - 母公司资产负债表
      - 公司资产负债表
  statement.income_statement:
    include:
      - 合并利润表
      - 利润表
    prefer:
      - 合并利润表
    exclude:
      - 母公司利润表
  statement.cash_flow:
    include:
      - 合并现金流量表
      - 现金流量表
    prefer:
      - 合并现金流量表
    exclude:
      - 母公司现金流量表
scope_keywords:
  consolidated:
    - 合并
  parent:
    - 母公司
    - 公司
```

### 港股示例

```yaml
market: hk
statement_titles:
  statement.balance_sheet:
    include:
      - consolidated statement of financial position
      - consolidated balance sheet
      - 綜合財務狀況表
      - 綜合資產負債表
    exclude:
      - company statement of financial position
      - 公司財務狀況表
  statement.income_statement:
    include:
      - consolidated statement of profit or loss
      - consolidated income statement
      - 綜合損益表
      - 綜合收益表
  statement.cash_flow:
    include:
      - consolidated statement of cash flows
      - 綜合現金流量表
scope_keywords:
  consolidated:
    - consolidated
    - 綜合
  parent:
    - company
    - 公司
```

### 美股示例

```yaml
market: us
statement_titles:
  statement.balance_sheet:
    include:
      - consolidated balance sheets
      - consolidated statements of financial position
    exclude:
      - parent company
  statement.income_statement:
    include:
      - consolidated statements of operations
      - consolidated statements of income
      - consolidated statements of earnings
  statement.cash_flow:
    include:
      - consolidated statements of cash flows
scope_keywords:
  consolidated:
    - consolidated
  parent:
    - parent company
```

## concept_aliases.yml

用于保守映射 raw label 到标准 concept ID。

### 规则格式

```yaml
concepts:
  cash_and_cash_equivalents:
    confidence: 0.98
    aliases:
      - 货币资金
      - 現金及現金等價物
      - cash and cash equivalents
      - cash and bank balances
      - bank balances and cash
  total_assets:
    confidence: 0.99
    aliases:
      - 资产总计
      - 資產總值
      - total assets
```

### 映射规则

- 精确匹配或规范化后精确匹配，才可自动映射。
- 模糊匹配只能作为候选，不能自动进入 trusted。
- 同一 raw label 命中多个 concept 时，必须 `requires_review = true`。
- `mapping_confidence < 0.95` 的映射不能自动用于主表 trusted 发布。

### MVP 必须覆盖的主表 concept

资产负债表：

- `cash_and_cash_equivalents`
- `total_current_assets`
- `total_non_current_assets`
- `total_assets`
- `total_current_liabilities`
- `total_non_current_liabilities`
- `total_liabilities`
- `total_equity`
- `total_liabilities_and_equity`

利润表：

- `revenue`
- `cost_of_revenue`
- `gross_profit`
- `selling_expenses`
- `administrative_expenses`
- `research_and_development_expenses`
- `finance_expenses`
- `investment_income`
- `operating_profit`
- `profit_before_tax`
- `income_tax_expense`
- `net_profit`
- `net_profit_attributable_to_parent`

现金流量表：

- `cash_received_from_sales`
- `subtotal_cash_inflows_from_operating`
- `subtotal_cash_outflows_from_operating`
- `net_cash_flow_from_operating`
- `net_cash_flow_from_investing`
- `net_cash_flow_from_financing`
- `net_increase_in_cash_and_cash_equivalents`
- `cash_and_cash_equivalents_beginning`
- `cash_and_cash_equivalents_ending`

## unit_patterns.yml

用于识别币种和 scale。

### 示例

```yaml
currency_patterns:
  CNY:
    - 人民币
    - RMB
    - CNY
  HKD:
    - 港元
    - 港幣
    - HKD
    - HK$
  USD:
    - 美元
    - US dollars
    - USD
    - US$

scale_patterns:
  1:
    - 元
    - dollars
  1000:
    - 千元
    - 人民币千元
    - HKD thousands
    - USD thousands
    - in thousands
  10000:
    - 万元
    - 人民币万元
  1000000:
    - 百万元
    - million
    - in millions
```

### 单位解析优先级

从高到低：

1. 单元格或列标题局部单位。
2. 表格标题/表头附近单位。
3. 页面顶部或表格上方单位。
4. 报告全局单位。

如果多个来源冲突：

- 局部单位优先；
- 冲突无法解释时，设置 `blocked_unit_unknown`；
- 不允许用猜测单位进入 trusted。

## period_patterns.yml

用于识别列期间口径。

### 示例

```yaml
period_patterns:
  point_in_time:
    - 期末余额
    - 期初余额
    - as of
    - at
  cumulative:
    - 本期金额
    - 上期金额
    - 年初至报告期末
    - six months ended
    - nine months ended
    - year ended
  single_period:
    - 本季度
    - three months ended
    - quarter ended
  comparative:
    - 上年同期
    - prior period
    - comparative
```

### 期间处理规则

- 报告披露什么就存什么。
- MVP 不自动推算未披露单季值。
- 资产负债表默认 `period_basis = point_in_time`。
- 利润表和现金流量表必须从列标题识别 `cumulative` 或 `single_period`。
- 不能识别期间口径时，主表不能自动 trusted。

## note_roles.yml

用于识别附注表角色。

### MVP 第一优先级

```yaml
note_roles:
  note.revenue_by_product:
    include:
      - 主营业务分产品
      - 分产品
      - by product
      - product line
  note.revenue_by_region:
    include:
      - 主营业务分地区
      - 分地区
      - by region
      - geographical
  note.customer_concentration:
    include:
      - 前五名客户
      - 前五大客户
      - major customers
      - customer concentration
```

### 后续优先级预留

```yaml
deferred_note_roles:
  note.receivables_aging:
    include:
      - 应收账款账龄
      - ageing analysis
  note.inventory:
    include:
      - 存货分类
      - inventories
  note.goodwill:
    include:
      - 商誉
      - goodwill
  note.financial_assets:
    include:
      - 交易性金融资产
      - financial assets
  note.expense_breakdown:
    include:
      - 销售费用
      - 管理费用
      - 研发费用
      - expense breakdown
```

## validation_overrides.yml

用于配置市场级容差和规则启用状态。

```yaml
tolerance:
  absolute_tolerance_display_units: 2
  relative_tolerance: 0.0001

rules:
  balance_sheet.assets_equal_liabilities_plus_equity:
    enabled: true
    severity: error
  cash_flow.ending_cash_reconciliation:
    enabled: true
    severity: warning
```

## Python 校验接口

核心校验规则应写成可测试的 Python 函数。建议接口如下：

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

ValidationStatus = Literal[
    "verified",
    "verified_with_rounding",
    "failed",
    "blocked_unit_unknown",
    "blocked_extractor_conflict",
    "requires_manual_review",
]

@dataclass(frozen=True)
class FactRef:
    fact_id: str
    concept_id: str
    value: Decimal | None
    raw_value: str | None
    currency: str | None
    scale_factor: Decimal | None
    unit_confidence: float
    page_number: int
    table_role: str
    row_label: str | None
    column_label: str | None
    cell_bbox_json: str | None

@dataclass(frozen=True)
class RuleTolerance:
    absolute_tolerance: Decimal
    relative_tolerance: Decimal

@dataclass(frozen=True)
class ValidationResult:
    rule_id: str
    rule_name: str
    severity: Literal["error", "warning"]
    status: ValidationStatus
    lhs_value: Decimal | None
    rhs_value: Decimal | None
    difference_value: Decimal | None
    involved_fact_ids: list[str]
    message: str
```

### 规则示例：资产 = 负债 + 权益

```python
def validate_assets_equal_liabilities_plus_equity(
    facts: dict[str, FactRef],
    tolerance: RuleTolerance,
) -> ValidationResult:
    assets = facts.get("total_assets")
    liabilities = facts.get("total_liabilities")
    equity = facts.get("total_equity")

    involved = [
        fact.fact_id
        for fact in [assets, liabilities, equity]
        if fact is not None
    ]

    if assets is None or liabilities is None or equity is None:
        return ValidationResult(
            rule_id="balance_sheet.assets_equal_liabilities_plus_equity",
            rule_name="资产总计 = 负债合计 + 权益合计",
            severity="error",
            status="requires_manual_review",
            lhs_value=None,
            rhs_value=None,
            difference_value=None,
            involved_fact_ids=involved,
            message="缺少资产总计、负债合计或权益合计，无法自动校验。",
        )

    if any(f.unit_confidence < 0.95 or f.scale_factor is None for f in [assets, liabilities, equity]):
        return ValidationResult(
            rule_id="balance_sheet.assets_equal_liabilities_plus_equity",
            rule_name="资产总计 = 负债合计 + 权益合计",
            severity="error",
            status="blocked_unit_unknown",
            lhs_value=None,
            rhs_value=None,
            difference_value=None,
            involved_fact_ids=involved,
            message="相关数值存在单位不明确，不能进入可信库。",
        )

    lhs = assets.value
    rhs = liabilities.value + equity.value
    diff = lhs - rhs

    if diff == 0:
        status = "verified"
    elif abs(diff) <= tolerance.absolute_tolerance or abs(diff / lhs) <= tolerance.relative_tolerance:
        status = "verified_with_rounding"
    else:
        status = "failed"

    return ValidationResult(
        rule_id="balance_sheet.assets_equal_liabilities_plus_equity",
        rule_name="资产总计 = 负债合计 + 权益合计",
        severity="error",
        status=status,
        lhs_value=lhs,
        rhs_value=rhs,
        difference_value=diff,
        involved_fact_ids=involved,
        message=f"资产总计 {lhs}，负债+权益 {rhs}，差异 {diff}。",
    )
```

## 抽取器一致性规则

三大主表自动 trusted 前，必须检查两个抽取器是否一致。

一致定义：

- 同一 `normalized_concept_id`
- 同一 `period_basis`
- 同一 `period_end` 或 `instant_date`
- 同一 `statement_scope`
- 单位解析后 `normalized_value` 在容差内一致

不一致时：

- 相关 facts 标记为 `blocked_extractor_conflict`
- 导出 review workbook
- 不自动选择“看起来更合理”的一个

## MVP 必测规则

必须有单元测试覆盖：

- 资产 = 负债 + 权益，完全通过。
- 资产 = 负债 + 权益，四舍五入通过。
- 资产 = 负债 + 权益，失败。
- 单位未知时 blocked。
- 缺少必要 concept 时 requires review。
- 抽取器冲突时 blocked。
- A 股合并报表标题优先于母公司报表标题。
- `mapping_confidence < 0.95` 不允许自动 trusted。

