# bugfix-731: As-built Design

> 本文在实现完成且用户确认两种真实截图后，按实际 diff 整理。没有事前设计审查或 milestone 派发。

## 实现范围

- 原始实施基线：`00972141a`；收尾已同步 `origin/develop` 的 `94d663626`（仅新增 bugfix-732 首文档，代码与既有验证版本相同）。
- 实施证据版本：`cd24971fb`；收尾受审版本由 `review.md` 记录。
- 受影响模块：Web 顶层通知协调 hook、toast 展示组件、Agent 完成身份 accumulator 与相应测试/翻译。
- 不涉及持久化 schema、Node/DSH 协议或模型可见信息，不需要部署迁移。

## 最终结构

### 组件与职责

- `useGlobalMessageToast` 沿用唯一用户事件流、完成累计、去重、未读和外部来源归类；在现有 toast 数据上补充会话标题与群聊类型。
- `InAppToast` 只展示：会话标题、可选群聊发送者行、消息摘要与原有查看/关闭动作。私聊省略发送者行。
- `agent-completion-accumulator` 与普通消息解析读取 canonical `sender.display_name`；保留已有可读顶层名称字段，缺省时使用本地化通用称谓，删除原始 ID 的名称兜底。

### 调用链与数据流

真实用户流 → 现有创建/完成候选与资格筛选 → 保存 toast → 优先查 `chat/conversations` 中的目标会话；未加载列表时，经已有鉴权 API 获取该会话详情（复用 `chat/conversation-detail` key）→ `App` 根据 `type === group` 决定是否传发送者 → toast 展示。

会话详情只按当前提醒的 ID 获取，不为通知加载全会话列表。读取失败仍显示“新消息”和摘要，不影响已有导航 ID。查询使用现有权限与失败处理，不引入额外轮询或重试机制。

### 状态、数据与兼容性

既有 pending completion 的持久化结构、message key 和 conversation ID 保持不变。名称显示使用独立会话标题，不影响实际导航与访问资格。共享 accumulator 的 canonical 名称纠正同样影响桌面系统通知候选，但本轮未改变其布局或资格逻辑。

## 关键决策

| 决策 | 原因与约束 | 代码定位 |
| --- | --- | --- |
| 私聊会话名优先，群聊额外显示发送者 | 用户明确要求；会话名允许用户自定义，同一 Agent 可有多条私聊 | `app/App.tsx`、`features/chat/hooks/use-global-message-toast.ts` |
| 群聊发送者独立成行 | 保留群名、发送者、摘要的辨识层级，避免长发送者吞掉摘要；此最终展示已由用户看图确认 | `features/chat/components/in-app-toast.tsx` |
| 名称行单行省略，摘要最多两行 | 维持原小型临时提醒，限定宽度且不扩大成长卡片 | 同上 |
| 设置页缺列表时读取单条会话 | 桌面设置入口可能从未打开聊天列表，不能要求先访问 Chat 才正确显示名称 | toast hook 的会话详情 query |
| canonical sender 名称作为消息展示身份 | 服务端真实消息形状为嵌套 Actor，不能用内部 UUID 或统一 Agent 配置名替换 | accumulator 与普通消息名称解析 |

以上前端路径均相对于 `src/IM/frontend/src/`。

## 失败路径、风险与回滚

会话元数据不可得时使用可读默认标题，发送者名称不可得时使用“成员”或“Agent”；不阻塞消息本身或原有查看入口。用户事件资格、去重、刷新 pending、外部影子消息判定保持原实现。回滚为撤销本 unit 的前端改动，无数据库或配置迁移。

## 与初始意图的差异

最初建议把“发送者：摘要”放在同一行；最终将群聊发送者独立成行，用户已查看实际截图并接受。私聊会话名与群聊“群名＋发送者”的目标没有变化。`View message` 文案沿用原样，不扩展通知整体改版。

## 本次审查安排

| 问题 | 能力与证据 | 边界 |
| --- | --- | --- |
| 来源解析、会话元数据补取、资格不变量与最终契约是否正确 | 独立 change-code-review，核完整 diff、测试、服务端 canonical 字段与 delta | 不以代码 review 替代真实画面 |
| 两种展示能否识别来源并跳转 | 复用实际 Web 收发/点击、两张截图与用户“很好，可以了”确认 | 桌面 1440×900；未声称手机或完整 daily 初始化通过 |

## 验证定位

- 用户原话与明确验收：`fix.md`；真实截图与持久消息记录位于本机报告目录。
- 通知窄套件 39 项通过，前端构建通过；完整前端 1081 通过 / 1 既有失败，原基线对照同样失败，详见 `fix.md`。
- 目录能力同步 504 不在本次修复范围；真实 IM/Node/Agent 的两条收发与跳转独立完成。测试服务、浏览器与 tmux 已停止，worktree clean。
- 最终本地检查、审查版本和 PR/CI 状态见 `review.md`。

## Canonical 文档影响

- delta：`specs/im/web-chat-ux.md`。
- 归并：`docs/specs/im/web-chat-ux.md` 新增来源提醒要求，更新 IM 包入口的条目数量与说明。
