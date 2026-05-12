# feat-333: Auto 模式默认体验

## Relations

无

## 原始需求

> '/Users/czj/Repos/nano-multiagent/docs/changes/feat-333-auto-mode-classifier/spec.md' 这个spec可能有点问题，帮我看下代码仓现在的现状是不是他说的那样，我印象中，至少现在是没有"dangerously-skip-permissions"的。

> '/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md'按照这个skill，跟我重新定一遍这个需求吧

> 一句话需求：我要把类似claude code的auto模式体验，作为我的默认体验，而且我暂时不提供其他模式，也就是只支持auto模式

> 你能不能先看一下 CC 的做法再问？问得不太靠谱

> 那就支持吧，为了简化代码和其他的东西一致。

> 你要把我原话放进去啊，目的是简化代码啊

> 对啊。你的问题就很奇怪。一共两个模式auto开了，dangerously-skip-permissions当然是关了

## 澄清记录

- Q1: 这个需求的核心用户问题，是“给 nano-multiagent 新增一个类似 CC Auto 的少打扰执行模式”，还是“先修正现有权限/安全模型的文档误差，不做产品功能”？
  A: 按新功能处理。目标是把类似 Claude Code 的 auto 模式体验作为默认体验，暂时不提供其他模式，也就是只支持 auto 模式。
- Q2: 这个“默认只支持 auto 模式”的生效入口，是否只针对 Coding CLI，还是也要覆盖个人助手 / IM 场景？
  A: 两个产品都覆盖：Coding CLI 和个人助手 / IM 场景都应采用 auto 模式体验。
- Q3: 在只支持 auto 模式的前提下，如果自动审批判定“不安全 / 不确定 / 分类器不可用”，用户体验应该是什么？
  A: 参考 Claude Code 的做法，最终权限决策仍然需要有 `allow` / `deny` / `ask` 三类结果。`allow` 和 `deny` 静默进行；`ask` 需要询问用户。
- Q4: nano 的目标是否就是“默认且唯一的权限模式 = CC auto 语义”，即不提供 default / plan / bypass 等用户可切换模式，但内部仍必须支持 `allow` / `deny` / `ask` 三类决策？
  A: 默认体验是 auto；同时额外提供一个对标 Claude Code `dangerously-skip-permissions` 的危险旁路入口，语义是不进行任何权限管控。除此之外不做 default / plan / dontAsk 等其他模式。`ask` 体验需要类似 Claude Code，按工具类型给不同选项，例如本次允许、拒绝、session 级允许、记住同类规则等。
- Q5: `dangerously-skip-permissions` 这个危险旁路要不要覆盖两个产品，还是只给 Coding CLI？
  A: 覆盖所有产品。启用方式应支持在配置文件中配置。
- Q6: 配置文件里启用 `dangerously-skip-permissions` 时，是否允许项目级配置打开，还是只能用户本机私有配置打开？
  A: 支持放在两个产品各自的 workspace 配置文件中：Coding CLI 使用 `<workspace>/.nanocode/config.yaml`，Personal Assistant 使用 `<workspace>/.nanoassistant/config.yaml`。
- Q7: 除了 workspace 级 `config.yaml`，是否也要支持用户全局配置？
  A: 支持全局与 workspace 两级 `config.yaml`。原因是“为了简化代码和其他的东西一致”，即沿用现有产品配置目录和优先级：workspace 覆盖 global。Coding CLI 为 `<workspace>/.nanocode/config.yaml` > `~/.nanocode/config.yaml`；Personal Assistant 为 `<workspace>/.nanoassistant/config.yaml` > `~/.nanoassistant/config.yaml`。
- Q8: 如果没有任何配置文件，默认行为是否就是 auto 模式开启，且 `dangerously-skip-permissions` 关闭？
  A: 是。只有两个模式：默认 auto 开启，`dangerously-skip-permissions` 默认关闭。
- Q9: auto 模式是否采用 Claude Code 的 `allow` / `soft_deny` / `environment` 三段自然语言规则配置，并把这些规则注入权限分类器？
  A: 是。照抄 Claude Code 的模式：用户可在配置文件中写 `allow` / `soft_deny` / `environment` 三类自然语言规则，这些规则会作为权限分类器的提示词上下文，用于判断工具调用应 `allow` / `deny` / `ask`。
