# feat-386-M1 progress

## 开工信

已读 design.md、接口与数据流、现有 `local_store.py`（`save_local_config` 第 295-412 行）、现有单测骨架。
范围 = `src/personal_assistant/config/local_store.py`（`save_local_config` + 新增 `_backup_existing_config`）+ `tests/unit/personal_assistant/test_local_store.py`。
基线：`pytest tests/unit/personal_assistant/test_local_store.py` → 32 passed。

---

### R1 — 写失败测试（Red）

- Context: 七条 backup 场景需被覆盖。`_make_minimal_config` 初版与 `main_cfg` 路径同为 `tmp_path/config.yaml`，导致"首次写盘"用例前置条件断言失败，修改 helper 改用 `tmp_path/_src/bootstrap.yaml` 隔离。
- Decision: 所有用例通过 `monkeypatch.setattr(ls, "default_local_config_path", lambda: main_cfg.resolve())` 把主配置路由到 `tmp_path` 下，保持幂等无真实 home 副作用。
- Rationale: 符合现有 test_local_store.py 的 `tmp_path + monkeypatch home` 风格；私有 helper 通过 `save_local_config` 集成路径间接测试，不暴露内部实现。
- Evidence:
  - Tests: `pytest tests/unit/personal_assistant/test_local_store.py` → 32 passed (Red: 1 failed on first new case)
  - Entry: N/A（纯文件 IO 单元测试）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: C1 = 39cf68a1
- Commits: C1=39cf68a1

### R2 — 实现 _backup_existing_config + 接入 save_local_config（Green）

- Context: 需在 `save_local_config` 写盘前调用 `_backup_existing_config(dest, new_text)`；helper 判定主配置路径、内容差异、备份命名（时间戳含微秒 + 碰撞序号）、留存裁剪 30 份；备份失败 raise 不吞。
- Decision: 
  - `datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S_%f")` 含微秒精度，极低碰撞概率；碰撞时追加 `_1`、`_2` 序号。
  - `_backup_existing_config` 接受 `(dest, new_text)` 而非仅 `dest`，内容相同时在 helper 内部直接 return 避免不必要的 `shutil.copy2`。
  - `save_local_config` 先序列化 `new_text`，再调备份，再 `dest.write_text(new_text)` — 备份失败时 dest 不变。
- Rationale: 满足 D4 fail-closed 语义；同秒碰撞去重逻辑简单可测；留存裁剪按文件名自然排序（时间戳单调），删最旧正确。
- Evidence:
  - Tests: `pytest tests/unit/personal_assistant/test_local_store.py` → 39 passed (全绿)；`pytest -m "not e2e"` → worktree 内 2407 passed（1 pre-existing failure 与本 unit 无关）
  - Entry: 纯文件 IO，无 HTTP/CLI 入口；单元测试已从 `save_local_config` 真实入口路径验证端到端备份行为
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: C2 = 47a0ef7c
- Commits: C1=39cf68a1, C2=47a0ef7c
- Next: R3 文档
