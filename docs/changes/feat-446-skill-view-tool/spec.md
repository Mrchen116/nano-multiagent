# feat-446: 增加独立 skill_view 工具 + Curator 生命周期管理

## Relations

- Related: feat-392（kernel spec 契约层）

## 原始需求

> 加个需求，增加skill view工具，我觉得从逻辑上，skill view更合理，因为skill工具隐含了执行的意思，但是其实看了skill详细情况，或许不适合就不执行。引入的目的是我刚刚所说，为了可审计可监控skill，在压缩时可以带上，如CC的。以及自进化时能知道使用情况的统计。但没必要有file_path参数

> 我skill_manage是从hermes 抄过来的。他是什么样的？

> ok，那我现在用到skill_manage的地方，你都得去hermes agent审视一下，他是不是把skill view工具也加进去了。这样才能安全的删除

> 继续，所以我的选择是增加skill_view，并skill_manage移除view

> 对比，CC和hermes，我来思考下

> 按我现有的skill_manage(action="view") 返回

> 好（指 use_count + last_used_at only）

> 对（指 addInvokedSkill 压缩存活）

> 等下，我们有hermes 的Curator机制吗

> 那这次把curator机制也补上

> 我的意思就是纳入Per-skill Batch到本需求中。所以你统计use_count的同时，还要统计在哪个session用的，才能拿jsonl分析。

> 这要学习hermes的设计

> 对（指 hermes curator 触发方式：periodic + 7天门控 + 确定性扫描）

## 澄清记录

- Q1: skill_view 和现有 skill_manage 的 view action 的关系——拆出来还是保留两处?
  A(原话): 继续，所以我的选择是增加skill_view，并skill_manage移除view
  Agent 解读: 明确选择拆分。skill_manage 去掉 view action，skill_view 成为独立只读工具。

- Q2: skill_view 返回格式——结构化 JSON 还是原始文本?
  A(原话): 按我现有的skill_manage(action="view") 返回
  Agent 解读: 沿用现有返回格式 `{success, name, content, location}`，不引入 hermes 的 linked_files/tags 等额外字段。

- Q3: 压缩存活机制——是否引入 CC 的 addInvokedSkill?
  A(原话): 对。
  Agent 解读: skill_view 调用成功后注册 addInvokedSkill(name, path, content)。compaction 时将已注册 skill 的 name + content 作为 `<system-reminder>` 重新注入。

- Q4: 使用统计——追踪哪些字段?
  A(原话): 好（指 use_count + last_used_at only）
  Agent 解读: 追踪 use_count 和 last_used_at。不区分 view/use（hermes 自己也不区分），patch_count 由 skill_manage 写侧追踪。
  后续补充（Q10）：F4 纳入后，skill_view 调用时记录 {session_id, timestamp}。timestamp 同步更新 last_used_at（给 Curator 用），session_id 存入 session 引用列表（给 F4 batch 分析找 JSONL 用）。一次记录两个用途。

- Q11: F2 蒸馏 skill 的触发方式?
  A(原话): 用户主动发起。看skill-evolution中讲的。agent自己判断这是现在就支持的，主agent用skill_manage搞，或者Per-turn Review。
  Agent 解读: F2 是用户主动入口（选 session + 写意图），和 F3/F4 的自动触发正交。agent 自动判断并创建 skill 已有 F3 覆盖。

- Q12: F2 的入口形态?
  A(原话): 我觉得这个可以做成一个skill，然后IM上可以在左边右键或者某种交互，选择某个session或者某几个session，然后跳转到一个新的对话中，写意图说明，然后用这个session总结生成skill的skill来给用户生成skill。这个skill用户可以选择生成成PA产品级的，还是agent级的
  Agent 解读: F2 两层实现——IM 前端做 session 选择交互（右键 → 跳转新对话），蒸馏 skill 本身是一个标准 SKILL.md（教 agent 读 transcript + 意图 → 生成 skill）。用户选 PA 级或 agent 级决定写入哪个 skill_root。

- Q13: 面板归哪?
  A(原话): 本unit包含了IM的实现
  Agent 解读: skill 使用统计面板（IM 前端）在本 unit 内实现，不只是数据层。

- Q14: Curator 管辖范围——所有 skill 还是只管自动创建的?
  A(原话): F2生成的skill属于手工生成，也不进行curator。然后所有skill虽然不都进行curator，但是都要记录使用次数，使用的session。
  Agent 解读: 使用统计对所有 skill 生效（不管来源）。Curator 只管自动创建的 skill（F3 Per-turn Review 输出 + F4 Per-skill Batch 输出），不管手工创建的（F1 从零 + F2 蒸馏）。F1/F2 的 skill 是用户显式创建的，生命周期由用户自己管理。

