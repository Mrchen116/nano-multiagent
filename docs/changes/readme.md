# docs/changes/ 目录规范

变更单元的所有相关文档统一放在 `docs/changes/` 下，按变更单元聚合，方便查找和追溯。

目录分为活动区与历史区：

```text
docs/changes/
├── <unit-dir>/              # 未完成、暂停或完成证据不足
└── archive/
    └── <unit-dir>/          # 已完成，随实现 PR 一起归档
```

归档是 `git mv` 整个 unit 目录，不删除、压缩或拆散其中的首文档、design、milestone、报告、delta-spec
与 evidence。现有 `docs/archive/` 存放退役系统文档，不用于 change unit。

---

## 什么时候不需要建 unit

不是所有改动都要建目录。仪式过重会让小修变成负担。下列情况直接 commit 即可，不建 unit：

- 单文件、无行为变化、无设计决策的小修：typo、注释、常量值、配置目录路径、日志级别
- 纯重命名 / 局部 inline / 删死代码
- commit message 关联最近相关 unit，例如 `chore(feat-337): 调整配置文件目录到 ~/.nano/`

判据：**如果你写不出有意义的 `spec.md` / `incident.md`（即没有"用户视角的事要说"），就不该建 unit。**

如果是已合并 unit 的内部清洁（用户不感知），用 `chore` 提交并在 message 里关联原 unit；如果用户能感知到错误行为，开 bugfix。

---

## 变更单元之间的关联

参考 GitHub issue 的轻量做法：在每个 unit 的首文档（`spec.md` / `incident.md` / `motivation.md`）顶部加 **Relations** 段：

```markdown
## Relations

- Depends on: feat-338
- Blocks: feat-340
- Related: feat-336
```

规则：
- 只列 `unit_id`，不展开理由（理由写在正文）。
- 三个字段缺省可省略。
- 不引入 dev-tasks.json 的结构化字段，靠 grep 反查即可。
- 在分解时发现未做的强依赖，先停下来开依赖 unit，并在当前 spec 写 `Depends on: <id>`。

---

## 模板

模板自带在各 skill 的 `assets/` 目录中,由 skill 自己复制到 unit 目录。无需手动操作:

| 文档 | 由谁产出 | 模板位置 |
|---|---|---|
| `spec.md` / `incident.md` / `motivation.md` / `fix.md` | `change-spec-author` | `.claude/skills/change-spec-author/assets/` |
| `design.md` | `change-design-author` | `.claude/skills/change-design-author/assets/` |
| `tasks.md` / `progress.md` | `change-impl-worker` | `.claude/skills/change-impl-worker/assets/` |
| `acceptance.md` / `regression.md` | `change-reviewer` | `.claude/skills/change-reviewer/assets/` |

---

## 阶段与门禁

变更单元从立项到归档分四个阶段，每两个阶段之间有一个**门禁**——前一阶段未达标，禁止进入下一阶段。

```
[探索] ──门禁1──▶ [设计] ──门禁2──▶ [实施] ──门禁3──▶ [验收/归档]
```

### 阶段 1：探索（Explore）

**目的**：和用户/团队对齐"做什么"。这是**思考态**，不是实现态。

允许：读代码、画图、对比方案、做调研笔记（任意临时 md 都可以）、写/改 `spec.md` / `incident.md` / `motivation.md` 的"原始需求"和"澄清记录"段。

**禁止**：写产品代码、派 worker、跳过澄清直接写"用户场景/验收标准/根因/目标"。

agent 应该把澄清问题一轮一轮抛给用户，每轮记录 Q/A 到首文档。**不要一次性问完然后批量生成**——这是 opsx propose 的反模式。

### 门禁 1：spec / incident / motivation 定稿

进入"设计"前必须满足：

- [ ] 首文档无 `<!-- 模板说明 -->` 块、无 TBD、无"待澄清"
- [ ] 验收标准/RCA/目标状态已与用户对完
- [ ] Relations 段已填（无依赖时显式写"无"或省略整段）

### 阶段 2：设计（Design）

写 `design.md` / 修订 motivation 的"迁移与回滚策略"。这一阶段产出**架构决策**，不产代码。

**禁止**：在 design 阶段反过来改 spec 的用户视角（如果发现 spec 错了，回到阶段 1，不要原地修补）。

### 门禁 2：design 定稿 + milestone 拆分

进入"实施"前必须满足：

- [ ] `design.md` 已对齐 spec.md，关键决策、接口、数据流、风险回退齐备
- [ ] milestone 已拆分（`M1-xxx/` 目录已建且仅含 `.gitkeep`；`tasks.md` 由 worker 启动后编写）
- [ ] 每个 milestone 的退出标准独立可验
- [ ] R1 创建了一个独立 design reviewer；后续返工始终唤醒同一 reviewer，由 reviewer 自主选择 `closure` / `delta` / `full`
- [ ] `design-review.md` 按 `## Round N` 保留全部轮次、每轮时间、问题与 Author Resolutions；最后一轮 `Approved`、`0 CRITICAL / 0 WARNING`

