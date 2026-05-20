# M3 unit-cli — Progress

## 开工

- 基线：11 failed / 158 passed（`pytest tests/unit -k "cli or sdk_client or managed_server or refactor_boundaries" -m "not e2e"`）
- 影响文件：`tests/unit/test_sdk_client.py`、`tests/unit/test_cli_managed_server.py`、`tests/unit/test_cli_refactor_boundaries.py`、`tests/unit/test_cli_main.py`（拆分）
- 不碰：tests/unit 其余文件、contract/integration/im_service/src

---
