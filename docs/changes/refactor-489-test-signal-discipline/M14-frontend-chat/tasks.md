# refactor-489-M14: frontend-chat — Tasks

> 对齐: ../design.md 的 refactor-489-M14 行与决策 1--2

## 目标

让 chat Vitest 只保护用户可观察的聊天交互、状态收敛和前端接口边界；删除源码/CSS/历史文件布局扫描，并把同一组件或 seam 上的重复断言合并为最低必要保护。

## 退出标准

- [ ] 27 个 M14 测试文件覆盖的风险都有 keep / rewrite-merge / delete 处置结论。
- [ ] 保留测试直接驱动组件、reducer、hook 或 API adapter，并从 DOM、回调、请求 payload 或公开 state 观察结果。
- [ ] 删除的源码/CSS/文件布局与重复断言不留下当前聊天交互、状态或接口保护缺口。
- [ ] M14 Vitest、frontend build、`git diff --check` 与 changed-path scope 全绿。

## 测试策略

- 被测行为（来自退出标准）：附件上传/发送与失败反馈；会话列表、群管理、mention/slash、消息正文/复制/fork/分页/滚动；权限卡、工具过程与 token 指标；chat API payload；REST/WS reducer、workspace 与全局 toast 的实时收敛。
- 已有测试在：`src/IM/frontend/src/features/chat/**/*.test.{ts,tsx}`；本 milestone 只删改现有文件，不新建测试域或产品 helper。
- 落层/目录/marker：frontend Vitest/jsdom component、pure-state 与 mocked API adapter tests，marker：无；真浏览器 E2E 不属本 milestone。
- 可选依赖 importorskip：无（Node/Vitest workspace 依赖）。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；测试资产改造前后数量、命令与结果写入 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| 附件预览、移除、drop/upload payload 与错误映射 | `attachments/{attachment-chip,attachment-dropzone,use-attachment-upload}.test.*` | rewrite-merge | 保留真实 DOM 交互、上传请求与错误码；删除空 DataTransfer、私有 `data-*` 状态和自定义 Error 类形状等无独立用户风险断言；完整 drop/paste→send 仍由 workspace/pane 覆盖 | attachment tests + workspace attachment cases |
| bind 成功后 owner snapshot/cache 收敛且 token 不重复消费 | `bind-confirm-page.test.tsx` | rewrite-merge | 保留成功等待、失败可重试与换 token 结果；不把固定 query-key 数量/顺序当产品契约 | bind tests |
| canonical 文件名、legacy 缺席与源码 owner 文本 | `canonical-chat-architecture.test.ts` | delete | 只检查文件布局、历史符号和源码字符串；公开 API/mention/error 行为已有直接测试，当前无文件名契约 | M14 collection + API/mention tests |
| chat REST adapter 的鉴权、URL、payload、响应与错误 | `chat-api.test.ts` | keep | 直接保护前端公开 adapter 和 IM HTTP contract，是最低合适接口层 | chat-api tests |
| canonical WS payload、message/tool/permission/timeline state | `chat-stream-reducer.test.ts` | rewrite-merge | reducer 是最低状态 seam；合并 completion 字段、sender、permission 等同一事件的碎片断言，保留排序、幂等、discard 与 boundary 结果 | reducer tests |
| 页面级历史/实时/发送/附件/导航/恢复协作 | `chat-workspace.integration.test.tsx` | rewrite-merge | 保留跨 query、user-stream、pane 与 API 的连接风险；合并与 leaf component/reducer 重复的状态值、双向状态或 milestone 叙事断言 | workspace integration + leaf tests |
| 会话筛选、选择、未读与蒸馏交互 | `components/conversation-sidebar.test.tsx` | rewrite-merge | 保留用户操作和 disabled/selection 结果；删除 KindBadge/file-era 视觉终态与重复 avatar DOM 形状断言 | sidebar tests + workspace distill cases |
| 群成员增删改、失败与移动/桌面入口 | `components/group-settings.test.tsx`、`components/new-group-modal.test.tsx` | rewrite-merge | 保留群管理回调、错误/disabled 与移动入口；合并纯列表/close/头像实现形状等重复展示断言 | group component + workspace group cases |
| toast 内容、导航、dismiss 与用户流通知状态 | `components/in-app-toast.test.tsx`、`hooks/use-global-message-toast.test.tsx` | keep | component 与 hook 分别守 UI 操作和跨事件/authority 状态，没有更低层等价保护 | toast component/hook tests |
| mention 解析、候选选择与 wire/DOM 呈现 | `components/mention-parser.test.ts`、`mention-picker.test.tsx`、`message-pane.test.tsx` mention cases | rewrite-merge | parser/picker 保留协议和选择 seam；pane 只保留接入后的插入、发送与代表性 block rendering，不复测每种 Markdown 容器 | mention/parser/picker + pane cases |
| 原生 context menu、link 分类、整条/代码复制序列化 | `components/message-content-policy.test.ts` | rewrite-merge | 保留 current 输入模态、link 类型与复制协议；删除距离/时间常量边界、Text-node/CSS display 与同义 DOM 组合 | content policy + pane interaction cases |
| MessagePane 分页、滚动、发送、copy/fork、附件、权限与指标 | `components/message-pane.test.tsx`、`message-pane-fork.test.tsx`、`message-pane-memo.test.tsx` | rewrite-merge | 保留 current DOM/interaction 状态；删除 react-markdown 框架语义、TokenChip/PermissionCard 重复和同义 stale-promise/viewport 断言 | pane + dedicated leaf tests |
| toolbar 层级与 web-search 对比色的 CSS 源码正则 | `components/message-toolbar-priority.test.ts`、`tool-detail-search-contrast.test.ts` | delete | 静态扫描 CSS 文本/数值，既不渲染真实视觉也不保护行为；本 unit 无 UI delta，不新增伪视觉测试 | M14 collection + build |
| 权限卡展示、提交、拒绝理由与错误 | `components/permission-card.test.tsx` | rewrite-merge | 保留待决/提交/错误/理由的用户结果；合并逐按钮文案、两种 resolved decision 与同义 omit-reason cases | permission-card tests + pane mount case |
| slash 候选解析、聚合、键盘与 pane 接入 | `components/slash-candidates.test.ts`、`slash-picker.test.tsx`、`message-pane.test.tsx` slash cases | rewrite-merge | helper/picker 守最低逻辑和键盘 seam；pane 只证明打开与插入，不重复 filter/escape 规则 | slash helper/picker + pane cases |
| token 总量、阈值和缓存命中详情 | `components/token-chip.test.tsx`、`message-pane.test.tsx` token cases | rewrite-merge | TokenChip 拥有格式/阈值/详情；pane 只保留有/无指标的接线，不重复阈值 | token-chip + pane mount cases |
| 工具过程、摘要、图标、详情、失败、长输出与授权 | `components/tool-calls-panel.test.tsx` | rewrite-merge | 保留各 presenter 的用户可见差异；合并 running 参数、locale、长输出与 approval suffix 的同义组合，删除 class/行数等实现断言 | tool panel tests |
| Node chip 名称与 online/offline/null 展示 | `components/node-chip.test.tsx` | keep | 小型 leaf component 的三种公开输入产生不同可见结果，无更低层替代 | node-chip tests |

