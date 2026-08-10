# feat-440: 工具拒绝时回传给 LLM 的语义化反馈

## Relations

- Related: feat-434（approval UX redesign：建立 `approval=user_allow/user_deny` 信号 + 闸门区 已授权/已拒绝 徽标，本 unit 复用该 `approval` 信号区分用户拒 vs 自动拒，但不改其徽标呈现）
- Related: bugfix-410（引入 `reason_code="denied"` 徽标分类，本 unit 复用该信号，不改徽标）

## 原始需求

> 现在IM上如果用户拒绝了执行某个工具，llm会收到什么具体消息

（Agent 调查后答复：现状统一回传通用字面量 `tool blocked by hook`。用户随即指出问题：）

> 这个不对，tool blocked by hook是一个通用消息。llml没法知道是用户拒绝的。看看CC的做法

（Agent 列出 CC `src/utils/messages.ts` 的分场景拒绝消息后，用户确认方向：）

> 对，大方向对。如果适用的话，文本可以照搬。

## 澄清记录


- Q1: 回传文本要不要区分「用户主动拒绝」vs「系统/策略自动拒绝」两大类?
  A(原话): 对。
  Agent 解读: 区分两类。用户主动拒绝 → 让 agent 停下等用户指示;系统/策略自动拒(限流 / 分类器 / fail-closed / 工具自身规则 deny 等)→ 让 agent 可尝试其他工具或上报,但禁止恶意绕过。

- Q1.1（追问）: 为啥只说「参考语气」,CC 原文不能照搬吗,有区别吗?
  A(原话): 对。问下，为啥只参考语气，原文不可以吗，有点区别是吗
  Agent 解读: 主体句子可逐字照搬(REJECT_MESSAGE 主体 + AUTO_REJECT_MESSAGE 主体不含 CC 私有概念)。只有触到 CC 私有名词/机制的局部要本地化:① `new_string`(CC Edit 参数名,在括号举例里,可保留或换本项目参数名);② CC 的 don't-ask 模式、`settings` 权限规则机制本项目无对应,相关句子不照搬。定为原则「文本照搬 CC,私有名词处本地化」,逐字定稿留给 design。

- Q2: 要不要在本 unit 顺带给 IM 拒绝卡加「填理由」输入框,让拒绝理由拼进回传文本?
  A(原话): 可以加
  Agent 解读: 本 unit 范围纳入 IM 拒绝卡的理由输入框 + reason 透传到回传 LLM 的文本。输入框**选填**(默认假设,未经用户否决):不填理由直接拒 → 走默认 REJECT_MESSAGE 文本;填了理由 → 走 REJECT_MESSAGE_WITH_REASON_PREFIX + 用户原文。两种都要作为独立 Scenario。

- Q3: subagent(Task 派生子 agent)的工具调用被拒时,要不要用和主会话不同的措辞?
  A(原话): 要区分
  Agent 解读: 区分。subagent 路径被拒用 CC SUBAGENT_REJECT_MESSAGE 风格(「换个方法或向上报告限制」),不用主会话的「停下等用户指示」。系统/策略自动拒(AUTO_REJECT 风格,换工具/上报语气)对主/子皆适用,不另分。

- Q4: 拒绝理由输入框的交互形态——常驻显示 / 点拒绝后展开 / 不加?
  A(原话): A
  Agent 解读: 选 A。理由输入框**常驻**显示在权限卡按钮区上方,选填;点「拒绝」时若框内有内容就带上理由,留空则走默认 REJECT_MESSAGE。允许类决策忽略该框内容。

## 用户场景

agent 在 IM 上替用户干活时,经常会试图调一个需要用户点头、或被安全策略拦下的工具(改文件、跑命令等)。今天**无论哪种拒绝**,LLM 拿到的工具结果都是同一句通用字面量 `tool blocked by hook`。后果是 LLM 分不清这次"失败"到底是:

- **用户亲手按了「拒绝」**——它本该停下来、不要再换个姿势重试同一件事,而是问用户想怎么办;
- 还是**安全策略/分类器自动拦的**——它本该换个工具、换个做法或如实向用户报告这条限制。