### 阶段 3：实施（Apply）

由 `change-impl-worker` 在 worktree 里按 roadpoint 跑 TDD（先 Red/Verify，再 Green）。每完成一个 roadpoint 实时更新 `progress.md`。

**硬约束：实现期发现 design 偏差，立即暂停。**

worker 不许悄悄绕过设计；必须：
1. 暂停编码
2. 在当前 milestone 的 `progress.md` 加一段 `[Design 修订] R<n>: X → Y` 说明现状
3. 同步改 `design.md` 正文；如果影响后续 milestone，追加 `design.md` 顶部 Changelog
4. 通知人/orchestrator 确认后再继续

这是借鉴 opsx apply 的 pause-on-design-issue 原则——**phase-locked 不重要，知识同步重要**。

### 门禁 3：实施完成

进入"验收/归档"前必须满足：

- [ ] 所有 milestone 的 `tasks.md` 退出标准全部勾选
- [ ] 所有 milestone 的 `progress.md` 写齐 Evidence
- [ ] `design.md` Changelog 已同步实现期的所有偏差

### 阶段 4：验收 / 归档

由 `change-reviewer`（独立视角，不能是写代码的同一 agent）写 `acceptance.md` / `regression.md`。验收必须包含**上层文档同步检查**：本 unit 是否需要更新 `SPEC.md` / `内核设计SPEC.md` / `AGENTS.md` / 各产品 SPEC？需要就在验收报告里列出并改掉。

验收、verifier、长青契约归并和本地 CI 门禁全部通过后，`change-orchestrator` 在创建 PR 前执行：

```bash
mkdir -p docs/changes/archive
git mv "docs/changes/<unit_dir>" "docs/changes/archive/<unit_dir>"
```

PR body 和同一交付会话内的 CI/review 小修使用归档路径。会话退出后，只允许在 branch、PR head、clean
三项校验通过时恢复自包含小修；需要修改 design 或新增 milestone 的反馈交人决定，不为归档态建立第二套
实施生命周期。PR 尚未 merge 时 main 不受影响；PR merge 后实现与归档同时进入 main。

### 完成判据与历史迁移

- **新 unit**：以 orchestrator 全部门禁通过、已达到可创建 PR 状态为完成；归档是提 PR 流程的强制步骤。
- **历史 unit**：只有已合并 PR 明确引用该 unit_id，或存在明确通过的最终验收/回归报告，才可批量归档。
- 有开放 PR、活动 worktree、失败报告，或完成证据不足时，保守留在活动区，不按编号或目录年龄推断完成。

按 `unit_id` 查找时必须同时检查两层，并要求结果唯一：

```bash
unit_matches=$(find docs/changes docs/changes/archive -mindepth 1 -maxdepth 1 -type d \
  \( -name "<unit_id>" -o -name "<unit_id>-*" \) -print 2>/dev/null)
match_count=$(printf '%s\n' "$unit_matches" | sed '/^$/d' | wc -l | tr -d ' ')
if [[ "$match_count" -ne 1 ]]; then echo "expected one unit, found $match_count" >&2; exit 1; fi
unit_path=$unit_matches
```

change-spec-author 分配新编号不得手写扫描命令，统一执行：

```bash
python3 .claude/skills/change-spec-author/scripts/next_unit_id.py <type>
```

脚本同时扫描活动区和 archive，并在 Git common dir 中原子记录最后一次 reservation；所有 type、并发进程和
同一 clone 的 worktree 共用递增序列。目录与 reservation 两者的最大编号共同决定下一号，已保留但尚未建目录
的编号也不回收或复用。

---

## Agent 协作分工

| 阶段 | 主导角色 | 产出 | 不允许做 |
|---|---|---|---|
| 探索 / spec / design | 人 + 主 agent（可调研子 agent） | `spec.md`, `design.md`, `motivation.md`, `incident.md` | 写产品代码、派 worker |
| Design Gate 2 | unit 固定的 `change-design-reviewer`（与 design-author 独立） | `design-review.md` 逐轮追加日志 | 每轮换 reviewer、让 author 指定 mode、覆盖旧 Round、修改受审产物 |
| 派单 | `change-orchestrator` | milestone 派发包 | 自己写代码 |
| 实施 | `change-impl-worker`（每 milestone 一个 worktree，可并行） | `progress.md` + 代码 + 测试 | 越界改 design（必须走暂停流程） |
| 验收 | `change-reviewer`（独立视角） | `acceptance.md` / `regression.md` + 上层文档同步 | 与实施 agent 是同一个 |