### 前端覆盖矩阵（本 milestone 无 UI delta）

用户路径分类：N/A（测试资产重构；不修改产品源码、样式或交互）。

| 状态 | 覆盖计划 |
|---|---|
| default | 保留 conversation/message/tool/attachment 基本渲染与操作 |
| loading | 保留历史加载、sending 与 permission pending |
| empty | 保留空聊天、无更早历史、无候选/成员等有 current 风险的空态 |
| error | 保留 attachment、permission、group、fork/API 错误反馈 |
| disabled | 保留发送中附件锁定、运行中蒸馏不可选和无 participant id 等状态 |
| submitting | 保留消息发送、权限提交、群管理 in-flight 结果 |
| permission denied | 保留 deny reason 与工具 denied 终态 |
| long content | 保留长工具输出与整条/代码复制结构 |
| missing/nullable data | 保留无 token usage、无 node、空 permission/attachment 等代表性结果 |
| mobile viewport | 保留 mobile header、composer Enter、More/fork 与 group fullscreen 接线 |
| desktop viewport | 保留 context menu、toolbar、分页与群 drawer 接线 |
| dark mode（如项目支持） | N/A；本 unit 删除不能证明真实视觉的 CSS 源码扫描，且无样式 delta |

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| chat 用户交互与状态 | 保留/收敛后的 Vitest DOM interaction/state regression | 是 |
| API/WS 接口适配 | adapter/reducer/workspace Vitest | 是 |
| 真实浏览器视觉与网络 | N/A；零 UI/product delta，不把本次测试清理升级为产品验收 | 否 |

Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — 删除静态扫描与叶子重复

- 状态: DONE
- 步骤: 删除三份源码/CSS/文件布局扫描；收敛 attachment、token、permission、sidebar/group 等 leaf tests 的私有形状和同义断言。
- 验证: 相关 leaf/component tests 与 M14 全量 Vitest 通过，源码扫描文件不再收集。

### R2 — 收敛消息与工具交互保护

- 状态: DOING
- 步骤: 合并 message-content、MessagePane、tool panel 中重复的 framework/CSS/常量边界/同义状态测试，保留 current interaction 与接口结果。
- 验证: content/pane/tool 定向 Vitest 与 M14 全量通过；保留 copy/fork/pagination/permission/tool/mention/slash 用户风险。

### R3 — 收敛状态协作并完成门禁

- 状态: TODO
- 步骤: 合并 reducer/workspace 中同一事件或 leaf behavior 的重复断言，复核 27-file 处置矩阵；rebase 最新 unit 后运行 M14、frontend build、docs/diff/scope 门禁。
- 验证: M14 与 frontend build 全绿；changed paths 仅 M14 chat tests 与本 milestone 文档。
