# Design Review: bugfix-499-lark-skill-bundle

## Round 1

### Metadata

- reviewer: `/root/design_review_r1`
- review_mode: `full`
- mode_reason: `R1`，按规程完整重建承重原子台账，并重跑四个架构进攻角度。
- started_at: `2026-08-04T16:48:00+08:00`
- completed_at: `2026-08-04T17:08:25+08:00`
- duration: `20m 25s`

### Verdict

Issues Found — 1 CRITICAL / 1 WARNING

### Coverage

- 完整阅读 `incident.md`、`design.md`、两个 Gateway delta-spec，以及 canonical
  `docs/specs/gateway/{agent-capabilities,external-channels}.md`、
  `docs/specs/kernel/skills.md` 和 delta 写法规范。
- 从真实产品入口正向追踪了两条能力激活链：前台 Gateway 启动
  `run_gateway()` → `load_gateway_runtime_config()` → 静态 `config.channels`
  registry；以及 IM 托管 manifest → `ManagedChannelControl` →
  `ChannelManager` → `FeishuActivationPolicy`。
- 核对了包内安装、PA search roots、`SkillRegistry` 的 root 优先级、会话将
  `AgentWorkspaceConfig.skills` 投影给 Kernel 的路径、以及 Gateway 外部 reply
  delivery。也读过拟修改单测和全局 Lark bundle：当前确为 27 个 `lark-*`
  目录、394 个文件，且目录间相对引用需要整包保留。

### 核实台账

#### 现状断言

| ID | design 断言 | 核实动作与证据 | 结论 |
|---|---|---|---|
| A1 | 包内 skill 目录以非覆盖方式安装到 `~/.nanoassistant/skills` | 前台入口在 `src/personal_assistant/gateway/process_lifecycle.py:135-147` 调 `install_builtin_skills_for_gateway()`；实际 installer 在 `src/personal_assistant/builtin_skills/bootstrap.py:39-54` 逐目录发现 `SKILL.md`，目标存在即跳过、否则 `copytree`。 | 成立 |
| A2 | PA roots 包含安装目标、不读取 `~/.agents/skills` | `src/personal_assistant/product.py:43-55,423-431` 只传 `~/.nanoassistant/skills`、`~/.claude/skills`、`~/.codex/skills` 给 Kernel。 | 成立 |
| A3 | managed activation 目前围绕一个 `feishu-doc` | `src/personal_assistant/gateway/managed_channel_control.py:143-155` 向 policy 传 `ensure_agent_skill_enabled(agent_id, "feishu-doc")`；`src/personal_assistant/gateway/channel_manager.py:154-185` 也只追加该名称。 | 成立，但不是全部生产路径；见 R1-C1 |
| A4 | 当前 Feishu 可见回复由 Gateway 回写并镜像 IM | `src/personal_assistant/gateway/composition.py:284-302` 将 reply metadata 交给 `OutboundRouter`；`runtime_delivery/observer.py:435-465` 仅在 Gateway observer 中把 assistant 可见文本提交到当前 run delivery。 | 成立 |
| A5 | 完整 bundle 保留全局 skill 的身份和相对引用语义 | `/Users/czj/.agents/skills` 下有 27 个 `lark-*` 目录、394 文件；`lark-im/SKILL.md:13`、`lark-event/SKILL.md:13` 和 `lark-vc-agent/SKILL.md:42-52` 分别锚定 shared identity 与 bot 例外，跨 skill 引用均以相邻目录相对路径表达。 | 成立 |
| A6 | 不迁移/清理旧 `feishu-doc` | incident Q7 (`incident.md:40-42`) 明确排除迁移；该约束没有与 current 代码硬要求冲突。 | 成立 |
| A7 | 通用 installer 可保留 references | `builtin_skills/bootstrap.py:41-54` 对整个 skill source directory 作 `copytree`，不是只复制 `SKILL.md`。 | 成立 |
| A8 | `SkillRegistry` 多 root 按先到优先 | `src/agent/core/skills/registry.py:41-58` 按 configured root 顺序扫描，已命名 skill 不被后续 root 覆盖。 | 成立 |
| A9 | `IMAgentConfigSync` 是修改显式 allowlist 的唯一落点 | managed path 的确在 `agent_config_sync.py:262-340` fetch/PATCH/republish；但静态启动另有 `local_store.py:367-390,644-708` 直接持久化 `feishu-doc`。 | **不成立；R1-C1** |
| A10 | 旧能力确实指向不存在的 `feishu-cli` | `src/personal_assistant/builtin_skills/feishu-doc/SKILL.md:2-12` 的名称、说明和命令均为 `feishu-cli`；现有测试仍以它为预览对象（`tests/unit/personal_assistant/test_builtin_skill_bootstrap.py:68-123`）。 | 成立 |

#### 关键决策

| ID | 决策 | 核实动作与证据 | 结论 |
|---|---|---|---|
| D1 | 将全局 Lark skills 作为 PA 随包版本快照，不把 `~/.agents/skills` 加入 product roots | A1/A2 证明 package data（`pyproject.toml:57-58`）和现有 global-root discovery 可直接承载 snapshot；运行时读取 `.agents` 确会绕过现有产品 roots。 | 自洽、范围明确、由 incident 的可复现部署诉求驱动 |
| D2 | 只补齐 Feishu 的完整 bundle，空 allowlist 不物化 | `session_composition.py:55-64` 将空 skills 投影成 `None`（默认 discovery），非空才成 whitelist；`agent_config_sync.py:314-340` 是 managed 远端 PATCH 所在。设计未纳入 A9 的静态 startup writer。 | **不完整；R1-C1** |
| D3 | 在 `lark-im`、`lark-event` 写渠道边界，不新建 Gateway 传输机制 | current external reply 已由 A4 的 Gateway route 独占；全局 `lark-event/SKILL.md:21-33,70-97` 本身是独立 blocking consumer，`lark-im/SKILL.md:38-42` 是直接 Lark API 操作。把针对当前 Feishu run 的模型行为约束放入这两个冲突 skill，符合 incident Q4/Q5，且不会复制 delivery。 | 自洽、边界明确 |

#### incident 约束、场景与非目标

| ID | 首文档原子 | design 落点与核实 | 结论 |
|---|---|---|---|
| I1 | Q1：Feishu agent 获得完整可用 `lark-cli` skill 集合 | D1、resource interface、27-directory inventory 和 capability delta 都承接“完整”。 | 覆盖；但静态 Feishu path 漏接线，见 R1-C1 |
| I2 | Q2：默认是 Gateway 机器已登录 user，不随发送者切换 | D1 保留原 skill，delta `agent-capabilities.md:7-10` 以消费者可见语义说明默认身份。 | 覆盖、无冲突 |
| I3 | Q3：只处理与 PA/Feishu 职责冲突项，不按偏好裁剪 | D1 完整 snapshot、D3 只改两个冲突 skill；没有删减日历、任务等能力。 | 覆盖、无越界 |
| I4 | Q4：`lark-im` 可操作另一 chat，当前 chat 仍 Gateway-owned | D3 和 external-channels delta `:27-37` 同时规定两个出口。 | 覆盖、无冲突 |
| I5 | Q5：`lark-event` 用于明确独立监听，不能接管普通回复 | D3、agent-capabilities delta `:30-33` 以及 runbook 的隔离旅程一致。 | 覆盖、无冲突 |
| I6 | Q6：`lark-vc-agent` 的 bot 例外不改 | D1/D3 明确不改；全局 skill 的 `lark-vc-agent/SKILL.md:46-52` 也正是该规则。 | 覆盖、无冲突 |
| I7 | Q7：不迁移旧文件、安装目录、allowlist | D2 不移除旧条目，实施顺序 `design.md:172-174` 只删除包资源，风险段也不删除用户目录。 | 覆盖、无冲突 |
| I8 | 已安装/授权时可发现并操作全量 Lark 资源，且不再指向 `feishu-cli` | D1/D2、agent-capabilities ADDED requirement 和资源替换覆盖。 | 覆盖；静态 path 仍为 CRITICAL 缺口 |
| I9 | CLI/授权缺失时给准确下一步且不伪称成功 | `design.md:195-197` 复用 `lark-shared` 的认证/失败指引，不把 optional capability 变为 startup precondition；真实旅程 runbook `:245-246` 复核该结果。 | 覆盖、无冲突 |
| I10 | 当前 Feishu 普通回复由 Gateway 回写并镜像 IM，不能 direct IM duplicate | D3、external delta `:27-31`、runbook `:247-249` 均有落点。 | 覆盖；M1 exit 没把此用户旅程明确列为 reviewer 退出，见 R1-W1 |
| I11 | 指定另一 chat 时可 direct IM，结果说明仍回原 chat | external delta `:33-37` 和 runbook `:247-249` 一致。 | 覆盖、无冲突 |
| I12 | 监听/自动化不成为 Gateway 托管系统 | D3、风险表 `design.md:221` 和 non-goal 一致。 | 覆盖、无越界 |
| I13 | 不改内核/IM 依赖方向 | `design.md:34-35` 保持 AGENTS/SPEC 的 `personal_assistant → agent.sdk` 和 IM 独立边界；D1-D3 都位于 PA resources/configuration。 | 覆盖、无冲突 |

