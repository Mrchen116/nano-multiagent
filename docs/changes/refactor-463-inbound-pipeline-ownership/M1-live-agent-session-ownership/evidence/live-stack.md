# M1 隔离真栈验收证据

日期：2026-07-15  
实现提交：`574da3ca6`（R3 C2）

本页只保留可复核的命令、公开入口结果和持久化对账摘要；临时栈由
`scripts/e2e-up.sh` 创建在 pytest 隔离目录，结束时由 `scripts/e2e-down.sh`
关闭。未记录访问 token、JWT secret 或 LLM 凭据。

## 1. 最终静态与回归门禁

```text
.venv/bin/ruff check src tests
All checks passed!

.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal
3346 passed, 1 skipped, 22 warnings in 33.22s
```

## 2. 动态 Agent 配置在下一轮生效

命令：

```text
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 PYTHONPATH=src \
  .venv/bin/pytest -xvs \
  tests/e2e/critical_paths/test_create_agent_via_im_critical_path.py
1 passed in 9.48s
```

该测试在 Gateway 已启动后通过 IM 配置中心创建 `e2eNew02fc8a`，随后才建立
直聊并发送 token。隔离栈 SQLite 对账：

```text
agent_profiles:
e2eNew02fc8a | E2E New e2eNew02fc8a | wt-e2e_critical_stack0-90674 | revision 1

messages, conversation 045f07f2a0fd4a1d9f17f1c41b7307b2:
user  | 请把这个 token 原样回复给我，只回 token 本身：NEW1D9EBDC1
agent | NEW1D9EBDC1

session_bindings:
web_relay:045f07f2a0fd4a1d9f17f1c41b7307b2:e2eNew02fc8a
  -> sess_9f11570c4969bdcf
```

因此创建事件发布到 `LiveAgentCatalog` 后，紧随其后的新一轮已按新 snapshot
路由并创建 session；不是重启后才偶然生效。

## 3. Gateway 重启续接与 cron canonical direct

在最终 C2 上一次运行两条真实关键路径：

```text
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 PYTHONPATH=src \
  .venv/bin/pytest -xvs \
  tests/e2e/critical_paths/test_restart_session_continuity_critical_path.py \
  tests/e2e/critical_paths/test_cron_push_critical_path.py
3 passed in 62.07s
```

重启测试先在直聊保存暗号，再真实停止并重启 Gateway，最后在同一公开 IM
会话追问。持久化对账：

```text
binding:
web_relay:065091d5b5fe447ab83e7538341c815d:default-agent
  -> sess_764addbe81431d60

same conversation messages:
user  | 请记住这个暗号:MEMO7511DA5E...
agent | 我已记住暗号：MEMO7511DA5E...
user  | 我刚才让你记住的那个暗号是什么?请原样复述它。
agent | MEMO7511DA5E
```

第一次运行该路径曾失败：启动 reconcile 对完全相同的 IM mirror 仍 publish
新 revision，进而 drop durable binding，重启后从 `sess_b0...` 漂移到新
`sess_e9...`。根因修复为“先持久化；若 catalog 中 config 完全相同则不
publish、不 invalidate”，并增加
`test_identical_reconcile_preserves_restart_binding`。以上最终运行证明续接恢复。

cron 路径在栈启动后动态创建 `cronBot395bde`，首轮对话让 Agent 注册 5 秒
周期任务；后续自动触发消息继续落同一 direct conversation。SQLite 对账只有
一条该 Agent 的 canonical direct binding：

```text
web_relay:60cf46c011a24bffbffeb44856150b63:cronBot395bde
  -> sess_5ca50565e3b28320

conversation 60cf46c011a24bffbffeb44856150b63:
07:55:29 user  | 注册 everyMs=5000、payload 含 CRONFFD124CE 的任务
07:55:57 agent | 已注册成功...
07:56:02 agent | 自动触发后的新消息
07:56:07 agent | 自动触发后的新消息
```

这同时证明 cron tick 读取的是动态 catalog，awareness/delivery 经 binder 找到
canonical direct，而不是 scheduler 保存的启动时 Agent/session 快照。

## 4. `send_message` 连续历史

在 `scripts/e2e-up.sh` 隔离栈中创建仅允许 `send_message` 的 Agent
`dispatchbdc9f8`、第二个真实 IM 用户，并从源直聊要求 Agent 把
`DISPATCH931A209B` 原样发给该用户。公开 IM 目标会话收到相同 token；当时的
SQLite 对账显示源/目标两个 Gateway conversation key 都绑定到同一 Kernel
session：

```text
web_relay:4e71656c972e40c2a1cd22fbd69fac9d:dispatchbdc9f8
  -> sess_0006d37a8997d39f
web_relay:8f9e67975c294dfeb428efa8388622bc:dispatchbdc9f8
  -> sess_0006d37a8997d39f
```

该 session 的持久化 JSONL 顺序为：

```text
1 user      | 要求调用 send_message(to=<第二个用户>, text=DISPATCH931A209B)
2 assistant | tool_call send_message，参数含精确 token 与目标 user_id
3 assistant | DISPATCH931A209B，idempotency_key=dispatch-sync:<call-id>
4 tool      | ok=true, target=<第二个用户>, text=DISPATCH931A209B
5 assistant | DISPATCH931A209B
```

第 3 条是 IM ack 后由 `InternalDispatchHandler` 追加到捕获 snapshot 的原 session；
第 4、5 条随后以它为 parent 继续，证明目标 conversation bind 与原会话历史没有
分叉或丢失。敏感签名与认证信息未复制进证据目录。

## 5. 未知 Agent 拒绝且无持久化副作用

在独立 `e2e-up.sh` 栈中通过公开 IM REST 创建 participants 含
`unknown-refactor463-live` 的直聊，并在请求前后查询 binder：

```text
HTTP 400
{"detail":"participant_ids contains unknown users"}
session_bindings matching unknown-refactor463-live: 0 -> 0
```

未知目标在公开 ingress 即被拒绝，没有创建 conversation/binding，也没有进入
Kernel；永久单测 `test_require_rejects_unknown_agent_without_fallback` 另锁定
Gateway catalog 不会回退到其他 Agent。

## 结论

上述证据覆盖 M1 的真实行为门槛：动态配置下一轮、Gateway 重启续接、cron
canonical direct、`send_message` 同一 Kernel session 的连续历史，以及未知 Agent
无副作用拒绝。隔离进程已全部由 `e2e-down.sh` 关闭。
