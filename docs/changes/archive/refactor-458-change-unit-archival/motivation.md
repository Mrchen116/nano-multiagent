# refactor-458: 完成 unit 自动归档

## Relations

- Related: refactor-457

## 原始诉求

> 这个pr还做一个事情。就是现在changes下面目录太多了，其中绝大部分都完成了，应该进行归档。并且后面每个需求做完提交pr的时候都应该归档。你理解嘛，和我对齐一次

> 都非常正确。补充一点。是不是可以在skill中加一个简单脚本，change-spec-author 分配新编号时，获取对应标号。

## 澄清记录

- Q1: 是否按“顶层只留活动 unit、完成证据不足则不归档、以后在提交 PR 前归档并让所有相关 skill 兼容新路径”的口径实施？
  A(原话): 都非常正确。补充一点。是不是可以在skill中加一个简单脚本，change-spec-author 分配新编号时，获取对应标号。
  Agent 解读: 用户确认完整归档口径，并补充要求把全局编号分配收敛为 change-spec-author 自带的确定性脚本。

## 现状痛点

`docs/changes/` 顶层当前堆积 131 个 unit 目录，其中大部分对应的实现 PR 已经合并，但已完成 unit 与尚未
实施、暂停或证据不足的 unit 混在同一层。维护者无法通过目录位置判断状态，日常浏览和 agent 定位当前工作
都会被大量历史单元干扰。

现有流程虽然把最后阶段称为“验收/归档”，却没有定义目录迁移动作；change-orchestrator 在验收、长青契约
归并和 CI 完成后只创建 PR 并退出，因此每个完成 unit 永久留在活动区。

同时，change-spec-author 通过临时扫描顶层目录分配全局编号。若完成 unit 被移入 archive，而编号逻辑仍只扫
活动区，后续 unit 会复用历史编号，破坏 `unit_id` 的全局唯一性和检索稳定性。

## 目标状态

`docs/changes/` 明确分为活动区与历史区：

- `docs/changes/<unit-dir>/` 只存放尚未完成、暂停或完成证据不足的 unit。
- `docs/changes/archive/<unit-dir>/` 保存已完成 unit 的全部首文档、design、milestone、报告、delta-spec 和证据。
- 归档是移动而非删除，unit_id、目录名和目录内部结构保持不变。
- 后续 unit 在实现、验收、验证、长青契约归并和本地门禁完成后，作为提交 PR 流程的一部分归档；PR 合并后
  main 同时获得实现与归档结果。
- change-* 中需要读取已完成 unit 的角色可同时解析活动区和 archive；PR body 使用归档后的稳定路径。
- change-spec-author 通过 skill 自带脚本扫描活动区与 archive，并在同一 Git clone 的共享状态中原子保留新 id；
  所有变更类型和本地 worktree 共用一条递增序列。

## 用户侧验收标准（不变性）

归档前，维护者可以在 `docs/changes/` 找到所有 unit 的完整历史资料，change-* 可以通过 unit_id 定位当前工作，
新 unit 使用全局递增编号。归档后这些能力保持不变；变化仅是完成 unit 进入明确的历史区，活动区更适合扫描。

### Requirement: 活动区只保留未完成或完成证据不足的 unit

#### Scenario: 批量整理现有目录
- **WHEN** 维护者浏览 `docs/changes/` 顶层
- **THEN** 已有明确完成证据的历史 unit 位于 `archive/`，未完成、暂停或证据不足的 unit 仍留在顶层

#### Scenario: 现有 unit 完成状态存在歧义
- **WHEN** 一个历史 unit 没有已合并 PR、通过的最终报告或其他同等级完成证据
- **THEN** 该 unit 不被推断为完成，继续留在活动区等待后续确认

### Requirement: 归档不得损失变更历史

#### Scenario: 查阅已完成 unit
- **WHEN** 维护者或 change-retro 按 unit_id 查找一个已归档 unit
- **THEN** 可在 archive 中找到原目录及其完整文档、milestone、报告和证据

#### Scenario: 区分退役系统文档与变更单元
- **WHEN** 维护者查找已完成 change unit
- **THEN** 使用 `docs/changes/archive/`，而现有 `docs/archive/` 继续只承载退役系统文档

### Requirement: 后续 PR 收尾必须归档完成 unit

