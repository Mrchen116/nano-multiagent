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
  - 在 `src/personal_assistant/main.py` 引入 `.gateway-state.json` 运行态文件，按配置目录记录 `pid/config_path/health_url/log_path`。
  - 新增 `stop_gateway(config_path=...)`：读取同一状态文件并区分 `STOPPED` / `NOT RUNNING` / `STALE` 三类反馈。
- Rationale:
  - 这样用户只需重复提供同一 `--config`，不用关心 pid；同时可把“无状态/坏 pid”都收敛为清晰可执行反馈。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_main.py tests/e2e/test_personal_assistant_main_e2e.py`
  - Entry: `main(["stop", "--config", ...])` 已输出 stop 反馈；后台启动会落 `.gateway-state.json`。
- Rollback:
  - `45fed26`（R1 红测）
- Commits: C1=`45fed26`, C2=`92ab1dd`, C3=<pending>
- Next:
  - 用真实 `python -m personal_assistant.main stop --config ...` 打通 e2e，并补 README/runbook。

### R2 真实 CLI 停止入口与文档
- Context:
  - 需要把 stop 从单测契约推进到真实 CLI/e2e，并同步 README / runbook。
- Decision:
  - 保留原默认 start 语法 `python -m personal_assistant.main --config ...`，并新增显式子命令 `python -m personal_assistant.main stop --config ...`。
  - README / runbook 改写为“默认后台 start + 显式 stop + `--foreground` 仅调试”的真实路径。
- Rationale:
  - 兼顾已有默认启动入口与新的可发现 stop 命令，避免把 stop 做成隐藏 flag 或要求用户手工 kill。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_main.py tests/e2e/test_personal_assistant_main_e2e.py`
  - Entry: 真实 e2e 已验证 background start -> `stop --config` 成功关闭；进程缺失时返回 `STALE`，无状态文件时返回 `NOT RUNNING`。
- Rollback:
  - `92ab1dd`（R1 C2）
- Commits: C1=`3227a53`, C2=<pending>, C3=<pending>
- Next:
  - 提交 R2 实现/文档，并补最终 docs commit。

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
