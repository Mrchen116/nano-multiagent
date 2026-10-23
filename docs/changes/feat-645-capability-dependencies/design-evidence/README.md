# 设计走查证据

> 修订状态：用户指出下列旧截图中的提示插行会把工具挤开；此前对这一体验的通过判断撤回。当前 prototype 已移除全部占位容器，改为独立浮层。修订版尚未完成实际渲染复验，下文保留为历史证据，不代表新版本视觉通过。

## 本次修订

- 删除 62/82/84px 的提示占位，提示不再插入工具 flex 或 Feature grid。
- 单一 body 浮层，锚定所点控件，简短文案、紧凑尺寸，约两秒消失；滚动或继续调整时收起。
- 待复验：1440/768/390 下 schedule_list 与 Task 关闭受阻，出现/消失前后控件坐标、列表换行与面板高度必须完全一致；不以源码检查代替画面验证。
- 本轮浏览器拒绝读取用户当前打开的 file:// 地址（仅允许 http/https）；未换用其他入口绕过该限制。
- 参考：[Atlassian Designing messages](https://atlassian.design/foundations/content/designing-messages/) 区分覆盖式短暂通知和会推动内容的系统 Banner；本原型的局部锚定与两秒时长来自本任务已确认交互，不声称是 Atlassian 的完整组件规范。

2026-10-23，作者通过 Codex browser 实际渲染本 unit `prototype.html`。这是一份设计原型，未调用产品 API、未改变生产开关、未证明真实 runtime 已实现。

## 当前产品依据

只读查看用户已打开的 Web `/settings/agents/nano-quality`：侧栏、Agent 标题/保存入口、配置标签和白色分区卡片沿用。生产快照当时未展示六项 Feature 目录，不能据此声称目标已上线。该页面包含用户配置，不保存或提交其完整截图。六项现有 Feature 布局另由 Web 源码核实；同期 bugfix-644 的 `design-evidence/baseline-desktop.png` 只作其独立 E2E 视觉参考，不作为本 unit 的产品验收证据。

iOS 依据 `AgentConfigView.swift` 的 native Form / Toggle / DisclosureGroup 结构。本目录的 iOS 图是 HTML 意图示意，尚未在原生模拟器验证；实现验收必须补原生焦点、VoiceOver 与安全区证据。

## 实际走查

| 路径 | 观察结果 |
|---|---|
| 默认打开 | Task 与 Cron 同时开；完整调度工具已选 |
| Task 开时关闭 Cron | Cron 保持开，轻提示要求先关 Task；见 web-1440.png |
| doing/waiting 模拟开启后关 Task | Task 保持开，提示先暂停/结束；未改变模拟业务状态 |
| 无 Task 责任时关 Task | Task 工具默认取消，Cron 仍开 |
| active 安排模拟开启后关 Cron | Cron 保持开，提示先删除安排 |
| 清除占用、关 Cron、单开 schedule_create | 仅该工具选中，Cron 保持关 |
| 关 Memory，再关 Skill 创建 | 先保留共享 read；最后依赖关闭后 read 取消；skill 因交互式回复仍开而保留 |
| 键盘 Space 操作受保护 Task | 开关保持开，焦点仍停留在原 Toggle |
| 保存前新增 Task | 恢复 Task 及依赖，未自动再次保存；反馈保存冲突 |
| 维护在途 | Memory 关闭被拒，开关保留 |

视觉宽度使用实际浏览器 viewport 1440、768、390；不是仅缩放截图。768 保留窄侧栏、Feature 单列；390 去侧栏，工具换行，Task 长提示完整换行且不覆盖点击目标。最初把提示放分区末尾，走查后改成窄屏紧随操作项的临时反馈空隙。iOS 模式独立使用 Form 行和 Toggle，而非直接缩窄 Web 卡片。

Toast 约 2 秒后淡出（150ms），重复点击更新同一条；普通文本状态采用 polite announcement，无关闭按钮。只验证了 HTML 原型的交互与焦点，未把它当作 iOS 无障碍或后端竞态的验证。

## 图像

- [Web 1440：Task 阻止关闭 Cron](web-1440.png)
- [Web 768：关闭记忆维护、共享依赖保留](web-768.png)
- [Web 390：Task 责任提示](web-390-task.png)
- [iOS 意图：Task 责任提示及焦点](ios-intent.png)

独立 reviewer 应自己渲染并操作原型，结合目标设计判断；以上截图不是预期评审结论。
