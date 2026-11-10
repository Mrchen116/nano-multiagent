# Nano IM for iOS

原生 SwiftUI 客户端，最低 iOS 26。聊天、任务图、Agent 管理/Work 和“我的”复用 IM 的现有 HTTPS API。新版 Intelligent UI 回复内容使用系统 WebKit；业务页面仍为原生实现，不启动本地 Agent 内核。

## 构建

需要完整 Xcode 26.4.1 或更高兼容版本及 iOS 平台组件，以及仓库支持的 Node / pnpm。首次构建先在根目录执行 `pnpm install --frozen-lockfile` 和 `npm --prefix src/IM/frontend ci`。项目固定使用 `swift-markdown` 0.8.0，依赖版本记录在项目内 `Package.resolved`。

```bash
./src/IM/ios/scripts/build.sh build
```

脚本默认使用 `/Applications/Xcode.app/Contents/Developer`，可以通过 `DEVELOPER_DIR` 指向其他完整 Xcode。产物默认放在 `/tmp/nano-ios-build`；可用 `NANO_IOS_BUILD_ROOT` 更改，不向仓库写 DerivedData。

脚本自动构建共享 product-contracts 和离线 Intelligent UI 资源，再执行 Xcode。资源位于 `NanoIM/Resources/IntelligentUI/`，包含组件、图标、公式字体与许可证，作为文件夹随 App 打包；生成物不入 Git。之后可以打开 `NanoIM.xcodeproj` 调试；更新共享组件后重新运行构建脚本。Debug 允许显式配置 loopback HTTP 开发服务；可在 scheme 的 Run environment 设置 `NANO_IM_BASE_URL=http://127.0.0.1:<隔离IM端口>`，或在登录页输入。正式 Release 只接受 HTTPS origin，不含路径。

模拟器测试：

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun simctl list devices available
NANO_IOS_SIMULATOR_ID=<设备UDID> ./src/IM/ios/scripts/build.sh test
```

## 显式 App UI 旅程

`NanoIMJourney` 是独立标准 XCUITest scheme，不随 `NanoIM` 的单元测试自动运行，也不直接调用 App 内部方法或注入 JavaScript。先按 worktree runtime 准备获准的隔离合成服务，再执行：

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild \
  -project src/IM/ios/NanoIM.xcodeproj -scheme NanoIMJourney \
  -destination 'platform=iOS Simulator,id=<设备UDID>' \
  -derivedDataPath /tmp/nano-ios-journey -jobs 2 \
  -parallel-testing-enabled NO build-for-testing
```

将生成的 `Build/Products/NanoIMJourney_*.xctestrun` 复制到同一目录中的本地专用文件，只在该副本的 `NanoIMUITests.EnvironmentVariables` 中填写以下输入，再使用 `test-without-building -xctestrun <副本> -only-testing:<目标case>`；普通 shell 环境不保证传入测试 runner。副本包含合成登录凭据，权限设为 `0600`，不得提交。

- 先在 host 核实本轮新建 runtime 的 IM PID/出生时间、命令、cwd、监听端口，以及该 runtime 内只读数据库中的合成账号、唯一聊天标题、会话 owner 和新卡片执行来源；不能仅凭 loopback 或任意环境变量声明合成。由核实结果生成 `NANO_UI_FIXTURE_JSON`：`runID`（新 UUID）、`origin`、`username`、`conversationID`、`chatTitle`、`cardIDs`、`cardLabels`。此 JSON 是对象绑定结果，不是执行权限，也不解除已拒绝 case。
- `NANO_UI_ORIGIN` / `NANO_UI_USERNAME` / `NANO_UI_CONVERSATION_ID` / `NANO_UI_CHAT_TITLE` 必须与该 JSON 一致，`NANO_UI_PASSWORD` 仅使用对应合成账号密码。测试在启动前强制检查 HTTP loopback 动态高位端口并排除既有 62814 预览；禁止使用 4000/8011/5173。API helper 只接受该 fixture 列出的卡片，字段编辑只接受列出的可访问名称。仅编辑环境变量不能代替 host 的进程与数据库核实。
- `OneShotBackgroundUITests` 使用已由真实产品产生的会议卡，字段为可访问名称“参会人数”、状态键 `$participants`。409 case 另需 `NANO_UI_CONVERSATION_ID` / `NANO_UI_CARD_ID`，会通过另一正常认证客户端推进真实草稿版本，然后验证 App 自动同步最新值并发出正文。成功 case 输出唯一 `716_NATIVE_RUN`，需用该标记核对隔离服务中的第一/第二消息 relay；UI test 成功本身不证明背景已一次性消费。
- 多卡 case `testTwoEditedCardsAreConsumedTogetherThenOnlyReeditedCardReturns` 另需 `NANO_UI_CARD_A_LABEL` / `NANO_UI_CARD_B_LABEL`，指向该合成会话两张独立卡片中唯一、可访问的人数字段；A 在 B 之前。它实际编辑 A/B、从 composer 连发两条、再改 A 发送第三条，输出 `716_NATIVE_MULTI_RUN` / `716_NATIVE_MULTI_REEDIT`。需核对三条真实 relay 的来源分别为 A+B、空、仅 A；不能只凭 XCUITest 通过宣布多卡语义成立。
- 私聊保存失败沿用普通发送错误和发送按钮。原生卡片可能因滚动暂时离开可见区域，测试应先把字段滚到可见范围再验证其值。
- transient case 的 `NANO_UI_OUTAGE_EXPECTED=1` 只是测试前置，不是故障演练授权。必须先获得专用服务停启的明确人类授权，并准备独占服务、原数据库/端口恢复与自有进程清理；不在 preview/共享服务上运行，不自动建立故障注入或录制代理。没有授权或前置就不选择该 case，保留未验证结论。