#### delta-spec 条目

| ID | delta 原子 | canonical 锚定与消费者可观察核实 | 结论 |
|---|---|---|---|
| DS1 | capabilities ADDED requirement | 新增是 Gateway 用户/IM consumer 可见的 skill capability，落在 `agent-capabilities.md` 这一最窄 area，未泄露 module/函数名。 | 合规 |
| DS2 | 新安装发现完整 bundle scenario | 与 canonical 通用 bootstrap (`docs/specs/gateway/agent-capabilities.md:112-124`) 互补，不重复写 copier 实现。 | 合规 |
| DS3 | 显式 allowlist scenario | 对应 D2 的消费者可见保留/补齐/幂等结果。 | 合规，但实现路径须包含静态 writer；R1-C1 |
| DS4 | 空 allowlist scenario | 与 `session_composition.py:61` 的 `None` default-discovery 语义一致。 | 合规 |
| DS5 | 独立 event listener scenario | 主语为 Feishu-agent 用户能力，THEN 是 listener 不接管对话，不含内部符号。 | 合规 |
| DS6 | REMOVED `内置 skills 启动自举` | 精确锚定 canonical `agent-capabilities.md:145-164`，并保留较通用的同 area requirement `:112-124`；符合 REMOVED 用法。 | 合规 |
| DS7 | external-channels MODIFIED requirement | 精确替换 canonical 同名 requirement (`external-channels.md:59-77`)，保留原三个 scenario。 | 合规 |
| DS8 | current-chat no-direct-IM scenario | 是用户在当前 chat 观察到的单一 Gateway reply + IM shadow，不写内部 API/日志断言。 | 合规 |
| DS9 | another-chat direct-operation scenario | 明确独立 chat 的操作和原 chat 的结果说明，消费者视角正确。 | 合规 |

#### Milestone

| ID | milestone | 核实动作与证据 | 结论 |
|---|---|---|---|
| M1 | `lark-skill-bundle` | 资源、清单、activation 和契约缺任一项均不能提供可用能力；`design.md:260-263` 已说明不按资源/接线横切拆分，故单 M1 合理。范围没有并行交集问题。退出项含 unit/docs checks，也混合用户旅程但未标出 reviewer/worker 轨和 Scenario；见 R1-W1。 | 单 M 合理；退出表达需修正 |

### 整体判断

- 上层说明、文本图和 D1-D3 能让读者快速看懂：资源 snapshot → 安装与
  discovery → Feishu allowlist，且当前 chat reply 仍属 Gateway。图与接口表、风险
  段基本一致。
- 资源安装、allowlist 物化、session discovery 和 reply delivery 的数据流闭合，
  但“Feishu activation”漏掉 static `config.channels` 这条真实生产分支，因此并未
  闭合到所有宣称的 Feishu binding。
- 没有 TBD、模板残留、横切 milestone 或违反 package dependency direction 的
  设计。没有常驻新服务；现有 Gateway 的重启/健康检查不因本设计而改变。

### 架构进攻

| 角度 | 主动攻击与证据 | 结论 |
|---|---|---|
| 归属 | 把 snapshot、资源名单放进 `personal_assistant.builtin_skills` 符合 PA 对部署能力的所有权；不把 `.agents` 加进 Kernel roots 也守住产品→SDK 边界。但 Feishu activation 不是只有 managed control：static config 的 owner 在 `local_store.py:367-390,644-708`，managed owner 才在 `ManagedChannelControl`。 | **R1-C1：遗漏该同层 owner 会让静态配置的能力契约断裂。** |
| 该不该存在 | 删除 `lark_bundle` 后，bootstrap、managed activation、static provisioning 和 tests 都得各自写 27 名称；这会重新引入 D1 所反对的多处浅重复。删除新 transport/service 反而直接复用 A4 delivery，复杂度没有被搬家。 | bundle module 与“不新增传输”均有必要，无新问题 |
| 深还是浅 | 现有 installer 已按目录完整复制，`SkillRegistry` 已做 root priority；新模块只暴露不可变名称集合、资源布局留在后面，接口显著浅于被隐藏的 394-file tree。manifest↔resource 反向测试使 bootstrap 不直接调用清单也不形成重复 source of truth。 | 没有多余 loader、factory 或 wrapper |
| 治本还是补丁 | 固定发布 snapshot 正面消除“本机恰有 `.agents` 内容才可用”的根因；D3 将唯一已知对话所有权冲突写到直接触发该行为的两个 skill，而没有以 adapter/常驻 consumer 绕过 Gateway。 | 方向是治本，不是临时 compatibility patch；C1 仅是该方向少覆盖一条现有入口 |

### Issues

- [R1-C1][CRITICAL] [现状分析 A3/A9；D2；M1 范围] 方案只把整组
  bundle 接入 IM 托管 channel 的 `FeishuActivationPolicy` /
  `IMAgentConfigSync`，漏掉静态 `config.channels` 的生产启动分支。
  `load_gateway_runtime_config()` 在 `src/personal_assistant/config/local_store.py:385-390`
  必定调用 `provision_feishu_doc_skill_for_gateway()`；后者在 `:668-708` 只为
  explicit allowlist 追加 `feishu-doc`。静态 FeishuAdapter 则由
  `src/personal_assistant/gateway/composition.py:626-675` 直接注册，完全不会经过
  `ManagedChannelControl` 的 policy（后者的唯一接线在
  `managed_channel_control.py:149-153`）。不改，worker 即使完整实现 design
  所列的 managed 路径，静态配置的 Feishu Bot 仍只得到旧 id；又因 M1 要删除包内
  `feishu-doc`，它不能发现完整 Lark bundle，违反 incident I1/I8 和 delta DS3。

- [R1-W1][WARNING] [M1 exit criteria；Runbook] M1 将“当前 chat reply 所有权”与
  `pytest`/`docs-check` 混写为一个未分轨的退出条件（`design.md:258`）。已有
  runbook `:237-252` 才给出实际 Feishu + IM shadow + 另一 chat 的旅程，但 M1
  没有将它标为 `[reviewer]`、也没有引用 external-channels delta 的两个 scenario；
  相应 unit tests 计划只检查复制版 skill 的边界段存在（`:191-193`），不能证明模型
  没有向当前 chat direct send。若不改，orchestrator 可把字符串/单测和 docs-check
  当成 M1 完成，而遗漏唯一能观察 duplicate/direct reply 的真实旅程。

### Recommendations

- [R1-R1] 将 static startup provisioning 纳入 D2 的责任表、主流程、M1 scope 和
  测试：以 bundle 清单替换 `local_store` 中只追加 `feishu-doc` 的 helper，同时保留
  空 allowlist 不物化与停用不移除的既有语义；增加覆盖
  `load_gateway_runtime_config()` 的静态 Feishu 显式/空 allowlist 回归。可复用同一
  bundle names source，不要另维护名单。
- [R1-R2] 把 M1 exit criteria 显式拆成 `[worker]`（资源清单、显式/空 allowlist、
  一次 PATCH、docs-check）与 `[reviewer]`（external delta 当前-chat 和另一-chat
  scenarios 的隔离真实旅程）；从 M1 链接到现有 Runbook 步骤 1-3。

### Author Resolutions

- [R1-C1] accepted. 已沿真实入口核实：静态 `config.channels` 经
  `load_gateway_runtime_config()` / `local_store` 直接持久化 allowlist，不会经过
  `FeishuActivationPolicy`。设计现将 static provisioning 与 IM-managed config
  sync 并列为 D2 的两个 owner，均从 `lark_bundle.lark_skill_names()` 取得同一组
  名称；补入静态显式/空 allowlist 的接口、数据流、实现顺序、单测与真实旅程
  runbook，并把 capabilities delta 的显式场景覆盖启动静态 channel 和调和托管
  channel。这样不增加第二个名单或迁移旧用户配置。
