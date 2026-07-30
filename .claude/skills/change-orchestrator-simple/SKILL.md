---
name: change-orchestrator-simple
description: 端到端实施已完成 spec / design 对齐的 change unit，并交付 CI 全绿的 PR。用户点名 `$change-orchestrator-simple` 时使用。
---

# Change Unit Delivery

## 目标

把一个 change unit 从实施推进到可审查、CI 全绿的 PR。交付覆盖需求、设计、milestone、
实现、测试、真实入口验证、适用的独立验收闸、文档和归档。

## 启动

1. 在 `docs/changes/` 中唯一解析目标 unit；命中歧义或只命中已归档 unit 时停止并说明。
2. 确认该 unit 已具备实施条件：首文档和 `design.md` 已定稿；独立 design review 的最新
   结论为通过，且此后受审产物未再修改；milestone 拆分、退出标准和仓库要求的实施前产物
   完整。任一条件不满足时停止并说明。
3. 完整阅读：
   - unit 首文档、`design.md`，以及其中引用的 prototype、reference 和 reviewer runbook；
   - 仓库级与受影响目录的 `CLAUDE.md` / `AGENTS.md`，并按其中路由读取本次实施相关规范；
   - `docs/development/change-workflow.md`；
   - `docs/development/testing.md`；必须在阅读现有测试和编写任何测试之前读完；
   - 受影响代码和现有测试。
4. `git fetch origin`，从最新 `origin/main` 建立或恢复 `unit/<unit-id>` 分支，并在
   `<repo-root>/.worktrees/unit-<unit-id>` 建立专属 worktree。恢复已有现场时先核对分支、
   远端 head 和未提交修改；禁止用 reset 覆盖不明现场。安全建立后把 unit 分支推送到
   origin。
5. 在 unit worktree 中运行仓库规定的实现前测试基线。基线已有失败时先区分并报告，
   不把它混入本 unit 或用后续结果掩盖。

所有 unit 分支写入、集成、修复、文档、归档和 PR 准备都在 unit worktree 中进行。验收
skill 若按自身契约使用只读 worktree，由该契约管理。不得切换、覆盖、清理或借用主仓
checkout 中已有的分支、修改和未跟踪文件。

## 组织实施

- 根据任务本身决定直接实现还是使用 subagent，以及拆分、顺序、并行度、工作区、提交和
  交接方式。
- 把 milestone 当作必须完成的交付目标；逐条满足其范围和退出标准。
- 自行管理协作中的写入冲突与集成，最终状态统一落在 unit 分支。
- 自行选择实施记录的形式；记录范围、关键决策、design 偏差、测试、真实入口证据和相关
  commit，使 milestone 退出标准能够逐条复核。
- 在已确认需求范围内调整技术方案时，同步 `design.md` 和实现记录。调整会改变用户需求、
  验收标准或 unit 范围时，先与用户重新对齐。
- 只处理本 unit 范围。发现 out-of-unit 问题时按仓库规则建立 issue 并记录关联，不顺手
  扩大实现范围。

## 实现质量

仓库规范和 unit 文档是完整权威；以下条目只标出实施阶段必须兑现的结果。

### 架构与失败处理

- 遵守 design、仓库架构边界和现有实现模式；实现细节优先扩展已有机制，不创建平行机制。
- 禁止吞错、神秘 fallback、临时常量和只绕过症状的 heuristic。
- 遇到非平凡 bug、测试失败或意外行为时，先使用 `$systematic-debugging` 定位根因，再在
  正确层修复。

### 测试

- 按 `docs/development/testing.md` 决定测试行为、位置、层级、命名、依赖和停止条件。
- 对可测试的新行为或 bug 修复先取得有意义的 Red / 失败复现，再完成 Green。
- 测试可观察行为，不依赖私有实现细节，不用 skip、xfail、放宽断言或重试掩盖失败。
- 先运行最窄相关测试，再按影响范围扩大；提交验收前，仓库规定的相关测试命令必须全绿。

### 真实入口

- 新功能必须从真实产品入口证明用户可以使用；bug 修复必须从用户报告的同一路径证明症状
  已消失。
- 前端改动必须在真实浏览器中执行关键交互，覆盖适用状态和 viewport，检查 console 与
  network。核心路径和历史 bug 提供与现有测试体系相称的 regression 保护。
- 跨进程或运行时行为必须运行真实服务链路直至用户可见结果。mock、stub 和进程内替代只能
  作为补充证据。
- prototype、reference、视觉和交互证据必须能够复查；交付需要引用的截图、录屏或报告放在
  unit 目录或仓库内的持久路径。
- 环境无法完成必需验证时明确报告阻塞，不能改变证据标准后宣告完成。

