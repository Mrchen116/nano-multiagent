# gateway Specification (delta for bugfix-404)

## MODIFIED Requirements

### Requirement: node.register 携带 per-agent workspace_root

Gateway 上线首帧 `node.register` 除 `agents`（agent id 列表）外，携带 `agent_workspaces`（agent_id → 本地 config 解析出的绝对 workspace_root 映射），供 IM 首次落库种子使用。重连重发同帧，内容一致。

#### Scenario: 本地 config 的 workspace_root 随注册上报
- **GIVEN** Gateway config 中某 agent 的 `workspace_root` 指向非默认路径
- **WHEN** Gateway 连接 IM 并发送 `node.register`
- **THEN** 帧 payload 的 `agent_workspaces[agent_id]` 为该非默认绝对路径

### Requirement: runtime workspace_root 以本地 config 为准

Gateway 为 agent 装配 runtime（session、heartbeat、工具沙箱）时，workspace_root 取本地 config 值（缺失时落到本地默认 factory）；IM 配置镜像中的 workspace_root 不进入 runtime。其余 agent 配置字段（system_prompt / skills / tool_allowlist / features / custom_prompt 等）仍以 IM 镜像为准同步。

#### Scenario: IM 镜像的 workspace_root 与本地 config 不一致时本地胜出
- **GIVEN** IM 中该 agent profile 的 workspace_root 为路径 A，Gateway 本地 config 为路径 B
- **WHEN** Gateway 同步 agent 配置并处理该 agent 的会话
- **THEN** session / heartbeat 实际读写路径 B；路径 A 不被读写

#### Scenario: worktree e2e 隔离（不变性回归）
- **GIVEN** worktree 内 `e2e-up.sh` 起的 Gateway，config 副本 workspace_root 已指向 worktree
- **WHEN** Gateway 运行（含 heartbeat）
- **THEN** 主仓 workspace 目录零读写