- [R1-W1] accepted. M1 exit criteria 已显式分为 `[worker]`（资源、静态/托管
  allowlist、一次 PATCH、聚焦 tests/docs-check）与 `[reviewer]`（Runbook 的
  隔离真实旅程，并逐项引用 external-channels delta 的当前 chat / 另一 chat
  Scenarios）。

## Round 2

### Metadata

- reviewer: `/root/design_review_r1`
- review_mode: `delta`
- mode_reason: 作者为 R1-C1 增补了 static `config.channels` 的 D2 owner、接口、
  数据流、测试、delta 与 M1 exit，并为 R1-W1 增补两轨 exit；需求范围、D1/D3 和
  milestone 拆分未变。本轮沿静态生产链追到 IM reconnect 后发现一个有界的
  config-sync 波及点，因此重查该链及受影响的归属、数据流、测试和 milestone，
  其余完整台账继承 Round 1。
- started_at: `2026-08-04T17:09:00+08:00`
- completed_at: `2026-08-04T17:18:47+08:00`
- duration: `9m 47s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### Coverage

- `retained_from: Round 1` — incident 全部约束、D1/D3、资源 snapshot、skill root
  discovery、外部 reply owner、两个 delta 的 canonical 锚定与单 M1 拆分均未因
  本轮 D2/M1 修订失效。
- 逐项重查 D2（`design.md:101-115`）、静态/托管接口与流程
  （`:137-168`）、实现顺序和测试 seam（`:173-201`）、runbook/M1 两轨退出
  （`:245-266`），以及两个更新过的 static allowlist delta Scenario。
- 从前台 `run_gateway()` 正向追静态配置，随后继续追带 `im_service` 的同一进程在
  register/reconnect 后的 profile 对账和 session capability 投影；没有只以
  `local_store` 单测代替生产路径核实。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | 静态 provisioning 与 IM-managed sync 共用 `lark_skill_names()`；补齐接口、数据流、测试、delta 和 runbook。 | 静态 startup 的补齐已准确落到 D2、接口表、主流程、实现顺序和 `test_gateway_launch.py`（`design.md:106-115,141-143,157-161,180-200`）；但该路径在连接 IM 后仍会被 mirror profile 覆盖，设计没有为这条后续生产链指定 bundle owner 或测试。详见 R2-C1。 | **not closed** |
| R1-W1 | M1 分为 `[worker]` 与引用 external-channels 两个 Scenario 的 `[reviewer]`。 | M1 现在明确把静态/托管 allowlist、PATCH、聚焦检查归给 worker，把“当前飞书 chat 不走直发”和“另一段 Lark chat”真实场景归给 reviewer（`design.md:245-266`）。这不再允许 orchestrator 仅凭 skill 文本/单测跳过可观察的 current-chat journey。 | **closed** |

### 本轮核实证据

| 受影响原子 | 实际核查与证据 | 结论 |
|---|---|---|
| D2 static startup owner | 前台 `run_gateway()` 在安装资源和组装 runtime 前调用 `load_gateway_runtime_config()`（`src/personal_assistant/gateway/process_lifecycle.py:135-147`）；后者调用 static provisioning（`config/local_store.py:367-390`）。现有 helper 只识别 enabled `feishu:<agent_id>` 且只修改非空 allowlist（`:668-708`）。静态 FeishuAdapter 由 composition 直接注册（`gateway/composition.py:626-675`），不经过 managed policy。 | 作者对 R1-C1 的 static 入口定位正确；改为 bundle 清单是恰当且不重复名单的归属。 |
| D2 的 post-connect data flow | 同一 `config` 有 `im_service` 时，composition 将**所有** `config.agents` 交给 `ConnectionReadyCoordinator`（`gateway/composition.py:355-373,515-527`）。每次 register/reconnect 先调 managed binding，随后调 `reconcile_all_agents()`（`gateway/connection_ready.py:99-109`）。该方法对每个 local agent 拉 mirror profile；没有内存版本时接受任意 IM 版本（`gateway/agent_config_sync.py:414-460`），并把 payload 的 `skills` 原样解码（`:502-512`）、持久化且发布完整新 agent config（`:529-575`）。现有测试也规定 reconnect mirror skills 会覆盖并写回 local config（`tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py:139-193`）。 | D2 图中的 `static loader → allowlist` 不是静态 Feishu agent 的完整生产数据流；它遗漏了随后 IM-authoritative 的覆盖边。 |
| 消费者影响 | 会话只在 `config.skills` 非空时传 explicit skill list；为空才是默认全局 discovery（`gateway/session_composition.py:55-64`）。因此旧 IM profile 若保有如 `("memory", "feishu-doc")` 的显式列表，startup 虽补入完整 bundle，register 后仍可被该 profile 写回为不含 Lark bundle 的列表。当前 static startup test 本身配置了 `im_service`，但只断言 loader 时的本地结果（`tests/unit/personal_assistant/test_gateway_launch.py:199-233`）。 | 这是用户可见的升级/reconnect 回归，不是纯持久化细节。 |
| R1-W1 的两轨 exit | Runbook 先要求隔离的 static 与 managed 验证、只读 Lark 操作，再执行当前 chat/另一 chat 的 reply-owner journey（`design.md:245-260`）；M1 的 reviewer exit 精确引用后两个 external delta Scenario（`:264-266`）。更新后的 delta 也把 static startup 与 managed reconciliation 清楚写成同一可观察场景（`specs/gateway/agent-capabilities.md:18-28`）。 | 两轨职责清晰，R1-W1 闭环；无需把模型实际行为错误地降格为字符串单测。 |

### 受影响架构进攻

| 角度 | 主动攻击与结论 |
|---|---|
| 归属 | 将名称清单留在 `lark_bundle`、让 static loader 与 managed policy 消费它是正确的深模块边界；但 `IMAgentConfigSync` 已是 reconnect 时完整 agent profile 的发布 owner。D2 只把它写为“托管 agent”的 owner，遗漏它对静态 agent 的同一 config owner 写入，造成职责断层。 |
| 数据流完整性 / 治本 | 删除 static loader 后会失去纯静态启动修复，删除 managed policy 后会失去 manifest 修复；但两者都不能消除 reconnect 覆盖。若只按当前 design 实现，预存 IM profile 的 static bot 会在首次连接后回到旧显式 allowlist，形成“启动瞬时正确、运行中失效”的补丁，而非 D2 承诺的稳定能力。 |
| 两轨退出 | M1 把真实 current-chat 和 another-chat journey 显式交给 reviewer，避免了 R1 指出的 orchestrator 漏检；但 worker 轨还缺少 static + existing IM profile 的收敛回归，不能证明 D2 的 static claim 在完整运行链成立。 |

### Issues

- [R2-C1][CRITICAL] [D2；接口与数据流；测试 seam；M1] R1-C1 对 static
  `config.channels` 的修复只覆盖启动前的 `local_store` 写入，漏掉带
  `im_service` 的静态 Gateway 在 register/reconnect 后的权威 profile 对账。
  `ConnectionReadyCoordinator` 会对全部 configured agents 调
  `IMAgentConfigSync.reconcile_all_agents()`（`src/personal_assistant/gateway/connection_ready.py:99-109`）；该方法接受同版本或更新的 IM profile 并以其
  `skills` 替换、持久化和发布 live config（`agent_config_sync.py:414-460,502-512,549-575`）。静态 adapter 不会重新进入 `FeishuActivationPolicy`，而 D2/interface
  仅规定 policy 触发“托管” bundle merge（`design.md:106-110,141-143`）。因此一个
  已存在、显式 skills 尚未含 Lark bundle 的 IM mirror（典型升级状态）会在连接后
  覆盖 static startup 的完整 allowlist；会话随即使用该非空旧列表而不能发现 bundle。
  当前计划的 loader-only static test 和 fresh runbook 不会强制覆盖这个 pre-existing
  profile case。若不改，worker 可以完全按 D2/M1 通过单测，生产静态 Feishu bot
  却在 reconnect 后失去 incident I1/I8 和 static delta Scenario 所承诺的能力。

### Recommendations

- [R2-R1] 把 D2 的 static contract 扩展到它的完整 IM-enabled 生命周期：明确由谁、
  在 `reconcile_all_agents()` 接受 mirror profile 的哪个顺序，使静态 Feishu agent
  的**显式** allowlist 仍收敛到 `lark_skill_names()`（并保持空列表不物化、单次
  PATCH/同步和 IM profile authority 的既有约束）。相应把这条边加入主流程/接口/M1，
  并增加一个从 static `config.channels` + `im_service` 启动、IM 返回预存非空旧
  allowlist 的回归：断言 connection 后 remote/local/live session 都保留完整 bundle，
  且无重复写入。Runbook 的 static 测试身份也应使用该预存 mirror 情形，不能只验证
  first-seen registration。

### Author Resolutions

- [R2-C1] accepted. 已核实 `ConnectionReadyCoordinator` 在每次 IM
  register/reconnect 后会对全部 local agents 执行 `reconcile_all_agents()`，因此
  static startup provisioning 不是完整生命周期。D2 现指定：对拥有本地静态 Feishu
  binding 的 agent，`IMAgentConfigSync` 在 decode/publish 显式 mirror profile 前
  用 `lark_skill_names()` 合并缺项、一次 PATCH 并只发布 PATCH 后 profile；空列表
  仍不物化。同步补入 interface/data-flow 图、实现顺序、静态 + 预存 IM profile
  的 connection/reconnect 回归、runbook、M1 worker exit 和一个 capabilities
  delta Scenario。此路径只收敛静态 binding 强制要求的 capability，不改变 IM 对
  其余 profile 字段的权威性，也不引入迁移或第二份名称清单。

## Round 3

### Metadata

- reviewer: `/root/design_review_r1`
- review_mode: `delta`
- mode_reason: 作者围绕 R2-C1 对 D2、`IMAgentConfigSync` 接口/数据流、实现顺序、
  static mirror test、runbook、M1 与 capabilities delta 作了有界的生命周期修订。
  本轮复核 register/reconnect 的修订链，并追同一 IM profile 的实时 ingress；它仍
  局限于 `IMAgentConfigSync` 的两个已知 publish 路径，故沿用 Round 2 台账做 delta
  review，而不重建全量设计审查。
- started_at: `2026-08-04T17:22:11+08:00`
- completed_at: `2026-08-04T17:25:24+08:00`
- duration: `3m 13s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### Coverage