- Q5: /skill:<name> 斜杠命令现在重写为 `Use the "<name>" skill for this request.`，模型随后用 `read` 读 SKILL.md。改完后这条路径也走 `skill_view` 吗？
  我的推荐：是。斜杠命令重写后的文案改为引导模型调 `skill_view` 而非 `read`。这样无论用户手动 `/skill-name` 还是模型自动调用，都走同一条路径，统计和 compaction 注册都能覆盖到。
  反方：斜杠命令是用户显式触发，语义上和模型主动 view 不同。但追踪的目的是知道"skill 被用了"，不管谁触发的都该算。
  A(原话): （用户未单独回答此问题，但从上下文确认了 skill_view 替代 read 的方向，此问题作为逻辑推导写入 spec）
  Agent 解读: 统一路径。formatter.py 的引导文案和斜杠命令重写都指向 skill_view。

- Q6: 你项目有 self_improvement.py（后台 review），但没有 hermes 的 Curator（定期扫描 skill 生命周期）。现在 use_count / last_used_at 写了之后没有消费者。是先追踪后补 Curator，还是这次一起补?
  A(原话): 那这次把curator机制也补上
  Agent 解读: scope 扩大，Curator 纳入本 unit。

- Q8: hermes Curator 是全局扫描（所有 agent 共享 `~/.hermes/skills/`），本项目多 agent per-workspace 隔离，Curator 怎么处理?
  我的推荐：改为 per-workspace 扫描。理由：本项目 skill 天然按 agent workspace 隔离，`skill_manage` 写入路径是 per-session 的，self_improvement 创建的 skill 也在当前 agent 的 workspace 里。全局扫描会打破隔离。
  A(原话): 对，我改成per-workspace的。
  Agent 解读: Curator 只扫描当前 agent 的 `<workspace_root>/<config_dirname>/skills/`，不碰别的 agent。状态文件 `.curator_state` 也存在 workspace 内。

- Q7: Curator 的触发方式——hermes 是"agent 空闲 + 距上次超过 7 天"时触发。Curator 是独立定时触发（hermes 的方式），还是挂在 self_improvement 里一起跑?
  我的推荐：独立。理由：Curator 是确定性扫描（检查时间戳，不需要 LLM），和 background review（LLM 审视）职责不同。混在一起会让 self_improvement 更复杂。
  反方：独立意味着要加新的调度机制（cron 或 heartbeat 触发）。挂在 self_improvement 里可以复用现有触发链路。
  A(原话): 这要学习hermes的设计
  Agent 解读: 读了 hermes 源码确认触发方式——CLI 启动时 daemon 线程调 `maybe_run_curator(idle_for_seconds=inf)`，Gateway 挂在 housekeeping loop 每 N tick 调一次。两者都传 `idle_for_seconds=inf`（始终 eligible），真正门控在 Curator 内部的 `config.interval_hours`（默认 7 天）。Curator 本身是确定性扫描：遍历所有 skill 的 last_used_at，30 天 → stale，90 天 → archived（物理移到 .archive/）。pinned skill 跳过。和 per-turn 的 self_improvement（LLM review）完全独立。

## 用户场景

用户（agent）在执行任务时，系统提示词里的 `<available_skills>` 列出了可用 skill 的名字和描述。agent 需要读取某个 skill 的完整内容来决定是否遵循其指令。

**当前做法**：formatter.py 引导模型用 `read` 工具读 SKILL.md 文件。问题是 `read` 是通用文件读取工具，没有 skill 语义——无法追踪"哪些 skill 被读过"，压缩时无法带上已读 skill 的内容（不像 CC 的 `addInvokedSkill` 机制），自进化体系也无法统计 skill 的使用频率。

**拆分后的工具职责**：
- **`skill_view`**（读侧）：读取 skill 完整内容，追踪使用统计，压缩时可带上。模型在判断"这个 skill 适不适合用"时调用，看了内容再决定是否执行。
- **`skill_manage`**（写侧）：只管 create / edit / patch / list / write_file / remove_file。去掉 view action。

**Curator 生命周期管理**：
Curator 只管自动创建的 skill（F3 Per-turn Review 输出 + F4 Per-skill Batch 输出），不管手工创建的（F1 从零 + F2 蒸馏）。手工 skill 的生命周期由用户自己管理。

自动创建的 skill 随着使用或闲置，在三个状态间流转：
- `active` → `stale`（30 天未被 skill_view 读取）
- `stale` → `archived`（90 天未用，物理移到 `<skill_root>/.archive/` 目录）
- `stale` → `active`（被重新读取，复活）

