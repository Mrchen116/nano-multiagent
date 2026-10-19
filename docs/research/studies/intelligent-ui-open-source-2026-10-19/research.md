---
status: research-snapshot
recorded-at: 2026-10-19
nano-baseline: e7088f9d5e84d98663e42803b94ab788ed517702
source-baseline: OpenUI 8d9c4c3b108a7b5352192a6a9d7327bdf7ea19b5; json-render 72568f990e5502c4d3115691facb8ca928a5c9fc; dsh-intelligent-ui c4920ad2327ee5dfdfb42744e4696286868d934e
current-owner: docs/specs/im/conversations-messages.md
---

# 从 Intelligent UI 到 Nano 的通用交互回复

状态：research snapshot / review pending。日期：2026-10-19。Nano 基线 `e7088f9d5e84d98663e42803b94ab788ed517702`；主 checkout 有既存 dirty 内容。本研究只读产品实现，没有运行候选库的浏览器或真实模型试验，也没有采用为 current 契约。

## 建议与判断依据

建议优先验证 **Thesys OpenUI 的独立语言与 React 渲染器**，保留 **Vercel json-render** 作为备选。复用解析、组件组合、状态绑定和交互回调，把会话、身份、消息保存和任务执行继续留在 Nano。用户认可开源，并不意味着必须接入一整套新聊天框架。

