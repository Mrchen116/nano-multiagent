# feat-394 测试清理执行清单

判据全部引用 `docs/TESTING_GUIDE.md`。每条均可直接执行，worker 照单操作，无需再判断。

---

## A. 删除（一次性证据/迁移，无长期回归价值）

> 判据：§6「半年后还该每次 CI 跑吗？否→删」

### A1. `tests/unit/personal_assistant/test_m9e_dead_code_removal.py` — 整文件删除（保留部分断言搬迁至 §E）

文件 docstring 明确自述「M9-E: full dead-code rip-out」。各断言逐一判定：

| 断言函数 | 判定 | 理由 |
|----------|------|------|
| `TestMainDeadCodeRemoval::test_parse_cron_enabled_function_deleted` | **删** | 断言函数已不存在。死代码删除即永远绿，无回归价值（§6） |
| `TestMainDeadCodeRemoval::test_parse_heartbeat_returns_4_tuple_no_enabled` | **搬迁→§E4** | 4-tuple 签名是持久行为防回归 |
| `TestMainDeadCodeRemoval::test_parse_heartbeat_empty_returns_4_none` | **搬迁→§E4** | 同上 |
| `TestMainDeadCodeRemoval::test_parse_heartbeat_non_dict_returns_4_none` | **搬迁→§E4** | 同上 |
| `TestAgentProfileNoCronJson::test_agent_profile_has_no_cron_json_field` | **删** | 断言字段不存在，无回归价值 |
| `TestAgentProfileNoCronJson::test_agent_profile_still_has_heartbeat_json_field` | **搬迁→§E3** | 防回归 heartbeat_json 不被误删 |
| `TestRepositoryNoCronJson::test_update_profile_signature_no_cron_json` | **删** | 参数不存在，无回归价值 |
| `TestRepositoryNoCronJson::test_update_profile_signature_keeps_heartbeat_json` | **搬迁→§E3** | 防回归 heartbeat_json 参数不被误删 |
| `TestConfigServiceNoCronJson::test_update_profile_signature_no_cron_json` | **删** | 同上 |
| `TestConfigServiceNoCronJson::test_update_profile_signature_keeps_heartbeat_json` | **搬迁→§E3** | 同上 |
| `TestRouteModelsNoCronJson::test_update_request_has_no_cron_json_field` | **删** | 字段不存在，无回归价值 |
| `TestRouteModelsNoCronJson::test_update_request_still_has_heartbeat_json_field` | **搬迁→§E3** | 防回归 |
| `TestRouteModelsNoCronJson::test_agent_config_response_has_no_cron_json` | **删** | 字段不存在，无回归价值 |
| `TestRouteModelsNoCronJson::test_agent_config_response_still_has_heartbeat_json` | **搬迁→§E3** | 防回归 |
| `TestEnableRoundTripAfterRipOut::test_sync_enable_via_features_not_cron_json` | **搬迁→§E1** | 「features 是 cron enable 唯一真源」持久行为防回归 |
| `TestEnableRoundTripAfterRipOut::test_sync_heartbeat_enable_via_features` | **搬迁→§E1** | 同上 |
| `TestEnableRoundTripAfterRipOut::test_heartbeat_cadence_still_parsed_from_heartbeat_json` | **搬迁→§E1** | heartbeat cadence 持久行为 |

操作：`git rm tests/unit/personal_assistant/test_m9e_dead_code_removal.py`（搬迁的 9 个断言见 §E）。

---

### A2. `tests/unit/personal_assistant/test_m9b_cron_json_retire.py` — 整文件删除（保留部分断言搬迁至 §E）

文件 docstring 自述「These tests are RED until M9-B lands」，是迁移期红测。各断言判定：

**Part A（`TestCoerceConfigDictsCronJsonRetire`）：**

