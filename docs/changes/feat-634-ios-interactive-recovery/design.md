# feat-634: iOS 交互回复与可靠发送恢复 — 技术方案

> 对齐: spec.md；基线 a782cdd3f。用户已授权实现和设备更新。

## Changelog

## 现状分析

### 涉及范围
`src/IM/ios/NanoIM/Features/Chat` 当前只读取文字及专用审批；ChatStore.pending 内存保存原始文字，ChatAPI 每次重新转换提及。新增代码限制在原生聊天、会话清理、构建版本和 iOS 测试；复用公开 OpenUI 依赖并提供可再生的打包脚本。不改 DSH、PA、Channels 或服务端授权。

### 既有约束
原生业务页面不嵌入网页；凭据只由 Session 管理；退出及撤销必须阻止迟到结果。服务端普通发送要求同 key 的不可变正文/附件/背景完全相同。交互发送使用现有 `interaction:${userID}:${key}` 存储键及服务端语义校验。原生测试已有会话代际与 mock HTTP seam，需扩展而不复制这些保护。

### 可复用能力
- 使用固定 `@openuidev/lang-core@1.0.1` 的公开 createParser/evaluateRoot/evaluate/createStore/resolveStateField/builtInValidators API；JavaScriptCore 只执行随包带入的解释器，不 eval Agent source 为 JavaScript。语法、表达式、Each、条件与动作使用上游实现。
- 从 product-contracts 的 nano-1 catalogue 生成解释器资源；SwiftUI 负责原生布局、字段、表格、图表、tabs、accordion、modal 等注册组件。资源含许可证及来源，不复制 React 页面。
- 使用现有 interaction-state GET/PUT（expected_draft_revision）、messages POST（interaction_reply/interaction_contexts）、message-attempts GET；不新增业务接口。
- Session 的请求代际、同源限制、错误 code 和 Keychain 登录继续复用。发送记录使用 Application Support 的按 origin/user 隔离、原子写入并启用 iOS 文件保护的文件。

### 相关历史
feat-617 保持服务器权威的公开源、私人 CAS 草稿与明确动作；本次扩展其原生消费者。feat-630 已实现普通发送结果查询，客户端必须冻结请求。feat-578/bugfix-618 的原生导航、只读权限和专用审批不变。

## 架构总览与关键决策

**解释器复用，呈现原生。** 一个随包 JSCore bridge 把公开源和本人的状态交给现有解析/求值器，返回无凭据的 JSON 元素树、绑定与待执行动作。SwiftUI 根据节点类型呈现；现有 Markdown/受保护媒体/主题复用。所有注册显示组件都有对应呈现，数据子组件由父级消费；不能操作的未知版本保留摘要并提示重试，不静默丢半张卡片。字段输入保持字符串、Slider 数组与选择对象的上游类型。输入验证走既有 rules/validators；输入组合不作为提交动作。

**字段编辑与业务发送分开。** 私人草稿 GET 后合并声明默认值；本地编辑立即重新求值，500ms 合并保存，离开前完成已排队保存。CAS 冲突停止覆盖并提供“读取最新”；本地探索不发模型请求。显式 Button/ContinueButton/ToAssistant/Mutation 使用操作时完整状态，先完成已有保存，再发不可变快照。成功后允许再次操作。历史只读卡片可阅读/本地展开，但不能保存或发业务请求。

**工具接线沿用既有白名单。** Query 只接 conversation_messages 的当前会话授权读取；Mutation 只接 continue_conversation 并进入同一可靠发送路径。其他工具返回错误；OpenUrl 只允许 http/https 并由系统处理。Query 参数变化重新查询，默认值先用于呈现；不将历史恢复当作 Mutation 触发。Set/Reset 与 ToAssistant 的先后顺序由 bridge 明确执行，快照在 Set 后捕获。

**第一次网络请求之前冻结并持久写入。** 每个 attempt 保存原 key、会话、完整序列化请求、普通输入快照（正文/附件）和可选卡片源。提及仅在创建 attempt 时转换一次。写盘失败则不 POST。已有 pending 不能被新发送覆盖。恢复只查询既有结果，不自动发送未确认的新草稿；用户重试先查询，404 后用原 bytes/key 再 POST。网络/5xx/408/429 保留，终局错误可恢复编辑；409 先核对已保存结果，不盲目换 key。交互 lookup 使用服务端既有带用户前缀的键。附件与最多三张相关私人卡片背景一起冻结。

**持久与会话清理有明确边界。** 按 origin/user 隔离，Session logout/切服务/资格失效时删除该用户记录；权限快照确认无权的会话同步删除。后台/SwiftUI view 消失只停 UI 和请求，不删除可恢复记录。ChatStore 的 epoch 与 Session generation 共同防止迟到结果重建清理过的数据。对已经确认的旧发送，只在当前草稿仍等于原快照时清空；新草稿保留。普通 pending 与卡片 pending 分开归属，恢复后的卡片未知状态提供同一次重试。

## 接口与数据流

