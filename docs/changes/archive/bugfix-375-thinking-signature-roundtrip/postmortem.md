# bugfix-375 复盘：与设计/spec 不一致的代码，为何当初成功 merge

> 范围：本文不重复 bug 的技术细节（见 `fix.md` / `design.md`），只回答一个流程问题——**这些与 design/spec 不一致的缺陷，当初是怎么通过 review 合进去的？** 这是本 unit 收尾时 owner 提出的复盘问题，独立成文以便后续避坑。

## 一、本 unit 一连串挖出的 bug

| # | bug | 与 design/spec 的不一致 | 落点 |
|---|---|---|---|
| 1 | auto_mode 安全门在 observe dispatch 里盲跑（空 transcript、白烧模型调用） | feat-333 design 明写"决策必须在 **TOOL_CALL intercept** 中完成"，实现却用 observe 默认注册 | #46 |
| 2 | `_strip_fork_conversation` 重建 HookContext 漏拷 `message_history` / `permission_requester` | design 要求 ctx 透传这些能力，手写重建丢了 | #46 |
| 3 | `_fork_locked` 重建 Message 漏拷 `reasoning_content` / `reasoning_signature`（fork 后会话不可用） | 同上反模式，fork 路径 | #44 (D) |
| 4 | `background_hook_ctx` 重建漏拷 `message_history` / `permission_requester` | 同上反模式 | #44 (M2) |
| 5 | fork 侧链不继承父执行上下文 → 安全门在 fork 里 `model_caller=None` 必 fail-close → self-evolution agent 处处碰壁 | CC（worker 继承 permissionContext）/ Hermes（review fork "uses the same auth"）都继承父 ctx，我们用裸默认 | #44 (M2) |
| 6 | self_improvement review prompt 是单薄意译，丢了 active 倾向 / 偏好阶梯 / 命名纪律 / do-not-capture 护栏 / 偏好嵌入 | feat-349 design 明写"**复刻 hermes 三件套**"，实现是意译 | #44 (M2) |
| 7 | `skill_manage` 缺 support files（references/templates/scripts/assets） | 调研 `hermes-reference.md §4` 记全了富技能模型，design L270 静默缩成单文件、无理由 | #49 |

## 二、为何当初能成功 merge —— 六条流程根因

### 1. 测试 mock 掉了 bug 所在的那条边界（最致命）
`tests/unit/test_auto_mode_gate_dispatch.py` 直接 `ctx.message_history = ()`、`ctx.call_model = AsyncMock(...)`——**从不走** `loop → registry.execute → dispatch_intercept → _strip_fork_conversation → on_tool_call` 那条真链。signature 测试跑在 mock 的 SSE 流上（本就没有真 signature）；fork 测试用 fake `context_fork`（不跑真 loop）。**bug 恰好住在被 mock 掉的那个接缝里**，所以"全绿"是假绿。

### 2. 验证是玩具级，真实失败面从没在合并前被触发
373 的 e2e 只有单次 `pwd && ls`。但：signature 缺失要**多轮深度**才发作；空 transcript 要**真实工具量 + observe 路径**才发作；fork 那几个要**真起一个 fork 跑真工具**才发作；持久化保真要**跨进程重启**才发作。这些真实路径在合并前**一次都没跑过**——玩具用例下每个 bug 都"恰好不致命"。

### 3. 复刻参考实现时信了二手笔记，没回原文
prompt 与 skill_manage schema 都标着"复刻 hermes"，但走的是 `hermes-reference.md`——它开头就自挂"⚠️ **未逐字亲验**"。worker 照摘要意译，丢了实质，**没人拿 Hermes 源码 diff 过**。（注：本 unit 修复时 agent 自己又意译了一版 prompt，被 owner 当场抓出"你忠实复刻了吗"——**同一个坑在同一个 unit 内踩了两次**。）

### 4. review 只比对"代码 vs design"，查不出 design 本身已偏离 spec/调研
#49 是典型：调研把 Hermes 富技能模型记全，**design 阶段静默缩成单文件、还不写理由**；实现忠实匹配了缩水的 design → PR review 通过。**缺陷被烤进了 design**，而 gate 只检查"代码对不对得上 design"，不回头比对"design 对不对得上调研/spec 意图"——设计层的静默砍因此一路绿灯。

### 5. 时间性 / 横切缺陷对"局部 diff review"天然隐形
手写逐字段重建，在**写下的那一刻是对的**（列全了当时所有字段）。bug 是后来 `message_history` / `reasoning_*` 加进 dataclass 时，**散落各处的多个旧重建点一起静默漏新字段**。审"加字段"那个 commit 的人不会去 grep 全仓所有重建点——local-diff review 看不见"这个新字段还要补到别处 N 个地方"。

### 6. 系统"碰巧能用"，把不一致也掩盖了
gate 注册成 observe 是错的，但旧机制"两种 dispatch 都跑全部 handler、只在 intercept 采纳返回值"让 gate 的 block **碰巧仍生效**。功能看着对、测试（mock ctx）也绿 → 没人发现注册模式错了。**能用 ≠ 对**，但"能用"足够骗过 merge。

## 三、最深层原因（一句话）

> **merge 的门槛是"单测绿"，而那套单测是按"局部 + mock + 玩具输入"建的；它与用户真正的使用方式（多轮 + fork + 跨重启 + 真模型）之间隔着一整条没人跨的鸿沟。**

于是：测试绿、review 看局部 diff 也挑不出、系统又碰巧能跑 → 一串与设计不一致的代码带着十足信心被合入。直到有人用**真实深度任务**去跑、并翻 **raw upstream-req 原始字节**，这些才第一次现形。

## 四、可操作的改进方向（避免重犯）

1. **禁止 mock 掉被测边界**：涉及 hook dispatch / ctx 透传 / 序列化 round-trip 的逻辑，至少有一条测试走真实链路（真 registry + 真 runner），不许直接 `ctx.field = ...` 灌值。
2. **关键路径要有"真实形态"验收**：thinking / fork / 跨重启 / 多轮工具，合并前必须有一次真 e2e（live 模型 + 翻 proxy raw 日志），玩具用例不算数。
3. **复刻参考实现 = 回原文 diff**：二手笔记只能定位行号；动手前读源码，复刻后逐条核对。reference 笔记必须标注"已逐字亲验 / 未亲验"。
4. **design gate 增一道"design vs spec/调研"回扣**：design-author 自检里显式核对"调研列出的能力，design 里每条有'用/改/不用 + 理由'的交代"——静默砍能力要被挡。
5. **不可变对象一律 `dataclasses.replace`**：手写逐字段重建列为反模式；加守卫测试，新增 dataclass 字段时若某复制点未透传即报警（本 unit 已落地 `test_message_jsonl_roundtrip_field_conservation_guard`）。
6. **派生上下文 = 复制父 + 只覆盖差异**：fork / 子 agent 的 ctx 必须从父 `replace` 派生，不许裸默认（本 unit M2 已落地 + 锁定测试）。