pinned skill 跳过自动流转。归档前先打 tar.gz 快照（best-effort）。restore 纯手动。

**Curator 是 per-workspace 的**：hermes 是单 agent 全局架构（`~/.hermes/skills/`），所有 agent 共享一个 skill 目录，Curator 统一扫描。本项目是多 agent 架构，每个 agent 有自己的 workspace，skill 天然按 agent 隔离（`<workspace_root>/<config_dirname>/skills/`）。因此 Curator 改为 per-workspace 扫描——每个 agent 只管自己的 skill 目录，不碰别的 agent。

**使用统计**：
所有 skill 不管来源（F1/F2 手工 + F3/F4 自动）都记录使用统计（use_count + session 引用列表）。统计对所有 skill 生效，Curator 只对自动创建的 skill 生效。

**使用统计面板（初版）**：
IM 前端增加 skill 使用统计面板，初版三个视图，后续根据使用体验迭代：

1. **Skill 列表视图**（主视图）：每行一个 skill，列：名字、来源（F1/F2/F3/F4）、状态（active/stale/archived）、use_count、最近使用时间、趋势 sparkline。默认按最近使用时间降序。一眼能回答"哪些 skill 在用，哪些是死重"。

2. **Agent 维度视图**：选一个 agent，看它的 skill 使用热力图——哪些 skill 用得多、哪些少。下面列该 agent 自动创建的 skill 列表（F3/F4 输出），每个标注 use_count。能回答"这个 agent 的自进化有没有产出价值"。

3. **自进化健康度视图**：三个数字卡片——F3/F4 创建的 skill 总数 → 其中 still active 的数量 → 其中 use_count > 0 的数量（漏斗比 = 自进化存活率）。下面是一个时间线：每个 skill 的创建时间 → 首次使用时间 → 最后使用时间，用色块区分来源。

Curator 每 7 天跑一次确定性扫描（不调 LLM），CLI 启动时和 Gateway housekeeping loop 中触发。状态持久化到 workspace 内的 `.curator_state` JSON 文件。

**Per-skill Batch 优化（F4）**：
skill_view 调用时记录 `{session_id, timestamp}`。当某个 skill 的 `uses_since_last_B` 达到阈值（默认 ~20），触发该 skill 的 batch 优化：收集这些已结束 session 的 JSONL transcript，用 LLM 分析跨 session 的系统性缺陷（用户纠正、工具报错、任务放弃等信号），找到 ≥2 个 session 反复出现的问题后，通过 `skill_manage(action="patch")` 修补 skill。

F4 只 patch 不创建。分析的是"这个 skill 哪里有问题"，不是"要不要建新 skill"。具体分析流程（W: map-reduce 多 agent 并行 vs A: 单 agent 单轮）留 design 阶段选型。

**F2 手动蒸馏 skill**：
用户在 IM 左边栏右键选择若干已结束 session → 跳转到新对话 → 写意图说明 → 系统读这些 session 的 JSONL transcript，提取模式，生成一个新的 SKILL.md。用户可选择生成到 PA 产品级还是 agent 级（决定写到哪个 skill_root）。

实现方式是一个蒸馏 skill（SKILL.md），教 agent 如何读 session transcript + 意图 → 生成 skill。IM 前端的 session 选择交互是 IM 层的事，本 unit 只做蒸馏 skill 本身。

**与 hermes 的对齐**：hermes 本来就是三工具拆分（skills_list / skill_view / skill_manage）+ Curator。用户抄代码时把 view 和 list 合进了 skill_manage，Curator 没抄。现在补上，并从全局改为 per-workspace。

**自进化体系总览**（五个正交机制）：

| | F1 · 从零创建 | F2 · 从历史蒸馏 | F3 · Per-turn Review | F4 · Per-skill Batch | F5 · Curator |
|---|---|---|---|---|---|
| **触发** | 用户手动 | 用户手动（选 session + 写意图） | 自动：单 session 内 tool calls ≥ 10 | 自动：单 skill uses_since_last_B ≥ 阈值（~20） | 自动：idle ≥ 2h + 距上次 ≥ 7 天 |
| **输入** | 用户口述 | 用户选的 session IDs + 意图文本 | 当前 session 的 hook 事件 | 该 skill 被用过的 X 个已结束 session 的 JSONL | 整个 skill 库（不读 transcript） |
| **分析深度** | 无（用户描述，agent 直接写） | 中：从 transcript 提取模式，生成 skill | 轻量：用户纠正、风格偏好、工作流改进 | 重量：跨 session 统计挖掘，≥2 证据阈值 | 维护级：时间戳扫描，不调 LLM |
| **能做什么** | 创建 skill | 创建 skill | 创建 + patch skill | 只 patch，不创建 | 归档 stale + 复活 active |
| **写入方式** | skill_manage(create) | skill_manage(create) | skill_manage(create/patch) | skill_manage(patch) | 直接改状态 + 物理移动目录 |
| **本 unit 现状** | 已有（skill-creator） | 新增：蒸馏 skill + IM session 选择交互 | 已有（self_improvement.py），补 skill_view 白名单 | 新增：阈值触发 + session 引用追踪 + 分析流程 | 新增：per-workspace periodic 扫描 |

