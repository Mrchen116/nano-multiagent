# bugfix-511: As-built Design

> 本文在实现完成后根据实际代码、diff 与已确认决定整理，描述最终落地设计。

## 实现范围

- Base: `eaaed4c3e` (`origin/main` at implementation start)
- Head: `b393ea873`
- Commits: `b393ea873 fix(workflow): enforce archived unit PR delivery`
- Included dirty files: 本 unit 的 `incident.md`、`design.md` 与待生成的 `code-review.md`
- 受影响模块：GitHub Actions、change unit 归档检查脚本、
  `change-orchestrator-simple` skill、change workflow 契约测试、历史 unit 文档与 IM canonical specs

## 最终结构

### 组件与职责

- `.github/workflows/ci.yml`：在既有 `Python checks` job 的依赖安装前执行归档门禁，沿用现有
  CI job，不引入新的 job 或本地 preflight。
- `scripts/check_change_unit_archived.py`：从 PR head branch 提取 unit ID，扫描 change unit 的
  active、archive、retired 三种位置并返回进程状态。
- `.claude/skills/change-orchestrator-simple/SKILL.md`：规定正常交付创建 Ready for review PR，
  并限定显式用户请求下的临时 Draft 例外。
- `tests/contract/test_change_skill_archive_contract.py`：以 subprocess 运行真实脚本，覆盖分支解析、
  生命周期位置和歧义；同时锁定 CI wiring 与 skill 文案。
- `docs/changes/archive/{bugfix-497-*,feat-501-*}` 与 `docs/specs/im/`：完成已具备条件的历史归档，
  并补齐 bugfix-497 已实现但未归并的 IM canonical requirements。

### 调用链与数据流

1. GitHub 在 pull request 上启动 `Python checks`，把 `github.head_ref` 传给脚本。
2. 非 `unit/*` 分支立即成功跳过；`unit/*` 分支必须匹配受支持的 `<type>-<number>`。
3. 脚本从 branch 提取 unit ID，检查 `docs/changes/`、`archive/`、`retired/` 的直属目录。
4. 仅一个 archive 命中返回 0；active、retired、缺失、多处命中或非法 unit 分支名返回 1。
5. 非零状态直接使既有 `Python checks` 失败，PR 不能显示 CI 全绿，simple orchestrator 也不能
   按自身交付契约把它称为可交付。

### 状态、数据与兼容性

脚本只读取 Git checkout，不写入状态。目录匹配接受 `<unit-id>` 和 `<unit-id>-*`，因此兼容
现有可选 short description。`unit/<unit-id>-<suffix>` 的 branch suffix 不参与目录定位。
非 unit 分支保持原 CI 行为。

## 关键决策

| 决策 | 原因与约束 | 代码定位 |
|---|---|---|
| 复用 `Python checks` | 该 job 已覆盖 PR；门禁失败会阻止 CI 全绿与 orchestrator 交付判定，本次不改 GitHub ruleset | `.github/workflows/ci.yml` |
| 使用纯标准库 CLI | 可在 dependency install 前执行，失败更快且不增加 CI 依赖 | `scripts/check_change_unit_archived.py` |
| 要求唯一 archive 命中 | 避免 active/archive 重复或错误 retired 状态被误判为完成 | `_unit_directories()` 与 `main()` |
| 非 unit 分支跳过 | 小修或其他合法分支未必有 change unit，本次只约束既有 unit 分支契约 | `main()` |
| 不增加本地 preflight | 用户明确选择 CI 作为硬门禁；避免维护两条交付路径 | `.github/workflows/ci.yml` |
| 默认 Ready，Draft 仅为中间态 | 正常 PR 应立即进入正式 review；用户显式要求早看 diff 时保留例外 | `change-orchestrator-simple/SKILL.md` |

## 失败路径、风险与回滚

- 失败信息会列出 unit ID 与实际位置，执行者移动整个 unit 到 archive 后重推即可恢复。
- 仓库当前没有 GitHub required status check；本门禁保证 CI 红灯并约束 orchestrator 的交付判定，
  不声称从 GitHub 权限层禁止人工强制合并。
- 若现有 unit branch 命名不符合 `unit/<type>-<number>[-suffix]`，CI 会明确失败；这与仓库当前
  unit branch 约定一致。
- 回滚只需移除 CI step、脚本和契约测试，并恢复 skill 交付文字；不涉及数据迁移。

## 与初始意图的差异

无。实现采用用户确认的 CI-only 方案，没有增加本地 preflight，也没有在“完成条件”重复规则。

## 验证定位

- 用户验收：用户在当前对话明确确认 CI 判定矩阵、取消 preflight、Ready PR 默认值与交付授权。
- 自动化测试：`tests/contract/test_change_skill_archive_contract.py`；
  `tests/contract/test_change_workflow_documentation_contract.py`。
- 运行证据：聚焦契约测试 14 passed；skill quick validation、ruff check/format、文档完整性检查通过。
  PR CI 作为最终远端证据。

## Canonical 文档影响

- Delta-spec：本次交付门禁不改变产品 observable behavior，无 product delta-spec。
- 归并目标：CI workflow、检查脚本及 consuming skill 本身就是 developer workflow 的 current truth。
- 历史归并：bugfix-497 的既有 IM delta 补入 `docs/specs/im/conversations-messages.md`、
  `gateway-relay.md` 与索引计数；该归并不属于 bugfix-511 的新行为。
