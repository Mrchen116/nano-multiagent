# feat-658 设计依据与走查

2026-10-25；设计基线 main `e5856ec23`（feat-658 spec 为 `0602dfcee`）。只核对设计和可用资源，没有实现本功能。其他 unit 的后续 main 提交不作为本项完成证据。

## 当前界面与代码

用户提供的当前 Web 截图（[原始附件](/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-6fcf300c-04bc-484c-b635-b8bb8e96a21d.png)）明确显示 Personal Agent 头像/姓名占主位，用户只在辅助标签里出现，正文又有“受 J 委托”大段前缀。设计保留相邻名字/来源行，改变主次；正文直接传达委托。基线图片不复制进仓库，以遵守不提交截图缓存的项目规则。

对应实际代码：Web `features/chat/components/message-pane.tsx` 中本人消息不显示头像/名字，其他发送者有头像/姓名/节点名/旧 delegation.label；iOS `ChatMessageView.swift` 中双方都有头像，群聊仅对方显示名字，消息模型目前没有 delegation。本轮未取得现版 iOS 实机截图，原生设计以真实 SwiftUI 组件及布局约束为基线，原型不是原生实现验证。实施 M1 必须在真实 iOS 客户端观察新身份行。

## 原型实际渲染

通过 in-app browser 打开本地 `prototype.html`，实际切换 Web 桌面、390/320 内容宽、iOS 构图，观察本人/其他成员、长名与附件、PA 自身发言、草稿采用。截图为本机可复查证据，按项目规则不提交截图缓存：

- [桌面收件人视角](/Users/czj/.codex/reports/feat-658-design-resource-check/prototype-web-other.png)：用户主名在正文之前，PA 为轻量标记，头像与 Q 的独立 Agent 身份有清楚区别；正文直接说明动作及禁止项。
- [320 宽本人长名](/Users/czj/.codex/reports/feat-658-design-resource-check/prototype-web-320-owner.png)：气泡/用户头像在右，长名与标记仍在气泡外；内容自然换行且附件没有挤压来源。宽度指聊天容器，外围是演示控件，不声称已测试真实设备 viewport。
- [iOS 本人构图](/Users/czj/.codex/reports/feat-658-design-resource-check/prototype-ios-owner.png)：保留原生右侧头像与浅色本人气泡，身份行位于上方；原生字体缩放和 VoiceOver 待真实实现检查。
- [PA 自身发言](/Users/czj/.codex/reports/feat-658-design-resource-check/prototype-pa-self.png)：仍是 Personal Agent/PA，不能与代表用户消息混淆。

走查发现原型 CSS 的 display 覆盖 hidden 属性，使 PA 自身发言旁误出现范围确认回执；已改为明确 hidden 优先。草稿采用后的展示同时移除草稿卡，展示原目标聊天与预填输入框，不追加发送消息。对受影响状态复查，不把固定示例回执作为真实后端执行证据。

## 验收资源核验

- 已执行 `scripts/e2e-up.sh --profile daily --wt /Users/czj/.codex/reports/feat-658-design-resource-check`；产生独立 IM 63283、node `wt-feat-658-design-resource-check-18953`、P/E/Q 与真实 PA 绑定、群与主人 PA 私聊。IM `/health` 返回 ok；gateway 日志报告 DSH hosts=1、relay register ready。清单在该目录 `.e2e-daily.json`，无凭据复制进 unit。
- 通过正式 IM API 向隔离测试 PA 私聊发送模型可用性请求，收到 completed 回复“环境可用”（message id `d4465166b7174537a1e14980be743a7f`）；脱敏证据 [model-probe.json](/Users/czj/.codex/reports/feat-658-design-resource-check/model-probe.json)。这证明现有模型与工具回复链可用，不是待实现 owner 模式或独立外发审核验收；M1 仍须完成全部实际旅程。
- `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun simctl list devices available` 成功：iOS 26.4、iPhone 17/17 Pro 等模拟器可用。默认 xcrun 未选 Xcode 时找不到 simctl，runbook 使用显式 DEVELOPER_DIR，构建脚本自身已设置默认路径。
- 测试普通成员 B、专项会话、虚构仓库/bare remote 都能在本轮隔离目录经正式产品入口/本地 Git 创建，无外部账号或权限依赖。生产不作为测试环境。

设计审查阶段原型服务地址为 `http://127.0.0.1:63358/prototype.html`。收尾已执行 e2e-down 并终止原型静态服务；后续可直接打开 HTML 或重新用本地静态服务查看。

## 方案修订与新增走查（2026-10-25）

修订基线 `797b225df`。按用户确认改为共用 send_message、根 PA 专属 send_user_message、通用 ComposeMessage；去掉新调用的 reply_draft 和模型填写的协议常量。此时仍无产品代码修改。原身份展示/来源链的 R1/R2 证据保留，新增草稿旅程和 context 接线需本轮独立复审。

静态审视真实 agent-config/global-mode/personal-security、交互 Feature/catalog/generator、policy/sources/approval、实际加载的 CC 模板与 iOS runtime：旧工具/schema/Skill 存在旧字段和“每次公开回复均用 send_message”“一次点击记录消息”的冲突，已在 design 上下文表逐项纳入实施。安装的 OpenUI lang-core 公开 defineAction 与 library actions 扩展能承载新动作；iOS 当前仅处理 set/reset/run/continue/open_url，需要接入自定义动作及 Swift host，不是只改 Web 示例。此为代码路径证据，不宣称新 context 已生成或真实模型已通过。

修订原型通过本地 IAB 实际操作：

- [普通 Agent、320 内容宽编辑器](/Users/czj/.codex/reports/feat-658-design-resource-check/prototype-compose-320.png)：普通 E 名字、明确目标、可编辑文字和两种按钮均可辨认；仅为容器宽度，非原生实现。
- [采用后目标输入框](/Users/czj/.codex/reports/feat-658-design-resource-check/prototype-compose-adopted.png)：先把文字改为“Q，只提交报告，不推送。”再采用，目标聊天输入框准确保留修改值，未出现新发送气泡。
- [已有草稿冲突](/Users/czj/.codex/reports/feat-658-design-resource-check/prototype-compose-conflict.png)：取消后编辑值保留；再次采用并替换后，同一修改值进入目标输入框。原型条件在演示区模拟，不宣称真实附件存储通过。
- [iOS 构图不可写反馈](/Users/czj/.codex/reports/feat-658-design-resource-check/prototype-compose-ios-denied.png)：目标不可写时仍停留编辑器，显示原因并保留修改值。
- [iOS 构图采用结果](/Users/czj/.codex/reports/feat-658-design-resource-check/prototype-compose-ios-adopted.png)：正常采用只导航、填稿并聚焦，发送按钮仍由用户另行操作。原生交互桥接与权限检查须在 M1 真客户端验证。

原型只模拟视觉与状态，不接模型或后端；资源仍使用上节已验证的本机 daily/Xcode，新增旅程不依赖第三方账号。修订审查期间临时重新开启 63358 静态原型服务，复审完成后已停止（进程正常退出）。
