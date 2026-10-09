# Code Review: Simulator correction R2

2026-10-07。使用 `change-code-review`，`review_mode: patch`，独立审查冻结 `1bd5d8eda → aa46dbf383b8c450d5d87903963270de39617dee`，仅四处 native 产品修正、图片粘贴测试及本批说明。没有操作 GUI、服务、生产或物理手机，没有改源码/测试/配置，没有重跑未失效范围。

## Findings

```json
[
  {
    "file": "src/IM/ios/NanoIM/Features/Agents/AgentChannelsView.swift",
    "line": 96,
    "summary": "[P2] Distinguish an offline channel node from a state conflict",
    "failure_scenario": "Reconnect or retry a pending removal while its node is offline. ChannelControlService returns HTTP 409 with detail.code=channel_node_offline (channel_control_service.py:96,108), and Session.swift:168-172 preserves that code. This catch ignores it and says the channel state changed and to reload before retrying. The removal card has no node-offline explanation, and reloading alone cannot restore the disconnected node. S21 requires a clear failure reason and recovery direction. Handle channel_node_offline with a message to reconnect the device and retry; retain the channel conflict wording for other 409 responses.",
    "review_mode": "patch",
    "status": "CONFIRMED"
  }
]
```

该条件不是推测：`tests/im_service/integration/test_agent_channels_api.py:185-190,214-218` 明确断言真实 reconnect/retry API 在离线 notifier 条件下返回 `channel_node_offline`。本 reviewer 只读该测试和直接服务/解码接线，不声称此轮实际 UI 复现。此前 `acceptance-r18.md` 的真实离线 retry/conflict 是相关现行用户路径，不以旧画面代替新文案验收。

## Other inspected changes

- `ConversationView.swift:341-347` 只为可编辑且有图片的系统 Paste action 开放能力，其他动作委托父类；图片内容仍仅在 paste 调用时读、进入已有回调和 addUpload，未自动发送或覆盖文字草稿。[Apple canPerformAction](https://developer.apple.com/documentation/uikit/uiresponder/canperformaction(_:withsender:))允许按状态启用编辑命令；[Apple hasImages](https://developer.apple.com/documentation/uikit/uipasteboard/hasimages)提供图片存在判断，无需用 image 读取来检测类型。
- `ChatListView.swift:173,183-185` 每次实际生成清旧 error，仅为服务真实的 source binding/file unavailable detail 提供中文恢复路径。`gateway/distill_prompt.py:84-97 → web_im.py:427-435 → APIError.detail` 接线一致；正常 completed 回调仍只在成功响应后发生，不生成假草稿或绕过来源/执行/同设备校验。
- `SettingsNodesView.swift:82`、`AgentChannelsView.swift:42` 使用既有 `NanoDateTime`；该组件解析 ISO8601 并按系统日期时间格式显示，解析失败保留原值，没有改变 heartbeat 或 channel 的真实时间/连接状态。
- `AgentChannelsView.swift:79` 成功重读清旧通用 error，实际 removal/apply_error 仍来自权威 channels 数据并单独显示，不将停止失败或 pending 伪报成功。

## Evidence and boundary

已读 `/tmp/nano-feat578-image-paste-red2.log`：独立测试模拟器写入图片专用剪贴板后，唯一失败为 canPerformAction(paste) 的 XCTAssertTrue；测试的图片回调、原草稿保持及只读条件未失败。日志还含 `simctl` 路径诊断，保留该事实。初次 red fixture 读取旧 pasteboard 被系统拦截不计为产品 red。

已读 `/tmp/nano-feat578-image-paste-green.log`：同独立测试 Simulator `AA8F9712-DDCB-405F-9DD9-6D14203B44CB` 上 26 XCTest + 10 Swift Testing、0 failure、`TEST SUCCEEDED`；xcresult `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.07_01-13-53-+0800.xcresult`。test 使用公开 UIKit 编辑能力与 paste 回调 seam，是行为回归；不是实际 Photos→系统菜单→待发预览旅程。Python/Web 未变，既有证据保留原 scope。

本轮有一项 confirmed feedback finding；不建议据此冻结版本接受产品或结束 Full。S21 受控 stop 故障允许的契约边界保留 [独立范围核对](verification-simulator-scope-r1.md)；不操作或创建 fixture。物理 Gate 按用户安排后置，未取消、降低或推断通过。
