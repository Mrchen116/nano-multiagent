# Design 评审: bugfix-431-runtime-skill-resolution

**结论**: Issues Found（复审；新增 1 条 CRITICAL：共享 helper 归属层选反，导致 core→sdk 反向依赖）

**评审日期**: 2026-06-24（复审，架构 taste 视角）

## 核实台账

逐条核过的承重原子；结论附证据。本轮重点：跳出单条 grounding，逐对扫决策组合后的依赖流向。

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状: `build_kernel` 构造 AgentRuntime 未传 config_resolver | grep config_resolver 全 kernel.py | ✅ 成立。kernel.py 全文件无 config_resolver 字样 |
| 现状: list_skills/preview 各自内联 `_WorkspaceDirnameSkillResolver` | grep | ✅ 成立。kernel.py:1163 / 1428 两处独立内联 |
| 现状: `_WorkspaceDirnameSkillResolver` 是纯逻辑、零 sdk 依赖 | 读 kernel.py:567-599 | ✅ 成立。只组合 `<ws>/<dirname>/skills + extra_roots` 去重，实现 `SkillRootResolver` Protocol，仅用 `Path` |
| 现状: `SkillRootResolver` Protocol 定义在 core | 读 discovery.py:12 | ✅ 成立。与 resolve_available_skills 同住 core/skills/discovery.py |
| 现状: `config_resolver=None` → 回退 codex/.codex/.nano roots | 读 discovery.py:38-49 | ✅ 成立 |
| 现状: resolve_available_skills 调用方 | grep | ✅ 仅 5 处(runtime:1307/1320、agent:657、kernel:1169/1437)，改造清单全覆盖 |
| 既有约束: `agent.core ↛ agent.sdk`(无反向依赖) | 读 test_agent_sdk_boundary_contract.py:13-14 + AGENTS.md | ✅ 硬规则。core 最内层，绝不可 import sdk |
| **决策 1 + 决策 2 组合: core runtime 调 sdk helper** | 逐对扫依赖流向 | ✗ **CRITICAL**。决策 1 让 AgentRuntime(core) 内部调决策 2 放在 agent.sdk.kernel 的 `_make_skill_resolver` = core→sdk 反向依赖；架构图自画 `RT → Helper` 跨层箭头(见 Issue 1) |
| 决策 2「拒绝放 core」理由 | 核理由是否成立 | ✗ 理由反了。resolver 纯逻辑零部署耦合；决策 1 已让 core 持有 skill_search_roots，"core 不感知部署输入"自相矛盾 |
| 决策 3: 移 property 换方法 | 四问 | ✅ 拍死；tools/hooks 不对称已说明 |
| 决策 4: 清 codex 回退 | 四问 + spec 驱动 | ✅ 拍死。但 product_skill_root 零生产调用方，None 分支当前不 consult 它(见 Rec) |
| 上轮 W1/W2/W3 | 复核 | ✅ 均已正确消化(surface guard `dir()` 断言、test_core_skills_location 仅 identity 断言不破、tools/hooks 不对称说明) |
| delta-spec 场景 1/2/3 | THEN 可观察？ | ✅ 均消费者可观察，无内部符号 |
| M1 单 milestone 垂直切片 | 垂直 vs 横切 | ✅ 全链路端到端，但范围里「core helper 归属」需随 Issue 1 调整 |

## Issues

### [CRITICAL] 共享 helper 放 sdk、让 core 反向复用 —— 依赖方向选反

**位置**: 决策 1 + 决策 2 + 架构总览图(`RT -->|内部调用 Helper| Helper`) + 接口段 228-239

**问题**: 决策 2 把 `_make_skill_resolver` + `_WorkspaceDirnameSkillResolver` 留在 `agent.sdk.kernel`；决策 1/接口段让 `AgentRuntime`(core 层) 的 `resolve_available_skills` **内部调用该 helper**。这等于 `agent.core.agent.runtime` 里 `from agent.sdk.kernel import _make_skill_resolver` —— **core→sdk 反向依赖**，违反 `agent.core ↛ agent.sdk` 硬规则。

三个坐实事实：① resolver 是纯逻辑零 sdk 依赖(kernel.py:567-599)；② 它实现的 `SkillRootResolver` Protocol 本就住 core(discovery.py:12)；③ boundary 规则明写 core 不可 import sdk。

决策 2 的「拒绝放 core」理由还是反的：它说"core 不感知 skill_search_roots 部署输入"——但决策 1 已经让 `AgentRuntime`(core) 持有 `skill_search_roots` 字段，前后矛盾。真正破坏层级的是决策 2 选的方案本身。

**不改→下游出什么坏事**: worker 照实现写出 core import sdk，M1 退出标准自列的「test_agent_sdk_boundary_contract.py 绿」直接撞红，卡死；或 worker 为绕开而临时把 helper 复制一份到 core，"同源"目标当场破功。

**建议**: 把 `_WorkspaceDirnameSkillResolver` + helper **下沉到 `agent.core.skills`**(紧邻 SkillRootResolver Protocol 和 resolve_available_skills)。则 AgentRuntime(core) 同层调用合法；Kernel(sdk) 的 list_skills/preview 向下 import core helper 合法(kernel.py:1150 本就已 `from agent.core.skills.discovery import resolve_available_skills`，同方向)。同源 ✓、product-neutral ✓(resolver 只组合传入参数，consumer 仍经 build_kernel 注入 roots)、依赖方向 ✓。决策 2「拒绝放 core」整段随之失效，架构图那条跨层箭头消失。

## Recommendations

不阻断门禁，作者自行取舍。

1. `product_skill_root` 全仓零生产调用方(仅 discovery.py 内部定义+引用)。决策 4「为减少波及面先保留」实际波及面为 0；可顺手删，或把「保持现有行为」改为「现无调用方，按显式 root 语义重建 None 分支」更准——当前 None 分支根本不 consult product_skill_root。
2. 风险 6 子 agent workspace_root 分歧(校验 ctx.repo_root vs 加载 ctx.cwd)已诚实标注并显式 defer，本 unit 保持现状即可。
