# Spec: Agent Core 核心能力补全（参考 ACP）

## 目标

参考 ACP（Agent Client Protocol）定义的标准 Agent 能力范围，系统性地识别 Agent Kernel 当前缺失的核心功能，逐一补齐。不引入 ACP 协议本身（不改接口名、不改通信格式、不做 initialize/authenticate 握手），只补齐功能缺口。

通信协议保持现有 HTTP + SSE 不变，接口命名保持现有风格。

---

## 能力对比：ACP 定义 vs 当前系统

| ACP 能力 | 当前状态 | 缺口说明 |
|---|---|---|
| 创建会话 (session/new) | 已有 POST /v1/sessions | 已有 |
| 列出会话 (session/list) | 已有 GET /v1/sessions | 已有 |
| 发送消息 (session/prompt) | 已有 POST /v1/sessions/{id}/messages:async | 已有，响应格式待增强 |
| 取消执行 (session/cancel) | 部分 POST /v1/runs/{run_id}/cancel | 按 run 粒度，缺 session 粒度 |
| 恢复会话 (session/load) | 隐式：run() cache miss 自动从 JSONL 加载 | **无需显式端点** |
| 关闭会话 (session/close) | 无 | **缺失** |
| 会话分叉 (session/fork) | 无 | **缺失** |
| 回溯 (rewind) | 无 | **缺失** |
| 恢复挂起 (session/resume) | 无 | **缺失** |
| 会话模式切换 (session/set_mode) | 无 | **缺失** |
| 会话模型切换 (session/set_model) | 无 | **缺失** |
| 会话配置 (session/set_config_option) | 无 | **缺失** |
| 会话模式切换 (session/set_mode) | 无 | **产品层概念，F-329 不做** |
| 多模态输入 (ContentBlock) | 仅 text | **缺失** |
| stop_reason 返回 | 返回 run_id | **缺失** |
| 事件通知丰富度 | RuntimeEvent | 缺 plan/thought/config_change 等细分类 |
| 可用命令广告 | 无 | **缺失** |
| 能力动态广告 | 静态 | **缺失** |

---

## 缺失功能清单（按优先级）

### P0 — 会话生命周期补齐

会话的完整生命周期管理，当前只有 create + message + cancel，缺 load/close。

1. 会话恢复（对应 ACP session/load）
   - 根据 session_id 恢复已有会话的上下文和状态
   - 现有 SessionStore 已有 load_session 能力，但缺 HTTP 接口暴露
   - 建议接口：GET /v1/sessions/{id}（增强）或 POST /v1/sessions/{id}:load
   - 需要：恢复后 session 状态可继续对话

2. 会话关闭（对应 ACP session/close）
   - 显式释放会话内存状态、flush 未落盘的 JSONL 写入
   - 当前 session 持久化到 JSONL，close 不封闭 session，后续发消息可从 JSONL 自然 resume
   - 建议接口：POST /v1/sessions/{id}:close
   - 需要：flush JSONL、cancel 活跃 run、清理内存状态（`_session_histories` / `_session_configs`）

3. 会话级取消（对应 ACP session/cancel）
   - 当前 POST /v1/runs/{run_id}/cancel 需要 Client 知道 run_id
   - 需要支持按 session_id 取消当前活跃 turn
   - 建议接口：POST /v1/sessions/{id}:cancel
   - 需要：session 到当前活跃 run 的查找和取消逻辑

### P1 — 会话高级操作

4. 会话分叉（对应 ACP session/fork）
   - 从现有会话创建分支副本，保留上下文但独立演进
   - 与现有 AgentContextFork 概念有关联
   - 建议接口：POST /v1/sessions/{id}:fork
   - 需要：session 状态深拷贝、新 session_id 分配、事件历史复制

5. 回溯（rewind）
   - 回到对话历史中某条消息节点，丢弃之后的所有消息，从该点继续对话
   - 被丢弃的消息在 JSONL 中物理保留（形成 DAG 死分支），但逻辑上不可见
   - 建议接口：POST /v1/sessions/{id}:rewind
   - 需要：指定 target_message_id、内存历史截断、parent_uuid 链重建

6. 恢复挂起（对应 ACP session/resume）
   - 恢复之前被暂停（非关闭）的会话
   - 与 load_session 不同：resume 针对的是内存中仍存在的活跃 session
   - 建议接口：POST /v1/sessions/{id}:resume
   - 需要：session 挂起/恢复状态机

### P2 — 会话控制增强

6. 会话级模型切换（对应 ACP session/set_model）
   - 当前 LLM 配置是全局的（PATCH /v1/llm-config）
   - 需要支持会话级 model 覆盖
   - 建议接口：PATCH /v1/sessions/{id}/model
   - 需要：session 级 model 存储、LLMClient 动态选择、model 变更事件通知

7. 会话级配置（对应 ACP session/set_config_option）
   - 允许 Client 在会话中动态调整 Agent 行为选项
   - 例如：开启/关闭 web search、切换代码风格、调整 temperature
   - 建议接口：PUT /v1/sessions/{id}/config
   - 需要：配置持久化（`config_update` JSONL 行）、内存同步（`_session_configs`）

> **关于 mode**：mode 切换（coding / review / planning）是产品层概念，对内核的影响仅限于 `system_prompt` / `skills` / `tool_allowlist` 的变更。产品层可自行定义 `mode → config` 映射，通过 `PUT config` 实现。F-329 不在内核层提供 `PATCH mode` 端点。

### P3 — 消息内容与事件丰富化

