# cli spec delta — bugfix-426

> 本 unit 对长青契约层 `docs/specs/cli/spec.md` 的增量。主语 = CLI 用户。

## ADDED Requirements

### Requirement: REPL 在 run 执行中可继续输入，输入 steer 进当前 run

run 执行期间 REPL 输入不被阻塞；用户在 run 运行中提交的输入注入当前 run 的下一轮，而非排队等其结束。

#### Scenario: run 执行中输入被注入当前 run 下一轮
- **GIVEN** REPL 的某个 run 正在执行（流式输出进行中）
- **WHEN** 用户在 run 未结束时输入并提交一条消息
- **THEN** 输入在当前 run 的下一次模型调用前被带入上下文，不阻塞、不等当前 run 整体结束

#### Scenario: 空闲时输入仍开新 run
- **GIVEN** REPL 当前无执行中的 run
- **WHEN** 用户输入并提交
- **THEN** 照常作为新 run 处理