- Q10: `ask` 在两个产品里的用户交互面，是否都要做成真实可响应的权限请求？
  A: 当然要做。Coding CLI 和 Personal Assistant / IM 都需要有真实可响应的权限请求；交互形态按产品不同。

## 用户场景

用户在 Coding CLI 或 Personal Assistant 中使用 nano-multiagent 时，默认得到类似 Claude Code Auto Mode 的体验：agent 对常规开发动作连续自主执行，不因为每个工具调用都打断用户；但当动作高风险、不确定、或自动审批无法判断时，系统仍能向用户发起明确的权限请求。

默认模式只有 `auto`。用户不需要选择 default / plan / dontAsk 等模式，也不会在无配置时进入裸权限。只有当用户显式配置 `dangerously-skip-permissions` 时，系统才进入危险旁路模式，此时不进行任何权限管控。

auto 模式的权限决策对用户呈现为三类结果：

- `allow`: 系统静默放行工具调用。
- `deny`: 系统静默拒绝工具调用，并把原因反馈给 agent，让 agent 改走安全路径。
- `ask`: 系统向用户询问，用户可按工具类型看到不同选项，例如本次允许、拒绝、session 级允许、记住同类规则等。

用户可在产品配置文件里调整 auto 分类器语义。配置沿用现有产品目录优先级，workspace 覆盖 global：

- Coding CLI: `<workspace>/.nanocode/config.yaml` > `~/.nanocode/config.yaml`
- Personal Assistant: `<workspace>/.nanoassistant/config.yaml` > `~/.nanoassistant/config.yaml`

配置中的 `auto_mode.allow`、`auto_mode.soft_deny`、`auto_mode.environment` 是自然语言规则，会作为权限分类器上下文，用来判断工具调用应自动允许、拒绝、还是询问用户。

## 验收标准

- [ ] 无配置启动时，Coding CLI 与 Personal Assistant 默认都是 `auto` 模式，且 `dangerously-skip-permissions` 关闭。
- [ ] 配置文件可显式启用 `dangerously-skip-permissions`；启用后两个产品都不做权限管控，并且用户能明确看出当前处于危险旁路状态。
- [ ] auto 模式下，每个受管控工具调用最终产生 `allow` / `deny` / `ask` 三类用户可理解的决策之一。
- [ ] `allow` 决策不打断用户，工具正常执行。
- [ ] `deny` 决策不执行工具，并把可理解原因反馈给 agent；agent 不应无提示地重复同一类被拒动作。
- [ ] `ask` 决策在 Coding CLI 中显示可响应的终端权限请求；用户可以允许或拒绝。
- [ ] `ask` 决策在 Personal Assistant / IM 中发送可响应的权限请求；用户可以通过 IM 允许或拒绝。
- [ ] `ask` 的选项按工具类型区分，至少覆盖“本次允许 / 拒绝 / session 级允许 / 记住同类规则”这类 Claude Code 风格体验；不要求所有工具暴露完全相同选项。
- [ ] 配置文件支持 `auto_mode.allow`、`auto_mode.soft_deny`、`auto_mode.environment` 三类自然语言规则；用户不配置时使用内置默认规则。
- [ ] workspace 级配置覆盖 global 级配置；两个产品分别使用自己的配置目录，不串用。
- [ ] 分类器不可用、上下文过长、或判断不确定时，系统不能静默放行；必须进入 `ask` 或可见拒绝路径。

## 范围与非目标

- 在范围：两个产品默认 auto 权限体验。
- 在范围：两个产品都支持显式 `dangerously-skip-permissions` 危险旁路。
- 在范围：两个产品的 global/workspace `config.yaml` 配置读取与优先级。
- 在范围：Claude Code 风格的 `allow` / `soft_deny` / `environment` 自然语言规则配置。
- 在范围：按工具类型差异化的 ask 选项。
- 在范围：Coding CLI 终端权限请求与 Personal Assistant / IM 权限请求。
- 非目标：提供 default / plan / dontAsk / acceptEdits 等其他用户可切换权限模式。
- 非目标：复刻 Claude Code 的账号、计划、远程 feature flag、商业 gating。
- 非目标：保证与 Claude Code 分类器逐条行为完全一致；目标是体验和安全语义对齐。
- 非目标：在 spec 阶段规定具体模块、接口、存储格式或分类器模型选型。
