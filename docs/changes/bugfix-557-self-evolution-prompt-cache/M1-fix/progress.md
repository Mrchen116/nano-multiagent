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
