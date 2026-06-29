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
  Agent 解读: 只追踪 use_count 和 last_used_at。不区分 view/use（hermes 自己也不区分），patch_count 由 skill_manage 写侧追踪。

- Q5: /skill:<name> 斜杠命令现在重写为 `Use the "<name>" skill for this request.`，模型随后用 `read` 读 SKILL.md。改完后这条路径也走 `skill_view` 吗？
  我的推荐：是。斜杠命令重写后的文案改为引导模型调 `skill_view` 而非 `read`。这样无论用户手动 `/skill-name` 还是模型自动调用，都走同一条路径，统计和 compaction 注册都能覆盖到。
  反方：斜杠命令是用户显式触发，语义上和模型主动 view 不同。但追踪的目的是知道"skill 被用了"，不管谁触发的都该算。
  A(原话): （用户未单独回答此问题，但从上下文确认了 skill_view 替代 read 的方向，此问题作为逻辑推导写入 spec）
  Agent 解读: 统一路径。formatter.py 的引导文案和斜杠命令重写都指向 skill_view。

- Q6: 你项目有 self_improvement.py（后台 review），但没有 hermes 的 Curator（定期扫描 skill 生命周期）。现在 use_count / last_used_at 写了之后没有消费者。是先追踪后补 Curator，还是这次一起补?
  A(原话): 那这次把curator机制也补上
  Agent 解读: scope 扩大，Curator 纳入本 unit。

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
skill 创建后，随着使用或闲置，自动在三个状态间流转：
- `active` → `stale`（30 天未被 skill_view 读取）
- `stale` → `archived`（90 天未用，物理移到 `.archive/` 目录）
- `stale` → `active`（被重新读取，复活）

pinned skill 跳过自动流转。Curator 每 7 天跑一次确定性扫描（不调 LLM），CLI 启动时和 Gateway housekeeping loop 中触发。

**与 hermes 的对齐**：hermes 本来就是三工具拆分（skills_list / skill_view / skill_manage）+ Curator。用户抄代码时把 view 和 list 合进了 skill_manage，Curator 没抄。现在补上。

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

#### Scenario: skill_view 调用记录使用统计
- **WHEN** agent 成功调用 `skill_view(name="xxx")`
- **THEN** 该 skill 的 use_count +1，last_used_at 更新为当前时间

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

### Requirement: 系统提示词引导模型使用 skill_view 而非 read

#### Scenario: formatter 引导用 skill_view 加载 skill
- **WHEN** 系统提示词生成 `<available_skills>` 块
- **THEN** 引导文案指示模型用 skill_view（而非 read 工具）加载 skill 内容

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
  - 使用统计追踪（use_count + last_used_at）
  - 压缩存活机制（addInvokedSkill + compaction 时 re-inject）
  - Curator 生命周期管理（active/stale/archived，periodic 触发，7 天门控）
  - 所有引用点迁移（product.py、kernel.py、self_improvement.py、feature_registry、reporter 等）
- 非目标：
  - skill_view 的 file_path 参数（用户明确排除）
  - fork 子 agent 模式（CC 特有，本期不做）
  - contextModifier（权限/模型/effort 覆盖，CC 特有，本期不做）
  - 条件激活 paths 字段
  - skills_list 独立工具（list 留在 skill_manage 里）
  - Curator 的 LLM 合并 pass（hermes 的 consolidate 功能，本期不做）
  - Skills Hub 社区分发
