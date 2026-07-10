# Design 评审: bugfix-431-runtime-skill-resolution

**结论**: Approved（第三轮；上轮 CRITICAL「helper 归属层选反」已修干净，无新引入问题）

**评审日期**: 2026-06-24（第三轮，复核 helper 下沉 core）

## 核实台账

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| CRITICAL 修复: helper 下沉 core | 读决策 2 + 架构图 + 接口段 | ✅ `_WorkspaceDirnameSkillResolver` + `make_skill_resolver` 落 `agent.core.skills.discovery`；AgentRuntime(core) 同层调用、Kernel(sdk) 向下 import；架构图箭头落进 Core subgraph |
| 依赖方向合法性 | 核 core↛sdk | ✅ core→core 同层 + sdk→core 向下，均合法。决策 2 拒绝段已翻转为「拒绝留 sdk」 |
| import 循环风险 | 追 discovery.py / runtime.py / kernel.py import 链 | ✅ 无。resolver 只用 Path 零新依赖；runtime.py 已 `from agent.core.skills import resolve_available_skills` 同方向；sdk→core 既有 |
| 同源闭环 | 数 5 条发现路径 | ✅ list_skills / preview / _resolve_session_available_skills / _from_config(compact) / agent 工具校验全经 make_skill_resolver |
| surface guard 不受影响 | 核 helper 公开性 | ✅ helper 是 core 公开 API（进 agent.core.skills.__all__），不进 agent.sdk.__all__；旧 `dir(agent.sdk)` 断言正确替换为 test_core_skills_location 归属断言 |
| 决策 4 删 product_skill_root | 核零调用方 + 测试影响 | ✅ 零生产调用方；删参数非删函数，存在性断言不破 |
| dirname=None 路径一致性 | 追 helper→None→resolve_available_skills | ✅ helper 返 None → 决策 4 空元组分支 → delta-spec 场景 3 一致 |
| M1 范围/退出标准 | 两轨齐？范围交集？ | ✅ 范围含 5 文件各改点；退出标准含 boundary contract 绿 + helper 归属断言，两轨齐、可验 |
| 上轮 W1/W2/W3 | 复核 | ✅ 均仍消化 |

## Issues

无。上轮 CRITICAL（helper 归属层选反致 core→sdk 反向依赖）已干净修复，复核无新引入矛盾。

## Recommendations（不阻断）

1. 决策 1 理由仍写「Kernel 已经用同一组参数构造 resolver」——下沉后 Kernel 改为调 helper 而非自己构造，措辞略滞后于决策 2。纯叙述瑕疵，worker 不会被带偏，可留可改。
2. 风险 6 子 agent workspace_root 分歧（校验 ctx.repo_root vs 加载 ctx.cwd）已显式 defer，本 unit 保持现状即可。

可进 change-orchestrator 实施。
