# bugfix-729: 交互 UI 不再强制附独立文字摘要

## 原始报告

> 做UI的motivation就是希望减少一些文字，或者说结合一些图像化的、结构化的表达方式，能够降低人类的理解认知负担。所以如果它必要的有一些文字，它完全可以放在UI里。不用说单独非要写一块文字。

> 那就按这个改吧，取消发 UI 必须附独立文字摘要的要求，必要的文字放在 UI 里，把相关 skill 和实现一起调整好。

> 你直接按快修模式走。

## 现象 / 复现

用户在 `https://im.nanoim.win/chat/c_f2mbtxa9` 看到长文字正文后又看到表达相同内容的 UI；11:00 的进展总览是直接观察到的实例。UI 应是完整答复：通过图像、结构与必要文字降低认知负担，无须额外写一份独立摘要。有效 UI 可在省略或清空文字正文时发送、持久化、回看并操作；无 UI 的空消息仍应拒绝。已有可选正文及历史内容保留，不把本次修复变为历史消息改写或统一隐藏正文。

## 根因

feat-617 原本提供任意 Agent 的通用交互表达，保留组件能力和既有权限。后续 bugfix-699 引入 Open Intelligent UI 目录；当前生成器、目录 preamble 和 Intelligent UI 运行时指导仍强制独立摘要。工具 schema、普通/Global 与 PA 发送校验、服务端消息入口沿用纯文字消息的必填正文条件，把原先客户端降级策略变成了每次生成 UI 的硬要求。客户端失败文案也假设一定存在“上方摘要”。

修复保留 UI 校验、真实发送回执、幂等性、PA 双身份审核、聊天权限和非交互空消息拒绝；不新增自动生成摘要或专用兼容层。无法显示 UI 时如实反馈，可选正文有则展示，无则不指向不存在的文字。外部纯文字渠道继续要求能实际投递的文字。

## 本次审查安排

采用 Bugfix lite，单个 M1-fix。使用 change-spec-author 记录已确认需求、change-orchestrator-simple 实施交付；Agent Context 和前端体验自检按实际影响执行，独立 change-code-review 一并核对最终契约。验证发送公开入口、持久回看及 UI 实际显示/操作；记录模型可见输入与真实模型行为的证据边界，不把静态文字检查当作模型验收。

## 修复

已完成 `bfc49d640`，独立审查修复 `2c39df4e3`：

- 生成器、OpenUI catalogue preamble、随包 Skill、运行时主/子 Agent 指导统一为 UI 是完整答复，必要文字放入 UI，不强制外部摘要。
- 公开工具允许省略 text，宿主规范化为空串；普通/Global、PA 自身与代表用户、WS 及 HTTP 路径接受有效 UI 独立发布。审核、幂等、回执和权限仍走原链路。
- 接收 Agent 的 SingleThread/Inbox 保留公开 UI 的真实内容，标为消息数据；UI 无正文时没有多余上边距。保留既有正文，Web/iOS 无法显示 UI 时不再指向“上方摘要”。
- 独立审查发现 HTTP 假值 UI 可绕过空消息限制，已修复并增加 undefined/null/false/空字符串/0 回归。无迁移，不自动改写历史，也未部署。

## 验证

- 修前 `/tmp/nano-729-red.log`：7 failed / 41 passed，覆盖 schema、普通与 PA、服务端拒绝无摘要 UI；修后 `/tmp/nano-729-green.log`：59/59 passed。
- HTTP `/tmp/nano-729-http-tests.log`：15/15；审查修复的 `/tmp/nano-729-null-red.log` 复现失败，`/tmp/nano-729-null-green.log`：15/15。
- Web 窄回归 `/tmp/nano-729-web-narrow.log`：115/115；全量 `/tmp/nano-729-frontend-tests.log`：1078/1078。
- Python `/tmp/nano-729-python-tests.log`：135 passed / 28 deselected；ruff、docs-check、构建、typecheck 与 native runtime 生成检查通过。后端全量 `/tmp/nano-729-backend-tests.log` 1183 passed / 1 failed；唯一失败是审查新增的假值 UI 红测在修复前被全量进程加载（测试与实现跨版本），修复后该15项文件独立重跑全通过。其余216文件/1183项没有受两行准入修复影响，保留结果，不冒称一次完整全绿。iOS generic Simulator 双架构编译成功（`/tmp/nano-729-ios-build.log`）；最终 HTTP/WS 关联22项通过（`/tmp/nano-729-final-http.log`）。
- Context 受控 wire：`/tmp/nano-729-context-wire.log` 1/1；真实 DSH 经 Anthropic adapter 向本地合成 provider 发出请求，首次 system 不再强制摘要，skill 工具后下一请求含更新后的完整 Skill，随后 send_message 无 text 仍规范化并确认成功。请求仅为合成测试，保存在 worktree `output/729-context-wire.json`，未提交。不是实际远端模型的 raw wire。
- 真实模型：daily 模板的 P（gpt-6.1-sol / high），主 session `614f7a9d-e6b2-4ffa-a13b-4bc1b0b7a2ea`，来源消息 `fee1c517722b42a6a8f124fd96c29622`，交付卡片 `b5728179bd5045c496448ecc62a0c8fc`；消息正文长度为 0，UI 内有必要说明、费用表和趋势图。此前单独发出 52 字长任务确认，不是卡片的外部摘要；没有改变既有长任务确认规则。实际远端 provider raw 日志不可用，不以 preview 补证。
- Web 作者自检：本轮隔离入口 `http://127.0.0.1:53674/chat/c_m4rb4os8`，真实卡片完整显示且刷新后仍可读。对滑块的 CUA 自动化未取得费用联动的决定性状态变化，不声称真实滑块联动通过；现有编辑/提交路径回归通过，渲染器业务逻辑本轮未改。原生设备 UI 未实测。
- 独立代码/契约审查及 closure 见 [review.md](review.md)。