关键原则：**写代码的 agent 不做验收**。验收角色独立才能给出真实判断。这一条比任何模板格式都重要。

---

## 命名规范

### 变更单元根目录

```
<type>-<id>[-<short-desc>]
```

| 段 | 规则 | 示例 |
|---|---|---|
| `type` | 变更性质：`feat`, `bugfix`, `refactor`, `perf`, `docs`, `chore` | `feat`, `bugfix` |
| `id` | 数字标识，全局递增 | `104`, `123` |
| `short-desc` | 2-5 个 kebab 词，可选 | `chat-mention-picker` |

全小写，连字符分隔，不超过 60 字符。

数字 id 在所有 type 间共享全局序列，由 change-spec-author 的 `scripts/next_unit_id.py` 原子保留并分配；归档
或并发 worktree 不重置序列。

示例：`feat-104-chat-mention-picker`, `bugfix-123-session-leak`, `refactor-150-session-manager`

### milestone 子目录

```
M<N>-<short-desc>
```

示例：`M1-domain-model`, `M2-ui-picker`

---

## 变更类型文档说明

### feat — 新功能开发

```
docs/changes/feat-104-chat-mention-picker/
├── spec.md                         # 需求规格
├── design.md                       # 技术方案
├── M1-domain-model/
│   ├── tasks.md                    # roadpoint 计划
│   └── progress.md                 # 实现记录
├── M2-ui-picker/
│   ├── tasks.md
│   └── progress.md
└── acceptance.md                   # 产品验收报告
```

| 文档 | 作用 | 什么时候写 |
|------|------|------------|
| `spec.md` | 定义功能边界、用户场景、验收标准来源。回答"做什么"。**只写用户视角，禁止讨论模块/接口/数据结构/库选型**——这些属于 design。 | 需求分解阶段，拆 milestone 之前 |
| `design.md` | 记录架构决策、接口设计、数据流、关键权衡与拒绝的方案。回答"怎么做"。顶部维护**变更日志**（见下）。 | 需求明确后、实现前 |
| `design-review.md` | 按 `Round` 保留固定独立 reviewer 的检查 mode、时间、台账、问题与 author 处理结果。 | design 自检后开始，Gate 2 每轮只追加 |
| `tasks.md` | 把 milestone 目标拆成可执行的 roadpoint，明确验收标准和测试策略。 | worktree 启动后、编码前 |
| `progress.md` | 记录每个 roadpoint 的完整执行过程（Context/Decision/Rationale/Evidence/Rollback/Commits）。 | 每个 roadpoint 完成后实时更新 |
| `acceptance.md` | 从产品经理视角判断功能是否对用户可用，记录用户旅程体验、问题清单与 verdict。 | 所有实现型 milestone 完成后 |

### bugfix — Bug 修复

bugfix 有两种规格，按影响面选：

**Lite 版（默认，适用于单 milestone、影响面小、无设计决策的 bug）：**

```
docs/changes/bugfix-123-session-leak/
├── fix.md                          # 现象 / 根因 / 修复 / 验证 四段合一
└── M1-fix/
    ├── tasks.md
    └── progress.md
```

`fix.md` 四段：现象与复现、根因（RCA）、修复方案、回归验证。一个文档说完。

**Full 版（影响面大、跨多 milestone、需要回归矩阵）：**

```
docs/changes/bugfix-123-session-leak/
├── incident.md                     # 问题报告与根因分析
├── M1-root-cause-fix/
│   ├── tasks.md
│   └── progress.md
└── regression.md                   # 回归验证报告
```

| 文档 | 作用 | 什么时候写 |
|------|------|------------|
| `fix.md`（lite） | 现象 / 根因 / 修复 / 验证 四段合一。 | 确认 bug 后开始写，修复后补全验证段 |
| `incident.md`（full） | 记录 bug 现象、复现步骤、影响范围、根因分析（RCA）。回答"什么问题"。 | 确认 bug 后、修复前 |
| `tasks.md` | 把修复任务拆成可执行的 roadpoint，明确复现验证和回归测试策略。 | worktree 启动后、编码前 |
| `progress.md` | 记录每个 roadpoint 的执行过程，重点记录根因确认和修复验证证据。 | 每个 roadpoint 完成后实时更新 |
| `regression.md`（full） | 确认 bug 已修复且未引入新破坏，记录复现验证和回归测试结论。 | bugfix milestone 完成后 |

判据：默认走 lite；只有当出现下列任一情况时升 full —— 多 milestone、需要独立的回归矩阵文档、根因横跨多个模块需要单独的事故复盘。

### refactor — 架构重构

