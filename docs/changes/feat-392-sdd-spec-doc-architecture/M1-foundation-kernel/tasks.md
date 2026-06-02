# feat-392-M1: foundation + kernel 契约层 — Tasks

> 对齐: ../design.md v1

## 目标

落地 SDD 长青文档体系的地基与最难的一包(kernel),让 M2-M4 三个并行 worker 照已验证的 GUIDE 各写一包:

- `docs/SPEC_GUIDE.md`：文档规范(判据两问 + 契约层骨架 + 不进 spec 的分流表 + 收尾归并 checklist + 读侧 grounding checklist + 内核契约写法纪律)。
- `docs/specs/kernel/spec.md`：从 `tests/contract/` + `src/agent/` 逆向出的当前内核对外行为契约(Purpose + Requirement/Scenario)。
- `SPEC.md` 重定位为跨包顶点(§6 文档索引指向 `docs/specs/`)；`AGENTS.md` 关键文档索引同步。
- `git mv` 退役 `docs/内核设计SPEC.md`。
- 三 skill 接入新读写闭环:`change-spec-author` / `change-design-author` 读侧指向 `docs/specs/<包>`(design 阶段对代码 grounding)；`change-orchestrator` §7 提 PR 前加「收尾归并」步 + reviewer/verifier 软对账。

## 退出标准

- [x] `docs/SPEC_GUIDE.md` 含:判据(两问)、契约层文件骨架、不进 spec 的分流表、orchestrator 收尾归并 checklist、读侧 grounding checklist、内核契约写法纪律(WHEN/THEN 主语=消费者,CDC 裁剪)
- [x] `docs/specs/kernel/spec.md` 是纯 `Purpose + Requirement/Scenario`,反映当前内核(`agent.sdk` 对外面)真实行为,不含已删的 HTTP API(refactor-387)
- [x] `SPEC.md` §6 文档索引指向 `docs/specs/`,与契约层不重复
- [x] `AGENTS.md` 关键文档索引指向 `docs/specs/<包>/` + `SPEC_GUIDE.md`
- [x] `docs/内核设计SPEC.md` 经 `git mv` 退役(进 `docs/archive/`),`SPEC.md` 索引不再指向它
- [x] 三 skill 文本接入新读写侧(读 `docs/specs/`、orchestrator §7 归并 + 软对账)
- [x] 契约层格式纪律:无 `覆盖:` 行、无 `[可执行]`/`[行为]` 标签、无 freshness 测试(决策 4)
- [x] 退役内核 SPEC 的连带修法:架构验收测试(`tests/contract/test_multi_product_architecture_acceptance.py`)的 `KERNEL_SPEC` 锚回 `SPEC.md`、`change-reviewer` 模板的文档同步清单改指 `docs/specs/` + `SPEC_GUIDE.md`(R5)
- [x] `pytest -m "not e2e"` 全绿(确认文档/skill 改动不破坏现有测试)——2342 passed

## 测试策略

本 milestone 产物是**文档 + skill 文本**,无运行时代码改动。按 design 决策 4,契约层 drift 走**软对账**(orchestrator 收尾时复用 reviewer/verifier 对每条 Requirement/Scenario 搜代码 + 测试),**不做 freshness 测试 / 机械绑定**,故本 unit 不新增任何 pytest。

- 被测行为(来自退出标准):无新增可执行行为。唯一的"测试"诉求是「我的改动不破坏现有套件」。
- 已有测试在:`tests/`(全树)。不扩展、不新建——本 unit 不动 `src/`,现有测试照常应全绿。
- 落层/目录/marker:N/A(不新增测试)。
- 可选依赖 importorskip:N/A。
- 一次性验收证据(收尾删除):无。契约层正确性的"验证入口"= 拿 `docs/specs/kernel/spec.md` 每条 Requirement/Scenario 对照 `tests/contract/` + `src/agent/sdk/kernel.py` 逐条核对(料源 ①②),核不上即弃。这是 worker 自检,过程记进 progress.md;系统级硬卡留给 orchestrator 收尾软对账(reviewer/verifier)。

前端 UI:N/A(纯文档 unit,无界面)。

## Roadpoints

### R1 — docs/SPEC_GUIDE.md 文档规范 — DONE

- 步骤:新建 `docs/SPEC_GUIDE.md`。含五块:① 判据两问;② 契约层文件骨架(Purpose + Requirement/Scenario + 对齐行);③ 不进 spec 的分流表;④ orchestrator 收尾归并 checklist;⑤ 读侧 grounding checklist;⑥ 内核/库契约写法纪律(research §7.5:WHEN/THEN 主语=消费者、每 Requirement 一份 pre→post 契约或 invariant、CDC 裁剪、spec-anchored)。
- 验证:自审 GUIDE 是否覆盖 spec.md 验收标准「文档规范 GUIDE 定义放什么/不放什么 + 骨架」的 Scenario;格式纪律符合决策 4(纯 Purpose+Req/Scenario,无标签/覆盖行/freshness)。

### R2 — docs/specs/kernel/spec.md 内核契约层 — DONE