#### Scenario: unit 通过全部交付门禁
- **WHEN** unit 已完成验收、验证、长青契约归并和提 PR 前本地门禁
- **THEN** change-orchestrator 在创建 PR 前将整个 unit 目录移入 `docs/changes/archive/`

#### Scenario: PR 需要引用交付文档
- **WHEN** change-orchestrator 组装 PR body 或等待远端 CI 后继续处理该 unit
- **THEN** 文档链接和后续读取均使用可解析的归档路径，不因目录移动失效

#### Scenario: 已退出的 orchestrator 重新处理开放 PR
- **WHEN** unit 已归档并创建开放 PR，之后收到 review feedback 或远端 CI 失败
- **THEN** change-orchestrator 可从开放 PR 恢复既有 unit 分支和 worktree，继续在 archive 中读写交付文档，不把 unit 移回活动区

### Requirement: 新 unit 编号覆盖活动区与历史区

#### Scenario: change-spec-author 分配编号
- **WHEN** change-spec-author 确定新变更类型并申请 unit_id
- **THEN** skill 自带脚本扫描活动区与 archive，并结合尚未落目录的 reservation，原子返回全局最大编号加一后的完整 unit_id

#### Scenario: 历史目录存在重复编号
- **WHEN** 旧数据中不同类型曾使用相同数字编号
- **THEN** 编号脚本仍按最大数字继续递增，不复用任何既有数字，也不因历史重复而阻塞新 unit

#### Scenario: 多个本地 worktree 并发申请编号
- **WHEN** 同一 Git clone 中两个 change-spec-author 进程同时申请 unit_id
- **THEN** 脚本在所有 worktree 共享的 Git common dir 中依次保留编号，两个进程得到不同的完整 unit_id

### Requirement: 归档不改变产品行为

#### Scenario: 用户继续使用现有产品能力
- **WHEN** 完成 unit 的文档被归档
- **THEN** kernel、gateway、IM 和 CLI 的运行时行为与归档前一致

## 范围与非目标

本期范围：

- 建立 `docs/changes/archive/<unit-dir>/`，批量迁移有明确完成证据的现有 unit。
- 在 `docs/changes/readme.md` 定义活动区、历史区、完成判据、未来归档时机和路径解析规则。
- 更新 change-orchestrator 的强制归档步骤及 PR body 路径。
- 更新需要在归档后读取 unit 的 change-* skill，使其兼容活动区和 archive。
- 为 change-spec-author 增加并实际调用全局编号脚本。
- 修复因目录加深而受影响的仓内引用，并验证 Markdown 链接。

非目标：

- 不删除或压缩任何 unit 历史文档和证据。
- 不把完成证据不足的 unit 强行归档。
- 不按年份或类型继续分片 archive；全局 unit_id 已提供稳定检索键。
- 不改变既有 unit_id，也不修复历史上已经存在的重复数字编号。
- 不引入数据库、外部归档服务或 GitHub Action；归档仍是 PR 内可 review 的 git move。

## 影响范围

- `docs/changes/` 的目录结构、规范和已完成 unit 路径。
- change-spec-author 的编号分配。
- change-orchestrator 的 PR 收尾流程及 PR body 模板。
- change-impl-worker、change-reviewer、change-verifier、change-retro 等归档后仍可能读取 unit 的角色。
- 仓内指向已归档 unit 的文档引用。

不影响产品源码、运行时配置、持久化数据和外部接口。

## 迁移与回滚策略

首次迁移使用保守完成判据：已合并 PR 明确引用 unit_id，或存在明确通过的最终验收/回归报告；开放 PR、活动
worktree、报告失败或证据不足的 unit 保留在顶层。迁移使用 `git mv` 保留完整历史，并在移动后统一检查仓内
引用、Markdown 链接和 change-* 路径假设。

未来每个 unit 由 change-orchestrator 在提 PR 前执行同样的单目录移动；编号脚本始终同时扫描两层并保留已
分配编号，因此迁移过程中、迁移后和并发申请时都不会回收编号。

若归档规则或批量分类在 review 中不被接受，可整体回退目录移动和 skill 规则；若单个 unit 被误分类，只需将
其完整目录移回 `docs/changes/` 并修复对应引用，不涉及运行时或数据回滚。