由于信息被抹平成一句话,实际观察到的行为是:用户明明点了拒绝,agent 却换个参数又试一遍同一个操作,像没听懂"不要做"。这正是用户报的问题——"llm 没法知道是用户拒绝的"。

**变更后**,LLM 收到的拒绝结果按场景给出语义化文本(措辞照搬 Claude Code,触到 CC 私有名词处本地化):

- 用户在主会话拒绝 → 一句明确"用户不想执行此操作,先停下、不要绕过,等用户进一步指示"的话;
- 用户拒绝且在权限卡里填了理由 → 上面那句之后再附上用户的原话理由,LLM 据此调整;
- 安全策略/分类器自动拦下 → 一句"此操作被自动拦截"的话(附拦截原因),引导 LLM 换做法或上报,但不得恶意绕过;
- subagent 的工具被拒 → 一句让 subagent"换个方法或向上报告这条限制"的话,而不是主会话那种"停下等人"。

同时,IM 的权限卡按钮区上方常驻一个**选填**的理由输入框:用户想说明为什么拒绝时,直接填,点「拒绝」后这段理由会一并传给 LLM;不想填就留空直接拒,走默认文本。允许类按钮忽略该框。

用户最终能观察到的是:**点了拒绝后,agent 真的停下来征询而不是闷头重试;填了拒绝理由时 agent 会据此回应;遇到策略自动拦截时 agent 会换路子或如实说明,而不是卡死在同一句无意义的报错上。**

## 验收标准

### Requirement: 主会话用户拒绝回传语义化反馈

#### Scenario: 用户直接拒绝、未填理由
- **GIVEN** agent 在主会话发起一个需要授权的工具调用,权限卡处于待决态
- **WHEN** 用户点「拒绝」且理由输入框为空
- **THEN** LLM 后续行为体现为"已被用户拒绝、停下来征询用户"——不再以换参数/换姿势的方式重试同一操作,而是转向询问用户接下来怎么办

#### Scenario: 用户拒绝并填写了理由
- **GIVEN** agent 在主会话发起一个需要授权的工具调用,权限卡处于待决态
- **WHEN** 用户在理由输入框填入一段说明(如"先别动这个文件")后点「拒绝」
- **THEN** agent 的后续回应体现出它读到了该理由——按用户给出的理由调整下一步,而非走与空理由时完全相同的通用应答

### Requirement: 策略自动拦截回传语义化反馈

#### Scenario: 安全策略/分类器自动拦下工具调用
- **GIVEN** agent 发起一个被安全策略/分类器判定需要拦截的工具调用,且当前无用户逐次授权(自动拦截路径)
- **WHEN** 该工具调用被自动拒绝
- **THEN** agent 的后续行为体现为"遇到一条自动限制"——尝试换工具/换做法或如实向用户报告这条限制,而不是把它当成用户的主动拒绝停下等人

### Requirement: subagent 工具拒绝回传区分于主会话

#### Scenario: subagent 的工具调用被拒
- **GIVEN** 一个由 Task 派生的 subagent 在执行中发起被拒绝的工具调用
- **WHEN** 该调用被拒
- **THEN** subagent 的后续行为体现为"换个方法或向上层报告这条限制",而不是主会话那种"停下来等用户指示"

### Requirement: IM 权限卡常驻选填理由输入框

#### Scenario: 待决权限卡展示理由输入框
- **GIVEN** 一张处于待决态的权限卡显示「允许 / 本会话内允许 / 拒绝 / 总是允许」按钮
- **WHEN** 用户查看该卡片
- **THEN** 按钮区上方常驻一个选填的理由输入框,留空亦可正常做任意决策

#### Scenario: 选择允许类决策时忽略理由框
- **GIVEN** 待决权限卡的理由输入框中已有文字
- **WHEN** 用户点「允许 / 本会话内允许 / 总是允许」中的任一个
- **THEN** 该工具被照常放行,理由框内容不产生任何可观察影响

## 范围与非目标

- 在范围：
  - 把 LLM 收到的工具拒绝结果从通用 `tool blocked by hook` 改为按"用户主动拒 / 策略自动拒 / subagent 被拒"三类区分的语义化文本(措辞照搬 CC,私有名词处本地化)。
  - 用户主动拒时,把用户在权限卡填写的选填理由透传进回传文本。
  - 在 IM 权限卡按钮区上方新增一个常驻、选填的拒绝理由输入框。
