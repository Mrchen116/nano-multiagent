# M6 Browser and Regression Evidence

2026-07-16 使用 runtime code HEAD `397701f78971d28482f67d289c957a95b7b5b25d`、隔离高位端口真 IM/Gateway、production frontend build 和主配置中的真实飞书测试通道完成 headed Chromium 复验。浏览器从真实登录页进入 `default-agent → Channels`；Gateway 配置、workspace、credential key、manifest cache 和 IM SQLite 均位于 evidence worktree。

## Browser journeys

| Journey | Real entry and result | Prototype result |
|---|---|---|
| Connected → Reconnect | 在线卡片先显示 `Connected / Current configuration applied`；点击真实 `Reconnect` 后 HTTP 返回成功，页面收到新 status 并进入 `Connecting`，未出现 500 或 desired revision/版本文案。 | `prototype.html#channel-reconnecting`：PASS |
| Offline failed last-known | 停止同一 Gateway，并通过 production SQLite status projection 固定最后一次 runtime 状态为 failed；真实页面在 375×812 显示 `Node offline / Last known status: Connection failed (node offline; not a current connection)`、最后更新时间和 disabled live action。 | `prototype.html#channel-failed/#channels-mobile`：PASS |
| Offline removal retry | 在真实离线页面确认删除，HTTP 持久化 removal receipt；点击 `Retry apply` 不发 live-only request，显示 `Waiting for the node to return before continuing deletion`，页面无 `channel_node_offline` raw code。 | `prototype.html#channel-deleting`：PASS |
| Node recovery / removal success | 重新启动同一 Gateway 后，真实 removal reconcile 把 receipt 收敛为 applied；页面自动进入 `No external channels yet`，旧 waiting notice 与 alert 均不存在。 | `prototype.html#channel-deleting`：PASS |

## Durable screenshots

所有截图由 headed Chromium/Playwright CLI 直接读取 production frontend；只显示产品掩码后的应用标识，不含完整 App ID、App Secret、access token、credential envelope 或 websocket ticket。

| Artifact | Viewport / state | SHA-256 |
|---|---|---|
| [`connected-reconnect-desktop.png`](output/playwright/connected-reconnect-desktop.png) | 1440×1000；真实 Reconnect 后进入 Connecting | `dfc89b9899044eab83f8a0c484f2fcf985551faee43d332e85695609753c81ce` |
| [`offline-failed-last-known-mobile-375x812.png`](output/playwright/offline-failed-last-known-mobile-375x812.png) | 375×812；offline failed 降级 last-known | `da94cf27f23d4548017b10d036eaa7eb07d41d2eec148830e4f57aa87ccb9252` |
| [`offline-removal-retry-waiting-mobile-375x812.png`](output/playwright/offline-removal-retry-waiting-mobile-375x812.png) | 375×812；Retry waiting，页面无 raw 409 | `2083155b597549c967192e8ed46faa834900196c7d594e63153a2550ae99ae8f` |
| [`removal-applied-empty-mobile-375x812.png`](output/playwright/removal-applied-empty-mobile-375x812.png) | 375×812；node 恢复、receipt applied、empty 无旧 alert | `b410ba3c8eb709cd0daafb7fa22737ca0a8a03da4484394a52b22651935d78f6` |

## Console, security, and cleanup

- HTTP access log：Reconnect `200`、offline delete `200`；offline Retry 走本地 waiting 分支，access log 无 removal-retry POST。整个 journey 无 channel HTTP `500` 或 raw `409`。
- Browser console：Gateway 在线/Reconnect 阶段零 error/warning；Gateway 被故意停止后仅有 Agent capabilities 的预期 HTTP `503`，无 React render error。
- worktree 配置的 startup/bootstrap 永久回归递归扫描配置目录，确认无 legacy marker、`*.bak` 或 `*.tmp`，最终配置 mode 为 `0600`。
- 浏览器关闭后停止 IM/Gateway，并删除 worktree config、workspace、SQLite、WAL/SHM、credential key、manifest cache、PID、logs、production dist 和 Playwright 临时目录；隔离高位端口无 listener。

## Permanent regression map

- Public sender identity / terminal FIFO：`test_gateway_im_connection_behavior.py`。
- Offline status incarnation coalescing / late result：`test_channel_status_protocol.py`。
- Safe startup config convergence：`test_builtin_skill_bootstrap.py`。
- First apply failure / real Connected → Reconnect HTTP-WS path：`test_channel_apply_failure_projection.py`、`test_channel_removal_reconcile.py`。
- Offline last-known / removal waiting / success cleanup：`agent-channels-panel.test.tsx`。