- 步骤:照 R1 GUIDE 骨架,从 ① `tests/contract/`(尤其 `test_agent_sdk_surface_contract.py` / `test_kernel_sdk_behavior_contract.py` / `test_agent_sdk_boundary_contract.py` / `test_core_no_platform_imports.py`)② `src/agent/sdk/kernel.py` 逆向出内核对外契约。每条 Requirement/Scenario 主语 = 经 `agent.sdk` 调用内核的消费者(产品/contract 测试)。旧 `docs/内核设计SPEC.md` 仅作 checklist 逐条拿代码重核,核不上即弃(§12 HTTP API 已删,不写)。
- 验证:逐条 Requirement 对照 `kernel.py` 方法签名 + contract 测试断言,确认可被代码/测试印证;无实现走查、无库选型、无内部数据结构。

### R3 — 顶点 SPEC.md 重定位 + AGENTS.md 索引 + 退役旧内核 SPEC — DONE

- 步骤:`SPEC.md` §6 文档索引改为指向 `docs/specs/`(去掉对 `docs/内核设计SPEC.md` 等的直接索引,内核 §4 的「详见」链接同步);`AGENTS.md`「关键文档索引」表加 `docs/specs/<包>/` + `SPEC_GUIDE.md`,去掉对四份旧子系统 SPEC 的索引(M2-M4 退役其余三份);`git mv docs/内核设计SPEC.md docs/archive/内核设计SPEC.md`。
- 验证:`grep 内核设计SPEC SPEC.md AGENTS.md` 无残留活引用;SPEC.md 仍是纯跨包内容,不下钻单包行为契约。

### R4 — change-* skill 接入读写闭环 — DONE

- 步骤:
  - `change-spec-author`:读侧 § 调研/相关代码处,指向 `docs/specs/<包>`(current 契约层)取词汇。
  - `change-design-author` §3.0 调研表:架构总图行 + 新增一行指向 `docs/specs/<包>`,并写明 design 阶段对契约层与当前代码做 grounding(发现不一致即报)。
  - `change-orchestrator`:§7 提 PR 前(§6.1 pass 之后)新增「收尾归并」步——依据本 unit design.md + 代码 diff,把行为增量直接编辑进 `docs/specs/<包>`、bump 对齐行(无行为变化记 "no spec delta");并在 reviewer/verifier 调度处补:对 spec vs 代码做软对账报偏离。
- 验证:三 skill 改动后 `grep docs/specs` 命中新读写侧;orchestrator 收尾归并步措辞符合决策 3/4(直接编辑 canonical、无 delta 工件、软对账不机械卡)。

### R5 — 退役内核 SPEC 的连带修法(架构测试 retarget + reviewer 模板) — DONE

- 背景:R3 把 `docs/内核设计SPEC.md` git mv 退役进 `docs/archive/` 后,两处还硬指向它,会 FileNotFoundError / 误导 reviewer:
  ① 架构验收测试 `tests/contract/test_multi_product_architecture_acceptance.py` 的 `KERNEL_SPEC` 仍 = `docs/内核设计SPEC.md`;
  ② `change-reviewer` 的 `SKILL.md` §7 / `assets/{acceptance,regression}.md` 文档同步清单仍点名退役的 `内核设计SPEC` + 旧子系统 SPEC。
- 修法 #1(走 b——架构测试在 `tests/`):`KERNEL_SPEC` 锚回 **`SPEC.md`**(不进契约层)。理由:该测试断言的是内核**分层 + 依赖方向 + 库形态(无 HTTP)**——按 SPEC_GUIDE,"实现能变而对外行为不变"以外的**跨包架构属性**不进单包契约层 `docs/specs/`,canonical 家是顶点 `SPEC.md`。`KERNEL_REQUIRED_DOC_SNIPPETS` 改为 SPEC.md §4「agent — 执行内核」实际措辞,逐字验三条属性:①「内部分四层(core / platform / products / sdk)」+ 目录树 sdk 行;②「`core` 纯逻辑,不依赖 `platform` / `products`」;③「对外只暴露 `agent.sdk`」+「内核是库不是服务,不内置任何对外网络 API」。**未为转绿掏空**——三条断言仍实质守住内核终态。
- 修法 #2(走 a——reviewer 模板在 `.claude/skills/`):三处文档同步清单从「`内核设计SPEC` + 相关产品 SPEC」改指「`SPEC.md`(跨包顶点)+ `docs/specs/<包>/spec.md`(长青契约层)+ `SPEC_GUIDE.md`」,并加一句:长青契约层写回是 orchestrator §7.0 收尾归并的职责,reviewer 只勾"是否已反映本 unit 行为增量"。只改引用/清单指向,不动 reviewer 的验收逻辑/评分模型。
- 验证:`pytest tests/contract/test_multi_product_architecture_acceptance.py` 3 passed;`grep 内核设计SPEC|*-SPEC` 在 `.claude/skills/` 与 `tests/` 仅余注释里的退役说明,无活引用;全树 `pytest -m "not e2e"` 2342 passed。
- 备注:`TASKS/` `PROGRESS/` `docs/需求.md` 内的旧 SPEC 引用属冻结历史归档,不动(R3 已界定)。
