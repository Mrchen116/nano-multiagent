# M1-fix — Progress

## Done

- Creator-owner 从 codex/bugfix-557 f15feb87d 创建 codex/bugfix-557-m1 独立 worktree。
- 冻结技能目录，加入仅技能扩充的 SDK deferred refresh；聊天与后台 runtime admission 均接入自动来源判断。
- 独立 skill sync lock 解决真实自动 PATCH/config callback 的互锁，pending 来源只覆盖在途且匹配的纯技能更新，失败后清除。
- 回填 fix 与 kernel/gateway current specs。

## Notes

- 只冻结技能目录，与既有 memory snapshot 同属会话内存；进程重启/载荷重建可重新发现，未新增持久 schema。
- 受影响测试保留已有 config sync 并发创建及 Feishu 并发保护，扩展现有 SDK runtime integration 与自进化 critical path；没有平行新建流水号测试。
- E2E harness 补齐当前 API 必填 conversation type；当前 direct conversation 已幂等，使用产品 fork 创建独立新会话。手动轮次用唯一响应标记排除 WS replay 旧完成事件。

## Validation

使用主仓 `.venv`、milestone worktree src，真实服务由现有 stub_llm_stack fixture 调用 e2e-up/e2e-down，独立高位端口、配置、workspace、node identity 和数据库，未访问生产。

- **红证据**：临时恢复 src 为 f15feb87d（保留新增测试与 harness 修正），运行 `pytest -q tests/e2e/critical_paths/test_self_evolution_skill_activation_critical_path.py --tb=short`，1 failed / 21.46s。错误为 `same_prompt == initial_prompt`，唯一新增块是 deterministic-review-workflow 的 available_skills 目录。之后完整恢复修复源码。
- **绿证据**：同一命令，1 passed / 21.05s。真实后台 review 调用 skill_manage 保存成功并启用；原会话请求 system 字节相同、timeline 无配置 boundary；新 fork 请求出现技能目录；手动取消与再启用目录立即更新，timeline 各增加一条 boundary。
- **SDK/回归**：`pytest -q tests/integration/test_self_evolution_gateway_skill_sync.py tests/integration/test_session_run_coordinator_real_kernel.py tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/unit/agent/test_runtime_skill_resolution_same_source.py tests/integration/test_kernel_idle_admission.py tests/contract/ --tb=short`，200 passed / 22.68s。SDK 参数化覆盖 explicit-empty/default-discovery、文件写入后冻结、新会话、压缩刷新、手动取消/启用、拒绝混入 model 变更。
- 追加 config-sync 参数化验证失败 PATCH 后手动同步不继承 automatic 来源，29 passed / 1.70s；Ruff check（src 与所有修改测试/fixture）通过。
- Limit：使用受控 LLM，证明实际 HTTP 请求前缀不变，不承诺模型供应商的实际缓存命中率；重启可刷新内存快照。

## Review correction — first config-operation publication

- Pre-fix: `650464f74`; independent review confirmed `_resume_config_operation` directly published the candidate before `_publish_agent_config` could attach automatic skill provenance.
- Correction: route that real `agent.config.apply` publication through the same config publish owner. Durable config is already equal, so it is not written twice; automatic provenance is attached to the first observable snapshot.
- Regression: `test_config_apply_admission_before_automatic_skill_patch_response` executes the real apply callback inside the automatic PATCH transport, holds its response with an event, and dispatches a second real Kernel turn while the request remains in flight. Pre-fix: 1 failed / 2.64s, final model system gained the skill catalog. Post-fix: system unchanged, no pending boundary, first published snapshot has automatic provenance.
- Narrow validation: `pytest -q tests/integration/test_session_run_coordinator_real_kernel.py tests/unit/personal_assistant/test_gateway_config_operations.py tests/unit/personal_assistant/test_gateway_im_config_sync.py --tb=short` — 54 passed / 6.37s, including config operation crash recovery and failed PATCH/manual sync. Ruff and diff checks pass. No repeated full-suite run.