### 运行时隔离

- 启动服务前分配隔离端口、Gateway config 和持久化状态，优先使用仓库提供的 worktree
  runtime 工具。
- 记录本 unit 启动的进程；完成、暂停或阻塞退出前清理这些进程。资源无法隔离时保存现场并
  报告阻塞。

## 验收闸

所有 milestone 完成并逐条核对退出标准后，对当前完整 unit 状态执行第一轮完整验收：

- 存在用户可观察旅程：执行 `$change-reviewer`、`$change-verifier` 和 `$change-code-review`。
- 零用户面：执行 `$change-verifier` 和 `$change-code-review`，不派产品 reviewer。

适用的 `$change-reviewer` 与 `$change-verifier` 分别由独立于实施上下文、彼此独立的 subagent
执行。`$change-code-review` 在实施上下文中执行，但必须按其自身 skill 派发独立的 finder /
verifier subagent，不得省略为自我审查。验收 subagent 只按各自 skill 的读写边界检查并产出
结论，不承担实现或修复；后续复验优先复用对应验收上下文，无法恢复时再新建。

按各 skill 的当前输入、输出和只读契约执行，并提供 unit worktree、当前 head、unit 文档和
实际证据位置；明确每个 milestone 退出标准对应的证据。适用时，给 reviewer 的验收口径只来自首文档
中的用户可观察行为，不添加协议、接口或内部实现标准。

逐条裁决 finding：

- 核实证据是否成立、是否属于本 unit、是否阻塞交付；
- 把 reviewer 建议视为问题线索，依据根因和架构判断正确修复层；
- 修复成立且阻塞交付的问题；
- 对拒绝、降级或移出范围的 finding 记录理由和证据。

每次修复后检查实际 delta 对适用门禁结论的影响，只复验失效或无法确认仍有效的范围；高风险
或边界不清时运行完整复验。后续的文档同步、rebase、冲突解决和 CI 修复也执行同样判断。
交付时所有适用门禁必须各自对最终状态持有有效结论，并能说明结论对应的 head、报告或继承依据。

## 交付

1. 完成验收闸指出的必要上层文档同步，并按仓库文档权威边界落到正确位置；这些修改影响任一
   门禁的验证对象时，复验受影响范围。
2. fetch 并把 unit 分支同步到最新 `origin/main`。根据 main 增量、门禁后的 unit 增量和最终
   unit diff，逐道判断原结论是否仍然有效：能证明无影响时保留，受影响时复验；高风险或边界
   不清时完整重跑。无法安全判断时保存现场并报告阻塞。
3. 按 `docs/specs/CONTRIBUTING.md` 的收尾归并规则，用实际实现校正 unit delta-spec。只派
   `$change-verifier` 以 `verification_mode: corrected-delta` 对账；结论为 `aligned` 后再把
   行为增量合入对应 canonical spec，无行为增量时记录 `no spec delta`。delta 不一致时继续
   校正并重新对账；实现不一致时修复实现并复验受影响的门禁。
4. 从当前 CI 配置读取命令，在 unit worktree 运行本地 CI 等价检查；使用只检查、不改写文件
   的格式化命令。
5. 适用门禁、长青契约归并和本地 CI 均收口后，按 `docs/changes/README.md` 把整个 unit 目录
   移入 `docs/changes/archive/`，并运行 `git diff --check`。
6. 检查 canonical 文档归并和 archive 移动是否使任何门禁失效，并确认 `origin/main` 没有
   越过第 2 步已经判断的 base；需要时返回相应步骤。通过后组装可追溯的 PR：说明需求和实现，
   链接归档后的 unit 文档，列出 spec delta、适用门禁的最新有效状态及验证结果。
7. 从 `unit/<unit-id>` 向 `main` 创建 PR，等待 required CI checks 全绿。CI 失败时先定位
   根因并修复，再复验受 delta 影响的闸；更新 PR 中对应的 head 和验证状态。
8. CI 全绿后清理由本 unit 创建的运行时资源和临时 worktree，输出 PR URL。未获用户明确
   授权时不合并 PR。

## 完成条件

仅在以下条件全部满足时报告完成：

- spec、design 和全部 milestone 的退出标准均已实现并有证据；
- 相关测试、本地质量检查和真实入口验证通过；
- 所有适用门禁对最终状态各有有效结论，所有成立且阻塞交付的 finding 已关闭；
- canonical spec 已按实际行为同步，整个 unit 已归档；
- PR 已创建且 required CI checks 全绿；
- 主仓 checkout 未受影响，本 unit 启动的运行时资源已清理。

若被阻塞，报告已完成范围、阻塞原因、证据和可恢复现场。
