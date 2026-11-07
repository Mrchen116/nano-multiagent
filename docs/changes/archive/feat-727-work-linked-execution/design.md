# feat-727: As-built Design

> 本文在实现完成后根据实际代码、diff 与已确认决定整理，描述最终落地设计。

## 实现范围

- 原始基线：`c2b41c096`；初次实现：`84eb50074`。
- 同步基线：`70d781d6197ccc918dd943f4743df5fe3bfc3719`；同步后的实现：`cd7f7f62d8e55a7943740f3d5150022a7b1bfe90`。
- 同步增量为 bugfix-713 的聊天占位消息投影恢复，不改变本次 Work 组件、关联数据或预览；上述两次实现的补丁相同，用户确认和既有浏览器观察保留有效。
- Included dirty files：无其他任务改动；收尾时另补本文、需求、delta 和 code review。
- 受影响模块：`src/IM/frontend/src/features/settings/agents/` 下的 `agent-work-panel.tsx`、`agent-work-presenters.tsx`、`agent-work.css` 及 panel 既有测试。

## 最终结构

### 组件与职责

`AgentWorkPanel` 的 Turn 渲染保留既有消息来源和子会话查找。消息正文卡片增加标题行，将原先卡片外的按钮移动到标题右侧；标题和链接在窄容器内允许换行。

`WorkTool` 将 childLink 移入工具卡片的 footer，在工具明细折叠时继续展示。`WorkBackground` 将已有的关联 detailFooter 放在卡片内、明细展开条件之外。没有关联入口时不创建 footer。按钮作为折叠按钮的兄弟，不嵌套交互控件。

`agent-work.css` 将关联按钮改为透明背景、内容宽度的轻量操作，保留 focus-visible 提示；关联执行总目录按钮的原有整行样式不变。移动端关联操作最小高度为 40px。

### 调用链与数据流

- 消息仍从持久记录的 `source_session_id` 调用 `onChild`。
- 工具和后台结果仍使用原有 `other_executions` 关联逻辑找到 session，然后调用同一 `onChild`。
- `selectChild`、会话查询、桌面子轨迹侧栏、窄屏返回与阅读位置机制均沿用；本次不改变请求、权限或数据形状。
- 思考、正文、参数、结果和状态保持原有归属；只调整展示容器及关联按钮在折叠时的可达性。

### 状态、数据与兼容性

不新增 API、持久字段、配置或依赖，不需要一次性部署迁移。没有已知关联的普通记录不凭空创建入口；加载和错误继续由既有子轨迹查询处理。此改动只影响人阅读的 UI，不影响模型可见信息及其加载、注入或恢复。

## 关键决策

| 决策 | 原因与约束 | 代码定位 |
|---|---|---|
| 消息入口与来源标题共处卡片头部 | 连续阅读时不用反复辨认卡片外按钮归属 | `agent-work-panel.tsx` 的消息分支 |
| 工具和后台结果折叠时保留入口 | 查看关联执行不必先展开大段参数或结果 | `agent-work-presenters.tsx` 的两个 presenter |
| 沿用现有关联与导航 | 本次只调整入口布局，不改变执行身份或权限 | `Turn` 的匹配逻辑与 `selectChild` |
| 保留用途和状态 | 紧凑入口仍需帮助辨认所查看执行；调用完成不冒充子执行完成 | 既有 presenter 内容及 footer |

## 失败路径、风险与回滚

关联执行不可访问、离线与加载失败继续使用现有反馈，本次不增加回退执行或重新启动任务。主要回归风险为入口误归属、折叠时不可达和窄屏拥挤；分别通过不同/重复来源的路由测试、已有后台结果测试和浏览器窄屏观察覆盖。回滚实现提交即可恢复先前展示，不需要回滚数据。

## 与初始意图的差异

除子执行返回外，将同样的紧凑归属应用于 Agent 消息、委派工具与后台结果；这些类型均已包含在提供给用户并获确认的交互预览中。没有扩展后端或原生轨迹功能。

## 验证定位

- 用户确认：见 [spec.md](spec.md) 的原话与日期。
- 最窄自动化：Work panel 与 presenter 测试共 32 项通过；扩展既有 panel 文件验证连续消息内部入口分别打开不同及重复来源，后台结果入口折叠时可见。
- 构建：Node 24.22.1 下 `npm --prefix src/IM/frontend run build` 通过。
- 浏览器：实际修改后的 `AgentWorkPanel`，本地 fetch 示例数据；桌面及 390px 窄屏检查，消息、折叠工具、折叠后台结果进入预期会话，窄屏可返回主轨迹。
- 本机证据：`~/.codex/reports/work-linked-execution-475/` 中的 `overview.jpg`、`desktop.jpg`、`mobile.jpg` 与 `README.md`。截图、示例 harness 与服务日志不提交。
- 证据边界：示例预览用于布局和前端导航验证，不证明后台产生了新的真实执行；线上页面仅只读核对原有样式，未修改生产。
- 完整检查与独立代码审查：见 [code-review.md](code-review.md)。

## Canonical 文档影响

- Delta：[specs/im/agent-work.md](specs/im/agent-work.md)。
- 归并目标：`docs/specs/im/agent-work.md`；相应 `docs/specs/im/spec.md` 更新 area 数量与摘要。