- 非目标：
  - 不改 IM 权限卡上"已授权 / 已拒绝"徽标的呈现(那是 feat-434 / bugfix-410 的范围)。
  - 不新增"限流"等本项目当前不存在的拒绝类别;只覆盖现有的用户拒 / 自动拒 / subagent 路径。
  - 不改变授权的判定逻辑本身(谁该被拦、分类器怎么判),只改被拦后回传给 LLM 的文本与 IM 的理由采集。
  - 拒绝文本的逐字定稿(CC 原文在何处本地化、参数名 `new_string` 是否替换)留给 design 阶段拍板,不在本 spec 钉死。

## CC 参考文本（实现素材，交接 design）

> 用户确认"文本照搬 CC,私有名词处本地化"(见 Q1.1)。以下从 CC `src/utils/messages.ts`(行号为参考项目当前快照)摘录原文,**作为 design 逐字定稿的素材,不是本 spec 的验收标准**——验收只看上面 Scenario 里描述的用户可观察行为。

CC 的关键做法:**按"谁拒的、怎么拒的"分多条消息常量/构造函数,而不是一句通用话**。本 unit 复刻这套分场景思路,落到本项目已有的 `approval` / `reason_code` 信号上(`approval=="user_deny"` → 用户拒;否则自动拒;subagent 上下文 → subagent 版)。

主会话用户拒绝(对应本项目 user_deny 路径):

```
# REJECT_MESSAGE（无理由）
The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). STOP what you are doing and wait for the user to tell you how to proceed.

# REJECT_MESSAGE_WITH_REASON_PREFIX（有理由，其后拼接用户原文）
The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). To tell you how to proceed, the user said:\n
```

subagent 路径被拒(对应 Q3,语气换成"换做法/上报"而非"停下等人"):

```
# SUBAGENT_REJECT_MESSAGE（无理由）
Permission for this tool use was denied. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). Try a different approach or report the limitation to complete your task.

# SUBAGENT_REJECT_MESSAGE_WITH_REASON_PREFIX（有理由）
Permission for this tool use was denied. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). The user said:\n
```

策略/分类器自动拒(对应本项目 auto block 路径,含共用的"善意绕过 vs 恶意绕过"指引):

```
# AUTO_REJECT_MESSAGE(toolName)
Permission to use ${toolName} has been denied. ${DENIAL_WORKAROUND_GUIDANCE}

# DENIAL_WORKAROUND_GUIDANCE（共用尾句，自动拒类附在后面）
IMPORTANT: You *may* attempt to accomplish this action using other tools that might naturally be used to accomplish this goal, e.g. using head instead of cat. But you *should not* attempt to work around this denial in malicious ways, e.g. do not use your ability to run tests to execute non-test actions. You should only try to work around this restriction in reasonable ways that do not attempt to bypass the intent behind this denial. If you believe this capability is essential to complete the user's request, STOP and explain to the user what you were trying to do and why you need this permission. Let the user decide how to proceed.

# 分类器拒（带原因，本项目自动拒的 reason 走这里）— buildYoloRejectionMessage(reason)
Permission for this action has been denied. Reason: ${reason}. If you have other tasks that don't depend on this action, continue working on those. ${DENIAL_WORKAROUND_GUIDANCE} <规则提示句>
```

design 阶段需本地化/裁剪的点(Q1.1):
- `new_string` 是 CC 的 Edit 参数名(仅出现在括号举例里),可保留或换本项目对应参数名;
- CC 的 don't-ask 模式(`DONT_ASK_REJECT_MESSAGE`)、`settings` 权限规则 / `Bash(...)` 规则提示句,本项目无对应机制,相关句子不照搬,自动拒尾部的"规则提示句"按本项目实际能力裁剪或省略;
- 上述常量在本项目落点(哪个函数构造、`approval`/`reason_code`/subagent 上下文如何映射到选哪条文本、用户理由如何从 IM 透传到 prefix 后)由 design 拍板。
