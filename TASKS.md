# TASKS (Current Milestone: M7)

## [DONE] R7.1 hooks 核心模块 + observe/intercept 语义 + 双源加载
- Steps:
  - 先补 hooks 子系统的 unit/contract/integration/e2e 失败测试（Red）
  - 实现 `hooks/types.py`、`context.py`、`registry.py`、`loader.py`、`runner.py`
  - 落地 observe/intercept 语义：优先级、同优先级顺序、超时、异常隔离（fail-open）
  - 支持双源加载：`src/nano_multiagent/hooks/builtins/` + `<repo_root>/.nano/hooks/`
  - 支持 `setup(hooks)` 模块约定与 `hooks.on(...)` 注册
  - 实现最小拦截返回契约：`input transform/handled`、`tool_call block`、`tool_result rewrite`
  - 跑目标测试与 `pytest -q` 全量验收
- Expected Tests:
  - `tests/unit/test_hooks_runner.py`
  - `tests/contract/test_hooks_contract.py`
  - `tests/integration/test_hooks_loader_integration.py`
  - `tests/e2e/test_hooks_pipeline_e2e.py`
  - `pytest -q`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R7.1 hash 与证据
  - 回填历史 C3 占位（R6.1）

## Milestone M7 状态
- R7.1 已完成并完成 C1/C2/C3 闭环。
- 按当前边界不进入 M8 runtime 深度打点接线与 M13 Hook 查询接口。
