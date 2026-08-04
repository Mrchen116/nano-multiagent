# bugfix-499: Lark skill bundle for Feishu agents

## Relations

- Related: feat-447

## 原始报告

> [`src/personal_assistant/builtin_skills/feishu-doc/SKILL.md`](/Users/czj/Repos/nano-multiagent/src/personal_assistant/builtin_skills/feishu-doc/SKILL.md)我觉得完全就不对了，应该考虑把全局的飞书skill弄过来，如果不适用的再改掉。

## 澄清记录

- Q1: Feishu 绑定 agent 默认应自动获得多大范围的 Lark 能力？
  A(原话): 很适合啊。我理解lark cli这些能力都能给他用
  Agent 解读: Feishu 绑定 agent 默认应获得完整的、可在其运行环境使用的 `lark-cli` Lark skill 集合；不只限于文档能力。

- Q2: Feishu 中用户让 agent 执行 Lark 操作时，操作应使用谁的身份？
  A(原话): 我觉得可以
  Agent 解读: Feishu agent 沿用全局 Lark skills 的默认 `--as user` 语义，使用 Gateway 机器上 `lark-cli auth login` 登录的用户身份；不随入站消息发送者切换身份。

- Q3: 本次是否以核对全局 Lark skills 与 PA/Feishu 产品的明显冲突为主，能沿用的能力尽量沿用？
  A(原话): 主要是看全局skill有什么明显跟我们产品冲突的地方
  Agent 解读: 不预设缩小 Lark 能力范围；先识别与 PA/Feishu 现有产品职责冲突的部分，仅为这些冲突做产品适配或边界处理。

- Q4: 是否保留 `lark-im` 给 agent 使用，但规定当前 Feishu 会话的正常回复仍只走 Gateway；只有用户明确要求操作另一段 Lark 聊天时，才用 `lark-im` 直接发消息？
  A(原话): 对
  Agent 解读: `lark-im` 可用于用户明确指定的其他 Lark 聊天操作；当前触发 run 的 Feishu 聊天继续由 Gateway 按既有回复、镜像和控制事件链路统一处理。

- Q5: `lark-event` 是否应保留给 Feishu agent，用于用户明确要求的独立监听/自动化，而不接管普通 Feishu 对话回复？
  A(原话):
  > 那没问题吧，我觉得。lark-event是一个skill吗
  >
  > ok，还有要对齐吗
  Agent 解读: `lark-event` 作为全局 Lark skill 随 bundle 提供；它仅在用户明确要求监听/自动化时运行，普通 Feishu 对话回复继续由 Gateway 处理。

- Q6: `lark-vc-agent` 是否原样保留其规则：真实应用机器人入会/离会使用 `--as bot`，个人会议查询仍按其现有规则使用 user 或 bot 身份？
  A(原话): 不用改。
  Agent 解读: `lark-vc-agent` 不为 PA 改写身份语义，沿用全局 skill 的现有 user/bot 规则。

- Q7: 旧版本已安装或已写进 agent skills 列表的 `feishu-doc`，升级后是否自动迁移或清理？
  A(原话): 旧的不管了。还没上线呢，不用考虑。
  Agent 解读: 本期不处理旧 `feishu-doc` 的安装目录或已有 agent 配置的迁移兼容；以尚未上线的目标状态为准。

## 用户场景与现状痛点

用户在飞书中与绑定的个人助手对话，不只会要求创建或读取文档，也会要求管理云盘、表格、日程、任务、审批、邮件、知识库、会议和其他 Lark 资源。用户期望这个助手能沿用本机全局 Lark skills 已经提供的能力与交互，而不是只看到一份过时的“飞书文档”说明。

现在，飞书绑定 agent 被自动赋予 `feishu-doc`。它指导 agent 调用 `feishu-cli`；当前运行环境提供的是 `lark-cli`，没有 `feishu-cli`。即使同一台机器已有完整的全局 Lark skills，PA 的运行态也不会发现它们。用户在飞书中提出相应请求时，助手无法可靠完成操作或给出当前正确的授权路径。

## 目标状态与验收标准

### Requirement: 飞书绑定 agent 可使用完整 Lark 能力

#### Scenario: 用户从飞书请求 Lark 资源操作

- **GIVEN** Gateway 所在环境已安装并配置可用的 `lark-cli`
- **WHEN** 用户在飞书中要求绑定 agent 操作文档、云盘、表格、日程、任务、审批、邮件、知识库、会议或其他 Lark 资源
- **THEN** agent 能发现并按产品提供的完整 Lark skill 集合执行相应操作
- **AND** 能力说明、命令和授权路径与当前全局 Lark skills 一致，而不是要求不存在的 `feishu-cli`

#### Scenario: Lark CLI 未安装或尚未授权

- **WHEN** 用户要求 Lark 操作，但 Gateway 环境缺少 `lark-cli` 或当前身份没有所需授权
- **THEN** agent 明确说明该前提或授权问题，并按 Lark skill 的当前指引协助用户继续
- **AND** 不把未执行的操作描述为已经成功

### Requirement: 飞书对话回复保持 Gateway 所有权

#### Scenario: 当前飞书对话产生普通助手回复

