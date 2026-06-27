# feat-430: IM slash skill picker

## Relations

无外部依赖。本 unit 为 IM 前端新增 slash picker，并需 SDK/kernel/gateway/IM 链路补 skill location 只读字段（详见 design 阶段交接）。

## 原始需求

> 你使用change-spec-author skill。在/Users/czj/Repos/nano-multiagent/，帮我分析，当前我们的IM无法输入“/”弹出所有该agent对话的skill，然后上下选择。你看看openclaw的是有的吧。我想加这个功能

## 澄清记录

- Q1: 这个 picker 里的"skill"具体指什么来源？是当前 agent 的 capabilities.skills 列表，还是 agent config 里已启用的 skills 白名单，又或者是其他？
  我的推荐：用当前会话 agent 的 capabilities.skills 列表作为候选。
  A(原话): 指的是当前对话的这个 Agent 他开启了的那些 Skill。
  Agent 解读: 候选来源应为当前对话 agent 已启用的 skills 白名单（agent config 里的 skills），而不是 capabilities 里全部可选技能。

- Q2: 用户选中的 skill 怎么落到消息里——是替换成 slash command 文本，还是插入某种标记？
  我的推荐：仿 openclaw 选中后补成 `/skill-name `，作为普通文本消息发送。
  A(原话): 好问题。对比下CC的和openclaw的做法
  Agent 解读: 用户没有直接选 A/B，要求我先对比 Claude Code 与 openclaw 的做法后再决定。

- Q3: 我们更接近哪种 slash 处理方式？A) 轻量 openclaw 型（补 `/skill-name` 文本，普通消息发送，不新增内核解析）；B) Claude Code 型（前端识别 slash，生成 meta 消息或专门流程触发 skill）。
  我的推荐：A，纯前端改动，不碰协议和 IM 后端。
  A(原话): （无直接答复；用户听完对比后进入 Q4）
  Agent 解读: 用户未明确选择 A/B，但后续讨论继续沿"补 slash 文本"方向扩展，未要求新增内核解析或消息类型。

- Q4: picker 候选是否只包含 skills，还是要同时包含 commands（如 stop）？如果包含 commands，commands 从哪里来？
  我的推荐：候选拆成两类——当前 agent 已启用的 skills + IM 前端内置本地命令（如 stop/new/reset/clear）。
  A(原话): 对的
  Agent 解读: 用户确认 picker 同时包含 skills 和 commands；commands 首期指本地内置命令。

- Q5: picker 在哪种会话里可用？单聊还是群聊也要能用？
  我的推荐：只在对 agent 的单聊里可用。
  A(原话): 其实我想要群聊也能用，这就得细化一下，思考一下，在群聊里面怎么定义这个产品逻辑。~/Repos/opensource-hub/clowder-ai也有群聊的概念，参考下
  Agent 解读: 用户希望群聊也能用，要求参考 clowder-ai 的群聊逻辑后再设计。

- Q6: 群聊里 @ 多个 agent 后输入 `/`，picker 该怎么表现？
  我的推荐：取最后一个 @agent 的 skills/commands。
  A(原话): 我觉得这样，command要分群聊能用的 还是群聊不适用的，比如/ stop，这种呢，就都在正常的时机发给每个agent，就像普通文字一样，然后幂等，在运行的真正受到了/stop。有的可能是不适用的。然后skill呢，就是整个群聊的所有agent的可用skill全集。都可/。都在正常的时机发给每个agent，就像普通文字一样。也是跟普通文字一样，是否按照skill做，是按照agent理解，用户是不是再跟他说，如果他觉得是跟他说，他就按skill做。
  Agent 解读: 群聊 slash 采用"广播 + 接收方自解释"模型：
  - commands 分"群聊适用"与"群聊不适用"两类；群聊适用的 command（如 /stop）像普通文字一样发给每个 agent，由真正在运行的 agent 执行（幂等）。
  - skills 取群内所有 agent 已启用 skills 的并集，都可 `/`；选中后作为普通文字发给每个 agent，各 agent 自行判断是否响应。

