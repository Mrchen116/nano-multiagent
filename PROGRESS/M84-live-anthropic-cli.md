# PROGRESS (Milestone: M84)

- Title: 多产品架构重构十一期：live anthropic 链路修复与真实 CLI 验收
- Goal: 修复 live anthropic provider 请求与 managed coding_cli 实链路在本地代理下的失败问题，使真实 send-message、live proxy e2e、live managed CLI e2e 一致恢复，并把实跑证据落盘。
- Exit Criteria:
  - `tests/e2e/test_anthropic_generate_e2e.py` 与 `tests/e2e/test_cli_managed_live_agent_e2e.py` 在启用 live 环境变量后通过。
  - 真实 `coding_cli` managed 模式 smoke 可完成至少一轮简单消息。
  - `TASKS/PROGRESS` 记录根因、修复、回滚点与 live 命令证据。
- Test command: `python3 -m pytest -q`
- Branch: `milestone/M84`

> 本文件记录 M84 的关键决策、证据、回滚点与 C1/C2/C3 哈希；`LOGBOOK.md` 只记录可复用经验。

## Baseline
- Context:
  - 按执行技能先在指定 worktree/branch 读取 `LOGBOOK.md`、`COMMENTING_GUIDE.md`、Milestone 上下文并执行 live 目标最小红灯。
  - M84 起点已知现象：`create-session` / `llm-config get` 成功，但 live anthropic send-message 失败；controller 明确要求在 DONE 前补 full sweep（包含默认 skip 的 live tests）。
- Decision:
  - 先以用户指定的两条 live e2e 作为 baseline，再顺着失败点定位到底是代理不可用、model 选择错误、请求体不兼容，还是 managed CLI 输出/运行时路径问题。
- Evidence:
  - Tests:
    - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py::test_anthropic_non_stream_generate_against_local_proxy` -> `FAILED`（`400 Bad Request` at `http://127.0.0.1:4000/v1/messages`）
    - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py::test_cli_managed_mode_can_complete_live_agent_turn` -> `FAILED`（`len(json_lines)==0`）
    - `python3` 直连 `http://127.0.0.1:4000/health` -> `200 {"ok":true}`
  - Entry:
    - 直打代理复核后发现：当前 anthropic live 失败并非代理宕机，而是本项目测试/默认模型选择与本地代理可用模型不匹配；同时 managed REPL 本身输出的是人类可读文本，不是 JSON 行。
- Rollback:
  - 当前为 baseline，无回滚点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - R84.1 固化 anthropic live 兼容模型选择；R84.2 将 managed live 验收收敛到既有单命令 JSON 契约而非破坏 REPL 文本契约。

### R84.1 anthropic live model 选择与代理兼容
- Context:
  - live anthropic e2e 初始稳定报错 `400 Bad Request`，但本地代理 `/health` 正常；进一步直打 `/v1/messages` 发现代理明确拒绝 `claude-3-5-sonnet-20241022`，提示当前 Codex(ChatGPT 账号)通道不支持该模型。
  - 仓内 `可用LLM_API与联调说明.md` 已记录 anthropic `/v1/messages` 的已验证模型实际上是 `codexOAuth:gpt-5.2-codex`。
- Decision:
  - 在 `src/nano_multiagent/core/llm/model_registry.py` 为 `provider=anthropic` 增加并默认切换到 `codexOAuth:gpt-5.2-codex`，同时保留旧的 Claude metadata 项，避免显式老配置立即失效。
  - live anthropic e2e 改用已验证的 codex 模型名，确保测试和本地代理实际能力一致。
- Rationale:
  - 问题根因是“anthropic 协议 + 本地代理账号可用模型”错位，而不是代理挂掉或 messages payload 结构错。优先收敛到真实可用模型名，改动最小且最贴近现场。
- Evidence:
  - Tests:
    - `python3 -m pytest -q tests/unit/test_llm_model_registry.py tests/integration/test_anthropic_generation_integration.py` -> `5 passed`
    - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py::test_anthropic_non_stream_generate_against_local_proxy` -> `1 passed`
  - Entry:
    - 直打 `http://127.0.0.1:4000/v1/messages`：
      - `model=claude-3-5-sonnet-20241022` -> `400`，响应含 `model is not supported when using Codex with a ChatGPT account`
      - `model=codexOAuth:gpt-5.2-codex` -> `200`，返回 `content[0].text = "pong"`
- Rollback:
  - 若需重做，回退到 `0c32df6`（R84.1 C1 红测基线）。
- Commits: C1=`0c32df6`, C2=`637de12`, C3=`TBD`
- Next:
  - R84.2 收口 managed live 验收入口，并补全 full sweep。

