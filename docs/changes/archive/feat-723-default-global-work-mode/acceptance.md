# feat-723 — 产品验收报告

> Round 1 · full · 2026-11-07 · 独立产品 reviewer
>
> Validation snapshot: `29e3f2947699fb92b382c5f61b4a1ef169a40ede → 6cf5cd5084f68baafaf7f211e666ccafdc48fc19`
>
> 用户本轮明确委托 Agent 实测；不是用户亲测记录。

## Verdict

**pass**。5 个必验 Scenario 均通过。blocking/major/minor 均 0；highest_required_action=pass；无需产品复验。后续版本若只归并文档，或同步 caller 指明的聊天搜索侧栏 CSS，须由 caller 记录证据保留依据，不能把后续树写成本文实测版本。

## 版本、环境与证据边界

- 验收前核对 HEAD 为上述 validated_at，branch=`unit/feat-723`。当时 dirty 为同 unit 收尾文档；未修改源码、测试或受控配置。
- 使用 caller 集中启动的真实 IM + Node + DSH，入口 `http://127.0.0.1:54056`，隔离测试账号 `nano`，node=`wt-feat-723-default-global-work-mode-73061`。前端为 caller 按源码内容指纹刚构建的同源 UI；未 mock 后端。
- 已读 `.e2e-daily.json`：P/E/Q 为 `codexOAuth:gpt-6.1-sol` / high / codex；PA 为 `codexOAuth:gpt-6-astra` / medium / codex；审核为 `codexOAuth:gpt-6-luna` / codex。真实 UI 确认 P/E/Q、PA 在线，聊天列表存在“研发日常”和个人助手入口；该阵容 ready 不冒充功能通过。
- 临时增量由 caller 准备：`pr471-legacy-no-mode` 缺少 `work_mode`。验收读取隔离 YAML 确认该键缺失、5 个 Features 均 false、tool_allowlist 为空；这是兼容 fixture，不是生产迁移。创建操作后节点重写的 YAML 已物化 skills 列表，本文不把“skills 为空”当作最终观察事实。
- 本轮真实产品写入：创建 `pr471-ui-global`、`pr471-ui-single`、`pr471-api-default`，打开单 Thread 私聊 `c_jzs57j6w` 并发送一次无工具的简单回复请求。无生产或外部群消息。
- 截图及脱敏 API 输出统一保存在 `/Users/czj/.codex/reports/pr471-close-20261107/acceptance/`（下文文件名均相对该目录），未提交截图、DB、token。测试后已关闭本 reviewer 创建的 Playwright 会话 `pr471accept`；caller 的服务保持运行供收尾使用。

## 用户旅程体验

桌面 1440×1000 的创建页沿用现有分组布局：Identity 后紧接 Work mode，Global mode 在左且已选中，Single thread 在右。两项说明分别明确跨聊天持续上下文与各聊天独立上下文；同组下方直接写明创建后不可切换。用户可不触碰模式完成默认创建，也能在提交前比较并选择另一种模式。创建后转入 Agent Config，Identity 下明确显示模式和 Fixed after creation，没有模式单选框。

390×844 窄屏把模式选项排成上下两行，Global 仍在前；两项说明和不可切换提示完整可读，单 Thread 可点选。底部 Cancel / Create agent 按钮可见，无需记住屏外模式说明才能判断。这一局部增量不引入新视觉语言或额外操作负担，受影响创建流程整体可交付。

证据：`desktop-default.png`、`narrow-default.png`、`narrow-single.png`、`global-created.png`、`single-created.png`。`legacy-single.png` 捕获的是配置能力刷新期间的画面，但模式已明确为 Single thread；最终模式和固定工具另由成功的 settings API 读取确认。单 Thread 私聊收到“单线程连接正常。”，见 `single-chat.png`，不是仅验证发送按钮。

## Reference Artifacts Reviewed

本 unit 无独立 prototype/reference screenshot 或单独 must-match 表；按 spec 与 as-built design 的创建/详情体验约定直接对照真实产品，不补造事前原型。

| Reference | Required contract | Actual evidence | Viewport / state | Conclusion |
|---|---|---|---|---|
| spec：创建页缺省全局；design：全局排首位 | 首位默认选中，说明可读；不触碰模式可创建 | desktop-default.png、global-created.png | 1440×1000，创建及创建后 | match |
| spec：可显式改回单 Thread | 对比两种用途并可切换后创建 | narrow-default.png、narrow-single.png、single-created.png | 390×844 创建选择；1440×1000 详情 | match |
| spec：既有模式及不可切换 | 详情可辨认模式，无切换控件 | legacy-single.png、single-created.png、api-results.json | 1440×1000，详情与 HTTP 边界 | match |

## 问题清单

无产品问题。工具使用中的 `run-code` 参数初次错误、CLI 不支持 `network` 命令、系统 Python 缺少 PyYAML 均为验收仪器问题，已分别改用正确调用、`requests`、局部 YAML 文本读取。初次 API 试探缺少必填字段收到 422，补齐正常创建/更新字段后才验证模式边界；422 不用作模式不可变的通过证据。登录前的 refresh 401 是未登录状态，登录后真实操作成功。

