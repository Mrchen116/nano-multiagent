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

- `NANO_UI_ORIGIN`：本 unit 的 loopback 隔离 IM origin；`NANO_UI_USERNAME` / `NANO_UI_PASSWORD`：专用合成账号；`NANO_UI_CHAT_TITLE`：实际会话标题。
- `OneShotBackgroundUITests` 使用已由真实产品产生的会议卡，字段为可访问名称“参会人数”、状态键 `$participants`。409 case 另需 `NANO_UI_CONVERSATION_ID` / `NANO_UI_CARD_ID`，会通过另一正常认证客户端推进真实草稿版本，然后从 App 操作比较/采用。成功 case 输出唯一 `716_NATIVE_RUN`，需用该标记核对隔离服务中的第一/第二消息 relay；UI test 成功本身不证明背景已一次性消费。
- 原生失败提示可能把原卡移出 lazy viewport，卡片和 composer 也可能同时提供同名恢复动作。测试只点击实际 hittable 的原生按钮，不以屏外字段查询或按钮数组顺序代替用户可操作性。
- transient case 的 `NANO_UI_OUTAGE_EXPECTED=1` 只是测试前置，不是故障演练授权。必须先获得专用服务停启的明确人类授权，并准备独占服务、原数据库/端口恢复与自有进程清理；不在 preview/共享服务上运行，不自动建立故障注入或录制代理。没有授权或前置就不选择该 case，保留未验证结论。

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

真实服务必须按仓库 [worktree runtime](../../../docs/development/worktree-runtime.md) 隔离。行为契约见 [iOS Client](../../../docs/specs/im/ios-client.md)，本版交付范围与证据见 [feat-578](../../../docs/changes/archive/feat-578-ios-app/release-acceptance.md)。模拟器 UI 与 API 验证不代替真机的中文输入、VoiceOver、免费续签和到期恢复；这些剩余实证跟进 [#327](https://github.com/Mrchen116/nano-multiagent/issues/327)。