| 断言函数 | 判定 | 理由 |
|----------|------|------|
| `test_cron_dict_does_not_produce_cron_json` | **搬迁→§E1** | 「`_coerce_config_dicts` 不再写 cron_json」持久防回归 |
| `test_cron_block_is_ignored_features_is_sole_source` | **搬迁→§E1** | 「cron 块不回写 features」持久防回归 |
| `test_features_field_is_cron_enable_source` | **删** | 与 `test_m9_agent_config_features.py::test_cron_enabled_true_from_features` 语义完全重复（§4 跨层重复） |
| `test_heartbeat_dict_still_produces_heartbeat_json` | **搬迁→§E1** | heartbeat_json cadence 写入持久行为 |
| `test_heartbeat_block_does_not_touch_features` | **搬迁→§E1** | 「heartbeat 块不回写 features」持久防回归 |
| `test_features_field_is_heartbeat_enable_source` | **删** | 与 `test_m9_agent_config_features.py::test_heartbeat_enabled_true_from_features` 重复 |

**Part B（`TestConfigSyncNotifierReadsFeaturesNotCronJson`）：**

| 断言函数 | 判定 | 理由 |
|----------|------|------|
| `test_cron_enabled_from_features_when_features_present` | **搬迁→§E2** | 「gateway 从 features 读 cron_scheduling」持久防回归 |
| `test_cron_disabled_when_features_cron_scheduling_false` | **搬迁→§E2** | 同上 |
| `test_cron_disabled_when_features_absent` | **搬迁→§E2** | 同上 |
| `test_cron_disabled_even_when_cron_json_says_enabled` | **搬迁→§E2** | 「cron_json 不覆盖 features」关键防回归 |
| `test_heartbeat_enabled_from_features` | **删** | 与 `test_m9_agent_config_features.py::test_heartbeat_enabled_true_from_features` 重复 |
| `test_heartbeat_cadence_still_from_heartbeat_json` | **搬迁→§E2** | heartbeat cadence 持久行为（合并 §E1 同义断言，只保留一个） |

操作：`git rm tests/unit/personal_assistant/test_m9b_cron_json_retire.py`（搬迁 10 个断言见 §E，删 3 个重复断言）。

---

### A3. 单函数删除：`test_heartbeat_m1_abc.py::test_polling_runner_has_trim_silent_tick_method`（L189-195）

断言 `hasattr(runner, 'trim_silent_tick')`，测「方法存在」而非行为——改内部即变红（§1 负债）。删除该单个函数，其余保留。

---

## B. 改名（流水号→行为名）

> 判据：§3「MUST NOT 用流水号：`test_m9*` 等」

### B1. `tests/unit/personal_assistant/test_heartbeat_m1_abc.py` → `tests/unit/personal_assistant/test_heartbeat_session_binding.py`

- 当前内容：A 部分（tick-time 查询 canonical session）+ B 部分（transcript 修剪）+ C 部分（heartbeat_json IM 落库）
- C 部分（5 个函数，L258-452）搬入 `tests/im_service/unit/test_gateway_handler.py`（见 §C2），从本文件删除
- 剩余 A+B 部分（约 205 行）重命名为 `test_heartbeat_session_binding.py`
- 额外将 `test_heartbeat_cron_vars_injection.py::TestAssemblePromptPreviewFeaturesGate` 里的相关 session binding 测试（`test_heartbeat_scheduler_reuses_stable_heartbeat_session_across_ticks`，见 §D4）并入本文件

### B2. `tests/unit/personal_assistant/test_m9_agent_config_features.py` → `tests/unit/personal_assistant/test_agent_features_config.py`

内容：`AgentWorkspaceConfig.heartbeat_enabled/cron_enabled @property`、YAML 解析映射、sync 路径。改名后接收 §E1/§E2 搬迁断言。

### B3. `tests/unit/personal_assistant/test_m9_feature_model_gate.py` → `tests/unit/personal_assistant/test_prompt_section_feature_flags.py`

内容：`_PA_HEARTBEAT/_PA_CRON/_PA_CRON_ROUTING` 的 `ctx.flags` gate；runtime.py 不再注入 vars；`Kernel.assemble_prompt_preview` 无 heartbeat/cron 参数。

### B4. `tests/unit/personal_assistant/test_m9_r5_tools_default_on.py` → `tests/unit/personal_assistant/test_capabilities_tools_format.py`