- `ChatMessage.interactive` 解码版本、source、read_only、superseded_by；interaction_reply 保留已提交历史。`InteractiveCardView` 位于文字摘要之后、专用审批之前。
- `InteractiveRuntime` 是 @MainActor 可观察模型，持有 root JSON/state/busy/readOnly/error、Session 身份 revision 和当前 ChatStore；`fieldValue/edit/activate` 是 SwiftUI 与 bridge 的窄接口。
- JS bridge 维护上游解析结果/store，返回带稳定节点 id 的元素树，绑定元数据保留用于 resolveStateField；执行本地动作后把业务事件交给原生宿主。上下文内没有令牌、文件系统或任意网络接口。
- ChatStore 负责整合已确认消息、普通发送及交互发送；独立磁盘 owner 在网络前原子保存/移除 attempt。UI 只能经同一发送入口发送。
- 私聊普通发送收集当前聊天中未被替代且可写的卡片选择，按最近交互顺序最多三张；群聊不附带。使用与 Web 相同的过滤，不修改原文字。
- 请求、草稿和查询返回都核对会话代际；不持久保存 token 或运行时对象。

## 前端原型

[prototype.html](prototype.html) 展示现有聊天气泡背景、新增本地探索与继续按钮、未知发送和只读历史。浏览器安全策略拒绝 file URL，不能绕过；采用同一内容的临时 SwiftUI 原生原型在隔离模拟器中渲染走查，HTML 只是可读设计附件，不宣称已经渲染。

现有 UX grounding：通过当前 iPhone 镜像确认白底、青绿强调色、原生输入控件；聊天基线由现有 ChatMessageView/ConversationView 与 feat-617 已验收画面交叉核实。手机当前未登录，不把登录页当作聊天走查。保持原气泡、头像、时间、底部输入和专用审批位置；卡片内容先结论、紧邻控件和变化结果，再解释及明确继续动作。

| 区域/状态 | 对齐级别 | 真实入口及体验结果 | 验证 |
|---|---|---|---|
| 回复内探索 | must-match | 原生聊天：主结论、控制、结果相邻；窄屏折行，非所有内容同权卡片 | M1 R1/W1 |
| 明确继续 | must-match | 可辨认动作，点击后保持内容，发送状态不冒充业务完成 | M1 R2/W1 |
| 未知发送 | must-match | 底部简短核对/重试；不铺内部阶段；新草稿保持 | M1 R3/W2 |
| 历史/冲突 | must-match | 内容可读，有权动作受限，读取最新入口 | M1 R2/W1 |
| 图表和系统控件 | may-adapt | Swift Charts/原生字段及 sheet，保留标签、单位、数据与操作语义；横向比较在窄屏转竖排 | M1 R1/W1 |
| 登录与专用审批 | out-of-scope | 保持现有页面与行为，回归验证 | M1 W2 |

原型走查：独立 Nano feat634 模拟器已渲染正常、CAS 冲突、未知发送及 accessibility1 大字体。实际点击继续出现请求回执，读取最新后分钟从20改为30、结果140改为210；未知发送核对后新草稿“稍后请提醒我”保留。截图位于 /tmp/nano-feat634-prototype-{normal,conflict,recovery,large}.png；独立审查者另行查看。原型大字体自动 scroll/drag 没有产生画面移动，滚动可达性未获实证，保留到 M1 真实客户端；不能以源码 ScrollView 代替该项验收。HTML未渲染。

## 契约层增量

- `specs/im/ios-client.md` → `docs/specs/im/ios-client.md`：新增通用交互与持久发送恢复，不覆盖既有 Scenario。

## 风险与回退

资源生成必须固定版本并可 check；上游协议演进不自动改变已打包解释器。新版本无法解析时摘要仍可读并明确错误。持久失败不误报发出，恢复失败保留原 attempt；不通过放宽服务端校验修复 409。可以回退 IPA；不删除账号和已有服务端消息，仍可用 Web。

## Runbook for Reviewer

无新增常驻服务。复用隔离真 IM：`pnpm build` 后按 `scripts/e2e-up.sh --wt <本工作区>` 启动，`scripts/e2e-down.sh --wt <本工作区>` 停止，健康检查 `<IM_URL>/health`。若现有受控模型不足，可使用测试 fixture Agent 发布卡片并明确外部 provider 边界；产品 reviewer 必须用真实原生客户端操作卡片及发送，不用 REST 替代 GUI。

构建：`NANO_IOS_BUILD_ROOT=/tmp/nano-feat634-build src/IM/ios/scripts/build.sh build`；测试用独立 iOS 26.4 simulator；archive 同一 tree。模拟器 Debug 配置 `NANO_IM_BASE_URL` 连接隔离 IM，测试账号来自隔离栈，不用生产凭据。通过 xcrun simctl 安装/启动调试目标，GUI 经 CUA Simulator 驱动。用户物理手机和 iPhone 镜像可用，AltStore 已安装并无线刷新通过；当前停在登录页，安装后如需登录由用户在官方 UI 输入。IPA 以原 bundle ID 更新 AltStore 现有应用，不能误覆盖旧的独立直装版本。检验 My Apps、新版本标识和实际打开，续签不冒充代码更新。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-native-chat | 原生交互与可靠发送完整闭环 | 无 | 单交付 | iOS 聊天、解释器资源/生成脚本、会话清理、测试、版本及文档 | [reviewer] R1 真客户端探索、条件/图表/查询与 390 宽可读；R2 私人草稿、冲突、显式动作、只读历史和权限；R3 未知发送恢复、重试无重复、新草稿保持、安装后可打开。[worker] W1 固定解析器、全目录原生呈现、类型/动作及状态契约测试、原型与实际画面对照；W2 重启持久恢复、提及改名不可变重试、附件与身份撤销测试；W3 iOS 模拟器测试、Release archive、独立审查、一致性、真客户端验收及 IPA 来源记录。 |
