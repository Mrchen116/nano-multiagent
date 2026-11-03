# Validation

## 自动验证

- Web：catalog / interactive-card / interactive-flow 共 3 文件、22 tests passed；生成资产一致性检查通过，Agent 生成指导未变。`pnpm check:ios-runtime` 通过。
- iOS 全量：2026-11-03，`/tmp/nano-ios-701/Logs/Test/Test-NanoIM-2026.11.03_11-48-13-+0800.xcresult`，50 XCTest + 27 Swift Testing 通过。
- 后续生产修复的最窄回归：`Test-NanoIM-2026.11.03_11-57-37-+0800.xcresult`，InteractiveRuntimeTests 10 tests passed；涵盖临时 Agent 不可用恢复、旧 WK 回调 generation 隔离、工具/草稿采用、沙盒 frame、会议状态恢复和显式提交。设 `TEST_RUNNER_NANO_IOS_VISUAL_NETWORK=1` 额外等待酒店首张可见照片加载；不把懒加载离屏图片作为全量 CI 网络断言。
- 真实 SwiftUI ChatMessageView 宿主：`Test-NanoIM-2026.11.03_12-02-39-+0800.xcresult`，新增测试通过。393pt 窗口中内容宽 361pt，Web 内容高度与原生容器一致，调用方只读变化传到 disabled fieldset。
- 设备 Release archive 已成功生成 arm64 App 和未签名 IPA，交付副本由最终提交重新构建，版本以包内构建修订号为准。未签名包供 AltStore 重新签名，不等同于真机安装验收。
- `scripts/docs_check.py` 和新增 Vite iOS config 的独立 TypeScript 检查通过。独立 full review 两个 P2 由 closure 确认 closed，最终生产 findings `[]`，见 code-review.md。

## 实际画面

酒店和看板保留既有运行的源码：酒店消息 `a4f7481228b84df3a9e8185a87b28566`，看板消息 `3120be0cb9fc4ef4afc695a2d55ff55d`，落在 Tests/Fixtures。未重新调用 LLM，未为 iOS 编写图像专用组件。

模拟器 iOS 26.4，在真实 WKWebView 检查手机宽度、图表/SVG 几何和交互，并人工查看最终像素附件：

- `output/ios-iui-701/hotel.png`：照片实际加载，横向酒店卡片、标签、图标、黑色 Book 按钮、拼图及打开的预订说明可见；本地点击没有向 Agent 发送消息。
- `output/ios-iui-701/dashboard.png`：指标卡、三组散点和分段漏斗几何实际显示，无横向溢出。源本身仍保持双列，手机上的图内小字较密；本次没有改变 Agent 生成的布局。
- 会议：改选时间后确认提交，用户消息中的 `$slot` 为最新值，label / message / context 正确，恢复草稿仍是所选时间。另在真实原生聊天宿主验证了宽度、高度和只读变化。

初次未绑定 UIWindowScene 的快照全黑，不计为视觉证据；绑定实际 scene 后重新取得酒店和看板画面。UIKit drawHierarchy 不捕获 WebKit 的独立合成面，原生宿主测试改用专门的 WebKit snapshot 截取内容，保留其透明背景；不伪造完整原生聊天截图。

## 边界与恢复

尚未在用户真机安装或获得用户本次 iOS 验收，unit 保持 active，canonical delta 尚未归并。没有发布 App、部署 IM 或合并本分支。

本任务不重跑 Intelligent UI 生成评测，也不声称修复上游对错误中文字段的静默空图。公网图片、地图底图与资源 API 仍依赖网络；并未逐个在真机操作全部通用组件。

分支 `codex/ios-intelligent-ui`。本地 Xcode 产物与日志：`/tmp/nano-ios-701`。预览服务和本 worktree 因用户此前明确要求保留，未停止；本次额外唤起的旧 Nano feat578 390 模拟器已恢复关闭，新测试模拟器保留。
