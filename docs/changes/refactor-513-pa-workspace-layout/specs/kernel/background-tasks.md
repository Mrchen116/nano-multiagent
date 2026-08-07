# kernel background-tasks Specification (delta for refactor-513)

## ADDED Requirements

### Requirement: 后台 bash 产物跟随 session 的 workspace config directory

消费者经 SDK 在一个 workspace-bound session 启动 background bash（含超预算自动转后台）时，工具返回的 `output_file` 与实际追加输出均位于 `<workspace_root>/<workspace_config_dirname>/background-tasks/`；未指定目录名时为 `.nano`。一个 Kernel 的不同 workspace 不混写输出。

#### Scenario: 自定义目录的 auto-background 输出
- **GIVEN** consumer 以 `workspace_config_dirname=".consumer"` 创建 session，前台 bash 随后转为后台
- **WHEN** consumer 收到 `async_launched` 结果并等待任务完成
- **THEN** 返回的 `output_file` 位于该 session workspace 的 `.consumer/background-tasks/`，完成通知仍送达同一 session
