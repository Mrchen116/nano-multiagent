# bugfix-605: Code Review

## Scope and versions

- Reviewer: 独立 Agent `/root/review_two_quick_fixes`，`gpt-6.1-sol` / high，使用 change-code-review；未参与实现，不修改受审文件。
- Mode: full，随后两次 finding closure。
- executed_base: `9ebe12f8553a593f6179784b0276849fb14e5358`。
- validated_at (full): `16d7b21a778e093f2f6e10069c601997b588f16b`。
- validated_at (closure 1): `4acd833e1c42b846f559dbd4d755085531bd72aa`。
- validated_at (final closure): `dafc76c8cb670175665912afbef81c4182842db5`。
- effective_base: `9d6946df23e6b061b2cefbda89d00c34955f15c0`。
- effective_through: `dcf72b79fc83ffb40de4e3fd3675c0cf1dae81fe`，后续仅追加本审查记录。
- Included dirty files: none。独立 worktree，主 checkout 的已有修改未纳入。

## Findings and resolutions

1. Full review 确认 P2：user:/agent:/裸收件人地址绕过会话复核。加入 IM 现有目标解析的非创建模式；PA 先查询已有会话身份，覆盖三类地址；真实 WS 用例验证查询不创建空聊天。第一次 closure 确认原问题 closed。
2. 第一次 closure 确认 P1：解析后的会话身份改写投递地址，Agent 私信跳过接收方 relay。保留原收件人投递地址，以独立 reviewConversation 仅作复核；新增发送地址公开协议断言。最终 closure 确认 closed。

最终结果 `[]`；无存活阻塞 finding。用户可观察目标没有扩展到 single_thread 或外部群聊。

## Validation

- PA 与外部适配 focused regression：最终 35 tests passed；含 Web 群、Web 私聊、飞书私聊、双向镜像身份、user/agent/bare 地址、原调用幂等、其他来源与背景输入不阻塞。
- 真实 IM WS control-work：4 tests passed，含收件人只读解析、无空会话副作用与原访问限制。
- `pnpm build`、最终 `pnpm typecheck` passed；最后投递修正后 PA build 和上述 focused tests passed。
- 完整后端 `pnpm exec vitest run --maxWorkers=2`：80 files / 303 tests passed。此前两个 worktree 同时跑默认并发时出现 providers/cron/control-work 超时，降低并发后失败项 9 tests passed，未修改 timeout 或无关产品代码。
- Python：56 passed / 31 deselected；ruff check 与 format check passed。
- docs-check 与 git diff --check passed；新增本审查记录后再运行 docs-check。

## Sync and remaining gate（候选交付时）

同步 main 增量只包含无关 bugfix-607 的 fix.md；所有受审产品文件与测试内容未变化，独立结论和用户场景证据 retained。code review 通过不代替快速开发的用户验收。

用户尚未亲自体验候选版本；本 unit 保持 active，delta 未覆盖 current，PR 以 draft 交付。用户确认后才能调用 change-fast-close 完成 canonical 归并、归档和正式交付。

## Fast-close after user acceptance

2026-10-14 用户确认“这两个都可以合入。”，快速开发的用户验收门禁已通过。真实 IM / Node / DSH / DeepSeek 拦截、读取与新调用发送的完整补测记录见 incident.md。

最终同步 main 至 `c17f53ab6`；该增量为 bugfix-607 的 composer 软换行/滚动条样式和对应文档，不触及本 unit 的 PA、目标解析、投递或工作事件。受审产品/测试文件相对已确认候选完全未变，独立 code review、用户验收和既有构建/全套测试结论 retained。此后仅校正并归并已确认的 delta、记录用户确认及整体归档；没有新增实现或用户可观察结果，不追加空 review。

本次同步后的 effective_base 为 `c17f53ab6`，effective_through 为 `a277e3ee3ae399f32b9cae6b374c1e01e4ec6073`；后续仅上述文档收尾。最终 focused regression、docs-check、archive gate 与 diff 检查结果随收尾提交记录。

最终同步后的三文件 focused regression：39 tests passed。canonical 归并后的 docs-check 与 git diff --check passed；原完整后端 303 tests、build/typecheck、Python/ruff 及远端 CI 结论 retained。归档后的文档完整性与 archive gate 再次检查。