- `retained_from: Round 1 and Round 2` — incident 目标、D1/D3、资源 bundle、static
  startup、managed activation、reply-owner journey、canonical delta 锚定和单 M1
  拆分均未因本轮 D2 修订失效。
- 重新逐项核验 R2-C1 Author Resolution 落到的 D2、接口/图、实现顺序、测试 seam、
  static profile delta、runbook 和 M1（`design.md:106-118,144-166,185-198,212,
  252-281`；`specs/gateway/agent-capabilities.md:30-35`）。
- 从真实 runtime wiring 追两条 IM mirror publish ingress：register/reconnect 的
  `ConnectionReadyCoordinator → reconcile_all_agents()`，以及长连接 `config.sync`
  的 `ConfigSyncClient → sync_agent()`；二者都会改变同一个 live catalog/session
  输入。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-C1 | 在 `reconcile_all_agents()` decode/publish 前，静态 Feishu binding 的显式 mirror profile 先按 bundle 合并、一次 PATCH 后发布；补入 test/runbook/M1/delta。 | 该 register/reconnect 分支已被精确纳入 D2：静态 binding 判定复用、显式 profile 一次 PATCH、空 profile 不物化、PATCH response 再 decode/publish，且 pre-existing profile 已有测试与真实旅程落点（`design.md:144-166,185-198,212,264-267`）。但 runtime 还有 `config.sync → sync_agent()` 的同一 profile publish 入口，设计和测试没有纳入；详见 R3-C1。 | **not closed** |

### 实际核查证据

| 受影响原子 | 实际路径与证据 | 结论 |
|---|---|---|
| register/reconnect merge 的归属与顺序 | 注册 ACK 后 `ConnectionReadyCoordinator` 调 `reconcile_all_agents()`（`src/personal_assistant/gateway/connection_ready.py:99-109`）。当前方法逐 agent GET mirror，版本可接受时 decode/publish（`gateway/agent_config_sync.py:414-460`）；现有 `_patch_agent_skills()` 已能以一次 PATCH 返回完整更新 payload（`:348-387`），随后 `_decode_mirror_agent_config()` 与 `_publish_agent_config()` 会持久化并替换 live snapshot（`:467-563`）。 | 作者把 required merge 放在唯一 profile owner、并指定“PATCH response 后再 publish”，能闭合 R2 所指出的 reconnect 覆盖，不需要新名单或第二套 owner。 |
| 空 allowlist、authority 和单次 PATCH | D2 与实现顺序一致限定为 mirror `skills` 显式非空才 PATCH，空列表不物化、仍走 global discovery（`design.md:106-118,191-198`）；session 将空 skills 投影为 `None`、仅非空列为 allowlist（`gateway/session_composition.py:55-64`）。patch helper 从刚获取的 profile 保留其他可写字段（`agent_config_sync.py:348-378`），而 planned static-mirror test 明确要求首次一次 PATCH、重连后不重复（`design.md:212,252-255`）。 | 对 **reconcile** 分支，空语义、IM 其余字段权威性和 PATCH 次数没有歧义。 |
| 实时 profile ingress | 带 IM 的 production composition 构造 `ConfigSyncClient(fetcher=im_config_sync_client.sync_agent)`（`gateway/composition.py:407-409`）；WebSocket 收到 `config.sync` 同步帧时直接调用它（`src/personal_assistant/ws/im_connection.py:879-882`）。`sync_agent()` GET 到满足 announced version 的 mirror 后直接 `_decode_mirror_agent_config()` / `_publish_agent_config()`（`gateway/agent_config_sync.py:132-154`），没有 static Feishu binding 判断、bundle merge 或 PATCH。 | 与 reconnect 使用同一 profile / local config owner / live catalog 的第二条生产入口绕过了新 D2 规则。 |
| 用户可见影响和测试覆盖 | 静态 Feishu adapter 可持续从 live catalog 选择 agent（`gateway/composition.py:626-675`），会话对非空 skills 使用严格 allowlist（`gateway/session_composition.py:55-64`）。因此 IM 将静态 agent 的 profile 改回 `("memory", "feishu-doc")` 并发送 `config.sync` 后，运行态会立即失去新 Lark IDs；不必等到下一次 reconnect。设计仅计划 `test_gateway_reconcile_on_connect.py` 的 pre-existing mirror case（`design.md:212`），Runbook/M1 也只列“静态 IM mirror 对账”（`:252-255,281`）。 | R2 的回归用例能通过，但它没有覆盖这条持续运行的 profile 覆盖链。 |

### 受影响架构进攻

| 角度 | 主动攻击与结论 |
|---|---|
| 归属 | `IMAgentConfigSync` 已同时拥有 reconnect reconciliation 和 notification refresh 的 decode/publish；只在其中一个方法插入 static bundle 强制规则，等于把同一配置不变量按 transport path 分裂。最小正确归属是该 owner 内可由两条 ingress 共用的、publish 前的 static-binding merge，而不是在 WebSocket 或 `ConnectionReadyCoordinator` 再造补丁。 |
| 治本 | 修复 reconnect 而让后续 `config.sync` 能撤销 required capability，只消除了“重连时丢失”的表象。长期代价是每次 IM profile 编辑、自动同步或升级恢复都可能重新触发能力漂移，且只有下一次重连才偶然修复。 |

### Issues

- [R3-C1][CRITICAL] [D2；`IMAgentConfigSync` 接口/数据流；测试 seam；M1] R2-C1 的
  Author Resolution 只把 static Feishu required-bundle merge 放进
  `reconcile_all_agents()`，遗漏在线 `config.sync` 的同一 mirror profile ingress。
  production composition 将 `ConfigSyncClient` 的 fetcher 绑定为
  `IMAgentConfigSync.sync_agent()`（`src/personal_assistant/gateway/composition.py:407-409`），
  WebSocket 的 `config.sync` frame 立即触发该 callback（`src/personal_assistant/ws/im_connection.py:879-882`）；`sync_agent()` 当前在版本检查后直接 decode/publish（`gateway/agent_config_sync.py:132-154`）。它不会经过 `ConnectionReadyCoordinator` 或计划中的
  `reconcile_all_agents()` merge。于是 IM 的一次正常 profile 更新若带回显式旧
  allowlist，就能在不断线时覆盖静态 bot 的 bundle，session 随即按该 nonempty
  allowlist 运行而不发现 Lark skills（`gateway/session_composition.py:55-64`）。不改，
  worker 完整实现当前 D2、reconnect test 和 M1 仍会放行一个运行中可复现的
  incident I1/I8/static-delta 违约。

