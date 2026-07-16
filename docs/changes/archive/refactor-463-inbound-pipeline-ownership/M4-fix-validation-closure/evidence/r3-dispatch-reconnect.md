# R3 — Dispatch / reconnect 真栈证据

日期：2026-07-15（Asia/Shanghai）

## 隔离栈与动态 internal dispatch

- 启动：`PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-up.sh`
- IM：`127.0.0.1:60817`
- Gateway：PID `95891`
- Gateway 实际监听：`lsof -nP -a -p 95891 -iTCP -sTCP:LISTEN` → `127.0.0.1:60831`
- 新建 session `sess_583b95392f596f95` 的 `session_created.metadata.gateway_dispatch_url` 为 `http://127.0.0.1:60831/internal/dispatch`，与实际 socket 完全一致；不是配置值 `0`，也不是历史固定端口 `8089`。
- 同一时间另起 `scripts/e2e-resilience.sh` 的 Gateway（IM 端口 `61032`），两套 Gateway 并存且均 ready，未发生固定 internal port 冲突。

## 真 `send_message`

1. 经 IM config PATCH 把 `default-agent.tool_allowlist` 设为 `['send_message']`，等待 Gateway config-sync publish。
2. 用户在 IM 直聊要求 `default-agent` 调用 `send_message`，把随机哨兵 `DISPATCH91BE9EB0` 发给 `plato`。
3. session JSONL 记录真实 tool call：`name=send_message, to=plato`。
4. tool result：`ok=true, target=plato, text=DISPATCH91BE9EB0`。
5. IM SQLite 对账：agent-agent conversation `ac34e421ea54427db13b6bf645a2a3f8` 中该哨兵消息 `delivery_status=completed`，随后 `plato` 已回复。

结论：session metadata 使用 listener 发布的实际 URL，`SendMessageTool` 经该 URL 完成了真实 Gateway → IM → 目标 Agent 投递。

## IM kill / restart 与 start-order

命令：`PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-resilience.sh`

- A1：初始 node online。
- kill IM 后 Gateway 进程存活。
- A2：同 DB 重启 IM 后，同 Gateway 无人工重启自动恢复 online。
- B1：Gateway 先于 IM 启动时保持存活。
- B2：随后启动 IM，node 自动进入 online。
- 脚本终态：`RESILIENCE E2E PASS`。

## Shadow guard 与清理

- 真栈 `.gateway.log` / `.im.log` 未出现 `RuntimeProtocolFacts` JSON 序列化错误或 `external shadow sync failed`。
- `scripts/e2e-down.sh` 已执行，`.im.pid` / `.gateway.pid` 均无存活进程，运行时 state 文件已清理。
- teardown 时仍观察到 background subscriber deadline warning；它不影响本 R3 的 dispatch/reconnect 判据，保留给 R4 的 accepted-work/shutdown 总签收处理，不在证据中静默忽略。
