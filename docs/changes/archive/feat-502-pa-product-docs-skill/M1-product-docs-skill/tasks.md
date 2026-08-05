# feat-502-M1: product-docs-skill

## Roadpoints

- R1 Red: 扩展现有 builtin skill bootstrap 测试，覆盖完整替换、非内置保留、切换失败恢复/继续，以及产品手册的发现与无 `read` 可达性。
- R2 Green: 实现逐 skill 事务式刷新，新增单文件 `nanoassistant-docs` 产品手册，更新 Gateway 启动日志语义。
- R3 Verify: 运行聚焦测试、skill 校验、ruff、docs-check、影响面测试与隔离真栈旅程，完成 milestone 证据。
- R4 Review revision: 用户在 PR review 中撤销“无 `read` 可达”要求；按 OpenAI 渐进加载方式把单文件手册改为精简入口 + 一层专题 references，同步 Gateway 契约、设计、测试与验收证据。

## 测试策略

- 保护的回归风险与可观察 seam: `install_builtin_skills()` 公开入口刷新后的目标目录、references、返回映射与日志；Gateway capabilities / Kernel `skill_view` 对安装后入口的可见性；默认 Agent 的 `read` 依赖与入口到全部单层 references 的直接路由。
- 已有保护与处置: `tests/unit/personal_assistant/test_builtin_skill_bootstrap.py` 中缺失安装、同名不覆盖、package data、Lark bundle、capabilities/prompt 测试改为 keep 或 rewrite-merge；`tests/unit/personal_assistant/test_gateway_pid_lifecycle.py` 启动顺序 keep。
- 落层/目录/marker: `tests/unit/personal_assistant/`，marker: 无；文件系统刷新、capability 投影与 `skill_view` 读取在该层已能暴露对应失败原因。真 LLM 触发另作一次性真栈验收。
- 文件归属: 扩展 `tests/unit/personal_assistant/test_builtin_skill_bootstrap.py`，同一失败原因已由该文件负责，不新建 milestone 命名的测试文件。
- 可选依赖 importorskip: 无。
- 本 milestone 产生的一次性验收证据(收尾删除,不进套件): 隔离 HOME 的真 IM/Gateway/真 LLM 对话轨迹与脱敏结论，摘要记入 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| 缺失内置 skill 被安装 | `test_install_builtin_skills_copies_missing_skill` | keep | 目标态仍必须覆盖新安装 | 聚焦 pytest |
| 已有同名目录 | `test_install_builtin_skills_does_not_overwrite_user_skill` | rewrite-merge | 旧前提被 spec 推翻，改为完整替换与旧文件清除 | 聚焦 pytest |
| Lark bundle 完整且可发现 | `test_install_builtin_skills_installs_the_complete_lark_bundle` / capability preview test | rewrite-merge | 保留 Lark 风险，在同一链路加入产品手册和 default-on 断言 | 聚焦 pytest |
| Gateway runtime build 前刷新 | `test_run_gateway_installs_builtin_skills_before_building_runtime` | keep | 启动 owner 与顺序不变 | 聚焦 pytest |
