# Feishu approval input E2E evidence

- Claim: 飞书真实原生审批卡用一套通用字段布局展示任意工具的 input values，而不是只展示参数名或整段 JSON；既有审批按钮仍可用。
- Executed base: `48d19d8a7` (`origin/main` at unit creation).
- Executed head: `39084f01ff40aa396ac216c9f1159248db6a869c`.
- Environment: `config/e2e/gateway.yaml` 经 `scripts/e2e-up.sh --feishu` 渲染到隔离 worktree；专用 `feishu:e2e` Bot、非默认 E2E 用户 profile、临时 IM 端口和临时 Gateway workspace。未使用生产 Gateway 配置或用户主 workspace。
- Method: 在隔离 Agent workspace 预置仅含 `value = before` 的测试 `.gitconfig`；测试用户在飞书 1:1 对话要求 Agent 使用 `edit` 将其替换为唯一哨兵 `value = BUGFIX526-E2E-FIELD-LAYOUT-4`，从真实消息入口触发 kernel 权限请求和飞书 native approval surface。
- Result: 飞书消息列表返回一条 `msg_type=interactive` 的 Bot 消息，卡片标题为 `Tool approval required`，Input 区按 `path`、`oldText`、`newText` 三个 label/value 字段展示，并包含 `Allow once`、`Deny`、`Allow for session` 三个操作；不存在整段 JSON 外壳。飞书 macOS 桌面端只读视觉检查确认字段原生对齐：短字段可两列排布，较长字段换到下一行。用户未执行审批，隔离文件仍为 `value = before`。
- Locator: 触发消息 `om_x100b68a02bfee4b0c3aa142bdf6a176`；审批卡 `om_x100b68a02b5e7d38c3b00fb16ea606b`；飞书会话 `oc_3b9bdbedb101b1b9ccf6353ac68c4777`；执行时间 `2026-08-10 11:32 +08:00`。
- Limit: 本次真实入口只验证卡片展示和操作入口，刻意不批准敏感写入；允许、拒绝、owner 限制与 first-wins 状态转换由既有权限 pipeline / adapter 自动化测试覆盖。
