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