内容：`_build_tool_names()` 返回 `{name, description, default_on}` 字典格式；`build_node_capabilities_payload` tools 格式。129 行，无需拆分。

### B5. `src/IM/frontend/src/features/settings/agents/agent-m9c-features-panel.test.tsx` → `agent-features-panel.test.tsx`（同目录）

同时去掉所有 `describe()` 名称里的里程碑前缀：
- `"M9-C: heartbeat controlled by Features list"` → `"heartbeat controlled by Features list"`
- `"M9-C: cron controlled by Features list"` → `"cron controlled by Features list"`
- `"M9-C: tool pills render default_on state"` → `"tool pills render default_on state"`
- `"M9-C: promptPreview reflects features for heartbeat/cron"` → `"promptPreview reflects features for heartbeat/cron"`
- `"M11: cadence input binds to config value, no hardcoded 30m fallback"` → `"cadence input shows actual backend value"`

拆分要求见 §D5。

---

## C. 合并/去重（文件爆炸 / 跨层重复）

> 判据：§2「新测试覆盖旧断言→删旧的」；§4「一个行为只在最低层断言一次」

### C1. 删除 `test_heartbeat_cron_vars_injection.py::TestHeartbeatCronVarsGate`（11 个函数，约 80 行）

`TestHeartbeatCronVarsGate` 中的 11 个函数与改名后的 `test_prompt_section_feature_flags.py`（原 `test_m9_feature_model_gate.py`）中的 `TestHeartbeatFlagsGate` / `TestCronFlagsGate` / `TestCronRoutingFlagsGate` 断言完全重复——同测 `_PA_HEARTBEAT/_PA_CRON/_PA_CRON_ROUTING` 的 `ctx.flags` gate。

操作：删除 `test_heartbeat_cron_vars_injection.py` 中 `TestHeartbeatCronVarsGate` class（L57-143，约 87 行）。保留其余三个 class（`TestInboundPipelineVarsInjection`、`TestRuntimeVarsFromMetadata`、`TestAssemblePromptPreviewFeaturesGate`）。删除后文件约 369 行，满足 400 行软上限，无需拆分。

具体删除的 11 个函数：`test_heartbeat_segment_disabled_by_default_no_flags`、`test_heartbeat_segment_vars_no_longer_enable`、`test_heartbeat_segment_vars_false_still_disabled`、`test_heartbeat_segment_enabled_by_flag`、`test_cron_segment_vars_no_longer_enable`、`test_cron_segment_vars_false_still_disabled`、`test_cron_segment_enabled_by_flag_and_tool`、`test_both_disabled_routing_segment_not_injected`、`test_both_enabled_routing_segment_injected_via_flags`、`test_only_heartbeat_routing_not_injected`、`test_only_cron_routing_not_injected`

### C2. 搬迁 `test_heartbeat_m1_abc.py` C 部分 → `tests/im_service/unit/test_gateway_handler.py`

`test_heartbeat_m1_abc.py` L258-452 的 5 个函数测 IM schema 层（`AgentProfile.heartbeat_json` 字段、`update_profile` 持久化、PATCH route 接受），落层应在 `im_service/unit/`：

- `test_agent_profile_has_heartbeat_json_field`
- `test_agent_profiles_db_has_heartbeat_json_column`
- `test_update_profile_persists_heartbeat_json`
- `test_agents_patch_route_accepts_heartbeat_json`
- `test_config_sync_notifier_includes_heartbeat_json`

操作：在 `tests/im_service/unit/test_gateway_handler.py` 文件末尾追加这 5 个函数（新增块，不要求整文件拆分，历史债豁免）；从 `test_heartbeat_m1_abc.py` 中删除对应内容。

---

## D. 拆分（本 PR 引入的 >400 行文件）

> 判据：§7「单文件软上限 400 行，超了按行为拆分」

### D1. `tests/unit/personal_assistant/test_heartbeat_scheduler.py`（928 行）→ 拆为 3 个文件