- Q7: 同名 skill 在群聊 picker 里怎么展示？
  我的推荐：同名 skill 合并成一个 `/skill-name`。
  A(原话): 不对，得看是不是真一个路径的skill。如果是就合并。然后群里/选skill的时候能看到每个skill是来自哪些agent
  Agent 解读: skill 按文件路径（location）区分同一性：同路径合并，不同路径即使同名也分开显示；picker 里每个 skill 要展示它来自哪些 agent。

- Q8: 现在系统里有哪些已有的 slash command？
  A(原话): 啥意思，现在不是有/stop吗？
  Agent 解读: 经核查，Gateway 已支持用户输入 `/stop`（及 `@agent /stop`、`/stop @agent`）中断当前 run；agent 内核已支持 `/skill:name` 触发 skill。但 IM 前端目前没有 slash picker，也没有 `/new`、`/reset`、`/clear` 等其他命令。

- Q9: 既然 commands 是已有的，本期 commands 做哪些？skill 选中后补什么格式？
  我的推荐：commands 首期只做 `/stop`；skill 选中后补 `/skill:name `。
  A(原话): 如果没有其他slash command，就只做 /stop和skill的。/skill:name 还是 /name ，/skill:name 吧
  Agent 解读: 本期 picker 只包含 `/stop` 命令和当前 agent(s) 已启用的 skills；选中 skill 后在输入框补 `/skill:name `，与现有内核 `rewrite_skill_command` 对齐。

- Q10: 前缀过滤时，`/stop` 这类命令要不要也跟着被过滤掉，还是始终显示？
  A(原话): A：你说的对
  Agent 解读: 采纳推荐 A——命令与 skill 一视同仁参与前缀过滤，输入 `/pr` 时不匹配前缀的 `/stop` 不显示，不再"命令始终显示"。

- Q11(design grounding 暴露的范围矛盾，回填本段)：design 阶段调研后端发现，群聊里 `/stop`、`/skill:name` 现在后端处理不了三处缺口（① picker 补的 `@agent:xxx /stop` 因 wire 前缀 strip 不净匹配失败；② 群聊裸 `/stop` 被 MENTION 投递策略丢弃；③ 群聊消息加 `[用户名] ` 前缀致 `rewrite_skill_command` 行首正则不匹配）。这与"群聊命令生效"的验收标准冲突于原非目标"不改后端解析"。问用户范围方向。
  A(原话): 用户在范围决策中选择"扩范围，修后端缺口"。
  Agent 解读: 本 unit 范围扩大为前后端一起改——一并修复群聊 `/stop`、`/skill:name` 在既有解析链上的识别缺口，让群聊命令真生效；这些缺口本就是 bug。原非目标"不改后端解析"作废，范围/非目标段据此修订（见下）。

- Q12: 群聊里 agent 可被设为"仅被 @ 才响应"（MENTION 投递策略），裸 `/stop`（不 @ 任何人）现在会被这个策略丢弃。`/stop` 要不要无视这个设置一律生效？
  A(原话): 明确下，不管群里的agent设置了是不是@才生效，裸的"/stop"都得生效
  Agent 解读: `/stop` 是控制命令，投递必须优先于 / 绕过群聊 MENTION 投递策略——无论群里各 agent 是否设为"仅 @ 才响应"，用户发裸 `/stop` 都要送达群内正在运行的 agent 并使其停止（幂等，不在运行的忽略）。这是对群聊 `/stop` Scenario 的强化，落成独立边界 Scenario。

## 用户场景

小林在 IM 里打开了一个对 `code-reviewer` agent 的单聊会话，想让它用特定的 skill 审一段代码。他在输入框里敲下 `/`，输入框上方立刻弹出一个候选面板：最上方是 `/stop`，下面列出 `code-reviewer` 当前已启用的 skills，如 `pr-review`、`tdd-execution-worker`，每个 skill 带有一行简短描述。小林用方向键上下移动，选中 `pr-review`，回车后输入框变成 `/skill:pr-review `，他继续粘贴代码并发送。`code-reviewer` 识别到 `/skill:pr-review` 后按 skill 流程执行。