8. 多模态输入支持（对应 ACP ContentBlock）
   - 当前 SendMessageRequest.text 只支持纯文本
   - 需要支持：Image、Audio、Resource（文件引用）、EmbeddedResource（内联文件内容）
   - 建议：扩展 SendMessageRequest 为 content: list[ContentBlock]
   - 需要：Message 模型扩展、LLM 接口支持多模态、Image/Audio 的 base64 传输

9. Prompt 响应增强 stop_reason（对应 ACP PromptResponse.stop_reason）
    - 当前 async message 返回 {run_id}
    - 需要在 turn 结束时返回 stop_reason 说明终止原因
    - 建议：扩展 SendMessageAsyncResponse，增加 stop_reason 字段
    - stop_reason 枚举：end_turn / tool_use / max_tokens / cancelled / error / stopped

10. 事件通知内容分类（对应 ACP session/update 类型）
    - 当前 SSE 推送 RuntimeEvent，类型不够丰富
    - 需要在现有事件体系基础上增加分类：
      - agent_message_chunk — Agent 文本输出
      - agent_thought_chunk — Agent 思考过程
      - tool_call_start / tool_call_progress / tool_call_end — 工具调用生命周期
      - plan — Agent 执行计划
      - config_change — 配置变更
      - usage — Token 使用量
    - 建议：在现有 StreamEvent 中增加 event_type 字段做细分类

### P4 — 能力广告

12. 可用命令广告（对应 ACP AvailableCommands）
    - Agent 可以广告当前可用的 slash 命令
    - Client 在 UI 中展示命令列表
    - 建议接口：GET /v1/sessions/{id}/commands
    - 需要：Command 定义、命令注册机制、按 session config（skills / tool_allowlist）动态过滤

13. 能力动态广告（对应 ACP AgentCapabilities）
    - 当前 GET /v1/capabilities 是静态全局配置
    - 需要支持按 session 或按 product 动态广告能力
    - 建议：增强 CapabilitiesResponse，关联到 ProductProfile
    - 需要：capabilities 模型化、与 product 绑定、支持扩展能力声明

---

## 接口映射方案（全部用现有风格）

### 保留不变

| 现有接口 | 说明 |
|---|---|
| POST /v1/sessions | 创建会话 |
| GET /v1/sessions | 列出会话 |
| GET /v1/sessions/{id} | 获取会话详情（增强：返回完整配置字段） |
| POST /v1/sessions/{id}/messages:async | 异步发送消息 |
| GET /v1/sessions/{id}/events | SSE 事件流 |
| POST /v1/runs/{run_id}/cancel | 按 run 取消（保留） |
| GET /v1/health | 健康检查 |
| GET /v1/llm-config | 全局 LLM 配置 |
| PATCH /v1/llm-config | 全局 LLM 配置更新 |
| GET /v1/tools | 工具列表 |

### 新增接口

| 建议接口 | 对应 ACP 能力 | 优先级 |
|---|---|---|
| GET /v1/sessions/{id}（增强） | session/load 语义由 run() 隐式承载 | P0 |
| POST /v1/sessions/{id}:close | session/close | P0 |
| POST /v1/sessions/{id}:cancel | session/cancel（session 粒度） | P0 |
| POST /v1/sessions/{id}:fork | session/fork | P1 |
| POST /v1/sessions/{id}:rewind | rewind | P1 |
| POST /v1/sessions/{id}:resume | session/resume | P1 |
| PUT /v1/sessions/{id}/config | session/set_config_option | P2 |
| PATCH /v1/sessions/{id}/model | session/set_model | P2 |
| GET /v1/sessions/{id}/commands | AvailableCommands | P4 |

### 响应格式增强

| 接口 | 增强项 |
|---|---|
| POST /v1/sessions/{id}/messages:async | 增加 stop_reason |
| GET /v1/sessions/{id}/events | 增加 event_type 细分类 |
| GET /v1/capabilities | 关联 ProductProfile，支持动态能力 |

---

## 验收标准

### P0 验收

- [ ] GET /v1/sessions/{id} 返回完整配置（含 system_prompt / skills / tool_allowlist）
- [ ] POST /v1/sessions/{id}:close 能关闭会话并释放内存（flush JSONL + evict 内存）
- [ ] POST /v1/sessions/{id}:cancel 能按 session 取消当前活跃 turn
- [ ] close 后重新发消息，session 可从 JSONL 自动 resume 并继续对话

### P1 验收

- [ ] POST /v1/sessions/{id}:fork 创建分支会话，保留原会话上下文
- [ ] 分支会话可独立对话，不影响原会话
- [ ] POST /v1/sessions/{id}:rewind 回到指定消息节点，后续消息被逻辑丢弃
- [ ] rewind 后从该节点继续对话，历史一致
- [ ] POST /v1/sessions/{id}:resume 恢复挂起会话

### P2 验收

- [ ] PATCH /v1/sessions/{id}/model 切换模型并影响后续对话
- [ ] PUT /v1/sessions/{id}/config 修改 system_prompt / skills / tool_allowlist 并持久化到 JSONL
- [ ] 配置变更触发 config_change 事件
- [ ] 配置变更后下一次 run() 使用新配置

### P3 验收

- [ ] 支持 Image、Audio、Resource 类型的消息输入
- [ ] async message 响应包含 stop_reason
- [ ] SSE 事件包含 agent_thought_chunk、tool_call_start/progress/end、plan 等细分类

### P4 验收

- [ ] GET /v1/sessions/{id}/commands 返回当前可用命令列表
- [ ] GET /v1/capabilities 返回与当前 product 关联的动态能力

---

## 参考

- [ACP Python SDK](https://github.com/agentclientprotocol/python-sdk) — Agent Client Protocol 官方 Python SDK，提供 Agent/Client Protocol 定义、JSON-RPC 路由、schema 模型
