# M115 Gateway 默认 workspace 与内部 kernel 配置收口

## 启动记录
- 已阅读：`/Users/czj/Repos/nano-multiagent/.worktrees/M115/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M115/COMMENTING_GUIDE.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M115/src/personal_assistant/config/local_store.py`、`/Users/czj/Repos/nano-multiagent/.worktrees/M115/src/personal_assistant/main.py`、相关 unit/e2e 测试、`/Users/czj/Repos/nano-multiagent/.worktrees/M115/README.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M115/docs/operator-runbook.md`。
- 注释规范承诺：后续新增 public module/class/function/method 均按 Google 风格 docstring 写契约；注释只解释意图、边界、代价，不复述代码。
- 当前处境：M115，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M115`，branch=`milestone/M115`。
- 测试门禁：`PYTHONPATH=src pytest -q tests/unit/personal_assistant tests/e2e/test_personal_assistant_main_e2e.py tests/e2e/test_m112_real_process_roundtrip_e2e.py`
- 基线结果：`45 passed`。
- prevention / 注意事项：
  - `workspace_root` 缺省必须落到 `~/nano-assistant/workspace/<agent_id>/`，仅显式配置时覆盖。
  - `kernel.base_url` 视为内部实现细节，用户最小配置不应暴露为必填项。
  - 真实入口验证不能退化为只测 loader happy path。
  - 只做最小必要改动，不做无关重构。

### R1 默认 workspace_root 解析与创建
- Context: 现状要求每个 agent 显式提供且预先创建 `workspace_root`，与 M115 的“缺省自动落到 `~/nano-assistant/workspace/<agent_id>/` 并按需创建”目标冲突；同时必须保留显式配置的现有约束，避免误改 operator 自定义路径语义。
- Decision: 在 `load_local_config()` 的 agent 解析阶段将 `workspace_root` 改为可选；缺省时按 `~/nano-assistant/workspace/<agent_id>/` 解析并在加载时 `mkdir(parents=True, exist_ok=True)`，显式值仍要求目录已存在。
- Rationale: 默认目录属于 gateway 自管本地状态，适合在配置加载阶段直接创建；显式路径则继续保持 operator 明确声明与预置目录的安全边界，避免悄悄帮用户创建错误路径。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/personal_assistant tests/e2e/test_personal_assistant_main_e2e.py tests/e2e/test_m112_real_process_roundtrip_e2e.py`
  - Entry: `test_run_gateway_e2e_starts_runtime_with_loaded_config` 已通过真实入口 `run_gateway()` 断言缺省配置会解析并创建 `~/nano-assistant/workspace/assistant-a`。
- Rollback: 9c70def
- Commits: C1=9c70def, C2=6fcc2c6, C3=待补
- Next: R2 收口 `kernel.base_url` 用户配置口径与文档示例。

## 里程碑收口备注
- R1 文档在实现提交中一并落盘，未产生额外独立文档 diff；因此没有单独的 R1 C3 hash。
- R2 因代码层已具备 `kernel.base_url` 默认行为，未额外制造“先红后绿”的伪实现提交，而是直接将测试入口与用户文档收口到最小配置契约。

### R2 kernel.base_url 内部化与文档示例收口
- Context: 代码层面对 `kernel.base_url` 早已存在默认值，但 runbook / smoke 配置示例仍要求用户显式填写，导致用户契约暴露了内部默认细节；同时要保证真实入口测试改成最小配置后仍能正常启动。
- Decision: 保持 loader 内部默认 `http://127.0.0.1:8000` 不变，仅更新真实入口 smoke / run_gateway 测试为“省略 `kernel.base_url` 也可启动”的口径，并同步收口 `README.md`、`docs/operator-runbook.md` 的最小配置示例与说明。
- Rationale: 该能力已存在，最小必要改动是把测试与文档改成真实用户契约，而不是再改运行时代码；这样既满足 M115，也避免无关重构。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/personal_assistant tests/e2e/test_personal_assistant_main_e2e.py tests/e2e/test_m112_real_process_roundtrip_e2e.py`
  - Entry: smoke 配置与 `run_gateway()` e2e 均在未填写 `kernel.base_url` 时通过，证明用户最小配置无需暴露该字段。
- Rollback: 6fcc2c6
- Commits: C1=未单独提交（现有实现已满足，直接以测试/文档收口）, C2=c4b187f, C3=待补
- Next: 全部 Roadpoint 已完成，等待主 agent 验收/后续集成。
