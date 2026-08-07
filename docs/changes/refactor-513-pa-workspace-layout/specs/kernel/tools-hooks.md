# kernel tools-hooks Specification (delta for refactor-513)

## ADDED Requirements

### Requirement: SDK consumer 的 workspace extension 跟随其选定目录并按 session 隔离

消费者经 `build_kernel(workspace_config_dirname=...)` 选择 workspace config directory 后，内核在每个 session 的 `workspace_root/<workspace_config_dirname>/tools` 与 `hooks` 发现 workspace extension；未提供目录名时为 `.nano`。同一 Kernel 的不同 workspace 不共享彼此的 workspace extension。消费者提供的 global extension roots 仍作为低优先级共享层，workspace extension 可用同名 tool 或 hook file 覆盖它。

#### Scenario: 同一 Kernel 的两个 workspace 使用各自 tool
- **GIVEN** 一个 Kernel 有两个不同 `workspace_root` 的 session，二者的选定目录各含不同 workspace tool
- **WHEN** 两个 session 分别运行并查询可用工具
- **THEN** 每个 session 只看到自己的 workspace tool（以及共享 base），不会调用或展示另一个 workspace 的 tool

#### Scenario: 未指定目录名的 SDK consumer 保持默认 extension 路径
- **WHEN** SDK consumer 不传 `workspace_config_dirname` 而在 workspace 中创建并运行 session
- **THEN** workspace tools/hooks 仍从 `<workspace>/.nano/` 发现

## MODIFIED Requirements

### Requirement: 内核内置基础工具集,执行受工作区安全约束

内核内置 `read` / `write` / `edit` / `bash` / `agent` 等基础工具,默认启用工作区安全约束;所有工具执行经工具注册表分发。应用经 `build_kernel(tools=…)` 追加原生工具、`create_session(enabled_tools=…)` 选子集; 每个 session 的 `<workspace_root>/<workspace_config_dirname>/tools` 下的同名工具可 override 内置(replace 语义,不致装配崩溃)。该 session 的 bash permission policy 从同一 `<workspace_root>/<workspace_config_dirname>/policy.toml` 读取；未指定 `workspace_config_dirname` 时该目录为 `.nano`，不把另一目录（包括旧 `.nano`）当作 fallback。

#### Scenario: bash 工具输出超限被截断且暴露完整输出路径
- **WHEN** 经内核运行的一次 `bash` 工具产生超过上限的输出
- **THEN** 工具结果标记 `truncated` 为真,并提供可取完整输出的路径

#### Scenario: bash 工具超时/被信号中断转为明确错误
- **WHEN** 一次 `bash` 执行超时或被信号中断
- **THEN** 工具结果暴露稳定的超时/信号细节(而非静默挂起或丢失)

#### Scenario: 会话可用工具集可查询
- **WHEN** 消费者 `kernel.list_session_tools(session_id, workspace_root=...)`
- **THEN** 返回该会话可用工具的描述信息

#### Scenario: 自定义 workspace 目录的工具 override
- **GIVEN** SDK consumer 用 `workspace_config_dirname=".consumer"` 构建 Kernel，session workspace 的 `.consumer/tools` 含一个与内置同名的有效工具
- **WHEN** consumer 运行该 session
- **THEN** 该 session 使用 `.consumer/tools` 的 override；另一个 workspace 不受影响

#### Scenario: 自定义 workspace 目录的 bash policy 约束命令
- **GIVEN** SDK consumer 用 `workspace_config_dirname=".consumer"` 构建 Kernel，session workspace 的 `.consumer/policy.toml` 与 `.nano/policy.toml` 对同一 bash command 给出冲突规则
- **WHEN** consumer 通过真实 pre-tool permission chain 请求该 bash command
- **THEN** permission decision 按 `.consumer/policy.toml` 产生，`.nano/policy.toml` 不作为该 session 的 fallback 或第二来源
