# bugfix-731: Review

## 范围与版本

- 独立执行者：`/root/toast_code_review`，`gpt-6.1-sol` / high；未参与实现，只读审查。
- 模式：full 实现审查与 corrected-delta 同轮。
- executed_base：`94d663626299b2cd69c99e9740d0c3e6607b2574`。
- validated_at：`2ec3bfe4a83bb1db5b569c296e505c6463cc9552`，完整 base..head 共 13 文件，无 dirty。
- 已验证的原产品代码版本 `cd24971fb` 与受审版本的前后端源码完全一致；同步 develop 的新增内容仅为 bugfix-732 首文档，既有测试/截图证据 retained。
- effective_base：`94d663626299b2cd69c99e9740d0c3e6607b2574`；effective_through：首次归档提交 `d9b5562a2`。审查后的 canonical 仅原样归并受审 delta，入口数量从 32 改为 33。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
| --- | --- | --- | --- |
| 私聊名、群名与发送者、空聊天列表时补取会话元数据，既有资格不变量 | 独立 change-code-review，`/root/toast_code_review`，full | pass | 真实调用方、服务端 Actor 投影、39 项通知回归；私聊用 title，群聊按 type；详情与列表同一投影，复用鉴权 query |
| canonical 名称优先与可读 fallback，完成阶段身份 | 同上 | pass | reviewer 独立执行无文件修改的 accumulator 窄断言：嵌套名称优先、缺名为 Agent、完成保留真实发送者均通过 |
| 最终 delta 与实现、测试及确认布局一致 | 同上，corrected-delta | aligned | delta 三个场景均有实现与有效证据；群聊发送者独立成行与用户已确认截图一致 |
| 两种提醒能识别来源并进入正确会话 | 用户验收复用，主 Agent 实际 Web 收发/点击与截图自检 | pass / retained | `fix.md` 的 1440×900 截图与实际持久消息，用户看图并获知限制后明确回复“很好，可以了”；不冒充独立视觉审查或手机验收 |

## Findings 与关闭

独立审查返回 `findings: []`，无存活阻塞项。具体覆盖：名称解析、设置页缺缓存、两个成员仍为群聊、完成累计/持久 pending/去重、自发抑制、外部影子消息分类、未读与真实导航身份均核过，未发现本次 diff 的实际缺陷。

## 证据与已知限制

- 通知窄测 39 项、前端与运行时构建、两条真实 Agent 收发/跳转与用户验收证据均保留。
- 完整前端为 1081 passed / 1 failed；同一草稿采用失败在未修改 `00972141a` 的独立源码 archive 也复现，reviewer 已直接核对两份日志。不声称全套前端全绿，不扩大本次范围修改该功能。
- daily capability 同步 504 单列；IM/Node/Agent 真实路径已完成，不声称完整 daily 初始化成功。
- 原始日志与两张截图位置：`fix.md` 的本机证据目录。CI、正式发布或生产状态不能从用户验收反推。

## 流程收口

重要目标和最终展示已由用户确认；独立代码与最终 delta 均通过，界面/旅程复用用户验收。本轮按快速开发收尾，没有补造事前门禁、milestone 或独立产品验收。

审查后只做批准 delta 的 canonical 归并、文档记录与整 unit 归档，产品代码未变，既有审查及测试保持有效。最终本地检查见下文，远端 CI 由 PR 状态承接；worktree 在 PR 开放时保留，合入后按清理规则处理。


### 最终本地检查

- `pnpm typecheck`、`pnpm check:ios-runtime`、Python `pytest -m "not e2e" -q`（135 passed / 28 deselected）、ruff check/format、docs-check、npm critical audit 均通过。
- `pnpm test --maxWorkers=2`：215 文件通过、1 文件失败；1173 passed / 1 failed。失败为后端 `trajectory.test.ts` 的 prepared reader expiry，在 20 秒阈值超时；该用例单独 `--maxWorkers=1` 复跑为 1 passed / 7 skipped（17.38 秒）。没有更改产品代码、测试或超时配置，不把首轮全套结果改写为全绿。
- 上述后端测试与 owning 代码相对 `94d663626` 完全未变；这是本次整仓检查发现的时序敏感用例，独立复跑已通过，未扩大通知修复范围。原始完整日志与单测复跑日志均保存在已有本机报告目录。
- 完整前端的既有草稿失败继续保留与披露。远端 CI 以 PR 实际结果为准，不因用户确认截图而跳过检查或授权合并。
- 收尾再次 fetch，`origin/develop` 仍为 executed_base；canonical 原样归并与 unit 路径归档属于文档变化，代码/测试/用户截图验收结论 retained。

PR 开放后，用户要求将群聊摘要调整为 `发送者名: 摘要`，并明确跳过实际测试与代码审查。本页的审查和截图记录对应首次归档版本。