五个机制正交不冲突：F1/F2 是用户主动创建入口，F3 在 session 内实时响应，F4 在 skill 维度批量深挖，F5 在库级别定期维护。

## 验收标准

### Requirement: skill_view 作为独立只读工具可用

#### Scenario: agent 调用 skill_view 读取 skill 内容
- **WHEN** agent 调用 `skill_view(name="change-spec-author")`
- **THEN** 返回该 skill 的 SKILL.md 完整内容（JSON 结构，含 success、name、content、location 字段）

#### Scenario: agent 调用不存在的 skill
- **WHEN** agent 调用 `skill_view(name="nonexistent-skill")`
- **THEN** 返回错误信息（success=false），不抛异常

### Requirement: skill_manage 不再包含 view action

#### Scenario: skill_manage 的 action 枚举不含 view
- **WHEN** 查看 skill_manage 工具的 input_schema
- **THEN** action 枚举为 create / edit / patch / list / write_file / remove_file，不含 view

### Requirement: 使用统计追踪

#### Scenario: agent 主动调用 skill_view 记录使用统计
- **WHEN** agent 调用 `skill_view(name="xxx")` 成功返回
- **THEN** 该 skill 的 use_count +1，last_used_at 更新为当前时间

#### Scenario: 用户通过 /skill:<name> 斜杠命令触发时也记录使用统计
- **WHEN** 用户输入 `/skill:<name>`，系统重写后引导模型调用 skill_view，skill_view 成功返回
- **THEN** 该 skill 的 use_count +1，last_used_at 更新为当前时间（和 agent 主动调用走同一条路径）

### Requirement: 压缩存活（compaction survival）

#### Scenario: 压缩后已读 skill 内容保留
- **GIVEN** agent 在对话中通过 skill_view 读取了 skill A 的内容
- **WHEN** 对话触发 compaction
- **THEN** skill A 的 name + content 在压缩后的上下文中以 `<system-reminder>` 形式重新注入

### Requirement: Curator 自动生命周期管理

#### Scenario: 30 天未用的 skill 标记为 stale
- **GIVEN** skill A 的 last_used_at 距今超过 30 天
- **WHEN** Curator 执行定期扫描
- **THEN** skill A 的状态从 active 变为 stale

#### Scenario: 90 天未用的 skill 归档
- **GIVEN** skill A 的 last_used_at 距今超过 90 天
- **WHEN** Curator 执行定期扫描
- **THEN** skill A 的状态变为 archived，其目录物理移到 `<skill_root>/.archive/`

#### Scenario: stale skill 被重新读取后复活
- **GIVEN** skill A 当前状态为 stale
- **WHEN** agent 调用 `skill_view(name="A")`
- **THEN** skill A 的状态恢复为 active

#### Scenario: pinned skill 不被自动流转
- **GIVEN** skill A 被 pinned
- **WHEN** Curator 执行定期扫描
- **THEN** skill A 的状态不变

### Requirement: skill_view 记录 session 引用

#### Scenario: skill_view 调用记录 session_id 和 timestamp
- **WHEN** agent 在 session S 中调用 `skill_view(name="xxx")` 成功
- **THEN** 记录 `{session_id: S, timestamp: now}`，其中 timestamp 同步更新 last_used_at，session_id 存入该 skill 的 session 引用列表

### Requirement: 从历史 session 蒸馏 skill（F2）

#### Scenario: 用户选 session + 意图生成 skill
- **GIVEN** 用户在 IM 左边栏选择若干已结束 session，跳转到新对话并写了一段意图说明
- **WHEN** 蒸馏 skill 被触发，读取这些 session 的 JSONL transcript
- **THEN** 系统从 transcript 中提取工作模式，生成一个新的 SKILL.md，内容覆盖用户意图描述的工作流

