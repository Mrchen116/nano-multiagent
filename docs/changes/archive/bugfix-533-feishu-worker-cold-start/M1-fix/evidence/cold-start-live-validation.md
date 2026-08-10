# Feishu cold-start live validation

- Claim: 修复后的 macOS spawn Gateway 能在生产默认 worker-ready budget 内连续冷启动，并完成真实 Feishu 入站、Bot 回复与唯一 IM shadow。
- Baseline: `045373db0b07dcea18a0b44602965501822d1f89`，专用已验证的非 default Feishu E2E profile；测试 App/Bot identity 对齐，LLM proxy 健康，无预热。
- Method: 在同一受控 shell 中以 `scripts/e2e-up.sh --feishu` 启动隔离 IM + Gateway，观察 Gateway 与直属 `multiprocessing.spawn` listener；最终轮由 `scripts/e2e-feishu-probe.py` 以测试 user 向测试 Bot 发送单次 nonce，并用 Lark 消息位置、IM SQLite 聚合计数和 external shadow saga 聚合计数交叉核对。每轮以 `scripts/e2e-down.sh` 配对清理。
- Result: 两轮完整观察均进入 ready，listener 持续存活且无 `feishu worker did not initialize` / `worker_crashed`。最终轮 Lark 新增 `user=1, app=2`；IM 新增 external conversation `1`、user shadow `1`、completed agent bubbles `2`、failed agent bubbles `0`；external shadow saga `1`。app 与 completed assistant 气泡数一致，符合多气泡镜像契约。关停后 Gateway/IM PID、listener、端口、listener lock、临时 JWT/config/channel credential/manifest 均不存在。
- Locator: `tests/unit/personal_assistant/test_feishu_worker_startup.py`；`docs/specs/gateway/external-channels.md` 的外部回复镜像契约；milestone `progress.md` R3。
- Limit: 这是专用测试 App 的一次性 live-critical 取证，不把 profile、凭据、消息正文、provider ID、完整日志、数据库或 runtime config 提交到仓库。
