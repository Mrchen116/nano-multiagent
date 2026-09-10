# 真实浏览器验收

## Claim

Web IM 未发送输入按会话隔离：切到没写过的会话是空输入框，切回去才恢复刚才那份；桌面侧栏切换和移动端回列表再进同一规则。

## Baseline

- 分支 `unit/bugfix-549`，隔离 IM `http://127.0.0.1:62005`，Vite `http://127.0.0.1:18765`
- 账号 `nano`；会话 Draft Chat A / Draft Chat B
- 桌面 1440×900；移动 Chromium `is_mobile` 375×812

## Method

登录后在 A 输入 `draft-for-chat-A`，切到 B 断言空，在 B 输入 `draft-for-chat-B`，再切回 A / 再进 B。移动端用返回按钮回会话列表再点进目标会话。

## Result

通过。`browser-qa.json`：`desktop.b_after_switch=""`, `desktop.a_restored="draft-for-chat-A"`, `desktop.b_restored="draft-for-chat-B"`, `mobile.b_after_switch=""`, `mobile.a_restored="draft-for-chat-A"`。

截图：`desktop-chat-a-draft.png`、`desktop-chat-b-empty.png`、`desktop-chat-a-restored.png`、`desktop-chat-b-restored.png`、`mobile-chat-a-draft.png`、`mobile-chat-b-empty.png`、`mobile-chat-a-restored.png`。

控制台有既有 user stream `Failed to fetch`（隔离栈未接该通道），与输入框草稿无关。

## Limit

未覆盖待发附件、发送失败重试、蒸馏预填；那些由 `message-pane-composer-draft.test.tsx` 保护。未覆盖刷新/关页后仍在——产品不要求持久化。
