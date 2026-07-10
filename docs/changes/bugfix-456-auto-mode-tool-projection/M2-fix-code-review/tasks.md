# bugfix-456-M2: Auto mode tool projection code review fixes - Tasks

> 对齐: `../fix.md` + M2 reviewer findings

## 目标

完成 code review 反馈中的 auto mode projection 修复：历史 tool_use 投影必须稳定来自历史记录，当前 action 复用已验证 projection，`skill_manage` 长文本投影能暴露头尾风险，`skill_manage view` 作为只读 action 走低风险 fast path。

## 退出标准

- [x] 历史 tool_use 投影只基于历史记录中的 `name` + `input`，不查询当前 live registry，不被同名 replacement tool 改写。
- [x] 当前 action 在进入 classifier prompt 时复用 gate 已验证的 `current_projection`，不在 prompt builder 内再次调用 tool projection。
- [x] `skill_manage create/write_file` 的长 `content` / `file_content` projection 包含长度、开头、结尾，并明确中间截断。
- [x] 代码确认 `skill_manage view` 为只读路径后，将 `view` 纳入工具级低风险 fast path。
- [x] 覆盖上述行为的红测已保留，并随实现转绿。
- [x] M2 `tasks.md` / `progress.md` 已回填。

## 测试策略

- 被测行为(来自退出标准): 历史 projection 稳定性、当前 projection 单次复用、`skill_manage` 长文本摘要、`skill_manage view` action 级 allow、contract 白名单行号同步。
- 已有测试在: `tests/unit/test_auto_mode_gate_hook.py`(扩展)、`tests/unit/test_skill_manage_tool.py`(扩展)、`tests/unit/test_auto_mode_gate.py`(适配 helper 签名)、`tests/contract/test_no_hardcoded_workspace_dirname.py`(行号白名单同步)。
- 落层/目录/marker: `tests/unit/` + `tests/contract/`，marker: 无。
- 可选依赖 importorskip: 无。
- 本 milestone 产生的一次性验收证据(收尾删除，不进套件): 无。

前端 UI：N/A。

Prototype / Reference Contract：N/A。

## Roadpoints

### R1 - Code review fixes

- 状态: DONE
- 步骤:
  - [x] 保留上一位 worker 已提交红测：历史 registry 独立、replacement tool 不重写历史、current projection 只算一次、长文本头尾摘要、`view` allow。
  - [x] `auto_mode_gate` 新增历史通用 projection，并把 prompt builder 入参改为已验证的 current projection。
  - [x] `skill_manage` 将 `view` 归入低风险只读 action，并为长文本投影输出 length/head/omitted/tail。
  - [x] 同步 hardcoded workspace dirname contract 的既有白名单行号，原因是本次 helper 增加导致同一既有 `.nanocode` fallback 下移。
  - [x] 跑窄测、相关回归、ruff 和 `pytest -m "not e2e"`。
- 验证:
  - [x] `pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_hook.py tests/unit/test_auto_mode_gate_allowlist.py tests/unit/test_auto_mode_gate_dispatch.py tests/unit/test_skill_manage_tool.py tests/unit/personal_assistant/test_cron_tool_permissions.py tests/unit/agent/platform/tools/builtins/test_web_fetch_permissions.py tests/integration/test_tools_registry_loader_integration.py tests/contract/test_no_hardcoded_workspace_dirname.py`
  - [x] `ruff check` 本次修改文件
  - [x] `pytest -m "not e2e"`