#### Scenario: 用户选择 skill 生成级别
- **WHEN** 蒸馏完成后
- **THEN** 用户可选择将 skill 写入 PA 产品级 skill root 或 agent 级 skill root

#### Scenario: 蒸馏 skill 是一个普通 SKILL.md
- **WHEN** 查看蒸馏 skill 的实现
- **THEN** 它是一个标准 SKILL.md 文件，教 agent 如何读 session transcript + 意图 → 生成 skill，使用 skill_manage(create) 写入

### Requirement: Per-skill Batch 优化触发

#### Scenario: 达到阈值后触发 batch 分析
- **GIVEN** skill A 的 uses_since_last_B 达到阈值 X
- **WHEN** skill_view 调用完成且计数器越线
- **THEN** 触发 skill A 的 batch 优化任务：收集对应的已结束 session JSONL，分析跨 session 系统性缺陷

#### Scenario: batch 分析只 patch 不创建
- **WHEN** batch 分析发现 skill A 的缺陷
- **THEN** 通过 `skill_manage(action="patch")` 修补 skill A，不创建新 skill

#### Scenario: batch 分析要求 ≥2 session 的证据
- **WHEN** batch 分析某个问题模式
- **THEN** 只有在 ≥2 个不同 session 中出现的问题才被采纳，单 session 的问题被忽略

### Requirement: 系统提示词引导模型使用 skill_view 而非 read

#### Scenario: formatter 引导用 skill_view 加载 skill
- **WHEN** 系统提示词生成 `<available_skills>` 块
- **THEN** 引导文案指示模型用 skill_view（而非 read 工具）加载 skill 内容

### Requirement: 使用统计面板（IM 前端，初版）

#### Scenario: Skill 列表视图
- **WHEN** 用户打开 skill 使用统计面板
- **THEN** 显示所有 skill 的列表，每行包含名字、来源（F1/F2/F3/F4）、状态（active/stale/archived）、use_count、最近使用时间、趋势 sparkline，默认按最近使用时间降序

#### Scenario: Agent 维度视图
- **WHEN** 用户选择某个 agent
- **THEN** 显示该 agent 的 skill 使用热力图 + 自动创建的 skill 列表（F3/F4 输出）及各自 use_count

#### Scenario: 自进化健康度视图
- **WHEN** 用户切换到健康度视图
- **THEN** 显示三个数字卡片（F3/F4 创建总数 → still active 数 → use_count > 0 数）+ 每个 skill 的创建→首次使用→最后使用时间线

### Requirement: 所有引用点正确迁移

#### Scenario: background review 白名单包含 skill_view
- **WHEN** self-improvement hook 启动后台 review
- **THEN** 工具白名单包含 skill_view（和 skill_manage）

#### Scenario: 产品层工具列表包含 skill_view
- **WHEN** coding_cli / personal_assistant 初始化工具集
- **THEN** skill_view 在可用工具列表中

## 范围与非目标

- 在范围：
  - 新建独立 `skill_view` 工具（platform 层）
  - `skill_manage` 移除 view action
  - formatter.py 引导文案从 read 改为 skill_view
  - 使用统计追踪（use_count + last_used_at + session 引用列表 {session_id, timestamp}），对所有 skill 不管来源生效
  - 压缩存活机制（addInvokedSkill + compaction 时 re-inject）
  - Curator 生命周期管理（active/stale/archived，per-workspace，periodic 触发，7 天门控，只管 F3/F4 自动创建的 skill）
  - Per-skill Batch 优化（F4）：uses_since_last_B 阈值触发，收集已结束 session JSONL，LLM 分析跨 session 系统性缺陷，≥2 证据阈值，只 patch 不创建
  - 手动蒸馏 skill（F2）：蒸馏 skill 本身（SKILL.md），教 agent 读 session transcript + 意图 → 生成 skill，支持 PA/agent 级别选择
  - IM 前端 skill 使用统计面板（per-skill 使用情况 + per-agent skill 使用分布）
  - 所有引用点迁移（product.py、kernel.py、self_improvement.py、feature_registry、reporter 等）
- 非目标：
  - skill_view 的 file_path 参数（用户明确排除）
  - fork 子 agent 模式（CC 特有，本期不做）
  - contextModifier（权限/模型/effort 覆盖，CC 特有，本期不做）
  - 条件激活 paths 字段
  - skills_list 独立工具（list 留在 skill_manage 里）
  - Curator 的 LLM 合并 pass（hermes 的 consolidate 功能，本期不做）
  - F4 的具体分析流程选型（W: map-reduce vs A: 单 agent，留 design 阶段）
  - Skills Hub 社区分发
  - Skills Hub 社区分发
