# M1-fix tasks

Lite 模式单 milestone。范围：fix.md 根因里点名的两处源码 + 两层回归测试。

- [x] R1: `src/agent/platform/hooks/builtins/auto_mode_gate.py` `SAFE_TOOL_ALLOWLIST` 追加 `"memory"`，inline 注释引用 bugfix-368 + 解释 safe 边界
- [x] R2: `tests/unit/test_auto_mode_gate.py::TestSafeToolAllowlist::test_memory_safe` 新增——issue #31 直接回归
- [x] R3: `tests/contract/test_tool_gate_coverage.py` 新增——builtin gate coverage 强契约
- [x] R4: 跑 `tests/unit/test_auto_mode_gate.py` + `tests/unit/test_auto_mode_gate_dispatch.py` + `tests/unit/test_memory_tool.py` + `tests/contract/test_tool_gate_coverage.py` 全绿
- [x] R5: 回填 `fix.md` 的"修复"+"验证"两段
