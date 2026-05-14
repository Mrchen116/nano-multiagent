# feat-349-M3: self-evolution-wiring — Tasks

## 目标

将 M1（background hook fork 基建）+ M2（MemoryStore + SkillWriter + 两个工具）的产物收口接线为可实际运行的自进化系统：nudge 计数信号链路、两产品接线（tools/hooks/guidance 注入）、self_improvement background hook 模块、回显（CLI + IM meta）、SSE 背景事件送达。

## 退出标准（worker 轨）

- [x] `platform/hooks/builtins/self_improvement.py` 实现完毕：读里程表判断 nudge、fork_conversation 触发 review、publish_session_event 回显。
- [x] 两产品（LC + PA）接线：`skill_manage` + `memory` 工具注册到默认工具集、`self_improvement` hook 注册。
- [x] memory block + SKILLS_GUIDANCE + MEMORY_GUIDANCE 注入 `build_system_prompt`，条件：工具在 session 工具集中。
- [x] PA `local_store.ensure_workspace_defaults()` seed 位置改到 `.<namespace>/memory/`。
- [x] LC workspace 级 `self_evolution` 配置读取接线。
- [x] `self_evolution_review` session event：CLI REPL 渲染层识别 → 一行系统提示；IM Gateway 消费 → meta 消息。
- [x] SSE 订阅生命周期覆盖 background side-chain（background 事件送达，Refs #8）。
- [x] 递归 fork 防护：fork 侧链内 nudge 间隔强制置 0 / fork_conversation 不注入。
- [x] 单测全绿（依赖方向 contract 不破坏）。

## 测试策略

| 场景 | 策略 |
|---|---|
| nudge 计数信号流（tool_iterations → hook payload → 阈值判定） | 单元测试 mock hook context |
| self_improvement hook 模块逻辑（fork 触发 / 跳过 / 递归防护） | 单元测试 mock fork_conversation |
| build_system_prompt memory block + guidance 注入 | 单元测试：注入条件断言 |
| 两产品接线：工具/hook 注册 | 单元测试：profile 工具列表 + hook 模块列表验证 |
| ensure_workspace_defaults seed 位置 | 单元测试：seed 文件路径断言 |
| self_evolution_review 事件 CLI 渲染 | 单元测试：REPL 事件处理函数 |
| PA self_evolution 配置透传 | 单元测试 |
| contract 依赖方向 | tests/contract/test_core_no_platform_imports.py + test_cli_http_only_contract.py |

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | self_improvement background hook 模块 (nudge 判断 + fork + 回显) | DONE |
| R2 | prompting.py 注入 memory block + SKILLS/MEMORY guidance | DONE |
| R3 | 两产品接线：toolset + hook 注册 + workspace 配置透传 | DONE |
| R4 | local_store seed 位置迁移 + LC workspace 配置读取 | DONE |
| R5 | CLI REPL 渲染 self_evolution_review 事件 | DONE |
| R6 | SSE 背景事件送达 (background 生命周期 Refs #8) | TODO |
| R7 | 收口集成：全部单测绿 + contract 验证 | TODO |
