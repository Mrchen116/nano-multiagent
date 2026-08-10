# bugfix-525: 后台自进化原始输出泄漏到聊天

## Relations

- Related: feat-349
- Related: feat-524

## 原始报告

> 那这个消息又是啥意思

> 截图：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-ea146fbc-d9d7-41d9-aded-947376fc38e4.png`

> 直接开unit修

## 澄清记录

- Q1: 这条后台 self-evolution 完成确认是否应作为普通 Agent 消息显示，还是只保留既有的结构化更新通知？
  A(原话): 直接开unit修
  Agent 解读: 修复截图中的异常可见消息，不新增另一种后台结果展示；self-evolution 继续静默完成持久更新，只沿既有 system notification 回显。

## 现象与复现

当开启 self-evolution memory curation 的 Agent 在外部飞书会话中达到后台 review 阈值时，正常回答之后会额外出现一条由 Agent 头像发送的英文消息，例如：

```text
Saved: user expects reference behavior to be verified before proposing or implementing an imitation, rather than inferred.
```

该英文内容不是用户请求的回答，也不是 runtime footer。它来自后台 self-evolution review side-chain：side-chain 调用 `memory` 成功后，模型生成了一条面向 review 调度者的完成确认；该确认被错误地当成普通 assistant 气泡投递到原飞书聊天。

2026-08-10 的生产复现证据：

- Kernel session：`sess_5f9eeb9f7479dd13`；
- `09:41:03` 的模型调用收到系统注入的 memory review prompt，并调用 `memory(action=add)`；
- `09:41:09` 的下一次模型调用生成上述 `Saved: ...` 文本；
- 对应用户偏好确实写入 workspace `USER.md`，说明后台整理本身成功，错误只发生在其原始输出的可见性边界；
- 飞书截图显示该文本成为正常回答后的独立 Agent 消息气泡。

## 影响范围

- 直接影响开启 self-evolution 且达到 review 阈值的 PA 会话；已在飞书外部 channel 复现。同一 Kernel session-event 投递面也服务内部 IM，因此不能把问题缩窄成飞书适配器格式错误。
- raw review prompt、工具状态或模型确认可能包含用户偏好、内部运行说明与调试信息；误发既造成对话噪音，也破坏后台维护任务的隐私边界。
- 已观察到的 memory 写入真实成功，没有数据丢失或数据库损坏；缺陷位于“哪些后台事件可见”的投递分类。
- skill review 还包含必须驱动产品状态的 `skill_created` 业务事件。只屏蔽全部 side-chain 事件会让 skill 文件创建成功但显式 allowlist 和活跃 session 不刷新，形成另一种静默功能损坏。
- 普通后台 Agent 明确面向用户产生的结果属于另一项现有能力，不受本单屏蔽。

## 用户场景与目标状态

用户在飞书或内部 IM 与 Agent 正常对话。达到 self-evolution 阈值后，后台 review 可以继续读取对话并更新 memory/skills，但用户不应看到 review Agent 的 prompt、工具进度或 `Saved: ...` 完成确认。用户只通过既有、可本地化且可归因的 system notification 知道 memory/skills 已更新。

如果 review 创建了新 skill，后台维护结束后该 skill 仍应按现有配置同步规则对 Agent 生效。无论 review 相对前台 terminal 是快是慢、Gateway 是否恰好切换到持久订阅或发生可恢复重连，用户都不应遇到“skill 文件已创建但 Agent 不会用”、重复激活、重复通知或 raw side-chain 消息回流。

普通后台 Agent 的用户可见结果继续按原有方式返回；本单只隔离 self-evolution 维护 side-chain。

## 验收标准

### Requirement: self-evolution 原始过程保持后台私有

#### Scenario: memory review 在正常回答后完成

- **GIVEN** 一个开启 memory curation 的 Agent 达到 review 阈值
- **WHEN** 用户在飞书或内部 IM 收到本轮正常回答，随后后台 review 完成 memory 更新
- **THEN** 用户不会收到 review prompt、memory 工具进度或 `Saved: ...` 等原始 side-chain 消息
- **AND** memory 更新仍真实保存
- **AND** 用户只看到既有的 memory-updated system notification

#### Scenario: 后台 review 没有可保存内容或执行失败

- **WHEN** self-evolution review 得出无需更新，或 review 本身失败
- **THEN** 用户不会收到 `Nothing to save.`、错误堆栈或其他 review Agent 原始回复
- **AND** 失败不改变本轮正常回答的完成状态

### Requirement: skill 更新在前台 terminal 之后仍可靠生效

#### Scenario: skill review 创建新 skill

- **GIVEN** Agent 使用显式 skill allowlist，且后台 review 创建了一个新 skill
- **WHEN** review 在前台回答完成前或完成后结束
- **THEN** 用户不会收到 review 的工具过程或完成确认
- **AND** 新 skill 按现有配置同步规则对相关 Agent 和后续 session 生效
- **AND** 用户只看到既有的 skills-updated system notification

#### Scenario: terminal 切换或可恢复重连覆盖事件边界

- **GIVEN** self-evolution 业务事件与前台 terminal、持久订阅切换或 Gateway 可恢复重连相邻发生
- **WHEN** Gateway 恢复并继续处理该 session
- **THEN** 新 skill 不会因事件落在切换边界而漏激活
- **AND** 同一更新不会重复激活或产生重复 system notification

### Requirement: 其他后台结果语义保持不变

#### Scenario: 普通后台 Agent 产生用户可见结果

- **WHEN** 一个非 self-evolution 的后台 Agent 按现有产品语义产生用户可见结果
- **THEN** 该结果继续投递给用户
- **AND** 不因本单对 self-evolution side-chain 的隔离而被屏蔽

## 根因分析（RCA）

### 原始设计意图与必须保住的不变量

`feat-349` 把 self-evolution 定义为不打断当前对话的后台 fork：review 继承主会话上下文、实际模型、工具和 unattended 权限语义，memory/skill 写入真实持久化；用户只通过轻量 system/meta notification 得知更新结果。普通后台 Agent 的用户可见输出不是该维护 fork 的回显机制。

修复必须保住：

- 达到阈值后仍自动运行 memory/skill review；
- review fork 仍继承主会话上下文、实际模型、workspace tool/hook 与 unattended permission；
- memory/skill 写入结果不回滚、不丢失；
- `skill_created` 继续驱动显式 allowlist 更新和相关 session 刷新；
- 用户仍收到既有结构化 `self_evolution_review` system notification；
- 普通后台 Agent 的用户可见结果不被全局抑制。

### 原始泄漏链路

1. 前台 turn 完成后，`make_fork_conversation()` 从父 turn 复制 HookContext 与 metadata，仅把 `run_origin` 改为 `background_task` 并清除递归 fork 能力；
2. fork 内部的 `AgentLoop.run()` 继续使用父 HookContext 执行 observe/realtime hooks；
3. 父上下文中的 session event publisher 与 Gateway delivery identity 因而被 side-chain 继承；
4. side-chain 的 assistant/tool/turn 事件被误认为原聊天 run 的用户可见输出，并镜像成普通 IM/外部 channel 气泡；
5. review 完成后，父 background hook 又按设计发布真正的 `self_evolution_review`，形成 raw 气泡与正式系统通知两条并行路径。

### 为什么局部过滤仍不完整

初版修复在 context-fork 边界把 publisher 全部变为 no-op，阻止了 raw 事件，但也吞掉了 `skill_created`。第二版把 `skill_created` 加入业务事件白名单，只证明它进入 Kernel session stream，仍没有覆盖真实 Gateway 生命周期：

1. self-improvement hook 是 fire-and-forget，前台 run 会先进入 terminal；
2. per-run Gateway consumer 在 terminal status 处停止并回收 RunDeliveryContext；
3. 后续持久 `BackgroundSessionEventSubscriber` 只订阅 `self_evolution_review`，会忽略晚到的 `skill_created`；
4. Gateway 的 skill config-sync handler 原本只挂在需要 live run context 的 observer 上；
5. 因而 review 创建的 skill 文件虽存在，显式 allowlist 和 session refresh 仍可能永远不发生。

### 为什么这种错能进入主线

- 既有测试分别覆盖 fork 工具执行、review structured event、Gateway system notification 和前台 `skill_created` handler，没有跨越“前台 terminal → 持久订阅 → config sync”整条时序。
- 初版 integration regression 只观察 public Kernel stream，证明 raw 输出已隔离，却把“Kernel 中有事件”等同于“Gateway 已消费并生效”。
- review 集中检查可见气泡，未同时盘点 side-chain 中非展示型但必须跨边界保留的业务事件。
- 现有持久 subscriber 的事件过滤原本只为 structured review notice 服务；新增 skill activation 责任需要明确 owner、序列边界、重放与去重语义，已超出单文件 Bugfix lite。

本问题不是 `NO_REPLY` 或 tool-only 空气泡缺陷：本次 side-chain 产生真实文本并完成真实持久写入，错误在于维护输出与业务事件没有被正确分类和分配生命周期 owner。

## 修复方向

- 在 self-evolution fork 的 publisher 边界显式区分私有 realtime 事件和需要驱动产品状态的业务事件；raw assistant/tool/turn 不进入父 session delivery。
- 由 Gateway 的持久后台 session 订阅承担前台 terminal 之后的 self-evolution 业务事件，使用 session binding 中的 Agent identity 调用既有 config-sync 能力，不依赖已回收的 per-run context。
- 为 terminal 前后的事件划分稳定 owner，并使用 Kernel sequence 边界和既有幂等能力避免 per-run consumer 与 persistent subscriber 双重处理。
- `self_evolution_review` 继续由父 background hook 发布并沿既有结构化 system notification 路径展示；不把 raw 文本或任意 background event 加入持久订阅。
- 用独立回归矩阵覆盖 memory/skill、terminal 前后、重复/重放、普通后台 Agent 不回归，再进入实现。

## 已完成的调查性实现与验证

以下提交用于稳定复现并暴露完整根因，不能单独视为最终修复：

- `de432ddd1`：在 fork 边界隔离 raw session events，并补真实 memory review Kernel integration regression；
- `2ecdd1cc4`：将 blanket no-op 收窄为 `skill_created` 业务事件白名单，并补真实 skill-create Kernel regression；
- code review 随后确认：该版本只证明事件进入 Kernel stream，未证明 terminal 后的 Gateway persistent route 能消费它。

当前证据：

- 修前生产症状由 session `sess_5f9eeb9f7479dd13`、`09:41:03` memory tool request、`09:41:09` raw completion 与飞书截图交叉定位；
- Kernel integration 已证明 memory/skill 持久写入可保留，raw assistant/tool/turn 可在最早稳定 seam 隔离；
- focused suites `90 passed`，完整非 E2E `3183 passed, 26 deselected`，Ruff/docs/diff checks 通过；
- 剩余缺口是经过真实 Gateway terminal/background subscriber/config-sync seam 的投递、去重与重放证明。

## 范围与非目标

- 本单覆盖 self-evolution memory/skill review 的 raw 输出隔离及其业务事件在 Gateway 生命周期中的可靠消费。
- 不设计 `feat-524` 的普通后台 Agent 折叠展示或结果归因 UI。
- 不改变 self-evolution 默认开关、nudge 阈值、review prompt、memory/skill 文件格式或权限策略。
- 不改变 runtime footer、飞书消息格式或所有 `RunOrigin.BACKGROUND_TASK` 的通用投递语义。
- 不把任意内部 session event 暴露给外部 channel；只保留明确有产品 owner 的 structured notification 和业务同步事件。
