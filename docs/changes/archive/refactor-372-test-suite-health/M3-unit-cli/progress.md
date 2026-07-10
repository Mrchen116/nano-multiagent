# M3 unit-cli — Progress

## 开工

- 基线：11 failed / 158 passed（`pytest tests/unit -k "cli or sdk_client or managed_server or refactor_boundaries" -m "not e2e"`）
- 影响文件：`tests/unit/test_sdk_client.py`、`tests/unit/test_cli_managed_server.py`、`tests/unit/test_cli_refactor_boundaries.py`、`tests/unit/test_cli_main.py`（拆分）
- 不碰：tests/unit 其余文件、contract/integration/im_service/src

---

## R1 — fix test_sdk_client.py

- 删除调用已不存在 `send_message` 的 `test_send_message_posts_http_payload_with_auth_and_request_id`
- 结果：13 tests, 0 failed
- commit: feat(refactor-372-M3/R1)

## R2 — fix test_cli_managed_server.py

- 从 6 处 `ManagedServerConfig()` 调用移除 `token="test-token"`
- 删除 `assert captured_env["NANO_MULTIAGENT_API_TOKEN"]`（managed_server.py 不注入 token）
- 结果：7 tests, 0 failed
- commit: feat(refactor-372-M3/R2)

## R3 — fix test_cli_refactor_boundaries.py

- 移除 `--token test-token` CLI 参数（commands.py 已无此参数）
- 移除 `token="test-token"` from `build_release_playbook_report()` 调用
- `_fake_build_reader` 签名加 `**_kwargs`，returned lambda 加 `**kw`（新增 `on_idle` 参数）
- 结果：10 tests, 0 failed
- commit: feat(refactor-372-M3/R3)

## R4 — 拆 test_cli_main.py (2754行)

- 拆分为 7 个文件（按行为聚类）：
  - `test_cli_structure.py`：5 tests — CLI 架构/模块位置校验
  - `test_cli_repl_input.py`：18 tests — REPL 输入引擎（键盘/光标/历史/CJK/paste）
  - `test_cli_repl_commands.py`：19 tests — REPL 命令（/help /new /use /session /tools /compact /history /exit）
  - `test_cli_repl_async.py`：16 tests — async event 渲染（过滤/去重/工具执行流/failed run）
  - `test_cli_mode.py`：20 tests — 运行模式 lifecycle + llm-config 子命令
  - `test_cli_text_sse.py`：8 tests — text 模式 + SSE REPL 路径
  - `_cli_async_stubs.py`：async stub helper（非测试文件，压缩 test_cli_repl_async.py 行数）
- 删除原 `test_cli_main.py`
- 最终：168 tests（R1-R4 全程用例数/通过数一致）
- commit: refactor(refactor-372-M3/R4)