- **WHEN** 飞书消息触发 agent 处理并产生正常的可见回复
- **THEN** 回复继续由 Gateway 回写原飞书对话并同步到内部 IM 影子会话
- **AND** agent 不因拥有 Lark IM 能力而向当前对话另发一条绕过 Gateway 的消息

#### Scenario: 用户明确要求操作另一段 Lark 聊天

- **WHEN** 用户明确指定要向另一段 Lark 聊天发送、查询或管理消息
- **THEN** agent 可使用 Lark IM 能力完成该独立操作
- **AND** 原飞书对话仍按 Gateway 的既有链路接收助手对操作结果的说明

### Requirement: Lark 监听与身份语义保持全局能力的边界

#### Scenario: 用户明确要求监听 Lark 事件

- **WHEN** 用户要求 agent 监听某类 Lark 事件并据此自动处理
- **THEN** agent 可使用 `lark-event` 建立该独立监听
- **AND** 普通飞书对话的消息接收与回复仍由 Gateway 处理

#### Scenario: 用户请求需要 Lark 身份的操作

- **WHEN** 用户要求读取或操作其 Lark 资源
- **THEN** agent 默认使用 Gateway 机器上已登录的 Lark 用户身份执行
- **AND** 需要真实应用机器人入会或离会时，`lark-vc-agent` 保留其既有的 Bot 身份规则

## 范围与非目标

- 本期将完整全局 Lark skill 集合以产品可发现的形式提供给飞书绑定 agent，并保留其中已有的能力边界和交互语义。
- 本期只为与 PA/Feishu 既有职责直接冲突的行为做必要适配：当前飞书对话的回复继续由 Gateway 统一处理；独立 Lark 事件监听不得替代该对话主链路。
- 不改写全局 skills 的一般能力范围，不按产品偏好删减日历、任务、审批、邮件、会议等 Lark 能力。
- 不处理旧 `feishu-doc` 文件、旧安装目录或已有 agent skills 配置的迁移兼容；产品尚未上线。
- 不在本期新建 Gateway 托管的事件自动化系统；用户明确请求时，agent 沿用 `lark-event` 的现有独立监听能力。

## 现象与复现

1. 启动已绑定飞书 channel 的 Gateway；
2. 在飞书中要求绑定 agent 创建或读取云文档；
3. agent 可见的 `feishu-doc` 指引其调用 `feishu-cli`；
4. 当前环境找不到该命令，而可用的 `lark-cli` 及其全局 Lark skills 又不在 PA 的运行态 skill 搜索范围内。

预期是用户能直接获得当前 Lark CLI 的相应能力，或在缺少 CLI/授权时得到准确的下一步指引；实际是已有的飞书能力入口指向过期命令，且完整能力集合不可发现。

## 影响范围

影响所有希望从飞书绑定 agent 操作 Lark 资源的用户，尤其是配置了显式 skills 列表、当前只被自动加入 `feishu-doc` 的 agent。不会损坏已存在的 Lark 数据；风险是操作不可用、错误地报告操作步骤，或在 Lark IM 场景绕开产品既有的回复与镜像链路。

## 根因分析（RCA）

feat-447 最初把文档操作写成依赖 `feishu-cli` 的单一 `feishu-doc` skill；该内容随后随 `2139df278` 被安装为 Gateway 内置能力。当前全局能力已演进为以 `lark-cli` 为命令入口、由多个相互引用的 Lark skills 组成的集合，但 PA 仍只打包并自动启用旧 skill。

PA 的部署级 skill 搜索根只包含 `~/.nanoassistant/skills`、`~/.claude/skills` 和 `~/.codex/skills`，不包含当前全局 Lark skills 所在的 `~/.agents/skills`；因此“机器上已有全局 Lark skills”不会自动变成飞书 agent 的能力。内置 skills 的启动自举和 Feishu channel 的显式 allowlist 激活也只围绕 `feishu-doc`，没有产品定义的完整 Lark bundle。

这让问题能够长期存在：现有测试证明旧 skill 会被复制、发现并写入 allowlist，却没有验证 agent 指引的 CLI 在 Gateway 环境实际可用，也没有验证全局 Lark capability bundle 的发现、身份和与 Feishu 回复链路的边界。

原始设计意图是：飞书绑定 agent 必须自动发现执行飞书文档操作所需的能力，且 Gateway 不能覆盖用户本地已有 skill；修复必须保住“能力可被发现”和“本地自定义不被覆盖”这两个不变量，而不能用移除飞书能力来消除错误。

## 修复方向

以当前全局 Lark skills 为基线，提供产品可发现的完整 Lark capability bundle，取代旧的单一 `feishu-doc` 默认入口。飞书绑定 agent 获得该 bundle 后，默认沿用 Lark user 身份、授权和高风险操作语义；`lark-vc-agent` 保留已有的 Bot 身份例外。

产品只保留必要的渠道边界：当前飞书对话的普通回复由 Gateway 统一回写；`lark-im` 的直接操作仅用于用户明确指定的其他聊天；`lark-event` 可用于用户明确要求的独立监听，不能替代 Gateway 的普通对话主链路。