| 目标文件 | 源行范围 | 主题 | 预估行数 |
|----------|----------|------|----------|
| `test_heartbeat_scheduler.py`（保留） | L1-319 + L365-398（tick core）| 基础调度：skip/run/interval/at/cron schedule、no-backfill、async tick、rejects-multi-mode | ~330 行 |
| `test_heartbeat_scheduler_gate.py`（新建） | L451-609 | per-agent heartbeat gate：disabled/enabled/mixed/active_hours/busy session | ~170 行 |
| `test_heartbeat_scheduler_config_every.py`（新建） | L617-928 | live_agents_getter；config_every 优先级；tasks per-task rhythm；大间隔触发 | ~320 行 |

搬迁：`test_heartbeat_scheduler_uses_provided_canonical_session`（L400-429）搬入 `test_heartbeat_session_binding.py`（§B1），从原文件删除。

操作步骤：
1. 创建 `test_heartbeat_scheduler_gate.py`，包含 L451-609 + 顶部 imports + `_FakeKernelClient` + `_agent` + `_write_heartbeat` helpers
2. 创建 `test_heartbeat_scheduler_config_every.py`，包含 L617-928 + 必要 helpers
3. 从原文件删除 L400-429（搬入 §B1）、L451-609（搬入步骤 1）、L617-928（搬入步骤 2）

### D2. `tests/unit/personal_assistant/test_cron_scheduler.py`（710 行）→ 拆为 2 个文件

| 目标文件 | 源内容 | 预估行数 |
|----------|--------|----------|
| `test_cron_scheduler.py`（保留） | `TestCronJob`（L56-71）+ `TestCronJobStore`（L79-190）+ `TestCronSchedulerStateStore`（L198-216）+ `TestNonBackfillEverySchedule`（L224-310）+ `TestNonBackfillCronSchedule`（L313-396）+ `TestNonBackfillAtSchedule`（L399-471）| ~420 行 |
| `test_cron_scheduler_tick.py`（新建） | `TestCronSchedulerTick`（L479-710）完整搬过去 | ~240 行 |

操作：新建 `test_cron_scheduler_tick.py`，把 `TestCronSchedulerTick` class（L479-710）连同 imports、`_make_job` helper 剪切过去；原文件删除 L479-710。

### D3. `tests/unit/personal_assistant/test_cron_awareness.py`（525 行）→ 拆为 2 个文件

| 目标文件 | 源内容 | 预估行数 |
|----------|--------|----------|
| `test_cron_runner_awareness.py`（新建，替换原文件名） | helpers + L132-405（isolated session 提交、awareness 注入、delete_after_run、shim 接口契约） | ~380 行 |
| `test_cron_runner_kernel_append.py`（新建） | `_AppendTrackingKernelClient` class + L441-525（awareness via `kernel.append_message`，非 raw JSONL） | ~120 行 |

操作：
1. 将原 `test_cron_awareness.py` 重命名为 `test_cron_runner_awareness.py`（去掉里程碑 M2 语境含义，改为行为名）
2. 新建 `test_cron_runner_kernel_append.py`，包含 `_AppendTrackingKernelClient` 定义（L412-438）+ `test_awareness_uses_kernel_append_message_not_raw_file`（L441-484）+ `test_awareness_does_not_write_raw_jsonl`（L491-525）
3. 从 `test_cron_runner_awareness.py` 中删除对应内容（L412-525）

### D4. `tests/unit/personal_assistant/test_heartbeat_im_delivery.py`（492 行）→ 拆为 2 个文件

第 5 个测试 `test_heartbeat_scheduler_reuses_stable_heartbeat_session_across_ticks`（L402-479）测 scheduler session 复用，与前 4 个 IM delivery path 测试主题不同，应归入 `test_heartbeat_session_binding.py`（§B1）。

操作：
1. 将 `test_heartbeat_scheduler_reuses_stable_heartbeat_session_across_ticks`（L402-479）搬入 `test_heartbeat_session_binding.py`
2. 从 `test_heartbeat_im_delivery.py` 删除该函数，文件降至约 394 行

### D5. `src/IM/frontend/src/features/settings/agents/agent-m9c-features-panel.test.tsx`（442 行）→ 改名 + 拆为 3 个文件

