# feat-386-M1: backup-on-write

## 目标

在 `save_local_config` 写盘前插入"主配置专属"的备份步骤，新增私有 helper `_backup_existing_config`，在 `tests/unit/personal_assistant/test_local_store.py` 补单测。

## 退出标准

**[worker]**
- `pytest tests/unit/personal_assistant/test_local_store.py` 全绿
- 新增单测覆盖：主配置备份内容一致 / 留存裁剪到 30 / 备份失败 raise 且 dest 不变 / dest 不存在跳过备份 / 非默认路径（worktree 副本）不备份 / 内容相同跳过备份 / 同时刻两次备份不互相覆盖
- `pytest -m "not e2e"` 无回归

**[reviewer]**
- 主配置写盘前产生内容等于旧版的时间戳备份、可恢复
- 保留最近 30 份且超出删最旧
- 备份失败则保存失败报错且原文件不变
- 首次写入与 worktree 副本不产生备份

## 测试策略

改动范围：`local_store.py` 的一个函数 + 一个私有 helper，无 HTTP 入口、无 CLI 路径变化。测试层选择：

- 单元测试（现有文件 `test_local_store.py`，追加用例）
- 用 monkeypatch 把 `default_local_config_path` 指向 `tmp_path` 下的路径，使测试可离线、幂等
- 浏览器/E2E：N/A（纯文件 IO helper，无 UI 影响）

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 写失败测试（Red） | DONE |
| R2 | 实现 `_backup_existing_config` + 接入 `save_local_config`（Green） | DONE |
| R3 | 文档 | DONE |
