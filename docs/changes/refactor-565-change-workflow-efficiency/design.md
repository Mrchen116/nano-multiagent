# refactor-565: 技术方案

## Changelog

## 现状分析

### 涉及范围

五个目标 SKILL.md 与 docs/development/change-workflow.md；tests/contract/test_change_workflow_documentation_contract.py 中强制固定 reviewer 身份的旧文本断言退役（其余 gate 矩阵检查保留），不新增逐句文本断言；设计 author/review-loop、原 orchestrator validation 和必要 handoff 是交叉引用同步面。

### 既有约束

需求已确认；只修改流程文档及因规则退役而失效的既有文档契约测试。保留独立 gate、真实旅程、权限授权、隔离现场、PR/CI、归档与人工 merge。旧实施 worker 流程仍可点名使用。

### 可复用能力

复用 closure/delta/targeted、retained、validated_at/executed_base/effective_through 及既有测试脚本；不新增调度系统、计费监控或模板台账。

### 相关历史

feat-563/refactor-564 的事后复盘提供重复工作证据。既有 default simple 已允许自主实施，本次明确默认组织并消除重复门禁。

## 架构总览

workflow 是角色组合与 gate 有效性唯一权威；Skills 只保留执行方法。默认由主 Agent 实施、一位独立静态审查者覆盖 code review 与 verification，有真实用户旅程时另有独立产品 reviewer。设计 Gate 2 仍独立完成。

## 关键决策

1. 主 Agent 负责完整实施与集成；可独立交付且值得并行的具体任务才派 worker。微小修复、环境命令与格式收尾直接完成。
2. code review 和 verification 可由同一未参与受审实现的 reviewer 在一次任务中完成，两类输出仍保留。产品 reviewer 独立于实现和静态审查。第二位候选核验者仅用于高风险或有争议、关键条件无法确认的发现；普通明确问题由独立审查者直接举证。
3. Gate 2 仅实质设计变化失效。格式/归档类变化由 author 记录 diff 与 retained 依据，不新建审查 Round；涉及 SDK/内核时审查业务职责及是否可复用既有入口。换 reviewer 可用范围明确的交接恢复，证据不足才 full，不因身份变化自动 full。
4. 校正 delta 可以并入同一独立静态审查任务；若校正后尚未受审，补查受影响 delta，不重复整个 unit。无行为 delta 明确记 no spec delta。
5. 批量修复后冻结版本，共享带命令、版本、结果的测试证据；先稳定 fixture 与窄测试再本地全量/CI。证据不可靠或关键复现需要时独立重跑。
6. 复用 reviewer 以历史上下文是否必要为依据；不保证缓存命中、不规定 TTL、不保活。新上下文携带范围、历史发现、差异和证据位置，不复制完整历史。
7. 产品验收环境集中准备，只允许既有授权下的隔离测试配置；不得因此修改源码、生产或扩大外发授权。复测仅覆盖失效旅程。

## 接口与数据流

派发继续使用现有 unit/path/SHA/mode/历史报告字段。同一静态审查任务分别产出 code review 结论和 verification.md；两种身份合并不合并 verdict 判据。reviewer 更换与 retained 依据写入已有报告，不新增记录系统。

## 契约层增量

no spec delta：产品包行为不变。开发流程权威文档与 Skill 同步更新。

## 风险与回退

风险是为省成本错误保留旧结论或失去独立性。保留受影响范围判断、证据不足扩大审查及作者不得自签的要求。通过下列矩阵人工核对入口与引用一致性；回滚本 unit 提交恢复旧流程。

## Runbook for Reviewer

无常驻服务、无外部测试资源、无产品旅程，不派产品 reviewer。独立静态审查检查实际 diff、入口与引用冲突。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 精简编排与复审 | 无 | 无 | 五个目标 Skill、workflow、必要引用及受影响旧测试 | [reviewer] 无产品用户面；[worker] 下列矩阵全部可执行，docs-check、相关现有契约检查通过，无相互冲突规则 |

## 验证矩阵

| 情景 | 预期 |
|---|---|
| 独立模块无明显并行收益 | 主 Agent 直接实施 |
| EOF 清理或归档路径变化不改设计语义 | 记录 retained，不唤醒设计 reviewer |
| SDK 新增业务回调 | 审职责与既有入口替代方案，不仅审 import |
| Full 实施一致性与代码审查 | 同一独立静态 Agent 可一次覆盖，保留两类结论 |
| 明确普通缺陷 / 高风险或争议发现 | 前者直接举证；后者按问题派第二人核验 |
| 修复一条产品旅程 | 静态检查受影响范围，产品验收定向复测 |
| fixture 仍在修改 | 先窄测试，稳定再全量，记录版本 |
| 长时间闲置 reviewer 或长上下文 | 按历史必要性选择复用或精简交接，不假定缓存仍有效 |
| 实现作者尝试自签 / 证据不足保留结论 | 不允许；维持独立审查或扩大验证 |

## 本 unit 执行规则

本 unit Gate 2 按修改前规则由独立 reviewer 执行；用户已明确授权合并静态审查的目标，实施验收使用该组织方式，但不能用尚未落地的简化免除检查。无产品面，不做产品验收。相关文档修改均纳入独立静态审查。
