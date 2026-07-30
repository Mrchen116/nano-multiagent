# Change Unit Storage

本文定义 `docs/changes/` 的目录、命名、文件归属、恢复信息以及 active/retired/archive 状态。是否建立 unit、Full/Bugfix lite/快速开发路径、开发阶段和门禁见 [`../development/change-workflow.md`](../development/change-workflow.md)。

## 目录语义

```text
docs/changes/
├── README.md
├── <unit-dir>/              # active / paused：仍可能继续推进
├── retired/
│   └── <unit-dir>/          # 未完成，但已经明确不会按原方案继续
└── archive/
    └── <unit-dir>/          # completed：达到可交付状态
```

`docs/changes/archive/` 保存 completed change 的整套历史；`docs/archive/` 保存被 current 文档取代的独立旧文档。两者不能混用。

归档必须 `git mv` 整个 unit，不能删除、压缩或拆散首文档、design、milestone、报告、delta-spec 和 evidence。

`retired/` 与 `archive/` 的差别是是否完成：retired unit 只保存被放弃或被后续方案取代的工作上下文，不能当作已经实现；若未来重新提出同一目标，应建立新 unit，并在 Relations 中链接旧 unit。

## 活动区索引

活动区只保留仍可能推进的 unit。每个目录根部必须有 `status.md`，因此 Agent 不需要根据目录时间或文档完整度猜测状态。

| Unit | Lifecycle | 恢复入口 |
|---|---|---|
| [`bugfix-448-web-fetch-cancel`](bugfix-448-web-fetch-cancel/status.md) | Paused after design | `status.md` |
| [`feat-397-spec-design-agent-team`](feat-397-spec-design-agent-team/status.md) | Paused after Gate 1 | `status.md` |
| [`feat-444-session-wakeup`](feat-444-session-wakeup/status.md) | Paused after design | `status.md` |
| [`feat-484-chat-message-interactions`](feat-484-chat-message-interactions/status.md) | Active — post-acceptance fixes | `status.md` |
| [`refactor-486-agent-native-repository-knowledge-system`](refactor-486-agent-native-repository-knowledge-system/status.md) | Active — Awaiting drift review | `status.md` |

状态变化时必须同步更新本表。`status.md` 保存单个 unit 的恢复快照，本表负责让 Agent 发现有哪些活动工作。

## 是否建立 unit

