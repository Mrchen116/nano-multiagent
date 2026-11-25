# feat-785 原型走查

> 对应 [design.md §前端原型](../design.md#前端原型) 与 [prototype.html](../prototype.html)。
> 截图 PNG 按 `.gitignore`（`docs/changes/**/evidence/**/*.png`）只保留在本地，本文用反引号记录路径，不建 Markdown 图片链接（避免 `scripts/docs_check.py` 将被忽略的本地截图判为断链）。

## 方法与边界

- **渲染方式**：使用本机 Google Chrome `--headless=new` 逐状态打开 `file://…/prototype.html?state=<state>` 实际渲染截图；桌面状态 `--window-size=1320,960`（承载 `1240×780` 桌面舞台），手机窄屏与 iOS 状态 `--window-size=460,1040`（完整承载固定 `390×740` 竖屏视口及底部导航/输入栏）。
- **原型性质**：零外链自包含静态 HTML，全部样式与交互脚本内联，采用 `src/IM/frontend/src/styles/global.css` 与 `src/IM/ios/NanoIM/UI/CommonViews.swift` 的 Crewden token（`--im-accent: #6b43d8`、`--im-butter: #fff0b5`、`--im-mint: #ddefe5`、`--im-bg: #f7f8fa`）。顶部深色 `.demo-chrome` 明确隔离「现有界面背景 / 本次重塑范围 / 仅演示控制」，产品区域内不含演示控制按钮或实现机制解释。
- **真实产品基线来源**：基线取自现行代码事实——Web `src/IM/frontend/src/features/tasks/{task-progress,task-graphs-page}.tsx`、`src/IM/frontend/src/features/chat/components/message-pane.tsx`、`src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`，以及 iOS `TasksView.swift`、`ChatMessageView.swift`、`PersonalAgentManagementView.swift` 与 `AgentConfigView.swift`。

## 渲染了哪些画面

| 状态参数 | 视口 | 本地截图路径 | 覆盖的对齐契约 |
|---|---|---|---|
| `?state=focus-web` | Web 1280 | `evidence/screens/focus-web.png` | `must-match`：默认「与我有关」焦点台（带会话归属胶囊的单卡速建、待你拍板、正在推进与盯梢、长线目标、切换按负责人/团队全部） |
| `?state=focus-triaged` | Web 1280 | `evidence/screens/focus-triaged.png` | `must-match`：翻牌后零待审安静态、无前置单卡直入 `doing` 而前置未完节点进入 `todo`、脱离文档流浮层提示 |
| `?state=goal-web` | Web 1280 | `evidence/screens/goal-web.png` | `must-match`：北极星全景图（置顶终局目标、多层子脉络钻取入口、阶段依赖 + 探索选型与负结果、含「批准立项/放远期/关闭」的前沿新芽、右侧同屏草稿） |
| `?state=chat-web` | Web 1280 | `evidence/screens/chat-web.png` | `must-match`：PA 私聊顶层 `task_cards` 活卡片与草稿查看入口 |
| `?state=focus-mobile` | Web 390 | `evidence/screens/focus-mobile.png` | `must-match`：390 窄屏焦点台纵向排布、会话归属选择与底部四栏导航完整可见 |
| `?state=ios-goal` | iOS 390 | `evidence/screens/ios-goal.png` | `must-match`：iPhone 纵向阶段脉络流（前序已完成可展开、`+ 子节点`、节点详情/编辑入口、候选新芽单手翻牌） |
| `?state=ios-draft` | iOS 390 | `evidence/screens/ios-draft.png` | `may-adapt`：iPhone 原生 Sheet 秒开随任务节点保存的准备草稿 |
| `?state=ios-chat` | iOS 390 | `evidence/screens/ios-chat.png` | `may-adapt`：iPhone PA 私聊内嵌同源活任务卡片与底部输入栏共存 |
| `?state=settings-online` | iOS 390 | `evidence/screens/settings-online.png` | `must-match`：PA 运行设置页承载单一「主动筹划」开关、与「任务图」依赖联动轻提示及顶栏统一「保存」 |
| `?state=settings-offline` | iOS 390 | `evidence/screens/settings-offline.png` | `must-match`：所属电脑离线时顶部只读提示、开关与保存按钮统一禁用 |

## 事实 → 判断 → 修正

| 观察到的事实 | 体验判断 | 原型修正动作 |
|---|---|---|
| 初版顶栏与卡片内写了「已过滤无关公开群底层子任务」「绑定真实任务 tg_bot」与「模拟重连刷新」 | 违反 *Let the UI speak for itself* 且混入模拟文案 | 清除内部机制解释文案与内部 ID；将「重置演示数据」移入顶部 `.demo-chrome`，离线横幅改为「重试刷新」 |
| 初版速建栏无会话归属选择，且点击「按负责人 / 团队全部」未切换实际内容 | 丢失为团队群新建任务的入口，且非默认范围视图未表达清楚 | 在速建栏内增加归属会话选择胶囊（默认小助私聊，可切至团队群）与「完整新建…」入口，并实装「按负责人 / 团队全部」切换视图 |
| 初版 `goal-web` 前沿新芽缺少「关闭」按钮，且在阶段 3 尚未完成时把阶段 4 新芽显示为「批准开工 → 推进中」 | 与后端「有未完成前置依赖时批准进入 `todo`」的状态机不一致，误导用户以为跳过了前置阶段 | 补齐前沿新芽的「关闭」按钮；对受前置阻塞的新芽将按钮标为「批准立项」，点击后准确呈现为「待办 · 等前置阶段 3 完成」，与无前置单卡「批准开工 → 推进中」形成直观对照 |
| 初版 `ios-goal` 前序已完成阶段不可展开，且缺少多层子脉络钻取、`+ 子节点` 与节点编辑入口 | 相对现有任务图页面发生功能回退 | 为桌面与手机阶段节点补齐子脉络钻取入口，为 `ios-goal` 补齐「展开查看 ›」前序折叠交互、顶栏 `+ 子节点` 与卡片「详情/编辑 ›」入口 |
| 初版 iOS 设置页将「主动筹划」画成无保存按钮的即时切换卡，且与二级 `AgentConfigView` 的 `task_graph` 依赖校验脱节 | 若二级页隐藏 `proactive_planning` 会造成关闭 `task_graph` 时遇到隐藏依赖死锁 | 对齐真实配置页架构：开关放在运行设置页与「任务图」「Dreaming」同处一处，共用顶栏/底栏「保存」按钮与「请先关闭主动筹划再关闭任务图」浮层轻提示，一级页以状态行跳转进入 |

## 未验证项（留给 M1 实施与真栈验收）

- 真实后端 API、WS `task_graph.changed` 推送收敛、409 revision 冲突逐字段恢复及真实 LLM 夜间草稿/提议质量，由 M1 真栈与真实模型旅程验证。
- 原生 iOS 的 SwiftUI Sheet 手势阻尼、动态字号、深色模式与 VoiceOver 焦点顺序，由 M1 在 Xcode / iOS Simulator 实测验证。
