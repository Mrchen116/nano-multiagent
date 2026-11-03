# bugfix-701: iOS 接入 Intelligent UI

## Relations

- Related: [bugfix-699](../archive/bugfix-699-openui-native-visuals/incident.md)
- Related: [feat-578](../archive/feat-578-ios-app/spec.md)

## 原始报告

> 我有个问题，你做的这个UI，在ios app上支持显示吗

核对后发现原生客户端只接受 `openui/nano-1`，新版 `openui/nano-iui-1` 仅支持 Web。用户继续要求：

> 得补

## 已确认范围

沿用本会话快修模式。补齐 iOS 对当前 Intelligent UI 消息的显示和交互，复用 Web 组件、布局与绘图；保持私人状态、显式确认后回复、草稿采用、原有权限与会话隔离。以已有酒店、看板及会议场景验证实际呈现。

## 根因与不变量

bugfix-699 / PR #452 升级了 Web 的协议和组件目录，但 iOS `InteractiveRuntime.load` 仍只接受 `nano-1`，旧 JavaScriptCore → SwiftUI 组件集不包含新布局和绘图原语。不能仅放开版本检查：新源码会在旧组件目录中失败。

聊天、业务管理页面和权限继续由原生客户端及既有 IM API 持有；只在回复内容中运行随包组件。无需 IM 发布预览服务、额外浏览器内核或 Agent 执行环境。提交仍由原生 ChatStore 生成一次用户消息，不能因本地探索自动唤起 Agent。

## 状态

实现、相关回归和独立 code review 已完成，验证记录见 [validation.md](validation.md)。尚无本次 iOS 用户验收，保留 active。未发布安装包或部署生产。
