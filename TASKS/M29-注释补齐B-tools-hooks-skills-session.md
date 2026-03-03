# TASKS (Milestone: M29)

- Test command: `PYTHONPATH=src pytest -q`
- Branch: `milestone/M29`
- Milestone status: `RUNNING`
- Refactor boundaries:
  - Must keep unchanged: `tools/hooks/skills/session` 现有运行时行为、错误语义、协议字段与序列化格式。
  - Allowed to change: 仅补充 public API docstring 与关键约束注释；允许新增里程碑内注释契约检查脚本。

## [DONE] R29.1 tools/hooks/skills/session 注释契约补齐与约束固化
- Acceptance:
  - `tools/hooks/skills/session` 的 public module/class/function/method docstring 补齐，且与真实行为一致。
  - `tools/safety.py` 写明路径沙箱与命令策略的安全边界、失败模式与代价。
  - `hooks/runner.py` 与 `tools/registry.py` 写明 hook 事件分发、异常隔离、fail-open 的约束与影响。
  - `session/manager.py`、`session/serializers.py`、`session/stores/*` 写明会话持久化边界（event/snapshot 语义、版本与存储边界）。
  - 不引入无规范 TODO/FIXME；若出现必须符合 `TODO/FIXME(<issue-id>): ...` 规范。
- Tests Plan:
  - `unit`: 选。新增注释契约检查脚本，先红后绿，约束 public API docstring 覆盖与关键约束语句存在。
  - `contract`: 不选。不涉及外部 HTTP/tool/session 协议行为变更。
  - `integration`: 选。复跑全量回归，确认注释增强未引入行为回归。
  - `e2e`: 选。通过既有 `pytest` 套件中的 e2e 测试验证入口行为不变。
- Expected Tests:
  - `python3 TASKS/m29_comment_contract_check.py`
  - `PYTHONPATH=src pytest -q`
- DoD:
  - `PYTHONPATH=src pytest -q` 全绿。
  - R29.1 的 C1/C2/C3 提交齐全。
  - `PROGRESS` 记录决策/证据/回滚点/提交哈希。
- Commits:
  - C1: `b748e77`
  - C2: `d449aae`
  - C3: `<pending>`
- Status: DONE
