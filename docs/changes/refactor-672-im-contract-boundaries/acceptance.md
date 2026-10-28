# refactor-672 — 验收报告

> 对齐 motivation.md 用户侧验收标准；Round 1，2026-10-28。
> Validation snapshot: `ff326c351 → 648b5439e914d6cf90f85a5296734c0e77e3c7eb`

## Verdict

**pass**。三项必验 Scenario 均通过，blocking / major / minor 问题均为 0。

## 用户旅程体验

按 design.md Runbook，以客户端相同 HTTP API、真实 IM WebSocket 和 SQLite 驱动专用服务 `http://127.0.0.1:53499`，独立执行读取、保存、刷新、拒绝越权、版本冲突和断连恢复。owner 保存后能看到新名称、Custom Instructions 与递增版本；失败不会显示候选已保存；重连后原操作确认成功，可继续读取。本 unit 无客户端变更，未评价 Web/iOS 视觉，也未运行模型或真实 Node 配置落盘。WS 节点为验收者控制的协议对端，模拟持有应用回执；不把此结果声称为真实 Node 工作区/模型执行验收。

服务由 caller 构建并交接，验收开始核对 checkout HEAD、clean status 与 PID 69336 的独立启动命令；没有重启共享服务。模型上下文基线不适用。专用 alice owner、bob 与 outsider 身份来自隔离环境。初始协议驱动曾缺必填 group_reply_policy、配置依赖和正确回包字段；按 API 错误与协议交接校正后重新执行有效旅程。这些驱动错误不计为产品失败；最终结论仅依赖校正后的独立观察。

## Reference Artifacts Reviewed

N/A。无原型、视觉或 must-match 契约；读取 motivation.md、design.md Runbook，以及 current `agents-nodes.md` 配置操作、`auth-tenancy.md` owner/空间权限和 `gateway-relay.md` 连接契约。

## 问题清单

无产品问题。

## 验收标准覆盖

| Requirement / Scenario | 期望来源 | 验证方式与实际证据 | 结果 |
|---|---|---|---|
| 配置编辑与空间权限保持 / owner 保存与刷新 | motivation.md；current agents-nodes、auth-tenancy | alice PATCH 200，将名称设为 `Reviewer saved`、custom_prompt 设为 `Reviewer preservation 672`；随后 live/mirror GET 200 均保持新值、profile_version=4。bob/outsider GET 与合法 PATCH 均 404。旧 version=1 PATCH 409 `profile_version conflict`，新值未覆盖。证据 A。 | pass |
| 配置未知结果可恢复 / 应用确认丢失或节点不可达 | motivation.md；current agents-nodes 的新离线请求/ACK 丢失契约 | 接到 apply 后不返回 ACK 并关闭节点连接，PATCH 返回 503 `config_apply_pending`；断线期间新 PATCH 同样待确认，未冒充成功。重连 status 请求仍用 `60aa9240ad9d45f98e1893518a9cc743`；返回匹配 fingerprint 的 applied 回执后 GET 200，名称 `Recovered original operation`、version=5；mirror 刷新一致。独立离线新写返回 409 `agent_node_offline`。SQLite 仅四条已接受操作、全部 committed，无 offline/stale/unauthorized 候选。最终旅程恢复期间只有一次 apply、原 ID status 查询，无重复 apply/create。证据 A/B/C。 | pass |
| 节点消息归属不变 / 连接更换与迟到结果 | motivation.md、design.md NodeRpc 契约 | 旧连接收到 get 请求 `df917533-e9e1-41da-8971-c3c9064d8222` 后注册新连接；从新连接冒用该 ID 回包、旧连接迟到回包均未完成原请求（各等待 300 ms，done=false），最终返回原持久配置，未采纳注入名称。新请求 `392c75a1-f4de-4a1c-94a1-458b4f94e830` 等待时再发旧 ID，done=false；只有新请求正确 ID 的当前连接回包获 ACK 并完成。证据 B。 | pass |

以上按现行契约走既有行为检验不变性；没有另启动基线版本做 A/B。连接场景选择替换连接与迟到结果这一必验分支，未扩展为所有 RPC 命令并发矩阵。创建工作区幂等没有真实 Node 文件系统证据；本轮验证更新操作不重发/不新建 operation，不声称实际创建工作区验收。

## 证据与清理

以下为本 worktree 临时验收证据，不提交运行数据：

- A：`.e2e-refactor-672/reviewer-evidence.json`，校正协议后的真实请求/响应；对应驱动 `reviewer.mjs`。
- B：`.e2e-refactor-672/reviewer-connection-evidence.json`，替换连接/迟到 ID/离线拒绝；对应驱动 `reviewer-connections.mjs`。
- C：`.e2e-refactor-672/reviewer-db-evidence.json`，只读 SQLite operation 状态及候选快照。

全部验收者启动的 WebSocket/HTTP 客户端已经关闭，脚本退出。IM 服务由 caller 最终清理；未操作生产、共享主仓或修改源码/测试/受控配置。报告未提交，由 caller 收口。

## 上层文档同步

- [x] `SPEC.md`：无需更新，产品边界未变。
- [x] `docs/specs/im/`：无需更新，no spec delta，验收符合已有契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。