按 [`change-workflow.md`](../development/change-workflow.md#什么时候不建-unit) 判断：

- 符合“不建 unit”判据的小修直接修改；
- Bugfix lite 建立 `fix.md` 和单个 `M1-fix/`；
- Full 建立完整 unit。
- 快速开发允许实现先发生，但在交付前建立事后 unit，记录最终需求、实际设计、用户验收和 code review。

## 命名与编号

### Unit 目录

```text
<type>-<id>[-<short-desc>]
```

- `type`：当前 change-* 流程支持 `feat`、`bugfix`、`refactor`、`perf`；
- `id`：所有 type 共用的全局递增数字；
- `short-desc`：可选，2–5 个 kebab-case 单词；
- 目录全小写、使用连字符，建议不超过 60 个字符。

示例：`feat-104-chat-mention-picker`、`bugfix-123-session-leak`。

新编号统一执行：

```bash
python3 .claude/skills/change-spec-author/scripts/next_unit_id.py <type>
```

脚本同时扫描 active/archive/retired，并在 Git common dir 原子保留编号。已 reservation 但尚未建立目录的编号不复用。

### Milestone 目录

```text
M<N>-<short-desc>
```

示例：`M1-domain-model`、`M2-ui-picker`。

Full 模式在 design 阶段只创建含 `.gitkeep` 的空 milestone 骨架。worker 开始实施时删除 `.gitkeep`，再创建 `tasks.md`、`progress.md` 和需要的 `evidence/`。

## Unit 之间的关系

在首文档中使用轻量 `Relations`：

```markdown
## Relations

- Depends on: feat-338
- Blocks: feat-340
- Related: feat-336
```

- 只写 `unit_id`，理由留在正文；
- 无关系时可以省略整段；
- 发现未完成的强依赖时，停止当前 unit，建立依赖 unit 并回填 `Depends on`。

## 标准目录

### Full

```text
docs/changes/<unit-dir>/
├── status.md                         # 跨 session 恢复快照
├── spec.md | incident.md | motivation.md
├── spec-review.md                    # 可选；spec review 发现问题时留痕
├── design.md
├── design-review.md                  # Gate 2 的全部 Round 与 Author Resolutions
├── prototype.html                    # 仅前端相关
├── specs/                            # 对 canonical specs 的 delta
│   └── <package>/<target>.md
├── M1-<slice>/
│   ├── tasks.md
│   ├── progress.md
│   └── evidence/
├── M2-<slice>/
│   └── ...
├── verification.md                   # verifier 产物
└── acceptance.md | regression.md     # 产品验收产物
```

`spec-review.md` 不是 Full 的必备文件。按需调用 `change-spec-reviewer` 且发现问题时才落盘；Approved 可以只保留在对话中。

`design-review.md` 按 `## Round N` 追加整个 Gate 2 的历史。同一 reviewer 写每轮审查，design author 在对应 Round 追加 Author Resolutions；不得覆盖旧 Round。

### Bugfix lite

```text
docs/changes/<unit-dir>/
├── status.md
├── fix.md
└── M1-fix/
    ├── tasks.md
    ├── progress.md
    └── evidence/
```

`fix.md` 依次记录现象/复现、根因、修复、验证。spec author 写前两部分，worker 回填后两部分。

### 快速开发

```text
docs/changes/<unit-dir>/
├── status.md
├── spec.md | incident.md | motivation.md
├── design.md                         # 实现后根据真实代码整理的 as-built design
├── specs/                            # 可选；对 canonical specs 的 delta
│   └── <package>/<target>.md
└── code-review.md                    # 强制 code review 的范围、finding 与闭环
```

快速开发 unit 不创建 milestone、`tasks.md`、`progress.md`、`design-review.md`、`verification.md` 或 reviewer 产出的 `acceptance.md`。用户已经完成的实际体验和确认记录在 `status.md`；没有发生过的过程不事后补造。

## 文件归属

| 文件 | Owner | 内容 |
|---|---|---|
| `status.md` | 当前阶段 owner；实施期为 `change-orchestrator`，快速开发收尾为 `change-fast-close` | 状态、Git/PR 定位、完成项、证据、阻塞和下一动作 |
| `spec.md` / `incident.md` / `motivation.md` / `fix.md` 前两部分 | `change-spec-author`；快速开发为 `change-fast-close` | 做什么、为什么、验收标准或 RCA |
| `spec-review.md`（可选） | `change-spec-reviewer` | 按需复核发现问题时留下的台账 |
| `design.md`、`prototype.html`、`specs/**`、milestone 空骨架 | `change-design-author`；快速开发的 as-built design 与 delta 为 `change-fast-close` | 怎么做、实际怎么实现、契约增量和实施切片 |
| `design-review.md` | `change-design-reviewer` + `change-design-author` | reviewer 逐轮追加审查，author 追加 resolutions |
| `tasks.md`、`progress.md`、`evidence/**`、`fix.md` 后两部分 | `change-impl-worker` | 单 milestone 的计划、过程和证据 |
| `verification.md` | `change-verifier` | 实现与 spec/design/tasks 的一致性 |
| `acceptance.md` / `regression.md` | `change-reviewer` | 用户旅程与产品可用性 |
| `code-review.md` | `change-fast-close` | 快速开发 diff 的 review 范围、findings、修复和最终结论 |

模板由各 skill 的 `assets/` 提供，本文不复制模板正文。

## 内容边界

| 文件 | 回答 | 不应包含 |
|---|---|---|
| 首文档 | 用户或消费者要什么、看到什么，或问题/RCA | 模块切分、类名、接口和库选型 |
| Full `design.md` | 架构、接口、数据流、关键权衡、风险回退 | roadpoint 级实现步骤 |
| 快速开发 `design.md` | 当前代码实际采用的结构、调用链、数据流、决策和风险回退 | 虚构的事前候选方案、milestone 或 review 过程 |
| delta-spec | 本 unit 对 current 行为契约的 ADDED/MODIFIED/REMOVED | 实现过程和历史叙事 |
| `tasks.md` | worker 可执行的 roadpoints、测试策略和退出标准 | 重新决定已经锁定的架构 |
| `progress.md` | Context/Decision/Rationale/Evidence/Rollback/Commits | 脱离当前 milestone 的未来规划 |
| acceptance/regression | 用户可观察旅程和 verdict | 用读源码代替真实产品体验 |

实现期发现 design 问题时，worker 按 workflow 暂停并升级，不能在 `progress.md` 中维护一套与 `design.md` 不同的影子方案。

## 状态与恢复

### `status.md` 最小契约

`status.md` 是恢复入口，不是过程日志。它固定记录：

| Field | 含义 |
|---|---|
| Lifecycle | 当前阶段；暂停、退役或完成时明确写出 |
| Last checked | 最近一次与 Git、PR 和 unit 文档核对的日期 |
| Branch | 当前实现分支；尚未创建时写 `None` |
| Worktree | 当前 worktree；不存在时写 `None` |
| Pull request | PR URL；尚未创建时写 `None` |
| Completed | 已完成的阶段或 milestone |
| Evidence | 可复查的报告、提交或 evidence 入口 |
| Blocker | 阻塞原因；没有时写 `None` |
| Next action | 下一位 Agent 可以直接执行的一步 |

快速开发 unit 还必须记录 `Implementation scope` 和 `User acceptance`：前者定位实际 base、head 与纳入范围的 dirty files，后者只写用户明确完成的体验和结论。

恢复时先读 `status.md`，再用 `git status`、`git worktree list`、branch head 和 `gh pr view` 核对会变化的外部状态。核对结果与快照不一致时，以实时状态为准并立即更新 `status.md`。milestone 内的 roadpoint 细节仍由 `tasks.md` 和 `progress.md` 负责，不能复制到状态页。

阶段 owner 在以下时点更新：

- `change-spec-author` 建立 unit，并在 Gate 1 后写明下一入口；
- `change-design-author` 开始设计、通过 Gate 2 或因需求问题暂停；
- `change-orchestrator` 建立实现 worktree、签收 milestone、完成验收、升级阻塞、归档和创建 PR；
- `change-fast-close` 建立事后 unit、完成 code review、归并契约、归档和按授权交付；
- 人工暂停或退役 unit 时，执行决定的人负责留下原因和下一动作。

### Active

下列任一情况存在时，unit 留在 `docs/changes/<unit-dir>/`：

- 仍在探索、设计、实施或验收；
- 有失败或 inconclusive 的门禁，或快速开发尚未获得明确的用户验收；
- 有开放设计问题或未完成 milestone；
- 完成证据不足，无法证明已达到可交付状态。

不能按编号大小、目录年龄或“看起来做完了”推断完成。

### Paused

Paused unit 仍留在活动区。`status.md` 必须说明暂停原因、恢复前需要重新核对的事实和第一步动作。暂停不等于完成，也不允许释放其 unit id。

### Retired

只有负责人已经明确决定不再按原 unit 推进，且文档中能指出替代方案或放弃原因时，才把整个目录移到 `retired/`。退役前将 `Lifecycle`、`Blocker` 和 `Next action` 更新为最终状态；retired unit 不允许由 orchestrator 恢复实施。

### 归档

Full 与 Bugfix lite 在 selected gates、canonical spec 归并和本地 CI 全部通过后归档。快速开发在用户验收已记录、强制 code review 通过、canonical spec 完成归并且本地检查通过后归档：

```bash
mkdir -p docs/changes/archive
git mv "docs/changes/<unit-dir>" "docs/changes/archive/<unit-dir>"
```

PR body、同一交付会话中的 CI/fix 和复验继续使用归档路径。PR merge 后，实现与归档历史一起进入 main。

### 已归档 unit 的恢复

- 没有对应开放 PR：视为已完成，不重新启动；
- 有开放 PR：branch、PR head、clean worktree 三项验证通过后，才进入受限 post-PR 小修；
- 只允许自包含修复；需要修改 design 或新增 milestone 时交由人决定。

## 唯一定位

按 `unit_id` 查找时同时检查 active、archive 和 retired，并要求结果唯一：

```bash
unit_matches=$(find docs/changes docs/changes/archive docs/changes/retired \
  -mindepth 1 -maxdepth 1 -type d \
  \( -name "<unit_id>" -o -name "<unit_id>-*" \) -print 2>/dev/null)
match_count=$(printf '%s\n' "$unit_matches" | sed '/^$/d' | wc -l | tr -d ' ')
if [[ "$match_count" -ne 1 ]]; then
  echo "expected one unit, found $match_count" >&2
  exit 1
fi
unit_path=$unit_matches
```

禁止用 `head -1` 吞掉歧义。执行型 skill 只能接手 active unit；archive 只允许开放 PR 的受限小修，retired 一律拒绝启动。

## Evidence 与本地产物

- 各类证据能证明什么、记录字段、保存位置和 promotion 规则见
  [`docs/development/evidence.md`](../development/evidence.md)；
- 可复查证据放在对应 milestone 的 `evidence/`，或 unit 根部的正式 review/verification 报告中；
- 新证据不再写入根目录 `ACCEPTANCE/`；
- PID、日志、SQLite、截图缓存、临时 config 和 worktree runtime 文件保持 gitignored；
- 证据中提炼出的长期行为进入 `docs/specs/`，长期操作约束进入 runbook。

## 历史迁移

根目录旧 `TASKS/`、`PROGRESS/`、`ACCEPTANCE/` 已停止接收新内容并整体迁入
[`docs/archive/legacy-development-records/`](../archive/legacy-development-records/README.md)。旧 milestone id
只代表当时的 TDD control-tower 流程，不能机械映射成 change unit。

`data/dev-tasks.json` 当前不存在；现行 orchestrator 明确只在内存和 unit 文档中维护调度状态。审计只发现一个
无生产调用者的旧 worktree symlink helper 及其测试，本次已移除该兼容接线；gitignore 条目暂时保留，避免旧
worktree 的本机残留进入版本控制。
