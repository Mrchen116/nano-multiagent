# docs/changes/ 目录规范

变更单元的所有相关文档统一放在 `docs/changes/` 下，按变更单元聚合，方便查找和追溯。

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
| `spec.md` | 定义功能边界、用户场景、验收标准来源。回答"做什么"。 | 需求分解阶段，拆 milestone 之前 |
| `design.md` | 记录架构决策、接口设计、数据流、关键权衡与拒绝的方案。回答"怎么做"。 | 需求明确后、实现前 |
| `tasks.md` | 把 milestone 目标拆成可执行的 roadpoint，明确验收标准和测试策略。 | worktree 启动后、编码前 |
| `progress.md` | 记录每个 roadpoint 的完整执行过程（Context/Decision/Rationale/Evidence/Rollback/Commits）。 | 每个 roadpoint 完成后实时更新 |
| `acceptance.md` | 从产品经理视角判断功能是否对用户可用，记录用户旅程体验、问题清单与 verdict。 | 所有实现型 milestone 完成后 |

### bugfix — Bug 修复

```
docs/changes/bugfix-123-session-leak/
├── incident.md                     # 问题报告与根因分析
├── M1-root-cause-fix/
│   ├── tasks.md                    # roadpoint 计划
│   └── progress.md                 # 实现记录
└── regression.md                   # 回归验证报告
```

| 文档 | 作用 | 什么时候写 |
|------|------|------------|
| `incident.md` | 记录 bug 现象、复现步骤、影响范围、根因分析（RCA），确保修复方向正确。回答"什么问题"。 | 确认 bug 后、修复前 |
| `tasks.md` | 把修复任务拆成可执行的 roadpoint，明确复现验证和回归测试策略。 | worktree 启动后、编码前 |
| `progress.md` | 记录每个 roadpoint 的执行过程，重点记录根因确认和修复验证证据。 | 每个 roadpoint 完成后实时更新 |
| `regression.md` | 确认 bug 已修复且未引入新破坏，记录复现验证和回归测试结论。 | bugfix milestone 完成后 |

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

## 与 dev-tasks.json 的关系

- `milestone_id`: `feat-104-M1`
- `unit_id`: `feat-104`

从 `milestone_id` 可直接推导目录：

```
docs/changes/<unit_id>/<milestone_id>/
```

例：`feat-104-M1` → `docs/changes/feat-104/feat-104-M1/`