这一判断来自目前的接口适配度：Nano Web IM 已使用 React 19；OpenUI 明确支持自建聊天界面，仅接入 `Renderer`，保留原消息列表、输入框和传输。源码公开 `response`、`isStreaming`、`onAction`、`onStateUpdate`、`initialState`，并导出 `mergeStatements`。它覆盖当前最关键的三件事：逐步展示、控件本地变化、选择回到 Agent。[自建聊天接入](https://www.openui.com/docs/build-agents/custom-chat-ui)、[Renderer 源码](https://github.com/thesysdev/openui/blob/8d9c4c3b108a7b5352192a6a9d7327bdf7ea19b5/packages/react-lang/src/Renderer.tsx)。

## 对用户提供讨论的核验

已读取用户提供的 ChatGPT 对话《分析Intelligent UI逆向》。它提出的 OpenUI、点击回传和 DIL 逆向是有效线索；其中“可以用于生产”的判断仍须用具体版本与 Nano 实测补足。

OpenAI [发布说明](https://openai.com/index/gpt-6-for-everyone/) 只确认原生可流式组件、编译器与模型设计判断训练。Thesys 的 [逆向报告](https://www.openui.com/blog/how-chatgpt-intelligent-ui-works) 进一步报告 DIL、服务端编译、隔离运行时、组件更新和 `issueNewTurn`，依据来自其捕获的客户端与网络样本。后者属于第三方直接观察，不是 OpenAI 的稳定公开接口，也没有证明 OpenUI 就是 ChatGPT 内部实现。

最值得迁移的是交互分工：调整滑块或筛选通常只更新界面本地状态；用户选择继续时，界面把当前选择组成新用户输入送给模型。OpenUI 对应的公开接口是 `@ToAssistant` → `onAction`，带 `humanFriendlyMessage`、`formState` 及可选 `params.context`。Nano 必须保留这份选择上下文，不能只发送按钮文字。相关机制见 [OpenUI 交互文档](https://www.openui.com/docs/openui-lang/interactivity)。

复杂自由 HTML/JS 是另一条能力路线。逆向报告描述了 AppBlock，但当前需求不要求首版同时复制 DIL 编译器、沙箱程序和自由页面。先验证通用组件能覆盖多少真实任务，再根据具体缺口决定是否增加隔离嵌入式界面。

## 活跃度与成熟度快照

以下 star、最后 push、许可证来自 2026-10-19 的 GitHub REST 仓库元数据；版本与发布时间来自 releases / npm registry。star 是采用热度的线索，不证明动作正确、持久化可靠或接口稳定。

| 项目 | Star | 维护与版本证据 | 对 Nano 的判断 |
|---|---:|---|---|
| [thesysdev/openui](https://github.com/thesysdev/openui) | 11,948 | MIT；最后 push 10-17；react-lang/lang-core 1.0.1，10-15 发布；1.0.0 于 10-12 发布；react-ui 0.18.1 | 首选验证，独立 Renderer 与现有 React 聊天接近；新版语言刚发布一周，不能称长期稳定 |
| [vercel-labs/json-render](https://github.com/vercel-labs/json-render) | 18,717 | Apache-2.0；最后 push 10-13；v0.21.1 于 10-13 发布 | 强备选；JSON 组件目录、状态绑定和流式 patch 清楚，仍在 0.x 演进 |
| [A2UI](https://github.com/a2ui-project/a2ui) | 16,737 | Apache-2.0；最后 push 10-19；多语言包持续发布 | 有跨端协议价值；仅做当前 Web IM 时未必比直接接渲染器更省工作，Swift 包尚未发布 |
| [thesysdev/open-intelligent-ui](https://github.com/thesysdev/open-intelligent-ui) | 548 | MIT；10-08 创建；最后 push 10-17；无 release | 体验示例；不能拿 OpenUI 主库的 star 和历史证明这个示例成熟 |
| [CopilotKit/OpenIntelligentUI](https://github.com/CopilotKit/OpenIntelligentUI) | 3,448 | MIT；最后 push 10-13；本轮 releases 查询被限流，未确认版本 | 可参考完整体验；采用前需说明引入其运行/传输层对现有系统的必要性 |
| [yunyv/dsh-intelligent-ui](https://github.com/yunyv/dsh-intelligent-ui) | 4 | MIT；10-09 创建；最后 push 10-17；release v0.1.0 | 适合作为 DSH 插件接缝和 artifact 历史参考，不宜仅因名字含 DSH 就直接当作 Nano Web IM 方案 |

OpenUI 的组件库、语言核心与示例各自版本不同。“语言 1.0”不能等同于整个产品栈已稳定。下一步应固定实际 npm 版本做验证，避免把 main 文档的新增能力误当作已安装包能力。

## OpenUI 与 json-render 的实质差别

两者都能让模型从组件目录组合新界面；使用通用组件并不等于把每个业务预制成固定卡片。

OpenUI 使用紧凑 DSL，内置组件覆盖表单、表格、图表和布局，支持响应式变量以及按语句名合并局部修改；应用可以复用其组件，再适配自己的主题。`onStateUpdate` / `initialState` 提供保存与恢复接点，数据库持久化仍由应用完成。`mergeStatements` 提供合并机制，哪个历史回复被修改、如何保存版本也仍由应用负责。[交互文档](https://www.openui.com/docs/openui-lang/interactivity)、[增量修改](https://www.openui.com/docs/openui-lang/incremental-editing)。

json-render 通过目录约束 JSON 组件树，提供状态绑定、条件显示、计算值和 JSONL 流式 patch。它更容易与熟悉 JSON schema 的链路对接；代价是否体现为更多输出、更多主题适配，必须用同一组任务测量，不能直接采信竞争项目的 token benchmark。[官方概览](https://json-render.dev/docs)。

OpenUI 的本地 DSL 生成成功率和真实交互质量，是当前最大未知。其开源渲染层不要求购买 Thesys 的托管模型服务，但 Nano 使用的 DeepSeek 等模型是否能稳定生成目标 DSL，不能从演示模型的效果外推。官方提示词可从所选组件目录生成，先采用足够覆盖任务的小目录即可，不必加载全部能力。

## Nano 应补的部分

下面是研究建议，尚未成为 design 或实施承诺。

1. **Agent 输出通用交互内容。** 任意 Agent 可以根据任务选择文字、表格、图表、输入项和按钮组合。隐私提醒、行程选择和草稿确认都是调用场景，不各自拥有一套特殊渲染协议。
2. **复用现有公开交付链。** Global Agent 的 prose 是私有草稿，公开回复必须经过 `send_message`。交互产物也必须明确交付到目标会话，不能把内部轨迹中的工具输出直接显示成公共消息。现有 `packages/dsh-integration/src/global-mode.ts` 与 `packages/personal-assistant/src/global-agent.ts` 是该边界的依据。
3. **点击回到同一任务。** “继续”携带原消息/交互版本、实际点击者、选择值和可读摘要，作为既有会话中的用户输入；普通打字也能引用已有选择。单纯拖动滑块或展开详情无需调用 LLM。
4. **消息服务保存已交付内容和确认结果。** 前端卸载、刷新、节点离线后仍能回看。群聊中的个人临时选择与已公开确认结果必须区分；展示状态不能冒充业务执行成功。
5. **业务动作接既有能力。** OpenUI 的 `Query` / `Mutation` 可以经浏览器 `toolProvider` 调用 API，这证明框架可扩展，不代表应直接暴露全部 DSH 工具。首版可把语义操作送回 Agent；确有确定性业务操作时，绑定明确的服务端能力与既有身份权限。[官方执行架构](https://www.openui.com/docs/openui-lang/architecture)。

包边界继续遵循 Nano `SPEC.md`：执行端仅通过 dsh-integration 接入公开 DSH 能力，IM/Channels 消费 product-contracts。OpenUI 解决渲染语言与控件机制，不替代这些产品职责。

当前已确认的是 OpenUI 支持流式解析，不是 Nano 已有“公开交互回复流”。特别是 Global Agent 的私有草稿与公开消息分离，必须先确定公开交付时机，再接公开 UI 更新流。第一轮验证可先完整交付一个可操作回复，再单独验证流式更新，避免用私有推理流冒充回复流。源码还注明 `isStreaming` 期间禁用表单交互，应实测其体验，不承诺生成未结束时就可以提交。

## 验证后再定选型

采用同一模型配置、同一任务与同一组件范围，先验证 OpenUI；只有具体失败或成本不合适时才扩大对比 json-render，不为选型搭两套完整系统。

- **行程调整：** Agent 给出路线与时间/偏好选项；本地调整立即响应；点击继续后 Agent 正确读到选择。
- **草稿修改：** 用户在表单改动正文；确认后 Agent 得到修改后的文本，对外发送仍有明确对象与实际回执。
- **通用提醒：** 用同一套组件表达普通事项与隐私提醒，验证不需要专用标题组件。
- **历史与移动端：** 刷新、重新进入、窄屏和断线恢复后内容可读、状态准确；生成损坏时仍有可读文字与继续输入入口。

记录生成成功/失败、首个可读内容时间、输出量、点击上下文是否准确、刷新后状态、实际动作结果及手机体验。结论应是“固定版本和模型在这些样本下通过”，不能写成“高 star 所以稳定”。

## 可复查基线与限制

- OpenUI HEAD：`8d9c4c3b108a7b5352192a6a9d7327bdf7ea19b5`；本轮读了 README、react-lang package.json、Renderer.tsx 和公开 exports；npm react-lang/lang-core 1.0.1、react-ui 0.18.1。
- json-render HEAD：`72568f990e5502c4d3115691facb8ca928a5c9fc`；本轮读了仓库页面、版本和官方架构文档，没有运行源码测试。
- dsh-intelligent-ui HEAD：`c4920ad2327ee5dfdfb42744e4696286868d934e`；README 描述插件工具、客户端展示 hook、磁盘 artifact 版本与 vendored DIL replica；其自述测试数量不等于本轮已验证。
- A2UI、CopilotKit 与 OpenUI 示例未固定 commit；只用于 2026-10-19 元数据/文档层筛选。
- 未执行完整安全审计、跨版本兼容测试、真实模型生成测试或 Nano 端到端测试。以上足以形成候选排序，不足以宣布生产可用。
