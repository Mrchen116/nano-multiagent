# Gateway 配置归位整改计划

> 日期：2026-03-17  
> 背景：对齐 `SPEC.md` 与 `docs/NodeGateway-SPEC.md`

## 1. 问题定义

当前实现中，Agent 的完整配置（如 `system_prompt`、`skills`、`tool_allowlist`、`workspace_root`）主要持有在 IM 服务侧的 `agent_profiles` 中，Gateway 仅维护一份简化的内存态副本。这与架构规约不一致。

根据顶层 `SPEC.md` 与 `docs/NodeGateway-SPEC.md`：

- Agent 配置的真源必须位于 **Gateway 本地**
- 本地持久化位置应为 `~/.nano-assistant/config.yaml`
- IM 是 **可选中心服务**，只负责：
  - Web IM 消息中继
  - 配置变更通知
  - 节点状态上报
  - 用户入口与管理界面
- IM 不应成为 Gateway 运行配置的最终持久层
- IM 离线时，Gateway 必须能使用最近稳定本地配置继续工作

## 2. 目标

将 Agent 配置 ownership 从 IM 侧收回到 Gateway 本地，形成如下模型：

- **配置真源**：`~/.nano-assistant/config.yaml`
- **运行态读取方**：`src/personal_assistant/`
- **聊天执行生效路径**：Gateway 本地配置 → Kernel session / runtime
- **IM 职责**：配置入口 + 通知 + 查询转发，不再保存最终权威配置

## 3. 目标状态

### 3.1 Gateway 本地配置文件

`~/.nano-assistant/config.yaml` 需要成为完整配置载体，至少包含：

- `node`
  - `node_id`
  - `user_id`
- `agents`
  - `agent_id`
  - `display_name` / `title`
  - `description`
  - `system_prompt`
  - `skills`
  - `tool_allowlist`
  - `workspace_root`
  - `group_reply_policy`
  - `default_model`
  - 可能需要的绑定规则 / profile_version
- `channels`
- `heartbeat`
- `im_service`
- 调试/高级模式下允许的 kernel 覆盖项

### 3.2 Gateway 运行时行为

Gateway 启动后：

1. 从 `~/.nano-assistant/config.yaml` 读取完整配置
2. 构建本地 Agent registry
3. 任意外部 IM / Web IM 消息到来时，都直接使用本地配置决定：
   - system prompt
   - skills 可见范围
   - tools 可见范围
   - workspace_root
4. 即使 IM 服务不可用，Gateway 仍能继续服务外部 IM 通道

### 3.3 IM 行为

IM 不再保存 Agent 真配置，只负责：

- 提供配置编辑 UI
- 将配置变更请求转发给 Gateway
- 接收 Gateway 的配置变更结果 / 失败信息
- 查询配置时向 Gateway 发请求或读取 Gateway 上报的只读快照

## 4. 整改分阶段

### 阶段 A：数据模型归位

1. 扩展 Gateway 本地配置模型，使 `AgentWorkspaceConfig` 不再只包含：
   - `agent_id`
   - `workspace_root`
   - `title`
2. 改为承载完整 Agent 运行配置
3. 将 `load_local_config()` 升级为能加载完整 agent 配置
4. 定义 `~/.nano-assistant/config.yaml` 的稳定 schema

**验收标准**：
- Gateway 本地配置模型足以独立决定一个 Agent 的所有运行行为
- 不需要依赖 IM 额外 metadata 才能决定 skills/tools

### 阶段 B：配置持久化入口改造

> **架构约束**：Gateway 在 NAT 后面，不可作为服务端被 IM 主动连接（见 `NodeGateway-SPEC.md` §8）。
> 所有双向通信复用 Gateway 主动发起的 WebSocket 持久连接。因此 **不在 Gateway 暴露 HTTP API**。

1. IM settings 页面修改配置后，通过现有 WebSocket 连接下推 `config.sync` 通知
2. Gateway 的 `_IMConfigSyncClient.sync_agent` 从 IM HTTP API 拉取最新配置
3. 更新内存态 registry（`InboundPipeline.register_agent`），使新会话立即生效
4. 调用 `save_local_config` 将变更落盘到 `~/.nano-assistant/config.yaml`

