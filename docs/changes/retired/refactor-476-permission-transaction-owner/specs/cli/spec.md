# CLI Specification delta — refactor-476

> 本 delta 完整替换 `docs/specs/cli/spec.md` 的非 TTY Requirement。用户可观察行为不变；
> 只移除对具体 `input()` 函数的实现绑定，使 TTY、管道与权限交互可由同一个可停止输入 owner
> 承担。unit 收尾时按最终实现归并。

## MODIFIED Requirements

### Requirement: 非 TTY 环境可用,退化为基础行输入而不崩溃

CLI 在非 TTY 环境（如管道喂输入、CI）必须可用：stdin 按完整行顺序读取和处理，输出不发终端
控制码（ANSI 转义），不因缺少交互终端而崩溃。具体 reader、pump 或系统调用属于内部实现，
不构成消费者契约。

#### Scenario: 管道输入下退化运行
- **GIVEN** stdin 非 TTY（管道喂入若干行 + `/exit`）
- **WHEN** 运行 CLI
- **THEN** 每个完整行按输入顺序被读取和处理，随后正常退出
- **AND** 输出不含面向终端的 ANSI 转义控制序列

#### Scenario: 一次 pipe write 跨过权限询问
- **GIVEN** stdin 非 TTY，normal command、权限决定、后续 command 与 `/exit` 在一次 pipe write
  中按行送达
- **WHEN** 前一条 command 触发权限询问，CLI 随后恢复普通输入
- **THEN** 权限询问只消费一条决定行
- **AND** 其余完整行保持输入顺序交给恢复后的普通输入，既不被权限询问吞掉也不因模式切换丢失
