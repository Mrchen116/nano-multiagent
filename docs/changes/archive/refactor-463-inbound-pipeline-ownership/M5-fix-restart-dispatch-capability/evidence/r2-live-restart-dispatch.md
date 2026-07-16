# R2 — 真栈重启 + live dispatch 签收证据

日期：2026-07-16（Asia/Shanghai）

对应 `verification.md` Round 2 CRITICAL-1：Gateway 重启后续接同一持久化 session/history 时，
`send_message` 之前会打到旧进程的 ephemeral internal-dispatch 端口；R1 已注入 live provider
(`InternalDispatchEndpoint.current_url` 经 `build_pa_kernel()` 注入 `SendMessageTool`)。本证据
验证真实全链路（真 IM + 真 Gateway 进程 + 真 LLM + 真 HTTP 投递）下修复确实生效。

## 隔离栈

- worktree：`.worktrees/refactor-463-M5`（本 milestone 专用，未复用主仓 8011/8000/5173）
- IM：隔离实例，端口 `51401`，独立 SQLite（`data/im_service.sqlite3`，运行期用，已在收尾清理）
- Gateway：`--foreground --auto-bind`，config 为主 config 的 worktree 本地副本
  (`.gateway-config.yaml`，`node_id=wt-refactor-463-M5-m5r2`，`workspace_base` 落在
  `.gateway-workspace/`，四个 agent：`default-agent` / `plato` / `hume` / `luban`)
- LLM：本地代理 `127.0.0.1:4000`（`kimiCoding:K2.6`，真实模型调用，非 stub/mock）

> 起停范式说明：本沙箱环境里，脚本内 `cmd &` 派生的后台子进程会在脚本自身进程退出后被连带
> 回收（不同于用户真实终端的常规行为），因此改为把 IM / Gateway 分别作为各自的长驻后台任务
> 直接启动（等价于手工在两个终端各起一个),配置派生 / 端口分配 / workspace 预建仍按
> `scripts/e2e-up.sh` 同一套逻辑手动执行一遍，未跳过任何隔离步骤。

## 时间线与观测

### 阶段 1 — 端口 A 创建并持久化 session，真 `send_message` 成功

1. Gateway 首次启动，internal-dispatch listener 实际 bind 端口 **A = `51661`**
   （`lsof -p <gateway_pid>` 确认；`personal_assistant.main` 内部用端口 `0` 绑定，
   由 `InternalDispatchEndpoint.publish()` 发布实际端口）。
2. 经 IM 配置中心把 `default-agent.tool_allowlist` PATCH 为 `['send_message']`。
3. 用户在 IM 直聊要求 `default-agent` 调用 `send_message`，把随机哨兵
   `DISPATCHA7F3C21` / `DISPATCHA7F3C21RETRY` 发给 `plato`。
4. `default-agent` 的 Kernel session（`sess_d912248cce78406e`）JSONL 记录：
   `session_created.metadata.gateway_dispatch_url = http://127.0.0.1:51661/internal/dispatch`
   （即端口 A，创建时刻的实际 URL，与本轮 M4 R3 观测到的模式一致）。
5. 两次真实 `send_message` 工具调用均返回 `ok=true`；IM SQLite 对账：
   agent-agent 会话 `e6230c0ab63448a9b1cbc2500403b287`（与 `plato` 的直聊）收到两条消息，
   `delivery_status=completed`，随后 `plato` 也真实回复（确认消息真正进了对方直聊）。

### 阶段 2 — Gateway 从端口 A 重启到端口 B，同 binding/session 续接

6. 对 Gateway 进程发 `SIGTERM`（PID 为 python 子进程本身，非 wrapper shell），等待其在
   ~0.6s 内正常退出（非 `SIGKILL`）。
7. 复核：`lsof -iTCP:51661` 空；`curl http://127.0.0.1:51661/internal/dispatch` 得到
   `Connection refused`（exit 7）——**端口 A 已确认彻底死亡**，此后任何成功投递都不可能
   打到 A。
8. 用同一份 `.gateway-config.yaml`（同 `node_id`、同 `im_service.url`、同
   `workspace_base` → 同一份 `session_bindings.sqlite3` persistent binding store）重新启动
   Gateway。新进程 internal-dispatch listener 实际 bind 端口 **B = `57495`**（与 A 不同，
   经 `lsof -p <new_pid>` 确认）。
9. IM `/im/v1/nodes` 显示同一 `node_id` 重新变为 `online`，`last_heartbeat_at` 晚于重启时刻
   （证明是新进程的心跳，不是旧进程残留）。

### 阶段 3 — 同会话续接后真 `send_message` 只打通新端口 B

10. 在**同一个** IM 直聊会话（`conversation_id=5848d215b6ff427aa48d934fe13a7dad`）里，
    向同一个 `default-agent` 发一条新指令，要求把哨兵 `DISPATCHB9E1F44AFTER` 发给 `plato`。
11. Kernel session JSONL 确认：复用的仍是重启前的同一个 `session_id`
    (`sess_d912248cce78406e`)，历史里保留了重启前的全部轮次（`DISPATCHA7F3C21` 等），
    **没有新建 session、没有丢历史**。
12. **持久化 session metadata 此时仍是端口 A 的旧值**
    (`gateway_dispatch_url = http://127.0.0.1:51661/internal/dispatch`)——`GatewaySessionBinder`
    的 reuse 分支按 design 不刷新该字段；这正是 CRITICAL-1 描述的 stale metadata 状态，
    此刻依然原样存在。
13. 真实 `send_message` 工具调用返回 `ok=true`；assistant 文本回复"已发送给 plato"。
14. IM SQLite 对账：`plato` 会话新增一条 `content=DISPATCHB9E1F44AFTER`、
    `delivery_status=completed` 的消息，`plato` 随后也真实回复。

**结论**：端口 A 在步骤 7 已被独立确认为不可达（连接被拒绝），步骤 13/14 的真实投递
成功且被目标 agent 收到——在 persisted session metadata 仍指向已死端口 A 的情况下，
唯一可能路径是 `SendMessageTool` 走了 R1 注入的 live provider 解析出的当前端口 B，
而不是 stale metadata。这与 R1 单测/集成回归的断言方向一致，本次是同一行为在真实
IM + 真实 Gateway 进程 + 真实 LLM 全链路下的端到端复现。

## 门禁前状态清理

- Gateway（新旧两个 PID）与隔离 IM 实例均已 `SIGTERM` 正常退出，复核 `ps -ef` 无残留。
- 隔离运行时文件（`.gateway-config.yaml` / `.gateway-workspace/` / `data/im_service.sqlite3` /
  `session_bindings.sqlite3*` / `group_context_buffer.sqlite3` / `relay_dedup.sqlite3` /
  `heartbeat-state.json` / `.e2e-jwt-secret` / `*.log` / `.gateway.pid`）已全部删除，
  `git status` 仅保留本 milestone 的文档改动。
- 本地 LLM 代理（`127.0.0.1:4000`）是跨 unit 共享的开发基础设施（`docs/可用LLM_API与联调说明.md`
  记录的常驻地址），保留运行供后续工作使用，不在本 milestone 的自清理范围内。