**验收标准**：
- IM 修改配置 → config.sync 通知 → Gateway 拉取并落盘，config.yaml 发生变化
- 重启 Gateway 后配置仍保留（从本地 YAML 加载）
- IM 离线时，Gateway 使用最近一次落盘的本地配置继续工作

### 阶段 C：运行态生效链修复

1. 聊天执行时直接从 Gateway 本地 agent 配置读取：
   - `system_prompt`
   - `skills`
   - `tool_allowlist`
   - `workspace_root`
2. Kernel session metadata 仅用于“冻结会话快照”，不是从 IM 取配置的兜底
3. 旧会话与新会话的配置快照语义保持清晰

**验收标准**：
- 新建 Agent 选择的 skills 能出现在 `<RUNTIME_FILL:SKILLS_SECTION>`
- 选择的 tool_allowlist 能决定 LLM 看到的 tools
- 未选择的 skills/tools 不可见

### 阶段 D：IM 角色收缩

1. 将 IM 中 `agent_profiles` 从“配置真源”降级为：
   - 临时缓存
   - 只读镜像
   - 或删除该职责
2. IM 查询 agent 配置时，改为请求 Gateway
3. 配置同步消息语义改为：
   - “配置变更通知”
   - 不是“请 IM 作为权威源给我最新配置”

**验收标准**：
- IM 离线时，Gateway 继续使用本地配置正常处理外部 IM
- IM 恢复后只负责管理面与转发面

## 5. 当前已暴露的直接症状

本整改需要直接解决以下问题：

1. Agent `A` 在 IM settings 中选中的 `skills` 未出现在 `<RUNTIME_FILL:SKILLS_SECTION>`
2. Agent `A` 选中的 `tool_allowlist` 未体现在实际可见 tools 中
3. `workspace_root` 在旧会话和旧 Gateway 进程下出现回退到 repo root 的问题
4. Gateway 重启后，动态 agent 配置无法作为本地稳定配置恢复

## 6. 非目标

本轮不解决：

- IM 前端整体信息架构重做
- Channel 新通道接入
- LLM provider 层改造
- agent 内核产品 profile 大规模重构

## 7. 推荐实施顺序

1. 先完成 Gateway 本地配置 schema 扩展（阶段 A → M226 ✅）
2. 再统一 skills / tools / prompt / workspace 的运行态取值，从本地 registry 读取（阶段 C → M228 ✅）
3. 再补 config.sync 落盘：Gateway 拉取配置后持久化到 config.yaml（阶段 B → M227）
4. 最后清理 IM 中不该保留的配置真源逻辑（阶段 D → M229）

## 8. 验收用例

### 用例 1：离线自治

- 先通过 IM 将 agent `A` 配置为：
  - 指定 `skills`
  - 指定 `tool_allowlist`
  - 指定 `workspace_root`
- 确认 `~/.nano-assistant/config.yaml` 已落盘
- 关闭 IM 服务
- 通过外部 IM / 本地 relay 给 `A` 发消息
- 仍能按本地配置正确执行

### 用例 2：skills 生效

- 给 `A` 仅选择 2 个 skills
- 发起新会话
- 检查上游 LLM 请求中的 system prompt
- `<RUNTIME_FILL:SKILLS_SECTION>` 中只出现这 2 个 skills

### 用例 3：tools 生效

- 给 `A` 仅选择 `read`、`bash`
- 发起新会话
- 检查上游 LLM 可见工具列表
- 只出现被允许的 tools

### 用例 4：重启保持

- 修改 `A` 配置
- 重启 Gateway
- 不启动 IM
- 通过聊天验证配置仍然生效

## 9. 结论

后续整改必须严格遵守以下原则：

- **配置真源在 Gateway 本地**
- **IM 只做中继 / 通知 / 管理入口**
- **运行态以 Gateway 本地配置为准**
- **IM 离线不影响 Gateway 主路径**