切换到群聊后，群里同时有 `code-reviewer` 和 `test-writer` 两个 agent。小林敲 `/`，面板里出现所有群成员 agent 已启用 skills 的并集；同名但来自不同 agent 的 skill 会分开显示，并在每一行标注它来自哪些 agent。`/stop` 也出现在面板里。小林选中某个 skill 后，消息作为普通文本发到群里，两个 agent 各自判断是否响应。

当某个 agent 没有启用任何 skill，或小林输入 `/xyz` 没有任何匹配时，面板显示空态提示，不阻塞他继续输入普通文字。

## 验收标准

### Requirement: 输入 `/` 弹出 slash 候选面板

#### Scenario: 单聊里敲 `/`
- **GIVEN** 用户正在一个对 agent 的单聊会话中
- **WHEN** 用户在输入框输入 `/`
- **THEN** 输入框上方弹出 slash 候选面板，包含 `/stop` 和当前 agent 已启用的 skills

#### Scenario: 群聊里敲 `/`
- **GIVEN** 用户正在一个包含多个 agent 的群聊会话中
- **WHEN** 用户在输入框输入 `/`
- **THEN** 面板包含 `/stop` 和所有群成员 agent 已启用 skills 的并集

#### Scenario: 输入框中间出现 `/` 不触发
- **GIVEN** 用户已经在输入框里输入了 `hello`
- **WHEN** 用户继续输入 `/world`
- **THEN** slash 候选面板不弹出

### Requirement: slash 面板支持键盘导航与选中

#### Scenario: 用方向键选择并回车确认
- **GIVEN** slash 面板已打开且有多个候选
- **WHEN** 用户按 `ArrowDown` 移动高亮，再按 `Enter`
- **THEN** 输入框内容变为当前高亮项对应的 slash 文本，面板关闭，输入框保持焦点

#### Scenario: 按 Esc 关闭面板
- **GIVEN** slash 面板已打开
- **WHEN** 用户按 `Escape`
- **THEN** 面板关闭，输入框里的 `/` 保留，用户可继续输入普通文字

### Requirement: skill 选中后补成正确的 slash 格式

#### Scenario: 选中 skill 后补 `/skill:name `
- **GIVEN** 单聊里 slash 面板打开了，当前 agent 启用了 `pr-review` skill
- **WHEN** 用户选中 `pr-review`
- **THEN** 输入框变为 `/skill:pr-review `，光标在末尾，等待用户继续输入

### Requirement: 群聊 skills 按 skill 实际路径区分同一性并标注来源

#### Scenario: 同路径 skill 合并显示
- **GIVEN** 群聊里两个 agent 都启用了同一路径的 `pr-review` skill
- **WHEN** 用户输入 `/`
- **THEN** 面板里只出现一行 `pr-review`，并显示它来自这两个 agent

#### Scenario: 不同路径的同名 skill 分开显示
- **GIVEN** 群聊里两个 agent 各有一个同名但路径不同的 `pr-review` skill
- **WHEN** 用户输入 `/`
- **THEN** 面板里出现两行 `pr-review`，每行标注各自的来源 agent

### Requirement: slash 面板支持前缀过滤

#### Scenario: 输入 `/pr` 过滤出匹配的 skill
- **GIVEN** 单聊里 agent 启用了 `pr-review`、`tdd-execution-worker`、`log-cleanup` 三个 skills，且命令 `/stop` 存在
- **WHEN** 用户在输入框输入 `/pr`
- **THEN** 面板只显示前缀匹配的 `pr-review`；不匹配前缀的 `/stop` 与其他 skill 都不显示（命令与 skill 一视同仁参与前缀过滤）

