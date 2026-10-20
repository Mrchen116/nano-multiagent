# Validation evidence

## 修前真实飞书复现

- Baseline: 0fa706a67 产品代码（文档 HEAD 9fa676f00），2026-10-20 09:53 Asia/Shanghai。
- Method: 专用测试 App 的 user identity 真实发送，经 SDK 到隔离正式 PA；IM/Node/DSH 位于本 worktree。
- Input: `PA621_BASELINE_0953`；平台消息 `om_x100b6258d6ff80b0b099c7ada43a8d5`；影子消息 `7a777f19734042a9984d47121a1eccd0`。
- Result: 输入被当 external 审查并产生“隔离测试是边界探测”的拒绝通知；来源事件仍 pending，Node 输出镜像报 `personal_reviewed_delivery_required`。证明真实链路存在误分类/交付拒绝，不以服务在线推断成功。
- Locator: 本地 `/tmp/bugfix-621-evidence/pa621-baseline/observations.json`、`gateway.log`（运行产物不提交）。
- Limit: 此基线证明本次测试输入的失败；此前生产 09:10 提醒误拒绝证据见 incident。

## 定向回归

- 初始 4 个新增回归在修复前失败，旧 31 个通过；修复后同组 35 个全部通过。
- External/Global/Inbox/PA 相关组初步 64 个通过，typecheck 全部通过；最终集成验证待以下实测完成后记录。


## 修后真实飞书链路

- validated_at: `fad8b8355716a73165bf0d688644dfbf0cc84dde`；executed_base: `732ba8a2c06c072f8a5b8ad74ad08d43d6cb34a9`。未提交代码 diff 为空；该源码构建后启动本 worktree 的隔离 IM/Node。构建 installer 标签仍为文档基线，不能据此声称生产部署；实际执行为本地 lib 产物。
- 隔离环境：2026-10-20 10:01，IM `127.0.0.1:62652`，node `wt-nano-multiagent-19058`，正式 PA `pa_52a910e43b0f`，主会话 `35d34236-f4c7-4817-a8cd-08378e63f25a`。模型 `codexOAuth:gpt-6.1-sol`，真实代理与 DSH；没有向生产发消息或改生产调度。
- 10:04:07 为新 PA 新建测试飞书 channel；中央初始 runtime 为空，随后首个真实来信将主人绑定为实际发送者。沿用自动首次绑定，无手工设置 owner_open_id。
- 10:04:19 用户身份真实发送 `PA621_REPLY_1005` 与两分钟提醒请求；平台源消息 `om_x100b62588cfe34b0cd0f935e822bad1`，中央镜像 `65b49ee28db842588e88b2ea5292e47a`，shadow `c_dhg8tck0`。中央 event 1 processed，Inbox seq 1 的 `personal_source_role=owner_instruction`、`channel=feishu`，只有一个对应输入。
- 原单聊收到回复 `om_x100b62588d28d880ce8a5f7c4d99e67`，内容含 `PA621_REPLY_1005`；创建完成通知 `om_x100b625888f4f48cb012d424622c5d1`。
- 一次性任务 `schedule-1b581927-5aa3-46c6-8b01-4fc13eb92559` 在同一主会话创建，scheduledAt `2026-10-20T02:07:04.522Z`，DSH deliveredAt `02:07:04.529Z`，输入 `0df3f89a-2dac-4855-83a7-5dd9bea89bb0`；任务随后 inactive。
- 飞书原单聊实际提醒消息 `om_x100b6258819514b0cd3a54305c30390`，正文精确为 `PA621_REMINDER_1005`。真实 user API 读取到此消息；ExternalStore 为 confirmed，platform_id 与读取一致，IM mirror `b721f314ca48436aa057968b46268919`。
- 平台消息读取使用专用 `e2e-feishu-testagent` profile 的 `im +chat-messages-list --as user`；测试聊天 `oc_3b9bdbedb101b1b9ccf6353ac68c4777`。证据明确区分 DSH 已触发、SDK 已确认、平台可读取三层。
- 本地原始证据：`/tmp/bugfix-621-evidence/pa621-fixed/snapshot.json`、`/tmp/bugfix-621-platform-latest.json`。原始日志、数据库、配置不提交。独立产品重验见 regression.md。

## 本地 CI 等价检查

- `pnpm typecheck`：通过，`/tmp/bugfix-621-final-typecheck.log`。
- `pnpm build`：通过，`/tmp/bugfix-621-build-fixed.log`；前端 `npm run build` 通过。
- `pytest -m "not e2e" -q`：62 passed / 31 deselected，`/tmp/bugfix-621-pytest.log`。
- `ruff check .` 与 `ruff format --check .`：通过，83 files formatted。
- 前端 `npm run test`：100 files / 936 tests passed，`/tmp/bugfix-621-frontend-tests.log`；`npm audit --audit-level=critical` exit 0（5 low）。
- `./scripts/docs-check`：通过，246 maintained sources / 67 routes；归档后再检查最终路径。
- 后端全量首轮：103 files / 453 tests passed，workspace-tools 单项触及既有 90 秒上限；同一冻结版本单独复跑该项 1/1 通过（36.97 秒，`/tmp/bugfix-621-workspace-tools-retry.log`）。合并覆盖全部 454 项；首轮超时发生于前后端与实测并行时，负载相关尚属推断，没有因此改测试上限或代码。


## 独立产品重验

- `regression.md`（提交 `a1415206e`）由独立 reviewer 记录 pass / 0 issues。
- 第二条提醒 `schedule-3228ba03-4c07-4911-a7f9-31f2c9be0b52` 在 `02:09:14.718Z` 注入同一主会话；真实平台消息 `om_x100b62589bc854bcce5c0699ce4956e` 正文精确为 `PA621_REVIEW_REMINDER_1006`，回执 confirmed，平台只出现一次。
- Web 源消息 `d3fb74b27c7445f78324e4f499f48c5a`，Web 回复 `9f5dcfaa0537456e86999f8eb8a4ff0c` 正文精确为 `PA621_WEB_REVIEW_1006`。三条用户输入在 Inbox 各一次，均进入同一主会话；两个一次性提醒均 inactive。
- 真实平台已证明收发与到时提醒；非主人/群边界、历史输出失败和重放则由受控回归证明，不声称在真实群聊测试。
