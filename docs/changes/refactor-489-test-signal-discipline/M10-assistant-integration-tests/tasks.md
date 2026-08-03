# refactor-489-M10: assistant-integration-tests — Tasks

> 对齐: ../design.md 的 refactor-489-M10 行与决策 1--2

## 目标

让 M10 integration 切片只保护 personal assistant / IM / Kernel 经过 channel、routing、session、后台通知与持久化边界后的可观察结果；删除 legacy bootstrap、迁移 golden、私有对象形状和低层重复断言。

## 退出标准

- [ ] M10 每项受影响存量测试都有 keep / rewrite-merge / delete 处置结论。
- [ ] 保留的 integration 直接证明真实 HTTP/WS channel 生命周期、群聊路由、前后台通知、会话配置/重启和 live dispatch 结果，不锁定私有调用、旧 metadata 或历史 prompt 句子。
- [ ] 删除的真实风险已有本切片保留测试或最低层 unit/contract/E2E 保护；纯迁移路径明确记录为无 current 风险。
- [ ] M10 切片、相关最低层替代保护、ruff、`git diff --check` 全绿，changed paths 不越界。

## 测试策略

- 被测行为（来自退出标准）：managed channel 经真实 HTTP/WS 保存、应用、状态、重连和删除；群聊 inline agent identity 经 repository/relay seam 精确路由；前台 bash 只走 tool result、真实后台 bash 通知进入父 session；Gateway 会话在 terminal overlap、配置替换、冷重启、fork 与进程重启后保持正确运行、历史和 live dispatch。
- 已有测试在：本 milestone 现有 10 个 root integration 文件、`background_tasks/` 子树与 `golden_prompts/`（收敛/删除）；替代保护位于 `tests/unit/agent/background_tasks/`、`tests/unit/agent/tools/`、`tests/unit/agent/prompt_sections/`、`tests/unit/agent/test_core_prompt_conditions.py`、`tests/unit/personal_assistant/`、`tests/im_service/unit/test_relay_service_mention_routing.py` 及 `tests/e2e/critical_paths/test_bash_background_notify_critical_path.py`。不新建测试域，只把保留测试改成当前 seam。
- 落层/目录/marker：`tests/integration/`，marker：无（真实 SQLite/HTTP/WS/loopback listener/local shell + fake LLM，无外部服务或长驻产品进程）。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；基线、替代保护和收尾门禁结果写入 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| 后台 bash 启动、输出文件、成功/失败通知、workspace 透传 | `background_tasks/test_bash_background.py::*`、`background_tasks/_runtime_stub.py` | delete | 直接 wiring + registry stub 重复 unit 行为并锁定内部 submit 参数；真实 Kernel 通知由 `test_foreground_single_channel.py` 保留，状态/失败/XML 由 background/tool unit 拥有 | foreground integration + background/tool unit |
| `task_stop` 的 bash/subagent terminal race | `background_tasks/test_task_stop.py::*`、`background_tasks/_runtime_stub.py` | delete | 直接 registry 形状与 lower unit 重复，不增加跨 seam 结果；current stop 行为由 task-stop/background unit 拥有 | task-stop/background unit |
| manual bind 导入 legacy desired state 与空 bootstrap 墓碑 | `test_channel_bootstrap.py::*` | delete | current spec 明确 managed manifest 为权威、legacy YAML/export 不属契约；真实在线 manifest/current lifecycle 由 reconcile/removal integration 保留 | channel reconcile/removal integration |
| channel credential producer/consumer 安全边界 | `test_channel_reconcile.py::test_gateway_key_file_opens_im_envelope_and_registers_public_only` | keep | IM seal + Gateway open + public-only register 是跨包安全 seam，低层单包测试不能替代 | channel reconcile pytest |
| 在线保存/替换 manifest 后 Gateway/IM 状态收敛 | `test_channel_reconcile.py::test_online_http_save_pushes_manifest_and_status_projects_connected` | keep | 真实 HTTP + Gateway WS + SQLite 投影，直接保护 current managed-channel 结果 | channel reconcile pytest |
| fake websocket 的 FIFO/dispatch 私有步骤 | `test_channel_reconcile.py::test_gateway_dispatches_manifest_and_correlated_result_releases_fifo`、`test_channel_removal_reconcile.py::test_gateway_consumes_manual_reconnect_and_per_token_result_ack` | delete | `_listen_once`、发送顺序与 event log 是内部步骤；真实协议收敛由保留 HTTP/WS integration、低层 IMConnection tests 和 contract 拥有 | channel integration + PA connection unit |
| connected channel 重连、失败 removal 同 revision 重试并最终消失 | `test_channel_removal_reconcile.py::test_connected_reconnect_and_failed_removal_retry_use_same_manifest_revision` | keep | 真实 HTTP/WS/SQLite 跨 seam 用户可观察生命周期，处于最低合适 integration 层 | channel removal pytest |
| 前台 timeout 单通道与真实后台完成通知 | `test_foreground_single_channel.py::*` | rewrite-merge | 保留 real `build_kernel` + shell + model input 结果，删除 change 叙事、固定内部路径注释和无条件等待 | foreground integration + background unit |
| 群聊 inline mention、旧 display-name、orphan/same-name 路由 | `test_group_mention_routing.py::*` | rewrite-merge | 保留一个真实 repository + RelayService 的同名 agent 精确路由结果；其余同义正反例由 IM mention unit 拥有，不在 integration 复述 | group routing integration + mention unit |
| PA/CLI prompt migration golden、历史句子、core gate/cache 实现 | `test_prompt_sections_golden.py::*` | rewrite-merge | 删除迁移/精确措辞与 core/unit 重复，只保留 PA product PromptSlots 接到 kernel assembler 后的 group capability 与 system/custom 输入输出；CLI/core 由其最低层测试拥有 | PA prompt integration + core/PA prompt unit |
| golden prompt fixture 文件 | `golden_prompts/*` | delete | M9 删除唯一引用的迁移 skeleton 测试后不再有 current owner；仅在 rebase 确认 M9 已合入且 `rg` 无引用后删除，否则保留并报告 | rebase 后 `rg` + M10/full collection |
| stale metadata dispatch URL 与 restart history/live endpoint | `test_send_message_restart_routing.py::test_restart_reuses_session_history_but_dispatches_only_to_new_listener` | rewrite-merge | 保留真实 Kernel restart + loopback HTTP + binding persistence 结果，删除对旧 session metadata 值的直接断言 | send-message restart pytest |
| 直接重建私有 `SessionDirectory` | `test_session_directory_reopen_integration.py::*` | delete | 只测 core 内部地址；同一 current 风险由 real Kernel 冷重启 runtime/session 测试覆盖，directory 细节由 unit 拥有 | session runtime integration + directory unit |
| Gateway terminal overlap 与 real Kernel session runtime/restart/fork | `test_session_run_coordinator_real_kernel.py::{test_terminal_observer_window_creates_one_fallback_run,test_kernel_reconfigures_one_session_without_losing_transcript,test_kernel_recovery_preserves_empty_feature_runtime_identity,test_kernel_fork_preserves_complete_runtime}` | rewrite-merge | 保留 Gateway↔SDK/current persistence seam；terminal test 改从 observer public event 取 run id，不读 `kernel._c` | session integration pytest |
| runtime identity 的 map/list canonicalization 实现 | `test_session_run_coordinator_real_kernel.py::test_runtime_identity_canonicalizes_maps_but_preserves_list_order` | delete | isolated pure identity 算法放在 integration 无跨 seam，current 要求稳定 identity 而非固定容器 canonicalization 细节；保留冷恢复/幂等 reconfigure 的外部结果 | session integration pytest |

前端 UI：N/A。

Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — 删除迁移路径与低层重复

- 状态: DOING
- 步骤: 删除 direct background registry、legacy channel bootstrap、私有 SessionDirectory、fake FIFO 和重复 routing/prompt/runtime 用例；先运行并记录保留/替代保护，再移除旧测试。
- 验证: 已删风险的最低层 unit/contract/E2E 节点全绿；M10 收集不再包含 legacy/golden/private-path nodes。

### R2 — 收敛当前跨 seam 保护

- 状态: TODO
- 步骤: 保留真实 channel HTTP/WS、real-kernel 通知、routing/session/restart 结果；移除私有字段、历史 metadata 和 change 叙事断言，改用公开事件或最终接收结果。
- 验证: M10 integration 全绿，保留用例只断言 current 跨边界结果。

### R3 — Rebase、golden 归属确认与门禁收尾

- 状态: TODO
- 步骤: rebase 最新 unit；确认 M9 已删除 golden 唯一引用后再删除 fixtures；复核处置表、changed paths 与替代保护，运行 M10、ruff、diff check。
- 验证: 所有门禁全绿；若 M9 仍引用 golden 则保留并在 progress 报告，不越界修改 M9。