## 原生进程级缓存旅程

`NanoIMJourney` 是单独的 XCUITest scheme，不混入不需要真实服务的 `NanoIM` 单测。它通过真实登录界面与服务 DTO 首次读取会话和历史，终止 App，再在**同一隔离 origin 不可达**时冷启动、打开缓存时间线并保存截图；不注入 SQLite 或直接调用 `ChatStore`。此路径不证明真机飞行模式、文件保护属性或性能达标。

先按 [worktree runtime](../../../docs/development/worktree-runtime.md) 准备独立 IM 和测试账号，创建一条有普通文本消息的会话。该局部旅程不调用 Agent，不需要为它启动团队或 LLM。使用**专用模拟器**，不要清除个人模拟器的账号或数据。

```bash
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
xcodebuild build-for-testing -jobs 2 -project src/IM/ios/NanoIM.xcodeproj \
  -scheme NanoIMJourney -destination "platform=iOS Simulator,id=$NANO_IOS_SIMULATOR_ID" \
  -derivedDataPath /tmp/nano-ios-journey
```

在生成的 `Build/Products/NanoIMJourney_*.xctestrun` 的 `NanoIMUITests.EnvironmentVariables` 中注入下列本轮输入，另存于**同一目录**（相对产物路径依赖此位置）。此文件和测试凭据不提交：

- `NANO_UI_ORIGIN`：本轮隔离服务的 loopback HTTP origin，不能使用生产地址。
- `NANO_UI_USERNAME` / `NANO_UI_PASSWORD`：该服务的测试账号。
- `NANO_UI_CHAT_TITLE` / `NANO_UI_MESSAGE`：已创建会话的唯一标题与消息文本。

先用 `xcodebuild test-without-building -xctestrun <注入后的文件> -destination ... -only-testing:NanoIMUITests/LocalFirstLaunchUITests/testPrimeFromRealServer` 执行在线阶段；通过后，让**仅此测试 origin**不可达，再执行 `testOfflineRelaunchReadsListAndTimeline`。两个阶段分别使用不同的 `-resultBundlePath`，读取其中保留的在线/离线列表和时间线截图。两阶段必须使用同一模拟器、同一 origin 和同一构建；不能用全新缓存替代冷启动，也不能把另一个阶段的截图当作本次证据。最后停止自建服务并确认监听已释放。

## 设备产物

```bash
./src/IM/ios/scripts/build.sh archive
```

输出 `NanoIM.xcarchive` 和 `NanoIM-unsigned.ipa`。未签名 IPA 供 AltStore Classic 重新签名，不能直接当作已安装验证。Xcode 真机调试需在 Signing & Capabilities 选择自己的 Personal Team；不要提交账户、证书或本机签名设置。

免费签名的续签和到期时间应以 AltStore 实际记录为准。该版本不使用 APNs，后台或关闭时不承诺新消息提醒；回前台重新同步。

## 代码与验证边界

- `Client/`：Keychain、token 刷新、请求取消和同源限制、WebSocket ticket/resume。
- `Features/`：四个入口及原生详情/表单，真实服务返回驱动界面。
- `UI/`：原生 Markdown、受保护媒体、Quick Look 和系统分享。
- `Tests/`：会话轮换/退出竞态、消息合并、管理请求与返回模型契约。

`openui/nano-iui-1` 复用 Web 的 `interactiveLibrary`、React Renderer 和组件样式，在只加载随包资源的 WKWebView 内呈现。认证、私人状态保存、查询、显式提交和草稿采用继续走原生 Session / ChatStore。桥接只接受主文档和已注册工具/资源；HtmlView 的沙盒子页面不能访问原生权限。图片、地图底图及远程资源仍需要网络，组件本身不依赖在线网页服务。CI 在共享组件变动时也运行原生测试和设备 archive。

旧 `openui/nano-1` 继续用随包 `lang-core` 1.0.1 在 JavaScriptCore 中求值并以 SwiftUI/Swift Charts 呈现。`Runtime/interactive-runtime.ts` 或旧目录改变后，在根目录运行 `pnpm exec tsx scripts/generate-ios-interactive.ts` 更新资源与许可证；`pnpm check:ios-runtime` 检查一致性。

本机测试前记录模拟器 UDID、是否本轮新建及原运行状态，并为本轮设置独占 `NANO_IOS_BUILD_ROOT`。`build.sh` 只构建/测试，不代管模拟器和构建目录；结束（含失败）后按 [测试资源回收](../../../docs/development/worktree-runtime.md#测试资源回收) 处理，临时专用模拟器须关闭并删除，借用设备恢复原状态。

真实服务必须按仓库 [worktree runtime](../../../docs/development/worktree-runtime.md) 隔离。行为契约见 [iOS Client](../../../docs/specs/im/ios-client.md)，本版交付范围与证据见 [feat-578](../../../docs/changes/archive/feat-578-ios-app/release-acceptance.md)。模拟器 UI 与 API 验证不代替真机的中文输入、VoiceOver、免费续签和到期恢复；这些剩余实证跟进 [#327](https://github.com/Mrchen116/nano-multiagent/issues/327)。
