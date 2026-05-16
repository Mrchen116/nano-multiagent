# M4: fix-tool-registry-injection — Progress

> Milestone: bugfix-355-M4
> Started: 2026-05-16

## 开工报信

已读 regression.md、design.md M4 行、Anchor C，理解范围：
- blocking #1: runtime._build_hook_context 注入 tool_registry 到 metadata（第884行已注入 permission_broker，类比注入 tool_registry）
- major #2: dangerous_paths.py DANGEROUS_FILES 匹配改为 startswith 前缀规则
- minor #3: design.md Runbook 路径修正（~/.nano-assistant/config.yaml → workspace .nanocode/config.yaml）

---