### Recommendations

- [R3-R1] 将“静态 Feishu binding 的显式 mirror profile 合并 bundle 后才
  decode/publish”定义为 `IMAgentConfigSync` 的共享 profile-ingress 规则，同时由
  `sync_agent()` 和 `reconcile_all_agents()` 使用：只对 enabled static binding 的
  nonempty mirror list 基于刚 GET 的 payload 一次 PATCH，并 decode/publish PATCH
  response；空 list 仍直接发布以保留 default discovery，其他 profile 字段仍以 IM
  为准。补充 `config.sync` → `sync_agent()` 的静态旧 profile regression（含首次一次
  PATCH、随后重复 sync 零 PATCH、remote/local/live session 一致），并把这一持续
  sync 情形写入 static delta Scenario、Runbook 与 M1 worker exit。

### Author Resolutions

- [R3-C1] accepted. 已核实 `sync_agent()` 与 `reconcile_all_agents()` 是同一个
  IM mirror profile 的两个 production publish ingress，不能在其中一个路径保留
  bundle merge。D2 与接口现指定一个 `IMAgentConfigSync` 私有 profile-ingress
  helper：两条 ingress 均在自身已有 stale-version 拒绝后、decode/publish 前调用；
  它只为本地静态 Feishu binding 的显式 profile 以 `lark_skill_names()` 补项，
  PATCH response 才可发布，空 profile 不物化。已补实时 `sync_agent()` 回归、
  主流程图标签、delta Scenario、runbook 与 M1 worker exit。这样既不在 WebSocket
  或连接协调器另建第三个 owner，也不会让一条正常 config sync 撤销 D2 能力。

## Round 4

### Metadata

- reviewer: `/root/design_review_r1`
- review_mode: `delta`
- mode_reason: R3-C1 的修订把同一 profile-ingress 规则从一个 reconnect 分支扩至
  `reconcile_all_agents()` 与 `sync_agent()`，并相应修改 interface/data flow、delta、
  test seam、runbook 和 M1；需求、模块边界和其余设计未变。本轮只重查这两个 publish
  ingress 的 guard/merge/publish 顺序及其错误边界。
- started_at: `2026-08-04T17:28:54+08:00`
- completed_at: `2026-08-04T17:30:19+08:00`
- duration: `1m 25s`

### Verdict

Issues Found — 0 CRITICAL / 1 WARNING

### Coverage

- `retained_from: Round 1–3` — incident 目标、D1/D3、bundle source、static startup、
  managed activation、reply ownership、canonical delta 与单 M1 拆分未因本轮 ingress
  收敛修改失效。
- 重新核验 R3-C1 resolution 的 D2/接口/图/实现顺序（`design.md:106-118,144-166,
  185-200`）、profile-ingress delta（`specs/gateway/agent-capabilities.md:30-35`）、
  test seam（`design.md:212-217`）、runbook/M1（`:252-285`）。
- 由 production wiring 分别追 `ConnectionReadyCoordinator → reconcile_all_agents()`
  与 `IMConnectionManager config.sync → ConfigSyncClient → sync_agent()`，以及两者
  共用的 patch/decode/publish 和 register callback liveness 约束。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R3-C1 | 共享私有 profile-ingress helper 在两个 ingress 的 stale guard 后、decode/publish 前合并静态 binding 的显式 mirror，PATCH response 才发布；同步补 delta/test/runbook/M1。 | 当前 `sync_agent()` 的 version guard 在 `agent_config_sync.py:138-149`，`reconcile_all_agents()` 的 memory-version guard 在 `:438-460`；设计精确把 helper 置于各自 guard 后、decode/publish 前（`design.md:145,194-200`）。Composition/WS wiring 证明两者正是唯一两个 mirror publish ingress（`gateway/composition.py:407-409`、`ws/im_connection.py:879-882`）。显式/空 profile、一次 PATCH、IM authority 和两条回归均有明确落点。 | **closed** |

### 实际核查证据

| 受影响原子 | 实际路径与证据 | 结论 |
|---|---|---|
| 两条 ingress 与 helper 顺序 | reconnect 在 register ACK 后进入 coordinator，再调用 `reconcile_all_agents()`（`src/personal_assistant/gateway/connection_ready.py:99-109`）；实时 frame 由 WS 交给 `ConfigSyncClient`，其 fetcher 是 `sync_agent()`（`gateway/composition.py:407-409`、`ws/im_connection.py:879-882`）。现有两个方法都在自己的 stale guard 后才 decode/publish（`gateway/agent_config_sync.py:132-154,414-460`），与设计指定的 shared helper placement 一致。 | R3-C1 的成功路径归属和顺序无歧义。 |
| static binding、空列表、authority 与 PATCH | D2/interface 将 helper 限为 enabled static Feishu binding 的 nonempty mirror list；空 list 不物化（`design.md:106-118,144-145,194-200`）。session 对空 skills 保持 global discovery、仅 nonempty 使用 strict allowlist（`gateway/session_composition.py:55-64`）。现有 `_patch_agent_skills()` 以刚 GET profile 构造一次 PATCH，并返回更新 payload 供后续 decode/publish（`agent_config_sync.py:348-387,467-563`）。 | 不会为 non-Feishu 或空 list 扩权；除强制 bundle 外仍以 IM profile 为准，重复 ingress 可零 PATCH。 |
| 契约和成功回归 | delta 把 reconnect 与 `config.sync` 并列为 static profile ingress（`specs/gateway/agent-capabilities.md:30-35`）。测试表分别覆盖 reconnect 的旧 mirror 和 `sync_agent()` 的实时旧 mirror、首次一次 PATCH/重复零 PATCH（`design.md:214-216`）；Runbook 与 M1 都要求两种 ingress（`:255-258,267-271,285`）。 | R3-C1 所需的正常行为、消费者可见结果和 worker/reviewer 门槛已闭合。 |
| reconnect failure boundary | 当前 `reconcile_all_agents()` 只把 GET 包在 `try/except`，HTTP/ValueError 时记录并跳过（`agent_config_sync.py:437-444`）；其现有回归明确要求 HTTP failure 不 raise（`tests/unit/personal_assistant/test_gateway_reconcile_callback.py:176-203`）。新增 helper 则在 stale guard 后执行 PATCH；`_patch_agent_skills()` 可由 `raise_for_status()` 抛错（`agent_config_sync.py:379-387`）。设计没有规定该 PATCH failure 如何保留“跳过该 agent、不打断 WS”语义，也没有 fault-injection test。若异常离开 reconcile，`ConnectionReadyCoordinator` 到 `schedule_drain()` 的后续步骤不会执行（`gateway/connection_ready.py:106-110`），虽然后续 `_notify_registered()` 会吞下 callback 异常（`ws/im_connection.py:1527-1535`）。 | 这是新网络写入引入、会使一个静态 agent 的暂时 PATCH 失败中断整次 post-register convergence 的缺口。 |

### 受影响架构进攻

| 角度 | 主动攻击与结论 |
|---|---|
| 归属 / 深度 | 一个 `IMAgentConfigSync` 私有 helper 服务两个已有 ingress，避免把规则复制到 WebSocket 或 coordinator，是最小且正确的归属；没有额外策略层或第二份 names source。 |
| 治本 / liveness | 共享 helper 消除了 R3 的 transport-path 漂移，但它新增的 PATCH 必须继承 reconcile 的“单 agent HTTP failure 不阻塞 WS convergence”契约。否则短暂 IM PATCH 故障会把错误从 agent 级能力收敛放大成整次 register callback 的提前退出。 |

### Issues

- [R4-W1][WARNING] [D2；profile-ingress helper；test seam；M1] 设计精确定义了
  helper 在 `reconcile_all_agents()` 的 stale guard 后执行一次 PATCH，却没有定义或
  验证 PATCH 失败时的处理。当前 reconcile 只捕获 GET 失败，且已有测试/注释承诺
  HTTP failure 只跳过该 agent、不向 WS callback 传播（`src/personal_assistant/gateway/agent_config_sync.py:437-444`；`tests/unit/personal_assistant/test_gateway_reconcile_callback.py:176-203`）。若 worker 依设计把
  `_patch_agent_skills()` 直接插在 guard 和 decode 间，`raise_for_status()` 会使
  `ConnectionReadyCoordinator` 在 `schedule_drain()` 前退出；`IMConnectionManager`
  虽保持连接，却只记录 `on_connected_error`（`gateway/connection_ready.py:106-110`、
  `ws/im_connection.py:1527-1535`）。不改，临时 PATCH 故障会让一个 static agent
  的能力修复阻断同次其他 agent 对账和 post-register delivery，而 M1 的成功路径
  测试仍会放行。