### R84.2 managed coding_cli live 验收到真实单命令链路
- Context:
  - managed live e2e 初始失败不是 managed API 无法完成对话，而是测试把 REPL 当作 JSON 行通道；实际 REPL 长期契约是人类可读文本，仓内大量 unit/integration 都显式断言 REPL 不输出 JSON。
  - 真实 managed REPL 现场复测已能完成 turn，只是输出形态为 `Started new session ... / Assistant: / State: ...`，并非 JSONL。
- Decision:
  - 将 live managed e2e 收口到已有稳定契约：`create-session` + `send-message` 单命令 JSON 输出。
  - 在测试中显式以 `--llm-provider anthropic --llm-model codexOAuth:gpt-5.2-codex --llm-base-url http://127.0.0.1:4000` 启动 managed local API，确保真正覆盖 anthropic 实链路。
- Rationale:
  - 这样既能验证 managed 本地 API + anthropic proxy 的真实成功闭环，又不会回流破坏已有 REPL 文本契约和大量历史门禁。
- Evidence:
  - Tests:
    - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py::test_cli_managed_mode_can_complete_live_agent_turn` -> `1 passed`
  - Entry:
    - 直接调用 `run_cli([... create-session ...])` + `run_cli([... send-message ...])` 可返回 JSON，并在真实代理下得到 assistant `pong`。
- Rollback:
  - 若需重做，回退到 `0c32df6`（同一 Red 基线提交）。
- Commits: C1=`0c32df6`, C2=`637de12`, C3=`TBD`
- Next:
  - R84.3 补 full sweep、managed 实跑命令证据、兼容回归与 main 集成。

### R84.3 full sweep / live evidence / main 集成
- Context:
  - controller 要求 DONE 前必须做 full sweep（含默认 skip 的 live tests）。首次全量 `python3 -m pytest -q` 暴露多处与本 Milestone 无直接关系但已存在于当前分支的脆弱/过期断言：旧 shim 私有导出、核心 dataclass 字段、CLI/task/bash 返回形态、测试导入目标等。
- Decision:
  - 修复 `server/routes/session.py` shim，显式 re-export `_CONTEXT_BUDGET_MAX_TOKENS` 与 `_to_message_response`。
  - 将 stale tests 收敛到当前 canonical 契约：`TurnResult/LLMGenerateResponse` 包含 `usage`；runtime monkeypatch 目标改到 `nano_multiagent.core.session.manager`；CLI retry/task/bash/platform shim 断言改成当前真实输出/导出语义。
  - 记录真实 managed smoke 三条命令：`create-session`、`llm-config get`、`send-message`。
- Rationale:
  - M84 不能在“live 目标通过但 full sweep 仍红”的状态下宣称 DONE；这些修复属于当前分支可见兼容债，顺手收口后才能满足 controller 明示的新纪律。
- Evidence:
  - Tests:
    - `python3 -m pytest -q` -> `593 passed, 4 skipped`
    - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py` -> `1 passed`
    - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py` -> `1 passed`
  - Entry:
    - 真实 managed smoke（端口 `56146`）：
      - `PYTHONPATH="/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M84/src:$PYTHONPATH" python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:56146 --token test-token --llm-provider anthropic --llm-model codexOAuth:gpt-5.2-codex --llm-base-url http://127.0.0.1:4000 create-session --title m84-live-smoke`
        -> `{"session_id": "sess_98bed07d5c553303", "status": "active", ...}`
      - `PYTHONPATH="/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M84/src:$PYTHONPATH" python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:56146 --token test-token --llm-provider anthropic --llm-model codexOAuth:gpt-5.2-codex --llm-base-url http://127.0.0.1:4000 llm-config get`
        -> `{"provider": "anthropic", "model": "codexOAuth:gpt-5.2-codex", "base_url": "http://127.0.0.1:4000", ...}`
      - `PYTHONPATH="/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M84/src:$PYTHONPATH" python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:56146 --token test-token --llm-provider anthropic --llm-model codexOAuth:gpt-5.2-codex --llm-base-url http://127.0.0.1:4000 send-message --session-id sess_98bed07d5c553303 --text "reply one word: pong"`
        -> `{"session_id": "sess_98bed07d5c553303", "message": {"role": "assistant", "content": "pong"}, ...}`
- Rollback:
  - 若需回退到 live 修复前稳定点，可回退到 `637de12`（anthropic live 绿点）；若仅需撤销全量兼容扫尾，可回退到本 Roadpoint 的 C1。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - rebase main、merge milestone/M84、push、更新 `data/dev-tasks.json`、删除 worktree。