在改名（§B5）基础上，将 4 组 describe blocks 拆分：

| 目标文件 | describe blocks | 预估行数 |
|----------|-----------------|----------|
| `agent-features-panel.test.tsx`（保留/改名，describe A+B） | `"heartbeat controlled by Features list"`（4 个 it，L162-241）+ `"cron controlled by Features list"`（3 个 it，L247-301） | ~170 行 |
| `agent-tools-pill.test.tsx`（新建，describe C） | `"tool pills render default_on state"`（2 个 it，L307-358）| ~60 行，含 mock setup |
| `agent-prompt-preview.test.tsx`（新建，describe D+E） | `"promptPreview reflects features for heartbeat/cron"`（1 个 it，L365-392）+ `"cadence input shows actual backend value"`（2 个 it，L398-441）| ~80 行，含 mock setup |

操作：
1. 将 `agent-m9c-features-panel.test.tsx` 重命名为 `agent-features-panel.test.tsx`，保留 A+B describe blocks 及公共 mock setup
2. 新建 `agent-tools-pill.test.tsx`，复制必要 mock setup + describe C
3. 新建 `agent-prompt-preview.test.tsx`，复制必要 mock setup + describe D+E
4. 从 `agent-features-panel.test.tsx` 删除 describe C/D/E 内容

---

## E. 抢救式搬迁（m9b/m9e 里值得留的断言）

搬迁目标统一追加到 `test_agent_features_config.py`（改名后的 `test_m9_agent_config_features.py`，§B2），除 §E3/§E4 例外。

### E1. 搬入 `tests/unit/personal_assistant/test_agent_features_config.py`

来自 `test_m9b_cron_json_retire.py::TestCoerceConfigDictsCronJsonRetire`（4 个函数）：
- `test_cron_dict_does_not_produce_cron_json` — 「`_coerce_config_dicts` 不再写 cron_json」
- `test_cron_block_is_ignored_features_is_sole_source` — 「cron 块不回写 features，唯一真源是 features 字段」
- `test_heartbeat_dict_still_produces_heartbeat_json` — 「heartbeat_json 依然被写入（cadence data）」
- `test_heartbeat_block_does_not_touch_features` — 「heartbeat 块不回写 features」

来自 `test_m9e_dead_code_removal.py::TestEnableRoundTripAfterRipOut`（3 个函数）：
- `test_sync_enable_via_features_not_cron_json` — 「cron enable 来自 features，cron_json 已退役」
- `test_sync_heartbeat_enable_via_features` — 「heartbeat enable 来自 features」
- `test_heartbeat_cadence_still_parsed_from_heartbeat_json` — 「`_parse_heartbeat_from_im_payload` 依然解析 cadence」（合并 §E2 中同义断言，只保留一个）

### E2. 搬入 `tests/unit/personal_assistant/test_agent_features_config.py`

来自 `test_m9b_cron_json_retire.py::TestConfigSyncNotifierReadsFeaturesNotCronJson`（5 个函数）：
- `test_cron_enabled_from_features_when_features_present`
- `test_cron_disabled_when_features_cron_scheduling_false`
- `test_cron_disabled_when_features_absent`
- `test_cron_disabled_even_when_cron_json_says_enabled`（关键：cron_json 不覆盖 features）
- `test_heartbeat_cadence_still_from_heartbeat_json`（与 §E1 同义，合并为一个函数）

### E3. 追加至 `tests/im_service/unit/test_gateway_handler.py` 末尾

来自 `test_m9e_dead_code_removal.py`（5 个 heartbeat schema 防回归断言）：
- `TestAgentProfileNoCronJson::test_agent_profile_still_has_heartbeat_json_field`
- `TestRepositoryNoCronJson::test_update_profile_signature_keeps_heartbeat_json`
- `TestConfigServiceNoCronJson::test_update_profile_signature_keeps_heartbeat_json`
- `TestRouteModelsNoCronJson::test_update_request_still_has_heartbeat_json_field`
- `TestRouteModelsNoCronJson::test_agent_config_response_still_has_heartbeat_json`

