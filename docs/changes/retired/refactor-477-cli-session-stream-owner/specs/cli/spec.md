# cli (coding_cli) Specification (delta for refactor-477)

## ADDED Requirements

### Requirement: 不完整的 session event source 或 projection 必须 fail closed,不得静默继续

普通单轮 input/network/runtime error 仍遵循 canonical 的“就地内联呈现并继续等待输入”。只有 CLI
用于维持 session 输出完整性的唯一 event subscription 发生 source failure，或 strict replay 证明
cursor 后存在不可重放缺口时，才进入本 Requirement 的 unsafe-session 分支。

source failure 时，CLI 暂停该 session 的普通输入，先终止并等待当前 USER run 及其自动 continuation
全部 settlement，再显示一次可执行错误。若 strict subscription 已恢复、旧 USER flow 已收口且错误已
呈现，CLI 可恢复该 session 输入。replay gap 时，CLI 必须明确说明事件历史不完整并持续阻断该 session
的普通输入；不得把 current anchor 重置为成功恢复。阻断期间只放行 `/new`、`/use <id>` 与 `/exit`
逃生命令。

若 renderer/history/stdout 在一个 event 投影中途失败，CLI 不把非事务的部分 side effect 当成可安全
exactly-once replay：该 session 在本进程内保持 projection-failed，不自动 retry/replay 未 ack event。
CLI best-effort 提示 projection 不完整，收口 USER lineage 后只允许 `/new`、`/use <其他安全
session>` 与 `/exit`；切回同一 failed session 必须拒绝。

#### Scenario: 普通轮次错误仍内联后继续
- **GIVEN** event subscription 完整,某一轮仅发生既有 input/network/runtime error
- **WHEN** CLI 内联呈现该轮错误
- **THEN** REPL 继续等待该 session 的下一次输入,不误进入 unsafe-session 阻断

#### Scenario: event source failure 先收口 USER flow 再恢复
- **GIVEN** 唯一 session event subscription 在 USER run 仍执行时异常退出
- **WHEN** CLI 处理该 source failure
- **THEN** 立即暂停该 session 普通输入,终止并等待该 USER run 及其自动 continuation 全部 settlement
- **AND** 旧 flow 收口、strict subscription 恢复后只显示一次可执行错误,随后才重新接受普通输入
- **AND** 旧 run 的输出或 steer 不得混入恢复后的下一轮

#### Scenario: replay gap 明确阻断且只放行逃生命令
- **GIVEN** CLI 切回 session 或恢复 subscription 时,已提交 cursor 后存在从有界 journal 淘汰的该 session event
- **WHEN** strict subscription open 返回 replay gap
- **THEN** CLI 明确显示该 session 的事件历史不完整,不把剩余 replay 当成完整恢复
- **AND** 该 session 的普通输入保持阻断,只允许 `/new`、`/use <id>` 与 `/exit`

#### Scenario: 重置 anchor 不能解除 replay gap
- **GIVEN** 某 session 因 replay gap 被阻断
- **WHEN** 内部仍无法从原 committed cursor 完成 strict replay
- **THEN** CLI 不得以当前最新 `sequence_num` 作为新成功基线并恢复普通输入
- **AND** 用户仍可切换到另一个安全 session 或退出

#### Scenario: renderer partial failure 不自动 replay
- **GIVEN** renderer 在 history 或 stdout 的部分副作用已发生后抛错
- **WHEN** CLI 处理该 projection failure
- **THEN** 不重试或 replay 该未 ack event,也不宣称本次投影完整
- **AND** 该 session 在本进程内持续阻断普通输入与同 session reattach
- **AND** stderr 可写时显示一次 best-effort 不完整提示；无论提示写入是否成功,用户仍可新建/切换到
  其他安全 session 或退出

### Requirement: REPL Ctrl-C 只中断 owner 当前 USER flow

CLI 在 USER run 执行/排队期间收到 Ctrl-C 时，以当前 owner 持有的 exact USER run identity 中断；同
session 的 background run、权限等待、foreground subprocess 与 completion notification 不得成为替代
目标。中断是 benign user interrupt，REPL 保持可用；只有 background 而没有 USER target 时，Ctrl-C
不把 background 当作“当前操作”取消。

#### Scenario: USER 与 background 交错时 Ctrl-C 只中断 USER
- **GIVEN** 同一 session 有 CLI 当前 USER run,同时 background task/run 仍在执行
- **WHEN** 用户按 Ctrl-C
- **THEN** 当前 USER run 被标记为 benign interrupt,中断提示只出现一次,REPL 不退出
- **AND** background run 不被取消,后续 completion notice 仍恰好呈现一次

#### Scenario: stale USER identity 不回退中断 background
- **GIVEN** owner 持有的 USER target 已 terminal 或过期,此时 session 只剩 background run
- **WHEN** Ctrl-C 的 exact compare 被拒绝
- **THEN** CLI 不回退到 session-current background run,也不把拒绝 id 标成 benign interrupt
