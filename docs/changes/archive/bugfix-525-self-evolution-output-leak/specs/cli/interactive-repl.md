# CLI Interactive REPL Specification (delta for bugfix-525)

## ADDED Requirements

### Requirement: REPL 只为真实自进化更新显示后台提示

CLI 收到包含非空真实更新对象的 `self_evolution_review` session event 时，以既有轻量 system line 显示 memory、skills 或两者已更新；没有成功写入时 Kernel 不产生该更新事件，CLI 不显示会误导用户的 updated 提示。review side-chain 的 prompt、工具过程与完成文本继续不进入终端输出。

#### Scenario: 成功更新显示真实对象

- **GIVEN** self-evolution review 确认成功写入 memory、skills 或两者
- **WHEN** CLI 消费对应 `self_evolution_review` event
- **THEN** 终端显示一条非第一人称后台更新提示
- **AND** 提示只包含真实成功的更新对象

#### Scenario: 无成功写入不显示更新提示

- **GIVEN** self-evolution review 无需写入、只执行读取/列举，或所有写操作失败
- **WHEN** 该后台 review 结束
- **THEN** CLI 不显示 self-evolution updated 提示
- **AND** 终端也不显示 raw `Nothing to save.`、错误文本或 review 工具过程
