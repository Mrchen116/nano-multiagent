# feat-398: change-* 工作流收口质量门禁（CI 门禁 + verifier 规范判据）

> 回顾性 spec：变更已落地（改了 `change-orchestrator` + `change-verifier` 两个 skill），本文档据已对齐的对话补记，"澄清记录"即对话原话。

## Relations

- Related: 无（独立改动，不依赖其它 unit）

## 原始需求

> 现在change-* 系列skill是不是没要求遵守TESTING_GUIDE。也没要求最后提PR之后要保证CI过了。

> change-verifier我觉得需要有这些规范的参考，还有啥规范，SPEC之类的没给verifer。不等 CI是错的，orchestrator要等！

## 澄清记录

- Q1: change-verifier 该挂哪些规范？是否连 COMMENTING/AGENTS 一起？
  A(原话): 连 COMMENTING/AGENTS 一起。
  Agent 解读: verifier §1 读上下文新增「项目权威规范」一类，含测试规范、架构总览/长青行为契约、注释规范/贡献约定，覆盖 TESTING_GUIDE + SPEC + docs/specs 长青契约层 + COMMENTING_GUIDE + AGENTS.md。

- Q2: orchestrator 提 PR 后 CI 红了怎么处理？
  A(原话): 红了当然是要解决呀，还用想吗，和找到bug是一样的处理逻辑
  Agent 解读: CI 红当作普通缺陷，接进既有的 §6.2 fix-implementation 循环（派 worker 修，不自己改），修到绿才退。

- Q3: 是否在提 PR 前先本地跑 CI？
  A(原话): 这个我确认下，其实本地在提PR前是可以本地跑CI的是吧，若是，那应该先本地跑了，再提
  Agent 解读: 经核实 `ci.yml` 无任何只能远端跑的步骤，本地可等价复现（ruff check / ruff format --check / pytest -m "not e2e" / 前端 npm ci + vitest）。故提 PR 前增加「本地 CI 等价门禁」，绿才提。

- Q4: §7.2 等节是否写得太啰嗦？
  A(原话): 写的太啰嗦了，不用这么啰嗦也能说明白。agent能很好遵循。…… 原有的我都想压缩了，agent实际上遵循很好，不用一个事情提3次以上。
  Agent 解读: 同一约束最多落 2 处，不在硬规则+流程+anti-pattern 三处重复；CI 门禁收敛到「§0 一句纲领 + §7 流程展开一次」。

- Q5（约束）: 这组 skill 是否本仓专用？
  A(原话): 注意一下这一组 skill 是通用 skill 不单针对本仓，所以不要写一些只有本仓有的东西。
  Agent 解读: CI 命令与规范文档名一律走通用机制（从 CI 配置 / `CLAUDE.md`·`AGENTS.md` 索引发现），不写死本仓特有路径或命令。

## 用户场景

镜头：**新增能力**——给 change-* 工作流的收口阶段增加两道质量门禁，将来跑这套流程时会自动生效。

谁是用户：运行 change-* 工作流的人，以及代其执行的 orchestrator / verifier 子 agent。

变更前的痛点：

- unit 全部 milestone 合到集成分支后，`change-orchestrator` 提 PR 即退出——**显式不等 CI**。CI 红没人盯，残品 PR 丢给人；提 PR 前也无任何本地全量门禁（worker 只跑自己 milestone 的窄测试命令），ruff / format / 跨包回归红往往要到远端才暴露。
- `change-verifier` 验收时只读 unit 局部的 spec/design/tasks，**手上没有判据真源**：判"测试覆盖够不够"无测试规范可依、核对 requirement 无长青契约层 / 跨包依赖方向可对、判"是否沿用既有模式"无注释 / 贡献约定可循。

变更后：

- orchestrator 走到提 PR 阶段时，**先在本地把项目 CI 等价跑一遍**（命令从 CI 配置照搬），全绿才提 PR；提 PR 后**等远端 CI 跑完**，全绿才退出交棒；CI 红则当 bug 走 fix 循环修到绿再退。退出时只是"不等 merge"（merge 由人做），但 CI 必须绿。
- verifier 启动时除 unit 文档外，**额外读项目权威规范作判据**（测试规范 / 架构总览·长青契约 / 注释·贡献约定），顺 `CLAUDE.md`·`AGENTS.md` 索引发现；项目没有对应规范则注明跳过、不自造标准。

通用性约束：两道门禁都走机制性描述——CI 命令从仓库 CI 配置（如 `.github/workflows/`）发现，规范文档从项目索引入口发现，不写死任何单仓专属命令或路径。

## 验收标准

### Requirement: orchestrator 提 PR 前有本地 CI 等价门禁

#### Scenario: 本地 CI 全绿才提 PR
- **GIVEN** unit 所有 milestone 已合到集成分支、验收通过
- **WHEN** orchestrator 进入提 PR 阶段
- **THEN** 它先在 worktree 内把项目 CI 等价跑一遍（命令照搬 CI 配置），全绿后才创建 PR

#### Scenario: 本地 CI 红 → 不提 PR，进 fix 循环
- **WHEN** 本地 CI 门禁有任一检查未通过
- **THEN** orchestrator 不提 PR，把失败当 bug 走 fix-implementation 循环（派 worker 修），修到全绿才继续提 PR

### Requirement: orchestrator 提 PR 后等远端 CI 绿才退出

#### Scenario: 远端 CI 全绿 → 退出交棒
- **GIVEN** PR 已创建
- **WHEN** 远端 CI 跑完且全部 check 通过
- **THEN** orchestrator 退出并交棒给人去 merge（不等 merge）

#### Scenario: 远端 CI 红 → 修到绿才退
- **WHEN** 远端 CI 有 check 失败
- **THEN** orchestrator 当 bug 走 fix 循环修复并 push（PR 自动重跑 CI），直到 CI 全绿才退出；不会红着交棒

### Requirement: verifier 以项目权威规范为判据

#### Scenario: 判测试覆盖时依据项目测试规范
- **WHEN** verifier 检查某 scenario 是否有测试覆盖
- **THEN** 它按项目测试规范判定覆盖是否达标，并把临时验收证据与真回归测试区分开（前者不计入覆盖）

#### Scenario: 核对实现时对齐长青契约与依赖方向
- **WHEN** verifier 核对 spec 的某条 requirement 是否被实现
- **THEN** 它既对照 unit 局部 spec，也对照项目长青行为契约与跨包依赖方向 / 模块边界，违反硬性边界的报为 WARNING 及以上

#### Scenario: 项目无对应规范时不自造标准
- **WHEN** 项目找不到某一类权威规范文档（测试 / 架构契约 / 注释·贡献约定）
- **THEN** verifier 在报告里注明"无 X 规范可依"并跳过该判据，而不是凭直觉自造一套标准

## 范围与非目标

- 在范围：
  - `change-orchestrator` §7 新增本地 CI 门禁 + 提 PR 后等远端 CI；翻转原"不等 CI"为"等 CI 绿、不等 merge"。
  - `change-verifier` §1 新增「项目权威规范」作判据，§3/§4 判定指向该判据。
  - 两处改动一律走通用机制，不写死单仓命令 / 路径。
- 非目标：
  - 不改其它 change-* skill（`spec-author` / `design-author` / `impl-worker` / `reviewer`）；`impl-worker` 本就已挂 TESTING_GUIDE，无需动。
  - 不对这两个 skill 做全文冗余瘦身（另一件事，需单独开）。
  - 不新增或修改任何项目 CI 配置（`ci.yml` 不动）。
  - 不引入只能在远端运行的检查——门禁要求的是"本地可等价复现的那套 CI"。
