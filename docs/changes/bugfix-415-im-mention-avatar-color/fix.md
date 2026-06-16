# bugfix-415: @mention 候选 / 新建群聊 agent 头像颜色与其他界面不一致

## Relations

- Closes: #108
- Related: PR #67（commit `0a7e0628`，建立 `colorForAgent`/`colorForAgentSeed` 头像取色单一真源）

## 原始报告

> 见 GitHub issue #108：https://github.com/Mrchen116/nano-multiagent/issues/108
>
> 两处 agent 列表的头像颜色与系统其他地方（chat sidebar、会话头、消息气泡、设置页 agent 列表/详情）**对不上同一个 agent**：
> 1. **@mention 候选 picker**（群聊里 @ 时弹出的 agent 候选列表）
> 2. **新建群聊的 agent 选择列表**
>
> 根因：这两处调 `Avatar` 时不传 `color`，于是 Avatar 回退到 `colorForAgentSeed(initials)`——而 `initials` 是截断后的 2 字符，不是完整 `display_name`，hash 不同→色相不同。
> PR #67 当年建立单一真源时改了 6 个文件，但漏改了 `mention-picker.tsx` 和 `new-group-modal.tsx`。

## 现象 / 复现

同一个 agent 在不同界面被渲染成**不同颜色**，用户无法靠颜色把它认成同一个 agent。

复现路径（两处各一条）：

1. **@mention 候选 picker**
   - 进入一个群聊会话 → 在输入框敲 `@` 弹出 agent 候选列表
   - 对照同一个 agent 在 chat sidebar 行 / 会话头 / 它发的消息气泡里的头像颜色
   - 候选列表里该 agent 的头像底色与别处**不一致**

2. **新建群聊的 agent 选择列表**
   - 打开「新建群聊」弹窗 → 看到可选 agent 列表
   - 对照同一个 agent 在设置页 agent 列表/详情、chat sidebar 里的头像颜色
   - 弹窗里该 agent 的头像底色与别处**不一致**

只要 agent 的 `display_name` 长度 > 2，或其前 2 字符与完整名字 hash 出的色相不同（绝大多数情况），就必现。两处头像之间、以及与其它界面之间三方都对不上。

## 根因

**直接原因**：两个调用点调 `Avatar` 时不传 `color`，触发了 Avatar 的「按 initials 取色」回退，而 initials 是截断后的 2 字符，与系统其它界面用的「完整 display_name」种子不同。

- `src/IM/frontend/src/features/chat/v2/components/avatar.tsx:48` — `const bg = color ?? colorForAgentSeed(initials);`（无 color 时回退到 initials 当种子）
- `src/IM/frontend/src/features/chat/v2/components/mention-picker.tsx:89` — `<Avatar initials={c.initials} size={26} />`（不传 color；`c.initials` 已是截断值）
- `src/IM/frontend/src/features/chat/v2/components/new-group-modal.tsx:105` — `<Avatar initials={a.display_name.slice(0, 2)} size={30} status={a.status} />`（不传 color；种子被显式截成 2 字符）

系统其它界面（chat-workspace / conversation-sidebar / message-pane / 设置页 list+detail）都通过 `colorForAgent({display_name})` 取色，种子是**完整 display_name**。两处漏接真源，种子从「完整 display_name」变成「2 字符」→ hash 不同 → oklch 色相不同 → 同一 agent 颜色不一致。

**原始设计意图与必须保住的不变量**（来自 `avatar.tsx:1-15` 的 docstring，PR #67 建立）：
> 同一个 agent 必须在所有出现处（设置页列表/详情、chat sidebar、会话头、消息气泡）渲染相同的头像颜色。种子**必须用 `display_name`**——因为它是唯一在所有界面都拿得到的标识：消息气泡只携带 `sender_user_id`，没有 `agent_id`；若按 `agent_id` 取色，气泡会与 sidebar/header 不同色。

修复必须保住这条不变量：**颜色种子用完整 `display_name`，所有调用点共用同一取色逻辑**。本 bug 的修复方向就是让这两处也接入真源（传 `color={colorForAgent({ display_name, agent_id })}`），而不是另立一套取色。

**为什么这种错能进来**：`Avatar` 组件把「无 color 时按截断 initials 取色」作为**默认回退**，等于给每个调用点埋了「忘传 color 就色偏、且不报错」的隐性坑。PR #67 建立真源时手工逐个改调用点，漏掉这两个新增/未覆盖的调用点也不会有任何编译或测试报警——这是同类问题的遗漏面，不是新引入的回归。
