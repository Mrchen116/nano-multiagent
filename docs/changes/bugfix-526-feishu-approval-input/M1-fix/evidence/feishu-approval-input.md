# Feishu approval input E2E evidence

- Claim: 飞书真实原生审批卡用一套通用字段布局展示任意工具 input；1:1 对话展示 values，群聊保留字段布局但隐藏 values；既有审批按钮仍可用。
- Executed base: `48d19d8a7` (`origin/main` at unit creation).
- Full-chain executed head: `39084f01ff40aa396ac216c9f1159248db6a869c`.
- Final-card executed head: `4cb7980d2ad49b55897bc35c1be550e00d8de34c`.
- Environment: `config/e2e/gateway.yaml` 经 `scripts/e2e-up.sh --feishu` 渲染到隔离 worktree；专用 `feishu:e2e` Bot、非默认 E2E 用户 profile、临时 IM 端口和临时 Gateway workspace。未使用生产 Gateway 配置或用户主 workspace。
- Method: 在隔离 Agent workspace 预置仅含 `value = before` 的测试 `.gitconfig`；测试用户在飞书 1:1 对话要求 Agent 使用 `edit` 将其替换为唯一哨兵 `value = BUGFIX526-E2E-FIELD-LAYOUT-4`，从真实消息入口触发 kernel 权限请求和飞书 native approval surface。
- Result: 完整链路中，飞书消息列表返回一条 `msg_type=interactive` 的 Bot 消息，Input 区按 `path`、`oldText`、`newText` 三个 label/value 字段展示，并包含 `Allow once`、`Deny`、`Allow for session`；飞书 macOS 桌面端只读视觉检查确认短字段可两列排布、较长字段换到下一行。最终 head 的 product card builder 直接发送到同一专用会话后，平台再次返回相同字段结构和三个按钮，哨兵为 `BUGFIX526-E2E-FINAL-5`。两次均未点击审批，隔离文件保持 `value = before`。
- Locator: 完整链路触发消息 `om_x100b68a02bfee4b0c3aa142bdf6a176`、审批卡 `om_x100b68a02b5e7d38c3b00fb16ea606b`（`2026-08-10 11:32 +08:00`）；最终 head 平台卡 `om_x100b68a0b84104acdfe8e45d15946d2`（`2026-08-10 12:11 +08:00`）；会话 `oc_3b9bdbedb101b1b9ccf6353ac68c4777`。
- Limit: 最终 head 的完整 Gateway E2E 因同机其他 worktree 全量测试占用 CPU，Feishu worker 连续超过既有 5 秒初始化门槛；未修改本 unit 之外的 worker 启动预算。最终 renderer 的真实平台接受度由 direct product-card send 覆盖，observer / permission pipeline、群聊隐私、输入上限和状态转换由自动化测试覆盖。真实入口刻意不批准敏感写入。