## 验收标准覆盖

### Requirement: 新建 Agent 不指定模式时按全局模式创建 — pass

| Scenario | 期望来源 | 验证方式与实际观察 | 证据 | 结果 |
|---|---|---|---|---|
| 创建页缺省选中全局模式 | spec 同名 Scenario | Agents → Create agent；首个 radio 为 `Global mode One ongoing context coordinates work across chats.` 且 checked；未触碰模式，填写 Agent ID/Display Name/指令后 Create agent。`pr471-ui-global` 创建成功，详情和 GET settings 均为 global，固定工具含 inbox/conversations/send_message/subagent | desktop-default.png、global-created.png、api-results.json | pass |
| 显式改回单 Thread 仍然生效 | spec 同名 Scenario | 390px 宽下 check radio `Single thread A separate context for each chat.`，创建 `pr471-ui-single`；详情为 Single thread；Tool Allowlist 不显示 inbox，live_capabilities.fixed_tools 仅 notes/history/new_context/get_context_remaining。Open chat 后发送“请仅回复：单线程连接正常。不调用工具。”，真实回复成功 | narrow-single.png、single-created.png、single-chat.png；chat/c_jzs57j6w；api-results.json | pass |
| 不经创建页创建的 Agent 同样缺省全局 | spec 同名 Scenario；design 验证平台选择 | 正常 login 取得认证后 POST `/im/v1/nodes/wt-feat-723-default-global-work-mode-73061/agents`，请求完全省略 work_mode；201 返回 `pr471-api-default`、work_mode=global，随后 GET settings 200 仍为 global。PA/iOS 共享语义复用下述有效测试与构建证据 | api-results.json；下节精确测试/CI locator | pass |

### Requirement: 既有 Agent 的模式与行为不因缺省值变化而改变 — pass

| Scenario | 期望来源 | 验证方式与实际观察 | 证据 | 结果 |
|---|---|---|---|---|
| 既有单 Thread 助手保持原样 | spec 同名 Scenario | caller 的旧 YAML 缺模式 fixture 经真实 Node 加载注册。点击 `Legacy No Mode` → Config，显示 `Work mode：Single thread · Fixed after creation`；GET settings 为 single_thread，固定工具不含 global 专有固定集合。按 Scenario 的“查看或聊天”选择查看路径 | legacy-single.png、api-results.json；隔离 YAML agent 条目 | pass |
| 模式仍不可切换 | spec 同名 Scenario | 创建后 Config 的 mode 只有文本，无 radio；对 global、显式 single_thread、legacy single_thread 各以完整正常配置 PATCH `/im/v1/agents/:id/config` 为相反模式，均 409 `work_mode is immutable`。每次随后重新 GET settings，模式分别仍 global/single_thread/single_thread | global-created.png、single-created.png、legacy-single.png、api-results.json | pass |

## 复用证据与未声称的范围

- PA/创建边界定向测试：`/Users/czj/.codex/reports/pr471-review-20261107/review.md` 的独立验证记录，执行 `pnpm exec vitest run apps/im-server/tests/configuration-edits.test.ts apps/im-server/tests/personal-agent-creation.test.ts apps/im-server/tests/configuration-boundaries.test.ts apps/im-server/tests/control.test.ts packages/product-contracts/tests/capabilities.test.ts apps/node/tests/configuration.test.ts`，6 files / 63 tests passed；执行 SHA `3099a9de01127a327709777e7e6563c7dc227f38`。caller 确认其后到本轮 SHA 的 merge main 未改 PA 创建及本次 iOS 内容，故复用这些仍有效的结论。
- iOS 简单默认字段/既有控件文案变更按平台规范复用 [iOS build and tests](https://github.com/Mrchen116/nano-multiagent/actions/runs/42142103352/job/127644739634)，head=`3099a9de01127a327709777e7e6563c7dc227f38`，caller 核实 Native regression tests 与 Release device archive success。另已读本轮 `/Users/czj/.codex/reports/pr471-close-20261107/ios-runtime.log`，caller 报 `pnpm check:ios-runtime` exit 0。
- 本轮未进行 iPhone 实机/模拟器体验验收、未让真实 PA 模型自行决定如何创建 Agent；不得据此声称这些额外路径已实玩。单 Thread 的一轮真实回复只证明该聊天可完成，不宣称穷尽跨聊天隔离或重测所有既有运行模式功能。本次不改变各模式本身的行为。
- 新提交的完整 CI 属 caller 后续交付门禁，本文不将当时尚未完成的 CI 记作成功。

## 上层文档同步

- [x] `SPEC.md`：无需更新，跨包架构未变化。
- [x] `docs/specs/im/agents-nodes.md`：需要由 caller 按最终 delta-spec 归并新建缺省全局，保留旧记录和不可切换约定；验收时 current 仍只写选择全局。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

本 reviewer 只写本报告；文档归并、归档、提交与远端 CI 由 caller 收尾。
