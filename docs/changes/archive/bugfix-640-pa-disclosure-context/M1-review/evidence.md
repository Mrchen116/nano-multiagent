# M1 实施与验证

## 基线与隔离

- Gate 2：R1 Approved，0 CRITICAL / 0 WARNING；设计没有实质变化。
- executed_base：`9600bf3b16929fa411bb6956909c5df9777b5c3a`。
- 实施分支：`unit/bugfix-640`；使用 Codex 托管 worktree `/Users/czj/.codex/worktrees/bugfix-640-pa-disclosure/nano-multiagent`，替代手工 `.worktrees` 路径，隔离契约相同。
- Node 24.22.1、pnpm 11.7.0；主仓既有修改未纳入。
- 私有运行证据：`/tmp/nano-pa-review-640/`，不提交原始聊天、配置、日志和 token。

## 测试策略与已执行结果

- 旧版失败：扩展现有 `apps/im-server/tests/personal-disclosure.test.ts`，在无关群增加 32 条长消息后，待审 evidence 含 `UNRELATED_PRIVATE_HISTORY`，新断言失败。命令 `pnpm exec vitest run apps/im-server/tests/personal-disclosure.test.ts -t 'independent of unrelated'`；本机 `red.log`。这是 IM 证据来源的最低验证层。
- 改后同文件 15 个测试通过；既有受众、来源、附件、版本、主人更正、共享任务、渠道回执和幂等测试继续保留。旧 guard 全文断言改为当前固定指纹，不再要求把授权库注入审核正文。
- 扩展现有 Codex budget/lifecycle 与 approval-sources 测试，覆盖完整私有材料、预算缺失标记、严格四态 parser、独立缓存、增量和上下文替换。复用既有 native 测试保护共享执行器，不新建平行执行器测试。
- `personal-child-delivery.test.ts` 保留真实 DSH 子执行范围，改为核对宿主 sessionId 和真正 reviewer 输入，消息/共享任务均经独立检查。接线初验发现 Cordis 服务需显式 inject，已按现有 service promise 方式修正；测试 fixture 改用原生 reviewer session 身份识别模型调用。
- 输入分类继续走原来的独立小调用，输出披露改用同一 Codex lifecycle。

## 真聊天种子边界

- 源材料：只读生产 DM `c_kuthz6vx`、群 `c_fqyj3bvq` 当天必要消息；原副本 17,121 bytes，权限 0600。
- 重放截止 `2026-10-23T04:28:00.810Z`，最终授权原话“直接放行吧，你帮我去发”；排除之后主人自行处理的消息。
- 创建新的隔离主人、PA、群和不会执行清理的测试参与者。历史作者映射与授权入口在验收记录中明确，不伪造生产发送成功。
- 本次只验证代发；不执行原文中的文件清理，不连接生产渠道。

## 真栈准备与边界

- 运行实现 `24e952eb905d75ffce07e1188e82767639fd4a45`，IM `127.0.0.1:55643`，Node `wt-nano-multiagent-63980`；独立 stdio runtime、workspace、config、数据与身份。主模型 `codexOAuth:gpt-6.1-sol`，披露审核 `codexOAuth:gpt-6-luna`。
- 首次 PA 热创建触发既有配置恢复异常：`TaskExecution.recover` 读取尚未安装到 agents 的 PA 配置，`features` 为 undefined。YAML 已落盘，Node 配置操作仍 pending。保留失败日志和配置 SQLite 备份；只把该测试 PA 的 Node 配置操作回执设为 applied，冷启动后经正常创建重试恢复 IM active。没有预置动作许可或消息回执。不声称新建 PA API 通过。
- 13 条事故相关历史保留原正文和时间，只映射会话与作者身份；测试群含主人、PA、两个没有运行时的被动参与者。另设无关旧群及 3,600,000 字符正文，不主动投递给 PA。

## 已授权代发实测

- 独立产品验收通过真实 HTTP 入口提交原话；用户消息 `a2d0ebd8e93d432594bf6e8602da0639`。
- 实际目标群 `c_b692y37a` 新消息 `85a6b4c1832541df80a80e3e8b39b546`，只出现一次；主人收到指向该消息的结果。未执行材料中的清理指令。
- 操作 `3e1935b1-172d-409d-a591-dcf37f56ede9` 为 confirmed，绑定该消息。IM evidence 2,893 字符；披露 reviewer 首次完整模型请求序列化后 67,061 字符，后续同会话请求 67,549 字符（日志文件含排版空白，首次约 67.7k 字符）。两次都包含主人原话与实际目标群，没有无关历史正文，没有旧全库 owner_messages。
- reviewer `nano-codex-f5e8b01e-23e8-4de0-815f-f3443d33a89d`，metadata `contextMode=full`；真实 verdict allow，明确匹配原授权、原群成员与受限范围。原始请求在本机 LLM_PROXY 对应 session 日志；仅提交指标与定位，不提交私有副本。

## 本地检查记录

- 首轮全后端：119 文件/579 tests 通过，2 tests 失败。一处旧测试仍要求把来源正文放进 evidence，已改为来源可访问事实且不带该正文；另一处 workspace-tools 在并发运行 Web/后端时超时。
- 上述两文件单独复跑：9 passed；workspace-tools 在 35.91 秒内完成。未改产品代码或提高超时阈值。最终后端以 4 workers 重跑：121 文件、581 tests 全部通过（109.30 秒）。
- Web：103 文件、963 tests 通过；构建通过。Python 非 E2E：65 passed / 31 deselected；ruff check/format、TypeScript typecheck、iOS 交互 runtime 检查通过。

- Web critical 依赖审计返回 0；现有 moderate/high 提示未触及 critical 门禁。final sync 的 origin/main 仍为 executed_base，无主干增量。

## 产品回归与清理

- 独立产品 reviewer R1 pass，0 blocking / major / minor；完整路径见 [regression.md](regression.md)。负向请求在真实输入分类阶段拒绝，群内合成私密标记出现 0 次；固定拒绝另经独立披露 allow 并绑定主人通知回执。不将该结果表述为独立动作审核的真实 deny。
- 同一许可重复提交、审核期变更与强制换窗由确定性自动化覆盖；本次真聊天实际观察为自主读取历史、发送一次、主人收到结果。
- 真聊天结束后通过 e2e-down 停止隔离栈，并清理首次创建失败留下的本任务 DSH 孤儿进程。最终 SQLite 快照与日志仅本机 `/tmp/nano-pa-review-640/` 留存；未连接或改动生产。

## Final sync 与门禁有效性

- executed_base = effective_base：`9600bf3b16929fa411bb6956909c5df9777b5c3a`；最后 fetch 无主干增量。
- 产品实现 validated_at：`24e952eb905d75ffce07e1188e82767639fd4a45`；测试适配 targeted validated_at：`1520c62fc71650e5898f8860ad269354c6c19513`。
- Gate 2 Approved；独立 code review 无 finding；verifier full + corrected-delta pass；独立产品 R1 pass。其后只精确归并已审 delta、补充证据和移动整个 unit，产品代码与测试不变，以上门禁 retained；effective_through 的最终完整 SHA 在 PR body 记录。
- Canonical 归并：`docs/specs/gateway/personal-agent.md` 增加已授权长期工作与换窗缺证据两个 Scenario；未新增契约含义。无新增长期文档，领域入口保持有效。
- 完整 unit 归档表示准备交付；尚待 PR required CI 全绿与人工审查，不表示合并或部署。
