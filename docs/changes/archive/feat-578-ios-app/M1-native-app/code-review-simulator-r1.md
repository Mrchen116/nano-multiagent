# Independent code review — Simulator R1 delta

2026-10-06。使用`change-code-review`，`review_mode: patch`；冻结范围`18477d8b3..aa7876fa9ab443b4cf12d1a4119fd2abc7d428d3`。现场`codex/feat-578-ios-app`，HEAD与候选一致；原有`output/`保持。只审本轮三个原生源码文件、现有ChatStateTests扩展和直接相关文档，不机械重审未失效范围。没有操作UI/服务/物理手机、修改产品源码或派其它agent。

## Findings

```json
[]
```

## Affected behavior and direct evidence

| 修正 | 独立核对 | 结论/边界 |
|---|---|---|
| 消息具名辅助动作与长按菜单共用 | `ConversationView.swift:54-56,271-279`保留contextMenu、容器`.contain`和`.accessibilityActions`都调用messageActions；复制仍转换可见mention/Markdown并置copied；分支仍限Agent会话、Agent发送、存在kernel_message_id且completed | 动作条件一致；分支只设置confirmFork，现有confirmationDialog明确确认后才发请求。没有削掉消息内子控件；实际辅助技术/操作器是否能调用待新包体验 |
| 离线蒸馏明确说明 | `ChatListView.swift:169,175-180`先保留同设备guard，再读取现有nodes快照；仅已知对应节点offline时说明恢复后重试并return，不调用生成/完成回调 | 不把未知节点当在线或离线成功，不伪造transcript/draft；owner节点列表与既有服务端source/execution owner/member校验保持 |
| 真人消息提醒协议 | `ChatStore.swift:96-111`真人sent触发、真人created不再次触发、非真人created保留；原cursor/floor、静音、当前聊天、自发与提醒开关过滤不变 | 与实际服务匹配；提醒目标来自已授权conversations，未增加正文泄漏或后台保证 |

服务端直接证据：`src/IM/infra/repositories/messages.py:267-277,355-370`的sent payload含sender_type/user_id/conversation_id，持久写入sent并可选created；Agent桥接`event_bridge.py:124-132`与`api/ws/event_types.py:143-160`产生带sender_type的created。caller提供的真实616sent/617delivered是辅助事实，源代码协议也独立核对，不以AX缺失推导运行结果。

辅助API语义按Apple原始文档核对：`.contain`保留子辅助元素在新容器下，`.accessibilityActions`由具名Button提供可调用动作。它们支持本轮静态接线判断，不证明真实VoiceOver或当前操作器成功。[Apple contain](https://developer.apple.com/documentation/swiftui/accessibilitychildbehavior/contain)、[Apple accessibilityActions](https://developer.apple.com/documentation/swiftui/view/accessibilityactions(_:))。

节点预检的读取路由`api/routes/nodes.py:150-163`仍按current_user及owner筛选；蒸馏服务`api/routes/web_im.py:358-415`再次核对来源会话成员、owner profile、single_thread、同Gateway和执行Agent。新增客户端说明没有替代或扩大权限。

## Validation

复用已有`ChatStateTests.testForegroundRemindersHandleHumanSentWithoutRepeatingCreation`的公开consume/真实decode seam回归。旧代码`/tmp/nano-feat578-human-reminder-red.log:297-298`真实两断言失败：真人sent无banner、后续真人created反而产生banner；该red另有诊断采集simctl不可用记录，不影响已经发生的断言失败事实。修正后`/tmp/nano-feat578-human-reminder-green.log`实际35项通过（25XCTest、10Swift Testing，0failure），xcresult`/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.06_22-36-55-+0800.xcresult`。测试观察目标、真人created重复、Agent、自发、静音、selected及重复event重放；positive notificationFloor过滤沿原代码，未宣称新增测试单独覆盖它。

测试/构建证明代码与接线可编译及指定协议逻辑通过，不证明正文操作、离线提示或banner点击已被新包实际接受。没有新增镜像文案/布局测试、没有重跑未改变的Python4120/Web808。冻结diff check通过。当前`origin/main=d87ffa3d19160d45d309f281b0ace4ff92f55a38`是候选祖先；该Git关系只回答本地已有远端ref，没有重新声明互联网主线永远无新增。

结论：有限patch无新的确认finding。`acceptance-simulator-r1.md`是旧8e产品实际事实，其操作器/前置限制保持，不能被aa7876源码替换成通过。新包S2/S9/S27实际窄复验仍需product reviewer。用户真机deferred；整体Full、物理IME/辅助访问、无线续签/自然到期及其它未完成场景继续开放，无Ready PR/merge/waive/部署结论。