### Recommendations

- [R4-R1] 在 D2/shared helper 约定中明确保持现有 reconcile liveness：对 static
  nonempty profile 的 PATCH 失败记录并跳过**该 agent**，不得发布未经 bundle merge 的
  raw profile，且继续其余 agents 与 post-register outbox；`sync_agent()` 保留其已有
  retry/error 语义。补充 `test_gateway_reconcile_callback.py`（或等价 existing seam）
  的 GET-success/PATCH-failure 回归，并把“PATCH failure 不阻断 reconnect convergence”
  列入 M1 `[worker]` exit 和 Runbook 静态验证。

### Author Resolutions

- [R4-W1] accepted. 新 helper 的 PATCH 是 `reconcile_all_agents()` 原本没有的
  网络写入，不能扩大为整次 post-register callback 的失败。D2、接口、实现顺序和
  风险表现已规定：该 helper 在 reconnect 的 per-agent HTTP/ValueError 容错范围内；
  PATCH 失败时记录并跳过当前 agent、绝不发布未合并 raw profile，继续剩余 agent
  和 outbox drain。`sync_agent()` 沿用已有 retry/exhaustion error 行为。已补
  `test_gateway_reconcile_callback.py` failure-injection seam、Runbook 与 M1
  `[worker]` exit；不新增重试器或恢复服务。

## Round 5

### Metadata

- reviewer: `/root/design_review_r1`
- review_mode: `closure`
- mode_reason: R4-W1 resolution 是对同一 shared profile-ingress 的有限 liveness
  clarification；本轮完整验证其 error boundary、两条 ingress 语义和验证门槛，未发现
  需要重新展开 bundle、静态/托管成功路径或 delta scope 的变化。
- started_at: `2026-08-04T17:34:05+08:00`
- completed_at: `2026-08-04T17:37:21+08:00`
- duration: `3m 16s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

- `retained_from: Round 1–4` — R1-C1、R3-C1 和 R4-W1 以外的 bundle source、静态/托管
  activation、reply ownership、delta 与 M1 拆分均未在本次 resolution 中改变。
- 仅核验 R4-W1 所需的三项：reconcile 的 PATCH 是否进入现有逐 agent error boundary、
  失败时 raw profile/其余 agent/outbox 的结果，以及实时 `sync_agent()` 的 retry
  语义；同时核验指定 unit seam、Runbook 和 M1 能否实际执行该保护。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R4-W1 | reconnect PATCH 失败记录并跳过当前 agent、不发布 raw profile、继续其余 agent 与 outbox；实时 sync 保留 retry/error，并增加 failure seam、Runbook/M1。 | D2、接口和实施顺序一致要求 helper（含 PATCH）进入 `reconcile_all_agents()` 既有 per-agent `HTTP/ValueError` 边界，且失败后只跳过当前 agent；明确要求不发布 raw、继续其他 agent 和 post-register outbox（`design.md:106-116,148,197-206,253`）。`sync_agent()` 明确沿用 retry/exhaustion。 | **closed** |

### 实际核查证据

| 受影响原子 | 实际路径与证据 | 结论 |
|---|---|---|
| reconcile 的 agent 级故障隔离 | 当前 `reconcile_all_agents()` 每个 agent 的 GET 失败记录并 `continue`，方法注释承诺不影响 WS lifecycle（`src/personal_assistant/gateway/agent_config_sync.py:419-425,434-444`）；新的 `_patch_agent_skills()` 会由 `raise_for_status()` 或非对象 response 抛出 `HTTPError`/`ValueError`（`:348-387`）。修订要求把 helper **含 PATCH** 纳入同一 per-agent boundary，并跳过当前 agent（`design.md:203-205`）。 | PATCH 不会扩大成整个 reconnect callback 的失败，且其 failure type 与既有 boundary 对齐。 |
| raw profile、其余 agents 与 outbox | 现有 publish 只在版本 guard 后进行（`agent_config_sync.py:445-460`）；设计规定 PATCH 失败时不得走这条 raw decode/publish 路径、继续其他 agent，保证 outbox 调度（`design.md:114-116,203-206`）。coordinator 在 reconcile 返回后才 `schedule_drain()`（`gateway/connection_ready.py:106-112`）；若异常逸出，注册 callback 仅记录 `on_connected_error`（`ws/im_connection.py:1527-1535`）。 | 设计明确保护了 R4 指出的整次 post-register 提前退出风险。 |
| realtime sync retry | 当前 `sync_agent()` 的 fetch、版本检查与 decode/publish 均在 retry loop 内；仅在 attempts/deadline 用尽时 re-raise（`agent_config_sync.py:132-154`）。修订要求 shared helper 放在同一 stale guard 后、decode/publish 前，并保留 retry/exhaustion（`design.md:148,197-206`）。 | 实时 ingress 不会误套 reconcile 的 skip 语义，既有 retry/error 仍是其 owner。 |
| failure seam、Runbook 与 M1 | test table 已指定 GET-success/PATCH-failure 的 `test_gateway_reconcile_callback.py`，断言 raw 不发布、其余 agent 和 post-register 继续（`design.md:216-223`）；风险、Runbook step 4 与 M1 worker exit 也都列出同一行为（`:245-270,291-295`）。虽然 step 2 的聚焦 pytest 命令没有列该文件（`:263-266`），step 4 单独要求同一 HTTP failure 注入，且 test table 已给出其现有 unit seam。 | 组合门槛明确覆盖 failure regression，不依赖新增测试层或人工推断行为。 |

### 受影响架构进攻

| 角度 | 主动攻击与结论 |
|---|---|
| liveness / fault boundary | 将 PATCH 放在 `reconcile_all_agents()` 的既有逐 agent boundary 是最小归属：不会在 coordinator 或 WebSocket 增加恢复层，也不会把实时 sync 的 retry 模型改成 skip。PATCH 失败后不发布 raw profile，避免用错误的“继续”换来能力回退。 |
| delivery continuation | 一次 PATCH failure 之后仍须让 reconcile 正常返回，才到达 coordinator 的 `schedule_drain()`；设计已把这一不可见但关键的因果链写明。 |

### Issues

None.

### Recommendations

None.

## Round 6

### Metadata

- reviewer: `/root/design_review_r1`
- review_mode: `delta`
- mode_reason: 本轮新增了隔离真栈 Runbook 与 M1 的 ID/依赖/并行组/精确范围/两轨
  exit contract。它们不改变 bundle/profile-ingress 架构，却直接决定 worker 可写范围和
  reviewer 能否执行必需的外部渠道旅程；因此重查这些 workflow atoms 及其真实脚本链路。
- started_at: `2026-08-04T17:40:16+08:00`
- completed_at: `2026-08-04T17:42:25+08:00`
- duration: `2m 09s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### Coverage

- `retained_from: Round 1–5` — D1–D3、static/managed activation、两条
  profile-ingress 的顺序与 R4-W1 liveness contract 未在本轮修订中改变；R4-W1 保持
  closed，R5 的 PATCH failure seam/Runbook/M1 result 要求仍完整。
- 重查新增的 Runbook lifecycle/health/cleanup 命令、外部 Feishu acceptance 前置，及
  M1 的 dispatcher fields、目录骨架、范围和 `[worker]` / `[reviewer]` exits。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R4-W1 | reconnect PATCH 失败在逐 agent boundary 内跳过当前 profile，仍让 outbox 与实时 retry 语义成立。 | R6 只新增 lifecycle 与 milestone presentation；D2/interface/implementation sequence 未改，M1 仍要求「PATCH 失败不阻断 post-register 收敛」（`design.md:253,292-293,318`）。 | **closed (retained)** |

### 实际核查证据

