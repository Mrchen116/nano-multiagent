# IM delta — bugfix-416

> 本 unit 对长青契约层 `docs/specs/im/spec.md` 的增量。lite 模式无 design-author 产出，
> 由 orchestrator 据实际代码补（§7.0 兜底）。

## ADDED

### Requirement: 工具徽标按中断原因显示终态

#### Scenario: 超时收口的工具仍显示其命令与描述
- **GIVEN** 一个 bash 工具调用运行中,已显示其命令与 description
- **WHEN** 该工具因看门狗超时(或其他异常终止)被收口为失败态
- **THEN** 该工具行仍显示原命令与 description(连同失败标识),用户能看出是哪条命令被中断,
  而非只剩工具名 + 失败标识

> 缘由(#111):前端 reducer 浅合并被收口事件的空 input 覆盖掉已展示命令。修复在后端重发原 input
> 为主、前端 reducer「空字段不覆盖非空值」为兜底。
