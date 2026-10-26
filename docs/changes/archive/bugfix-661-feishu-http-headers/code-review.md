# bugfix-661: Code Review

## Review scope

- Base / executed_base / effective_base: 09eb59bd9073bfd1d071bdfc84bf75a0be99c018。
- Head / validated_at: b3124ba106634d62c5240a23d8a808afad5fac40。
- Review mode: full。
- Included commit: b3124ba10；7 个任务文件，无未提交生产代码。
- Reviewer: 独立 bugfix661_code_review，gpt-6.1-sol / high。
- Skills: change-code-review；agent-context-review Implementation Review。

## Round 1

- Result: Passed，findings `[]`。
- 核查 Node 每次读取当前 credential、三种 HeadersInit、大小写无关的 Authorization 替换、调用方对象不可变、超时和请求体不变。
- 核查真实 HTTP 测试覆盖 PA/普通 Agent 图文上传、消息落库、PA 来源事件及提交后丢失回执的重启去重。
- 核查旧实现 5 新测试失败 / 15 原测试通过及修复后 84 相邻用例通过的日志；审视结论没有外推为全仓无效。
- 唯一文档校正：as-built 的 implementation Base 改为实际 parent 09eb59bd；a16859ac 保留为生产故障基线。其间两个上游提交仅修改部署验证文档/Skill，无生产源码差异。

## Context 与证据限制

覆盖 ExternalChannels → HTTP → IM messages/attachments → observations 的交付段，既有 owner/source、生命周期与幂等约束不变。没有捕获真实 provider 输入或验证模型消费、Feishu SDK 连接及回复，不作为用户验收。

以上是独立代码审查时的证据边界；后续真实收发证据见下节，不改变该审查的范围。

## 专用飞书 Bot 真实收发补验

2026-10-26 10:24–10:30，按用户明确要求使用专用测试 Bot，通过 `e2e-up.sh --feishu` 启动完全隔离的 IM、Gateway、owner、workspace 和 PA。验证 App/Bot identity，使用独立非 default CLI profile；普通 Agent channel 停止后才连接 PA channel。本轮未修改生产数据、生产配置或生产服务。

- 普通 Agent 一轮：唯一标记 `FEISHU661_ordinary_codex_482e7e3f`，正确回复 437。
- PA 新会话首轮：唯一标记 `FEISHU661_pa_8919b5ec`，正确回复 437。
- PA 同会话追问：唯一标记 `FEISHU661_pa_followup_8a7fc341`，正确回复 483。
- 三轮均核对真实飞书发送、SDK 入站、accepted=1 与 IM mirror、模型回复、confirmed 出站回执、飞书消息 API 读回和隔离 IM 浏览器可见正文。PA 两条 source event 均 processed，每轮一条入站和一条回复。
- 首轮默认 DeepSeek 模型返回 402 InsufficientBalance，错误正确回到测试会话，但不计为业务成功。仅通过隔离配置 API 切换测试 Agent/PA 为 codexOAuth:gpt-6.1-sol 后完成上述三轮；未修改生产模型或源 fixture。
- 本轮现场覆盖文本收发；图片与丢失回执重启去重仍以真实 HTTP 集成测试为证据。飞书侧使用平台消息 API 读回，未宣称完成原生飞书客户端交互验收。
- 执行 e2e-down，核对 IM/Gateway/DSH 退出、端口释放、Bot listener lock 释放、tmux 结束；删除隔离 config、JWT secret 与 channel credential 文件。本地日志、截图和数据库未提交。
- 本机证据：`/Users/czj/.codex/reports/bugfix661-feishu-live-20261026/report.md`，包括平台 message_id、IM message_id、原始读回、事件状态、截图和清理结果。

本次补验由 Agent 执行，不记为用户亲自验收；未重放生产积压消息，未合并或部署修复。生产代码仍为 b3124ba10，审查结论 retained。

## Validation

- Node 窄 typecheck、全仓 build/typecheck、check:ios-runtime：通过。
- 相邻 TS 套件：14 files / 84 tests passed。
- 原错误 mutation：5 新用例失败，15 原用例通过；已恢复修复。
- docs-check、Python non-E2E（70 passed / 32 deselected）、ruff check/format：通过。
- 完整 TS 套件：140 files / 758 tests，首次 755 passed / 3 failed（473.57s）。失败为 workspace-tools 90 秒超时、agent-disable-native 的 kill EPERM、workflow-approval 事件列表缺失；均在未改动的 DSH 层。
- 失败项串行复跑：3 files / 10 tests passed（61.64s，未调超时或弱化断言）。保留首次失败，不将其改写为全量一次通过；没有证明三者具有同一根因。
- 该轮宿主曾观测到 load average 26；这是环境线索，不作为三项失败的确定归因。
- 本次没有前端或 iOS App 修改；check:ios-runtime 仅为共享打包一致性检查，不是设备验收。
- 本机日志：/Users/czj/.codex/reports/bugfix661-feishu-http-20261026/。

## Closure

无代码 findings，无修复复审。effective_through 为同一生产代码树 b3124ba10；审查后的文档提交仅更正 Base 与补录审查/检查结果，代码和测试相对 validated_at 不变，结论 retained。用户随后查看真实飞书补验结果并要求“合入代码”，本轮据此收口归档、创建 PR 并等待 CI 后合入；不冒充用户亲自操作测试，不含生产部署。

## 最终同步与交付判断

- 用户确认：2026-10-26，在专用 Bot 真实收发报告之后明确要求“合入代码”；作为结果接受与合并授权，不写成用户亲自执行验收。
- executed_base: 09eb59bd9073bfd1d071bdfc84bf75a0be99c018；validated_at: b3124ba106634d62c5240a23d8a808afad5fac40。
- effective_base: 18e0d73d74b3739024646e99280aaebfc35995c1；effective_through: 本文归档提交所代表的最终 PR tree（仅增加文档与归档，具体 SHA 由 PR body 记录）。
- main 增量仅为 bugfix-662 的 Agent 设置控件/无障碍公告、相关文档和 refactor-663 的研究文档；没有 Node HTTP、ExternalChannels、IM 路由、模型交付、依赖或 CI 配置变化。本次两处生产源码、两处回归测试和被验收的飞书链路未变化，独立代码审查、Context 审查与专用 Bot 收发证据 retained。
- 原 build/typecheck、共享 runtime、Python/ruff 证据仍适用；归档后复验 docs-check 与归档门禁，前端测试由最终集成树执行。首次 TS 全量失败及串行复跑证据保留，最终完整检查以同一 PR head 的远端 CI 为准。
- 无 spec delta：恢复已承诺的渠道交付和幂等行为；无一次性部署迁移。整个 unit 一并归档。