| 受影响原子 | 实际路径与证据 | 结论 |
|---|---|---|
| 隔离栈起停与健康检查 | Runbook 的 `--wt`、`PATH`、`.e2e-ports.env`、`openapi.json`、Gateway PID/log 与 paired down（`design.md:264-279`）对应脚本的 `--wt`/`--main-config` parsing（`scripts/e2e-up.sh:29-45`；`e2e-down.sh:19-27`）、worktree-local config（`e2e-up.sh:76-106`）和 runtime 的组合健康检查（`docs/development/worktree-runtime.md:100-114`）。`bash -n scripts/e2e-up.sh`、`bash -n scripts/e2e-down.sh` 与两者 `--help` 均通过。 | 通用 IM + Gateway 隔离、存活检查与清理命令真实有效，且未新增服务或改变 D1–D3 ownership。 |
| M1 dispatch contract 与骨架 | M1 的 `bugfix-499-M1` / `lark-skill-bundle` 正符合 orchestrator 的 `<unit-id>-M<N>` 与 `M<N>-<title>` 约定（`change-orchestrator/SKILL.md:131-142`）；unit 中恰有对应的 `M1-lark-skill-bundle/.gitkeep`。`channel_manager.py` 实际拥有 `FeishuActivationPolicy`（`src/personal_assistant/gateway/channel_manager.py:154-180`），`managed_channel_control.py` 实际创建它（`:147-153`），与 M1 文件范围相符；单 M1 的 `—` / A 不产生并行写冲突。 | 新表格保持单一垂直 slice、空骨架和既有 worker/reviewer 两轨；文件归属没有引入新的实现边界冲突。 |
| 外部 Feishu 旅程的实际启动条件 | Runbook 要求同一隔离 Gateway 用测试 Feishu chat 验静态 `config.channels` 和 IM 托管 manifest（`design.md:260-262,297-312`）。但 `e2e-up.sh` 默认只复制 `$HOME/.nano-assistant/config.yaml`，未给出或验证可用的测试 config（`:29-45,76-79`）；它每次删除 IM DB、channel key 与 manifest（`:132-148`）。新鲜 IM 因而没有托管 channel；静态 `credentialRef` 而没有 `appSecret` 的 Feishu channel 也会被 registry 直接跳过（`gateway/composition.py:636-665`）。 | generic stack health 不等于存在可接收/发送的 test Feishu channel；两种 M1 旅程都没有可复现的 provisioning/availability path。 |
| current external-channel baseline | current E2E catalog 明确 Feishu 1:1 的真 app/WS/LLM 依赖外部 credentials/network，尚无稳定默认 Gateway E2E（`docs/development/e2e-critical-paths.md:66-68`）。 | 这不是可以由 mock 或刚启动的空 IM 替代的验证；Runbook 必须把外部 fixture 的来源和可用性作为明确门槛。 |

### 受影响架构进攻

| 角度 | 主动攻击与结论 |
|---|---|
| 生命周期归属 | 复用 `e2e-up.sh` / `e2e-down.sh` 是正确的最小做法：脚本已经拥有 worktree config、node identity、PID 与清理，Runbook 不应复制另一套服务启动逻辑。 |
| 验收真实性 | 不能把「IM/Gateway 健康」当作「外部 Feishu 入口可用」。前者由脚本建立，后者还需要 test app credentials、静态 adapter 或 fresh-IM managed manifest 的明确来源；遗漏会使真入口门槛退化成无法执行的文字。 |

### Issues

- [R6-C1][CRITICAL] [Runbook 外部验收前置；M1 `[reviewer]` exit] Runbook 声明要在
  `e2e-up.sh` 的隔离真栈中以测试 Feishu chat 覆盖静态与托管两条 binding，但只列出
  generic 启停和「测试 Bot/channel」的名称，没有定义隔离测试 config/credentials 的来源、
  可用性检查，或 fresh IM 中托管 manifest 的建立路径。实际脚本默认复制
  `$HOME/.nano-assistant/config.yaml`，每次删除 channel key/manifest 和 IM DB
  （`scripts/e2e-up.sh:29-45,132-148`）；静态配置若是本仓允许的 `credentialRef`-only
  形态则不会注册 Feishu adapter（`src/personal_assistant/gateway/composition.py:656-665`），
  而全新 IM 也没有托管 channel。**不改，worker 可以通过 Runbook 的启动健康检查却没有
  一条真实 Feishu message 能进入 Gateway；或为完成 M1 临时复制主状态/凭据而破坏隔离。
  M1 的两个 reviewer Scenario 因而既不能可靠执行，也不能用 mock 替代。**

### Recommendations

- [R6-R1] 保留现有脚本化生命周期，但在 Runbook 明确列出：隔离测试 Feishu
  config 的安全来源并以 `--main-config` 传入（静态场景须是可启动的 test `appSecret`
  配置，而非仅 `credentialRef`），以及 fresh IM/node 上建立托管 test manifest 的既有
  操作入口；启动后先验证 test bot 已绑定、可收发一条探测消息，再跑三个真实 Scenario。
  若任一外部 fixture 当前不能提供，按现有规则记录为 M1 产品门禁 blocker，而不是把
  空栈 health 或 mock 当成通过。

## Round 7

### Metadata

- reviewer: `/root/design_review_r1`
- review_mode: `delta`
- mode_reason: R6-C1 的修订具体新增了仓外 source config、静态 credential 形态、fresh-IM
  managed-channel 建立、fixture ping/shadow evidence 与 M1 gate。它限定在真实验收驱动链，
  但需要沿脚本、Web IM route/control service、Gateway manifest receiver 和前端运行时
  逐段验证，才能判断该闭环是否真的可执行。
- started_at: `2026-08-04T17:49:51+08:00`
- completed_at: `2026-08-04T17:52:57+08:00`
- duration: `3m 06s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### Coverage

- `retained_from: Round 1–6` — bundle source、static/managed capability contract、两条
  profile ingress、R4-W1 liveness、M1 单一 vertical slice 和 R6 的 process ownership 均未
  改变。
- 重查 R6-C1 resolution 的 `--main-config`、`appSecret` static adapter、fresh-IM
  managed manifest、channel reconcile/status、fixture ping/shadow evidence，以及为使用
  `/settings/agents/<id>` 而新增的 Web IM runtime 前置。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R6-C1 | 仓外 `0600` source config 通过 `--main-config`；静态 test channel 使用 `appSecret`；fresh IM 由 Web IM 创建 managed Feishu channel 并等待 connected；两种 fixture 都 ping/shadow 验证，缺失即 blocker。 | `e2e-up.sh` 确实接收并复制 `--main-config`（`scripts/e2e-up.sh:29-45,76-79`）；static registry 对 `credentialRef`-only 跳过、对 `appSecret` 建 adapter（`src/personal_assistant/gateway/composition.py:636-665`）。Web IM 的 channel panel 调用该 POST（`src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts:562-574`），route/service 以密文 store 保存 secret 并推 `channel.reconcile`（`src/IM/api/routes/agent_channels.py:207-232`、`IM/application/channel_control_service.py:40-64`、`IM/api/deps.py:174-205`）；Gateway 接收并 apply reconcile（`src/personal_assistant/ws/im_connection.py:764-781,883-893`）。 | **closed**, 但本轮发现其指定的 Web IM 入口尚缺 worktree runtime 前置（R7-C1）。 |

### 实际核查证据

| 受影响原子 | 实际路径与证据 | 结论 |
|---|---|---|
| static 与 fresh-IM managed fixture | Runbook 精确要求仓外 `0600` config、static `appSecret`、第二 agent、fresh IM UI create、desired/applied/connected、两次 ping 和 shadow API/UI（`design.md:264-283,299-356`）。Gateway `node.register` 把 source config 全部 agent 与 skills seeds 带入 fresh IM（`src/personal_assistant/reporter/upstream_reporter.py:245-276`），IM persistence 逐个创建 profile/user/binding（`src/IM/infra/gateway_persistence.py:99-161`）。 | R6 所指出的 credential、manifest 与 availability ownership 已明确且走现有生产路径；无需复制主环境 manifest。 |
| managed-channel UI/control/reconcile | `/settings/{path}` 是现有 SPA entry（`src/IM/app.py:201-218`），agent detail 实际挂载 `AgentChannelsPanel`（`frontend/.../agent-detail-page.tsx:1616-1653`）；panel POST create 并轮询 pending/apply/connection state（`agent-channels-panel.tsx:568-648,755-790`）。IM `push_reconcile()` 把新 manifest 交给已连接 node（`src/IM/ws/gateway/channel_control.py:37-43`），Gateway 的 managed bindings 已在 composition 和 WS dispatcher 中接线（`gateway/composition.py:494-523,584-590`；`ws/im_connection.py:883-893`）。 | 文档所指的受控入口、密文保存、下发和 `connected` 观测均真实存在。 |
| Web IM runtime availability | `src/IM/frontend/dist/` 是 `.gitignore` 的本地构建产物，`dist/index.html` 不受 Git 跟踪（`.gitignore:242`；`git ls-files --error-unmatch src/IM/frontend/dist/index.html` 退出 1）。`e2e-up.sh` 只以 worktree `PYTHONPATH` 启动 IM，未传 `IM_FRONTEND_DIST_DIR`（`scripts/e2e-up.sh:150-153`）。IM 仅在候选 dist 存在时服务 `/settings/...`，否则转发到默认 `http://127.0.0.1:4173`（`src/IM/app.py:88-131,174-183,213-218,262-268`）；开发运行文档也明确 e2e-up 不启动 Vite（`docs/development/worktree-runtime.md:116-129`）。 | 新 milestone worktree 通常没有 dist 且没有 Vite，Runbook 的 Web IM setup 不能保证打开。 |

