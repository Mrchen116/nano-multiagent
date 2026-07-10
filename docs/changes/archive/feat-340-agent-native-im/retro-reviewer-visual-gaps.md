# Retro: 16 轮 reviewer 验收仍漏掉明显视觉差距 — 根本原因分析

> 记录时间: 2026-05-13
> 触发人: 用户亲自 side-by-side 对比原型 vs 实现后提出

## 现象

Round 16 reviewer 给出 verdict `pass`，但用户在浏览器中实际查看时立即发现以下差距（均在原型代码中有明确对应）：

| # | 差距 | 原型位置 | 实现位置 | 严重程度 |
|---|---|---|---|---|
| 1 | UserMenu 下拉菜单项缺左侧图标（账户👤、节点🖥、语言文、退出登录↗） | `im-mypage.jsx` | `user-menu.tsx` | 明显 |
| 2 | UserMenu Nodes subtitle 为静态 i18n 文本（"资料与网关"），非动态计数 | `im-mypage.jsx` | `user-menu.tsx` | 明显 |
| 3 | UserMenu 语言行布局错误（"语言 │ EN │ 中" vs 原型左标签右切换） | `im-mypage.jsx` | `user-menu.tsx` | 明显 |
| 4 | UserMenu 退出登录缺 ↗ 图标、红色样式不对 | `im-mypage.jsx` | `user-menu.tsx` | 明显 |
| 5 | Agent message bubble 头像消失（背景色不生效） | `im-components.jsx` | `message-pane.tsx` | 严重 |
| 6 | TokenChip 在气泡外部而非内部 | `im-components.jsx` | `message-pane.tsx` | 明显 |
| 7 | Chat header 头像与标题布局偏差 | `im-chat-page.jsx` | `chat-workspace-page.tsx` | 中等 |

## 根本原因分析

### 根因 1: reviewer 验收视角严重偏离 UI 细节

change-reviewer skill 要求 reviewer 从"用户可观察"角度验收，但实际执行中 reviewer 的精力分配严重偏向功能通路验证：
- WS 连接是否正常
- 消息能否发送/接收
- API 是否返回正确数据
- 页面能否加载

对 UI 细节（图标缺失、subtitle 内容、布局方向、颜色值）只做"扫一眼"级别的检查，没有逐元素核对。

### 根因 2: 原型代码未进入 reviewer 的验收路径

虽然 M26/M27 的 worker prompt 强制要求"修改前必读原型代码"，但 **reviewer 的 prompt 中没有同等要求**。reviewer 验收时：
- 不打开 `attachments/prototype/project/im-*.jsx` 文件
- 不做 prototype-vs-actual 逐项元素对照
- 只依赖截图"目测"判断

结果是：原型中明确存在的元素（如 UserMenu 图标）在实现中缺失，reviewer 根本注意不到。

### 根因 3: 验收标准"近/精"过于模糊

viewport 评级表定义：
- **精**: 与原型像素级一致
- **近**: 结构对齐，有 minor 差距
- **偏**: 明显偏离

但 reviewer 连续多轮给出 "9/9 近" 并认为这足以 pass，而用户的实际标准是"和原型完全一致"。这个语义差距从 M19 开始持续到 M27，从未被纠正。

### 根因 4: worker 的"原型对照检查表"流于形式

M22 起每个 worker 的 exit criteria 都要求 `progress.md` 附"原型对照检查表"，但实际执行中：
- worker 只列出自己修改的部分，不检查未修改的部分
- 检查表是 worker 自评，不是独立第三方验证
- 没有要求 worker 用 DOM  inspector 逐项确认原型中的元素在实现中存在

### 根因 5: orchestrator 调度失职

作为 orchestrator，在派发 reviewer 时：
- 只透传 design.md 已有的验收语
- 没有明确要求 reviewer "必须打开原型代码文件，逐项列出原型中的 UI 元素"
- 没有将源码对比 agent 的报告作为 reviewer 的前置输入
- 对 reviewer 报告中的 "9/9 近" 没有追问"为什么不是 9/9 精"

## 影响

- **时间成本**: M19-M27 共 9 个 fix milestone、16 轮 reviewer 验收，大量时间花在功能通路验证上，UI 差距反复遗漏
- **信任成本**: 用户亲自发现 reviewer 漏掉的问题，对自动化验收流程的信任下降
- **代码成本**: 多轮修改累积了大量"补漏"式 commit，而非一次性对齐原型

## 改进建议（供后续 unit 参考）

1. **reviewer 验收前置条件**:  reviewer 开始前必须先跑源码对比 agent，对比报告作为验收输入
2. **原型对照检查表 reviewer 版**: reviewer 必须逐项打开原型代码中的每个组件/页面，列出原型中存在的视觉元素，逐一检查实现中是否存在
3. **验收标准量化**: "精"的定义从"像素级一致"改为"原型中每个可见元素在实现中都有对应，且样式值（颜色/圆角/间距/字号）偏差 < 5%"
4. **用户亲自验收作为最终 gate**: reviewer pass 后，orchestrator 必须提醒用户"请亲自打开页面看一下"，作为最终确认
5. **worker 修改范围强制要求**: worker 修改任何 UI 文件时，必须同时修改对应的原型对照检查表，且检查表必须由独立 agent 复核

## 相关文件

- 原型: `attachments/prototype/project/im-mypage.jsx`
- 原型: `attachments/prototype/project/im-components.jsx`
- 原型: `attachments/prototype/project/im-chat-page.jsx`
- 实现: `src/IM/frontend/src/app/shell/user-menu.tsx`
- 实现: `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx`
- 实现: `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx`
