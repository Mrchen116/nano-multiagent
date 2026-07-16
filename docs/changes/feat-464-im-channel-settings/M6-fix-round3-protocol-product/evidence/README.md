# M6 Browser and Regression Evidence

2026-07-16 使用本 milestone worktree 的隔离高位端口 IM、Gateway、Vite 和主配置中的真实飞书测试通道完成 headed Chromium 复验。浏览器从真实登录页进入 `default-agent → Channels`；Gateway 配置、workspace、credential key、manifest cache 和 IM SQLite 均位于 worktree，收尾已删除。

## Browser journeys

| Journey | Real entry and result | Prototype result |
|---|---|---|
| Connected → Reconnect | 在线卡片先显示 `Connected / Current configuration applied`；点击真实 `Reconnect` 后 HTTP 返回成功，页面收到新 status 并进入 `Connecting`，未出现 500 或 desired revision/版本文案。 | `prototype.html#channel-reconnecting`：PASS |
| Offline failed last-known | 停止同一 Gateway，并通过 production SQLite status projection 固定最后一次 runtime 状态为 failed；真实页面在 375×812 显示 `Node offline / Last known status: Connection failed (node offline; not a current connection)`、最后更新时间和 disabled live action。 | `prototype.html#channel-failed/#channels-mobile`：PASS |
| Offline removal retry | 在真实离线页面确认删除，HTTP 持久化 removal receipt；点击 `Retry apply` 不发 live-only request，显示 `Waiting for the node to return before continuing deletion`，页面无 `channel_node_offline` raw code。 | `prototype.html#channel-deleting`：PASS |
| Automatic removal success | 将同一真实 receipt 收敛为 applied 后 reload，Channels 进入 `No external channels yet`；旧 waiting notice 与 alert 均不存在。 | `prototype.html#channel-deleting`：PASS |

桌面 Reconnect、375×812 offline failed、offline removal waiting 和最终 empty 截图由 Playwright CLI 生成在临时 `.playwright-cli/`；截图只包含产品掩码后的 App ID，不含 App Secret。临时浏览器 artifact 已在完成文字取证后随运行目录清理，避免把本机 runtime 标识和测试应用标识提交为长期产品资产。

## Console, security, and cleanup

- Reconnect journey 无 HTTP 500、raw protocol error 或 React render error。
- Gateway 被故意停止后，console 仅有 Agent capabilities 的预期 HTTP 503；Channels list、delete 与本地 retry feedback 均正常。
- worktree 配置的 startup/bootstrap 永久回归递归扫描配置目录，确认无 legacy marker、`*.bak` 或 `*.tmp`，最终配置 mode 为 `0600`。
- 浏览器关闭后停止 Vite/IM/Gateway，并删除 worktree config、workspace、SQLite、WAL/SHM、credential key、manifest cache、PID、logs 和 Playwright 临时目录；两个高位端口均无 listener。

## Permanent regression map

- Public sender identity / terminal FIFO：`test_gateway_im_connection_behavior.py`。
- Offline status incarnation coalescing / late result：`test_channel_status_protocol.py`。
- Safe startup config convergence：`test_builtin_skill_bootstrap.py`。
- First apply failure / real Connected → Reconnect HTTP-WS path：`test_channel_apply_failure_projection.py`、`test_channel_removal_reconcile.py`。
- Offline last-known / removal waiting / success cleanup：`agent-channels-panel.test.tsx`。
