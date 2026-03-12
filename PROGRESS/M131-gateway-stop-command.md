# M131 Progress - Gateway 后台关闭命令

## Plan
- 先补 stop CLI 契约与运行态元数据测试，收敛“如何定位当前后台 Gateway”。
- 再用最小实现打通默认后台 start/stop 主链路，并补 README / operator runbook。
- 文档只写真实默认路径：`python -m personal_assistant.main --config ...` 启动，配套显式 stop 命令关闭；`--foreground` 仅作调试路径。

### R1 停止契约与状态文件
- Context:
  - 默认入口已经后台启动 Gateway，但缺少面向用户的 stop 命令；现有 e2e 靠直接 kill pid 清理。
  - stop 需要基于同一配置路径/同一运行态元数据定位进程，而不是要求用户记 pid。
- Decision:
  - 待实现。
- Rationale:
  - 待实现。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_main.py tests/e2e/test_personal_assistant_main_e2e.py`
  - Entry: baseline 24 passed，当前尚无 stop 用户入口。
- Rollback:
  - 计划提交之后的首个稳定点。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
  - 写 R1 Red 测试，先让 stop 契约失败。

### R2 真实 CLI 停止入口与文档
- Context:
  - 需要把 stop 从单测契约推进到真实 CLI/e2e，并同步 README / runbook。
- Decision:
  - 待实现。
- Rationale:
  - 待实现。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_main.py tests/e2e/test_personal_assistant_main_e2e.py`
  - Entry: 待补真实 start/stop e2e 证据。
- Rollback:
  - R1 C3。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
  - 待 R1 完成后补 e2e 和文档。