### 受影响架构进攻

| 角度 | 主动攻击与结论 |
|---|---|
| 验收 owner / 深度 | 用既有 Web IM → ChannelControlService → Gateway reconcile 是正确的深路径；没有为本 unit 新造 credential bootstrap 或专用管理 API。 |
| 可执行性 | `e2e-up` 只证明 API/Gateway 就绪。真实 review 把 managed channel setup 放在 Web IM，便必须同时拥有 UI asset/server；依赖当前 checkout 恰好留下的 ignored dist 会使门禁随 worktree 漂移。 |

### Issues

- [R7-C1][CRITICAL] [Runbook Web IM managed fixture setup；M1 `[reviewer]` exit] R6
  resolution 要 reviewer 在 fresh IM 的 `/settings/agents/<managed-test-agent-id>` 创建 managed
  Feishu channel（`design.md:325-332`），但启动命令只设 `.venv` 的 `PATH`（`:264-276`）。
  `e2e-up.sh` 不起 Vite，`dist/` 又是不提交的本地产物；新 milestone worktree 没有 `dist`
  时 IM 会把 settings 路由 307 到未启动的默认 `127.0.0.1:4173`（`scripts/e2e-up.sh:150-153`；
  `src/IM/app.py:174-183,213-218,262-268`；`docs/development/worktree-runtime.md:116-129`）。
  **不改，外部 Bot/credentials 即使齐备，reviewer 仍无法经文档指定的受控入口创建 fresh-IM
  manifest；R6-C1 的 managed fixture、ping 与 M1 reviewer Scenario 会在 health check 已通过后
  才中断。**

### Recommendations

- [R7-R1] 在 Runbook 的启动前置中选择并写死一个受控 Web IM 入口。最小路径是在确认
  `NANO_MAIN_ROOT/src/IM/frontend/dist/index.html` 存在/已按当前 UI 构建后，把
  `IM_FRONTEND_DIST_DIR="$NANO_MAIN_ROOT/src/IM/frontend/dist"` 与现有 `PATH` 一同传给
  `e2e-up.sh`，再验证 `$IM_URL/settings/agents/<managed-test-agent-id>` 返回 Web shell；或
  按 `worktree-runtime.md` 启动受控 Vite、设置对应 dev-base URL 并记录/回收其 PID。两者均
  不可用时按现有规则记录产品门禁 blocker，不能把 IM OpenAPI health 当作 Web IM 可用。

## Author Resolution after Round 6

| Issue | Resolution | Evidence / contract change |
|---|---|---|
| R6-C1 | 接受。Runbook 现在要求仓外 `0600` 的 `FEISHU_E2E_MAIN_CONFIG` 经 `e2e-up.sh --main-config` 传入，给出静态 channel 必须使用实际 `appSecret` 的字段形状，并明确 `credentialRef`-only 不会启动静态 adapter。fresh IM 清除 manifest 后，reviewer 必须在现有 Web IM `设置 → Agent → 通道 → 添加通道 → Feishu` 入口为独立 managed test agent 保存测试 App ID/Secret，等 runtime `connected`；不能复用/复制主环境 manifest。 | 实际脚本确实复制指定 main config 且清空本地 key/manifest（`scripts/e2e-up.sh:29-45,76-79,145-148`）；静态 registry 只接受 `appSecret`（`gateway/composition.py:636-665`）；受控托管入口实际为 `POST /im/v1/agents/{agent_id}/channels`，并封装 secret 后通知在线 node（`IM/api/routes/agent_channels.py:154-178`; `IM/application/channel_control_service.py:39-62`）。设计 `Runbook` 现把这些前置、两个隔离 chat、静态/托管各一条 `fixture ping`、IM shadow 的真实核查和缺 fixture 的 blocker 写为可执行 M1 reviewer exit。 |

## Author Resolution after Round 7

| Issue | Resolution | Evidence / contract change |
|---|---|---|
| R7-C1 | 接受。Runbook 继续使用既有 Web IM 受控入口，不新增前端服务：它先确认主 checkout 的本机 `src/IM/frontend/dist/index.html` 存在，否则仅在该 checkout 执行既有 `npm run build`，然后把该目录作为 `IM_FRONTEND_DIST_DIR` 继承给 `e2e-up.sh`。启动后以临时 `IM_URL/settings/agents/<managed-test-agent-id>` 返回 Web shell 为硬检查，才执行 managed channel create；build/route 任一不可用时按 M1 product-gate blocker 退出。 | `e2e-up.sh` 不会启动 Vite，且 IM 已以 `IM_FRONTEND_DIST_DIR` 作为优先 frontend candidate；本 unit 不改 UI，故复用主 checkout 的当前 build 是最小、隔离的既有路径。它不复制 ignored `dist` 到 milestone worktree，也不在本期修改 IM/frontend 或新增 lifecycle owner。 |

## Round 8

### Metadata

- reviewer: `/root/design_review_r1`
- review_mode: `closure`
- mode_reason: 本轮是 R7-C1 的直接运行时前置补足：只增加既有 IM frontend asset
  candidate 的环境传递、缺失时的现有 build、settings shell probe 和 blocker 规则；不改变
  Web/IM/Gateway 的职责、R6 managed fixture 流程或 M1 scope。
- started_at: `2026-08-04T17:54:39+08:00`
- completed_at: `2026-08-04T17:55:46+08:00`
- duration: `1m 07s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R7-C1 | 若主 checkout 没有 dist 则原地 build；把其目录经 `IM_FRONTEND_DIST_DIR` 传给 `e2e-up.sh`；probe 临时 IM settings shell；不用 Vite、不复制/提交 dist，失败则 blocker。 | `IM.app` 把 `IM_FRONTEND_DIST_DIR` 放在 worktree-local candidates 之前，并在候选含 `index.html` 时直接服务 `/settings/...`（`src/IM/app.py:88-131,174-183,201-219,262-268`）。Runbook 先 build/check `index.html`，再以同一 env 启动脚本并检查 shell（`design.md:264-295`）；`e2e-up.sh` 的 Python 启动只补 `IM_JWT_SECRET`/`PYTHONPATH`，不清除继承 env（`scripts/e2e-up.sh:150-153`）。`e2e-down.sh` 仍只删除 worktree 运行态，不触碰主 checkout build（`scripts/e2e-down.sh:77-84`）。 | **closed** |

### 直接核查证据

- `src/IM/frontend/dist/` 确为 ignored、不追踪的本机 build artifact（`.gitignore:242`；
  `git ls-files --error-unmatch src/IM/frontend/dist/index.html` 退出 1）；Runbook 正确地
  既不复制它到 milestone worktree，也不把它纳入本 unit。
- 当前 `dist/index.html` 的 Web shell 标识正是 Runbook probe 检查的
  `<!doctype html>`；`IM.app` 对 `/settings/{path}` 复用同一 entry responder，故该 probe
  能排除 R7 指出的 307-to-Vite fallback（`src/IM/app.py:174-183,213-218`）。
- R6 的 managed fixture 不受 asset source 变化影响：settings page 的 channel panel 仍调用
  `POST /im/v1/agents/{agent_id}/channels`（`src/IM/frontend/src/features/settings/agents/
  im-agent-config-api.ts:562-574`），IM 仍 push reconcile，Gateway 仍 apply manifest
  （`src/IM/api/deps.py:174-205`、`src/personal_assistant/ws/im_connection.py:764-781,883-893`）。

### Issues

None.

### Recommendations

None.
