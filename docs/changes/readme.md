# Change Unit Storage

本文定义 `docs/changes/` 的目录、命名、文件归属以及 active/archive 状态。是否建立 unit、Full/Bugfix lite 路径、开发阶段和门禁见 [`../development/change-workflow.md`](../development/change-workflow.md)。

## 目录语义

```text
docs/changes/
├── readme.md
├── <unit-dir>/              # active：探索、设计、实施、验收中，或完成证据不足
└── archive/
    └── <unit-dir>/          # completed：达到可交付状态，随实现 PR 一起归档
```

`docs/changes/archive/` 保存 completed change 的整套历史；`docs/archive/` 保存被 current 文档取代的独立旧文档。两者不能混用。

归档必须 `git mv` 整个 unit，不能删除、压缩或拆散首文档、design、milestone、报告、delta-spec 和 evidence。

## 是否建立 unit

按 [`change-workflow.md`](../development/change-workflow.md#什么时候不建-unit) 判断：

- 符合“不建 unit”判据的小修直接修改；
- Bugfix lite 建立 `fix.md` 和单个 `M1-fix/`；
- Full 建立完整 unit。

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

脚本同时扫描 active/archive，并在 Git common dir 原子保留编号。已 reservation 但尚未建立目录的编号不复用。

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
├── fix.md
└── M1-fix/
    ├── tasks.md
    ├── progress.md
    └── evidence/
```

`fix.md` 依次记录现象/复现、根因、修复、验证。spec author 写前两部分，worker 回填后两部分。

## 文件归属

| 文件 | Owner | 内容 |
|---|---|---|
| `spec.md` / `incident.md` / `motivation.md` / `fix.md` 前两部分 | `change-spec-author` | 做什么、为什么、验收标准或 RCA |
| `spec-review.md`（可选） | `change-spec-reviewer` | 按需复核发现问题时留下的台账 |
| `design.md`、`prototype.html`、`specs/**`、milestone 空骨架 | `change-design-author` | 怎么做、契约增量和实施切片 |
| `design-review.md` | `change-design-reviewer` + `change-design-author` | reviewer 逐轮追加审查，author 追加 resolutions |
| `tasks.md`、`progress.md`、`evidence/**`、`fix.md` 后两部分 | `change-impl-worker` | 单 milestone 的计划、过程和证据 |
| `verification.md` | `change-verifier` | 实现与 spec/design/tasks 的一致性 |
| `acceptance.md` / `regression.md` | `change-reviewer` | 用户旅程与产品可用性 |

模板由各 skill 的 `assets/` 提供，本文不复制模板正文。

## 内容边界

| 文件 | 回答 | 不应包含 |
|---|---|---|
| 首文档 | 用户或消费者要什么、看到什么，或问题/RCA | 模块切分、类名、接口和库选型 |
| `design.md` | 架构、接口、数据流、关键权衡、风险回退 | roadpoint 级实现步骤 |
| delta-spec | 本 unit 对 current 行为契约的 ADDED/MODIFIED/REMOVED | 实现过程和历史叙事 |
| `tasks.md` | worker 可执行的 roadpoints、测试策略和退出标准 | 重新决定已经锁定的架构 |
| `progress.md` | Context/Decision/Rationale/Evidence/Rollback/Commits | 脱离当前 milestone 的未来规划 |
| acceptance/regression | 用户可观察旅程和 verdict | 用读源码代替真实产品体验 |

实现期发现 design 问题时，worker 按 workflow 暂停并升级，不能在 `progress.md` 中维护一套与 `design.md` 不同的影子方案。

## Active、归档与恢复

### Active

下列任一情况存在时，unit 留在 `docs/changes/<unit-dir>/`：

- 仍在探索、设计、实施或验收；
- 有失败或 inconclusive 的门禁；
- 有开放设计问题或未完成 milestone；
- 完成证据不足，无法证明已达到可交付状态。

不能按编号大小、目录年龄或“看起来做完了”推断完成。

### 归档

selected gates、canonical spec 归并和本地 CI 全部通过后，在创建 PR 前执行：

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

按 `unit_id` 查找时同时检查 active 和 archive，并要求结果唯一：

```bash
unit_matches=$(find docs/changes docs/changes/archive -mindepth 1 -maxdepth 1 -type d \
  \( -name "<unit_id>" -o -name "<unit_id>-*" \) -print 2>/dev/null)
match_count=$(printf '%s\n' "$unit_matches" | sed '/^$/d' | wc -l | tr -d ' ')
if [[ "$match_count" -ne 1 ]]; then
  echo "expected one unit, found $match_count" >&2
  exit 1
fi
unit_path=$unit_matches
```

禁止用 `head -1` 吞掉歧义。

## Evidence 与本地产物

- 可复查证据放在对应 milestone 的 `evidence/`，或 unit 根部的正式 review/verification 报告中；
- 新证据不再写入根目录 `ACCEPTANCE/`；
- PID、日志、SQLite、截图缓存、临时 config 和 worktree runtime 文件保持 gitignored；
- 证据中提炼出的长期行为进入 `docs/specs/`，长期操作约束进入 runbook。

## 历史迁移

根目录旧 `TASKS/`、`PROGRESS/`、`ACCEPTANCE/` 和 `data/dev-tasks.json` 不属于当前 change unit 模型。整理历史时保留原始证据并单独迁移，不能把旧 milestone id 机械映射成新 unit，也不能继续向旧目录写入新工作。
