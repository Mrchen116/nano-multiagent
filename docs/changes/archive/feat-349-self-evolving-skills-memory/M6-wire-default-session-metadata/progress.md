# feat-349-M6 — Progress

## R1 — SessionService 接收 + merge default_session_metadata

- Context: bootstrap 把 workspace config.yaml 的 `self_evolution` 写入 `ResolvedProductConfig.default_session_metadata`，但 `SessionService` 构造时不接收，`create_session` 时不 merge —— bootstrap 字段死接线
- Decision:
  1. `SessionService.__init__` 加 `default_session_metadata: Mapping[str, Any] | None = None` 参数，存 `self._default_session_metadata`（dict）
  2. `create_session` 做 shallow merge：`merged = dict(default); merged.update(caller_metadata or {})`；空 dict 传 None 保持原语义
- Rationale: shallow merge —— 不知道每个子段 schema，深 merge 风险更高；caller 想细粒度覆盖应自行 resolve
- Evidence:
  - Tests: 见 R3
  - Entry: N/A
- Rollback: e17b58f1 (unit/feat-349 HEAD)
- Commits: C1=<pending>
- Next: R2 接线 app.py

## R2 — app.py 注入 resolved_product.default_session_metadata

- Context: `create_app` 在 `if product_profile is not None` 块里跑 bootstrap，但 `session_service = SessionService(...)` 没用 bootstrap 产物
- Decision:
  1. 在 if 块外先声明 `resolved_default_metadata: dict | None = None`
  2. if 块内赋值 `resolved_default_metadata = resolved_product.default_session_metadata`
  3. `SessionService(..., default_session_metadata=resolved_default_metadata)`
- Rationale: 不破坏 `product_profile=None` 的早期/测试路径
- Evidence:
  - Tests: 见 R3
- Rollback: R1 commit
- Commits: C1=<pending>, C2=<pending>
- Next: R3 单测 + E2E

## R3 — 单测 + E2E 验证

- Context: 单测保证 wire 正确；E2E 用真实 CLI 入口产物（managed server + HTTP create session）确认文件真落盘
- Decision:
  1. `tests/unit/test_session_service.py` 新增三测：
     - `test_create_session_inherits_default_metadata_when_caller_passes_none`：default 流到 session.metadata
     - `test_create_session_caller_metadata_overrides_default_top_level_key`：caller 顶层 key 覆盖，未指定 key 保留 default
     - `test_create_session_no_default_no_caller_metadata_yields_no_self_evolution`：无 default 无 caller → 不泄漏 self_evolution
  2. E2E：
     - workspace `/tmp/feat349-m6-e2e`，`.nanocode/config.yaml` 写 `skill_nudge_interval: 1`
     - 在该 cwd 启 `coding_cli.kernel_app:app` 监听 :8993
     - POST /v1/sessions（无 metadata 字段）→ 响应 metadata.self_evolution.skill_nudge_interval == 1（来自 workspace config，而非 platform 默认 10）
     - 发教学性消息 "remember debug-flaky-tests skill ..." → SSE 收到 `self_evolution_review` 含 `skill_manage` 调用
     - 检查 `<workspace>/.nanocode/skills/debug-flaky-tests/SKILL.md` 真出现，内容含 3 步流程
- Rationale: workspace config → bootstrap → ResolvedProductConfig → SessionService → session.metadata → hook → fork → skill_manage(create) → 文件落盘 整条链路端到端验证
- Evidence:
  - Tests: `pytest tests/unit/test_session_service.py tests/unit/test_session_service_with_profile.py tests/unit/test_platform_bootstrap.py -q` → 20 passed
  - Entry: HTTP API + SSE stream（真实 LC managed kernel）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: |
      启动: `cd /tmp/feat349-m6-e2e && PYTHONPATH=.../src python3 -m uvicorn coding_cli.kernel_app:app --host 127.0.0.1 --port 8993`
      创 session 响应 (no metadata in request):
        {
          "session_id": "sess_8b1de0efa0800539",
          "metadata": {
            "workspace_root": "/private/tmp/feat349-m6-e2e",
            "self_evolution": {
              "enabled": true, "skill_creation": true, "memory_curation": true,
              "skill_nudge_interval": 1, "memory_nudge_interval": 1
            }
          }
        }
      → 证明 default_session_metadata 流到 session：interval=1（来自 workspace config），而非 platform 默认 10
      发消息 "remember debug-flaky-tests skill (3 steps)..."
      SSE event:
        event: self_evolution_review
        data: {"reviewed_skills":true,"reviewed_memory":true,
               "tool_names_called":["memory","skill_manage","skill_manage","memory","memory","skill_manage"],
               "completed":true}
      文件落盘:
        $ find /tmp/feat349-m6-e2e -type f ! -name config.yaml ! -path "*/.nano/*"
        /tmp/feat349-m6-e2e/.nanocode/skills/debug-flaky-tests/SKILL.md
        $ cat .../SKILL.md
          ---
          name: debug-flaky-tests
          description: Steps to debug flaky tests
          ---
          # Debug Flaky Tests
          Whenever debugging a flaky test, follow these 3 steps:
          1. Run it 10 times to confirm flakiness
          2. Capture both stdout and stderr
          3. Check for time/order dependencies
      LLM 调用证据 (LLM_PROXY log):
        skill_manage 调用 input 包含 {"action":"create","name":"debug-flaky-tests",...}
      → AC-1 ("自动出现 skill 文件") 真通过
  - Visual/Interaction: N/A
- Rollback: R2 commit
- Commits: C3=<pending>
- Next: 合并到 unit/feat-349