将上述 5 个函数以新区块 `# heartbeat schema 防回归（feat-394）` 追加到文件末尾，函数名改为行为名（去掉 `NoCronJson`/`StillHas` 等迁移语气，改为「heartbeat_json_field_present」等）。

### E4. 追加至 `tests/unit/personal_assistant/test_heartbeat_session_binding.py`（§B1 新文件）

来自 `test_m9e_dead_code_removal.py::TestMainDeadCodeRemoval`（3 个函数）：
- `test_parse_heartbeat_returns_4_tuple_no_enabled` — 改名为 `test_parse_heartbeat_returns_cadence_4tuple`
- `test_parse_heartbeat_empty_returns_4_none` — 改名为 `test_parse_heartbeat_empty_input_returns_nones`
- `test_parse_heartbeat_non_dict_returns_4_none` — 改名为 `test_parse_heartbeat_invalid_input_returns_nones`

---

## F. 不动（历史债/合规）

以下文件在 main 上已 >400 行，本 PR 不负责重构整文件（scope 边界约定）。新增块已在 §C2/§E3 中按行为追加，无流水号命名。

| 文件 | main→PR 行数 | 说明 |
|------|-------------|------|
| `tests/im_service/unit/test_gateway_handler.py` | 610→1111 | 历史债。§E3 在末尾追加 5 个 heartbeat schema 防回归断言，合规新增，不整文件拆分 |
| `src/IM/frontend/.../agent-detail-page.test.tsx` | 679→1041 | 历史债。本 PR 新增块无流水号文件名（describe 内有 milestone 注释可选清理）|
| `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py` | 730→1006 | 历史债 |
| `tests/im_service/integration/test_agent_config_api.py` | 616→965 | 历史债 |
| `tests/im_service/contract/test_agent_config_contract.py` | 635→643 | 历史债，微增 |
| `tests/integration/test_prompt_sections_golden.py` | 416→417 | 历史债，微增 |

其余本 PR 变更测试文件（`test_cron_at_expiry.py`、`test_cron_config_sync.py`、`test_cron_delivery_chain.py`、`test_cron_file_tools.py`、`test_cron_polling_runner.py`、`test_cron_prompt_sections.py`、`test_cron_run_origin.py`、`test_cron_tool_openclaw.py`、`test_cron_tool_permissions.py`、`test_gateway_channel_and_session.py`、`test_gateway_im_config_sync.py`、`test_gateway_process_manager.py`、`test_gateway_upstream_reporter.py`、`test_heartbeat_prompt_openclaw.py`、`test_permission_pipeline.py`、`test_persistent_session_binding_store.py`、`test_preview_heartbeat_cron_params.py`、`test_personal_assistant_profile.py`、`test_product_profiles.py`、`im-agent-config-api.test.ts`、contract 文件群）—— 命名合法、行数合规、无一次性证据问题，全部**不动**。

---

## 操作汇总

| 类型 | 数量/说明 |
|------|-----------|
| **整文件删除** | 2 个：`test_m9b_cron_json_retire.py`、`test_m9e_dead_code_removal.py` |
| **单函数删除（死代码/重复）** | 约 24 个：m9b 中 3 个重复 + m9e 中 6 个死代码断言 + `TestHeartbeatCronVarsGate` 11 个重复 + `test_polling_runner_has_trim_silent_tick_method` 1 个实现细节 + `test_heartbeat_m1_abc.py` C 部分搬走后删除 5 个原位函数 |
| **文件改名** | 6 个：Python 5 个（§B1-B4）+ TypeScript 1 个（§B5） |
| **文件拆分** | 5 组：`test_heartbeat_scheduler.py`→3、`test_cron_scheduler.py`→2、`test_cron_awareness.py`→2、`test_heartbeat_im_delivery.py`→2、`agent-m9c-features-panel.test.tsx`→3 |
| **搬迁函数（抢救有价值断言）** | 约 19 个：m9b→10 个 + m9e→9 个，分散至 §B1/§B2/§E3 目标文件 |