```
docs/changes/refactor-150-session-manager/
├── motivation.md                   # 重构动机
├── design.md                       # 技术方案
├── M1-extract-interface/
│   ├── tasks.md                    # roadpoint 计划
│   └── progress.md                 # 实现记录
├── M2-migrate-callers/
│   ├── tasks.md
│   └── progress.md
└── acceptance.md                   # 产品验收报告
```

| 文档 | 作用 | 什么时候写 |
|------|------|------------|
| `motivation.md` | 说明当前架构痛点、目标状态、影响范围、迁移策略、回滚方案。回答"为什么改"。 | 决定重构后、拆 milestone 之前 |
| `design.md` | 记录新架构设计、接口变化、迁移步骤、兼容性策略、关键权衡。 | 需求明确后、实现前 |
| `tasks.md` | 把重构任务拆成可执行的 roadpoint，明确行为不变验证和迁移检查点。 | worktree 启动后、编码前 |
| `progress.md` | 记录每个迁移步骤的执行过程，重点记录行为一致性验证和回退点。 | 每个 roadpoint 完成后实时更新 |
| `acceptance.md` | 验证重构后系统行为一致、性能不劣化、迁移无残留。 | 所有实现型 milestone 完成后 |

### perf — 性能优化

```
docs/changes/perf-201-message-render/
├── motivation.md                   # 优化动机（含 benchmark）
├── design.md                       # 技术方案
├── M1-baseline/
│   ├── tasks.md                    # roadpoint 计划
│   └── progress.md                 # 实现记录
├── M2-optimization/
│   ├── tasks.md
│   └── progress.md
└── acceptance.md                   # 产品验收报告
```

| 文档 | 作用 | 什么时候写 |
|------|------|------------|
| `motivation.md` | 说明性能瓶颈定位数据（benchmark）、优化目标、影响范围。回答"为什么优化"。 | 确认瓶颈后、拆 milestone 之前 |
| `design.md` | 记录优化策略、算法/数据结构变更、测量方案、降级/回滚策略。 | 方案确定后、实现前 |
| `tasks.md` | 把优化任务拆成可执行的 roadpoint，明确基准测试和优化验证策略。 | worktree 启动后、编码前 |
| `progress.md` | 记录每个优化步骤的执行过程，重点记录 benchmark 前后对比数据。 | 每个 roadpoint 完成后实时更新 |
| `acceptance.md` | 验证优化目标达成、无功能退化、无性能回退。 | 所有实现型 milestone 完成后 |

---

## 文档边界硬约束

agent 在写文档时最常见的越界：在 `spec.md` 阶段问技术选型问题。下面是各文档**禁止**讨论的内容，违反就要打回。

| 文档 | 只回答 | 禁止讨论 |
|---|---|---|
| `spec.md` / `incident.md` / `motivation.md` | 用户做什么、看到什么、验收标准、问题现象 | 模块切分、类/函数命名、库选型、数据结构、接口形态、存储格式 |
| `design.md` | 模块切分、接口、数据流、关键权衡、被拒绝的方案 | 行级实现、变量名、具体的 SQL/HTTP body |
| `tasks.md` | 可执行步骤、测试策略、roadpoint 顺序 | 设计决策（决策应已在 design 锁定） |
| `progress.md` | Context / Decision / Rationale / Evidence / Rollback / Commits | 未来计划（属于 tasks） |

经验法则：如果澄清这个问题会改变"用户感知到什么"，它属于 spec；否则推迟到 design。

---

## design 变更日志

实现期发现 design 不完美，**直接修订 design.md + 同步改代码**，不开新 unit。

但 design 修订要可追溯。约定：

- **只影响当前 milestone 的修订**：在当前 milestone 的 `progress.md` 记一笔 `design 修订: X → Y, 原因 Z`，同时改 `design.md` 正文。
- **影响后续 milestone 的修订**：除上面之外，在 `design.md` 顶部维护变更日志：

```markdown
## Changelog

- 2026-04-29 (M2): 配置存储从 JSON 改为 SQLite — 见 M2/progress.md "design 修订"
- 2026-04-25 (M1): 取消 worker pool，改单进程串行 — 见 M1/progress.md
```

否则后续 milestone 启动时只读 design 会漏掉历史修订。

什么时候开新 unit 而不是改 design：当修订是**结构性遗漏**（影响其他已合并 unit、或需要数据迁移、或改变对外契约）时，开新 `refactor-` 或 `feat-`。

---

## 与 dev-tasks.json 的关系

- `milestone_id`: `feat-104-M1`
- `unit_id`: `feat-104`

从 `milestone_id` 可直接推导目录：

```
docs/changes/<unit_id>/<milestone_id>/
```

例：`feat-104-M1` → `docs/changes/feat-104/feat-104-M1/`
