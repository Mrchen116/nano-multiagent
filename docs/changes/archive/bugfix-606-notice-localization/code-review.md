# bugfix-606: Code Review

## Scope and versions

- Reviewer: 独立 Agent `/root/review_two_quick_fixes`，`gpt-6.1-sol` / high，使用 change-code-review；未参与实现，不修改文件。
- Mode: full。
- executed_base: `9ebe12f8553a593f6179784b0276849fb14e5358`。
- validated_at: `ad5e91d7225bde6d896ba243295898d614a756aa`。
- effective_base: `9d6946df23e6b061b2cefbda89d00c34955f15c0`。
- effective_through: `5701fb016c5bf3c6aa7e49ea0aa517bb60e0ea41`，后续仅追加本审查记录。
- Included dirty files: none。独立 worktree，主 checkout 的已有修改未纳入。

## Result

完整固定 diff review 返回 `[]`。已核对首次发布、幂等重试、历史快照、事件转换、reconcile reducer 和当前语言渲染调用链。无存活 finding，无额外修复轮次。

## Validation

- 服务端真实隔离进程/认证 WS 的 system-notices regression：1 test passed，首事件有完整 notice，重试/历史保持同一快照，唯一持久事件。
- 前端 reducer + notice components：47 tests passed；修复前缺字段断言为红。
- 前端完整 93 files / 871 tests passed；npm audit critical=0，生产构建 passed。
- 后端完整运行 81 files / 297 tests 中，providers/cron 两项发生 timeout；降低并发单独重跑两文件 5 tests passed，其余 295 tests passed。未修改 timeout 或无关产品代码。
- `pnpm build`、`pnpm typecheck` passed；后端改动完成后再构建 im-server passed。
- Python 56 passed / 31 deselected；ruff check/format check passed。
- 隔离真实 Web IM：中文历史 memory notice 与后到的实时 skills notice 都显示中文；切到英文两行均切到英文；英文和中文刷新后均保持对应语言。使用候选前端生产构建和当前服务端 handler，fixture 仅生成后台通知，没有替代真人验收。
- 页面证据为本机临时截图 `/tmp/nano-notice-606-zh.jpg`、`/tmp/nano-notice-606-en.jpg`、`/tmp/nano-notice-606-zh-refresh.jpg`，未提交缓存。
- docs-check 和 git diff --check passed；新增本审查记录后再运行 docs-check。

## Sync and remaining gate（候选交付时）

同步 main 增量只包含无关 bugfix-607 的 fix.md；受审产品、测试与需求均未变，独立结论 retained。首次完整事件和时间线契约继续有效；浏览器实际发现摘要仍为英文后，同一 unit 增加摘要一致性 delta，仍待用户确认后归并。

用户尚未亲自体验候选版本；unit 保持 active，PR 以 draft 交付。自动化及 Agent 浏览器检查不冒充用户验收；用户确认后才能调用 change-fast-close 完成归档和正式交付。

## Browser-discovered preview correction

首轮浏览器截图发现左侧会话摘要仍显示存储英文。补入最新消息的结构化 notice 到会话 REST 摘要，Sidebar 复用当前语言 formatter；普通消息更新快路径清除旧 notice。新增 Sidebar 语言切换/普通消息替换断言，扩展真实进程用例核对摘要语义，并扩展既有消息快路径用例。该追加 diff 待独立 patch review，首轮产品内容的结论 retained。

独立 patch review 已在 `4f47a844ac9c6e696df828bb8bc0c8ca603365ce` 核对 `25168b92323ee13d6fa2b2adcd97e1bf2b709206..HEAD`，返回 `[]`。核对摘要持久身份、实时会话缓存刷新、当前语言渲染与普通消息清除旧 notice；无存活 finding。最终追加后前端全套 93 files / 872 tests passed，IM 全套 16 files / 76 tests passed，typecheck 和前端生产构建 passed；其余未变化检查 retained。追加范围的 effective_through 为 `4f47a844ac9c6e696df828bb8bc0c8ca603365ce`，后续仅记录本结论。

## Fast-close after user acceptance

2026-10-14 用户确认“这两个都可以合入。”，快速开发的用户验收门禁已通过。

最终同步 main 至 `c17f53ab6`；增量为 bugfix-607 的 composer 软换行/滚动条样式及对应输入场景，不触及通知首次发布、消息 reducer、Sidebar 或通知 formatter。受审产品/测试文件相对已确认候选完全未变；样式仅限定 composer，不作用于通知行或摘要。独立 full/patch review、用户验收和既有构建/全套测试结论 retained。此后仅归并既有 delta、记录确认及整体归档，不追加空 review。

本次同步后的 effective_base 为 `c17f53ab6`，effective_through 为 `3e90fe3f0c8575f3b9336638d16c45f27250c93e`；后续仅上述文档收尾。最终 focused regression、docs-check、archive gate 与 diff 检查结果随收尾提交记录。

最终同步后的前端四文件 focused regression：82 tests passed；真实 IM system-notices：1 test passed。canonical 归并后的 docs-check 与 git diff --check passed；既有前端全套 872 tests、IM 全套 76 tests、build/typecheck、Python/ruff 与远端 CI 结论 retained。归档后的文档完整性与 archive gate 再次检查。

## Final integration after PR 355

PR 355 合入后的最终 main 为 `0ccd61589304052eb55da93ec5a7d5068ec7ec23`。本 unit 在 `fc2aede0d678915f0dc464d55b3f46f6f70310eb` 已集成同一组 bugfix-605 commits，并通过完整 build/typecheck 与四文件后端组合回归（40 tests）；前端 82 tests 及既有全套检查 retained。随后同步 main 的 merge commit，Git tree 完全相同。

bugfix-605 在 Messaging 的收件人解析和 Work 查询增加只读解析，PA 增加发送前复核；本 unit 修改通知发布、会话最新 notice 和前端展示。共享文件的改动位于不同方法，无通知语义或投递语义冲突，真实 IM 两条链路在组合树上通过。独立审查、用户确认和真实候选证据继续有效；没有新增实现或需要重新确认的结果。

最终 effective_base 为 `0ccd61589304052eb55da93ec5a7d5068ec7ec23`，effective_through 为 `dae4278c90c0d7b22b260b8c4d26b74b5f3958fc`；后续仅追加本集成记录。最终 docs-check、归档唯一性与 git diff --check 通过后交付。