#### Scenario: 输入 `/xyz` 无匹配
- **GIVEN** 单聊里 agent 启用了 `pr-review` skill
- **WHEN** 用户在输入框输入 `/xyz`
- **THEN** 面板显示空态提示，提示用户没有匹配的 slash 项

#### Scenario: 编辑已补入的 `/skill:` 文本时重新过滤纠错
- **GIVEN** 输入框里已是 `/skill:doc`（之前选中 skill 补入），picker 已关闭
- **WHEN** 用户删除末尾字符改成 `/skill:d`
- **THEN** picker 重新弹出，把 `d` 当作 skill 前缀过滤出匹配的 skills（如 `doc`），用户可重新选中纠正（不会因为 `/skill:` 前缀而匹配落空）

### Requirement: 发送后行为与普通消息一致

#### Scenario: 选中 skill 后继续输入并发送
- **GIVEN** 用户已把输入框内容变成 `/skill:pr-review 请 review 这段代码`
- **WHEN** 用户按 Enter 发送
- **THEN** 消息作为普通用户消息出现在聊天流中，agent 按既有规则处理 `/skill:` 前缀

#### Scenario: 群聊里发送 `/stop`
- **GIVEN** 群聊里某个 agent 正在运行
- **WHEN** 用户从 slash 面板选中 `/stop` 并发送
- **THEN** 当前正在运行的 agent 收到后停止其当前 run

#### Scenario: 群聊里裸 `/stop` 不受 agent "仅 @ 才响应" 设置影响
- **GIVEN** 群聊里某个 agent 被设为"仅被 @ 才响应"，且它正在运行
- **WHEN** 用户发送裸 `/stop`（不 @ 任何 agent）
- **THEN** 该 agent 仍然收到 `/stop` 并停止其当前 run（`/stop` 投递优先于群聊 @ 投递策略）

#### Scenario: 群聊里 `/stop` 对未在运行的 agent 幂等
- **GIVEN** 群聊里有 agent 当前没有正在运行的 run
- **WHEN** 用户发送 `/stop`
- **THEN** 这些 agent 不受影响（无报错、无副作用），只有正在运行的 agent 被停止

## 范围与非目标

- 在范围：
  - IM 前端在单聊和群聊的 composer 中实现 `/` 触发的 slash picker。
  - picker 展示 `/stop` 命令和 agent 已启用的 skills。
  - 单聊 skills 来源为当前会话 agent 的已启用 skills。
  - 群聊 skills 来源为所有群成员 agent 已启用 skills 的并集；同路径 skill 合并，不同路径同名 skill 分开。
  - 键盘导航（上下、Enter、Esc）、前缀过滤、空态提示。
  - 选中 skill 后在输入框补 `/skill:name `。
  - 修复群聊 `/stop`、`/skill:name` 在既有后端解析链上的识别缺口，使其在群聊真生效（详见 design）：
    - gateway 能识别 picker 补入的 wire mention 形式的 `/stop`；
    - 群聊裸 `/stop` 不论各 agent 是否设为"仅 @ 才响应"都投递并生效（送达群内 agent，正在运行的停止、未运行的幂等忽略）；
    - 群聊消息的 sender 前缀不再阻断 `/skill:name` 重写。
  - 后端补 skill `location` 只读字段全链路透传（SDK→kernel→gateway→IM capabilities API→前端），用于群聊按真实路径区分同名 skill 并标注来源。

- 非目标：
  - 新增 `/stop` 以外的其他本地命令（如 `/new`、`/reset`、`/clear`）。
  - 改变 `/stop` 的中断机制本身、`/skill:name` 重写后的目标语义、以及单聊既有命令行为（本 unit 后端改动只补群聊识别缺口与 location 字段，不动这些既有行为）。
  - 引入新的 wire 格式、消息类型或聊天消息协议字段（`location` 是 capabilities API 的只读响应字段，不属聊天 wire/消息协议）。
  - 在 picker 中执行命令（所有 slash 都只是补文本到输入框，发送后由后端按既有规则处理）。
