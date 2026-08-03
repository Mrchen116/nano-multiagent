# refactor-489-M6: assistant-config-feishu — Tasks

> 对齐: ../design.md

## 目标

保留个人助手配置、Agent capability、Feishu 渠道与权限安全的当前可观察 seam，删除只约束历史迁移终态、旧 standalone 配置、私有实现步骤或提示词原句的测试。

## 退出标准

- [ ] 指定 M6 切片只保留当前配置、capability、渠道适配与安全风险的最低层保护。
- [ ] 历史实现/措辞、重复 wrapper 与旧 standalone Feishu YAML 契约已删除或合并。
- [ ] 删除真实风险前已有当前可运行替代，最窄测试与 M6 全切片通过；无产品行为/spec delta。

## 测试策略

- 被测行为（来自退出标准）：Agent 完整配置与 capability 投影保持一致；Feishu 入站、出站、群上下文、租户权限诊断和审批安全保持现行行为；provider/config 失败明确暴露且 secret 不泄漏。
- 已有测试在：本 milestone 指定的 35 个 unit test 文件；优先删改/合并现有文件，不新建测试文件。
- 落层/目录/marker：`tests/unit/`，marker：无；真实进程 worker 保留在既有 unit 文件但不新增同类进程测试。
- 可选依赖 importorskip：有，`lark_oapi`；删除误放在 unit lane 的真实网络搜索用例。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| live Agent snapshot 原子替换与未知 Agent fail-closed | `test_agent_catalog.py` | keep | 当前并发读取与路由 admission seam，最低层唯一保护 | M6 pytest |
| 配置同步不重建会话、差异 owner 独立 | `test_agent_config_sync_ownership.py`、`test_config_sync_concrete_owners.py` | keep | 直接保护 current 完整配置代次与会话连续性 | M6 pytest |
| heartbeat/cron 历史字段迁移终态 | `test_agent_features_config.py`、`test_agent_features_cron_json.py` | delete | 只断言构造器/私有 parser 不含旧字段；当前 capability wire 与调度由 contract/integration/M7 测试拥有 | capability/prompt alternatives + M6 pytest |
| PromptSection 退役参数与源码缺句 | `test_prompt_section_feature_flags.py` | delete | 私有签名/源码负断言；当前 PromptSlots 装配由 `test_prompt_sections_golden.py` 保护 | targeted alternatives |
| PA builtin skills 安装、用户文件不覆盖、运行时可发现 | `test_builtin_skill_bootstrap.py`、`test_builtin_skills_bootstrap.py` | rewrite-merge | 合并重复安装用例，删精确正文与私有 `kernel._c` 断言，保留 package/discovery seam | targeted + M6 pytest |
| capability tools wire shape | `test_capabilities_tools_format.py` | delete | 与 `tests/contract/test_capability_payload_contract.py` 完整 wire contract 重复 | contract test |
| 群 communication context 可携带身份与 mention 协议 | `test_communication_context.py` | rewrite-merge | 保留 group/direct 语义，删除行前缀、旧措辞缺失和同义片段断言 | targeted + M6 pytest |
| group context 按 sender 有序持久化并原子 drain | `test_group_context_store.py` | rewrite-merge | 合并 getter/空列表/默认值式重复，保留隔离与一次消费风险 | targeted + M6 pytest |
| foreground/unattended 使用同一 Agent capability | `test_unattended_session_skills.py` | rewrite-merge | 保留跨入口同配置 seam，删除 cron 路径与同字段重复 | targeted + M6 pytest |
| IM/Feishu permission request/resolved 投递 | `test_permission_pipeline.py` | rewrite-merge | 保留外部审批与 IM 可见结果，删除迁移叙述和 M7 heartbeat origin 重复 | targeted + M6 pytest |
| permission response handler | `test_permission_response_handler.py` | delete | 与 `tests/unit/test_permission_decision_loop.py` 相同 public handler/first-wins 路径重复 | permission alternative |
| 本地含 secret 配置写失败时原文件与临时明文安全 | `test_sensitive_local_config.py` | keep | 真实安全风险，当前最低层保护 | M6 pytest |
| web_search provider 选择、失败显式、结果归一化 | `test_web_search_tool.py` | rewrite-merge | 删除 unit lane 中真网络/可选集成及内部 provider-map 重复；保留 ops current 行为 | targeted + M6 pytest |
| web_search 用户可见 presentation | `test_web_search_presenter.py` | rewrite-merge | 合并同一 summary/emoji 的重复断言，保留 success/empty/error 状态 | targeted + M6 pytest |
| managed Feishu preflight、metadata、activation retry 与 secret 脱敏 | `test_feishu_preflight_and_metadata.py` | keep | 当前 managed channel 安全/恢复 seam | M6 pytest |
| Feishu capability accepted scope 与 unknown/missing 区分 | `test_feishu_capability_diagnostics.py`、`test_feishu_client_scopes.py` | keep | 租户授权是高风险安全/可用性边界，精确 scope set 属 provider protocol | M6 pytest |
| Feishu worker 进程隔离、回收、背压与 card RPC | `test_feishu_worker_runtime.py` | rewrite-merge | 保留真实并发/回收及日志 secret 风险，删除对 SDK 私有 `_connect` 成员的存在性断言 | targeted + M6 pytest |
| Feishu adapter 入站路由、mention 与 ack | `test_feishu_adapter.py`、`test_feishu_mentions.py` | rewrite-merge | 合并同义 name/DM/multi-bot/mention 用例，保留当前规范化消息与 trigger seam | targeted + M6 pytest |
| Feishu owner 绑定与群标题 | `test_feishu_adapter_owner_binding.py`、`test_feishu_adapter_chat_title.py` | rewrite-merge | 保留首个真实 inbound 绑定、历史不绑定和用户可见 shadow title；合并重复已绑定分支 | targeted + M6 pytest |
| Feishu approval first-wins、owner gate、reason 与 secret 摘要 | `test_feishu_adapter_permission_approval.py` | rewrite-merge | 删除 card 元素布局/英语措辞精确契约，保留安全和交互风险 | targeted + M6 pytest |
| Feishu outbound 目标映射、空消息、ack 终态与失败 | `test_feishu_adapter_send.py`、`test_feishu_adapter_ack_lifecycle.py` | rewrite-merge | 合并 control/final ack 重复，删除 stop/异常类透传重复 | targeted + M6 pytest |
| Feishu client event/API adapter | `test_feishu_client.py`、`test_feishu_client_chat_info.py`、`test_feishu_client_interactive.py` | rewrite-merge | 保留 provider request/response 与错误分类，删除 exact retry count、noop lifecycle 和 wrapper call 重复 | targeted + M6 pytest |
| 旧 standalone Feishu YAML 与 `_build_channel_registry` | `test_feishu_config.py`、`test_feishu_integration.py` | delete | current spec 明确 managed manifest 为权威，旧 YAML/legacy export 不属于契约；managed alternatives 已通过 | channel alternatives |
| Feishu 群历史补齐与 mention-only 可见内容 | `test_feishu_group_history_catchup.py`、`test_feishu_history_client.py`、`test_feishu_mentions.py` | rewrite-merge | 合并 parser/echo 变体，保留 last-bot boundary、权限失败继续当前触发与可见 mention | targeted + M6 pytest |

替代保护预检：`tests/contract/test_capability_payload_contract.py`、`tests/integration/test_prompt_sections_golden.py`、`tests/integration/test_channel_bootstrap.py`、`tests/integration/test_channel_reconcile.py`、`tests/unit/test_permission_decision_loop.py`、`tests/integration/test_group_mention_routing.py` 共 42 passed。

前端 UI：N/A。

## Roadpoints

### R1 — 配置、capability 与 prompt 测试收敛

- 状态: DOING
- 步骤: 删除迁移字段/私有签名契约，合并 builtin skill、communication context、group store 与 unattended capability 测试。
- 验证: 受影响 personal_assistant 最窄 pytest + 已确认的 capability/prompt 替代测试。

### R2 — Feishu adapter 与 provider client 测试收敛

- 状态: TODO
- 步骤: 合并入站/出站/mention/history/provider wrapper 覆盖，删除旧 standalone YAML/registry 与 SDK 私有成员断言。
- 验证: root `test_feishu_*.py` 最窄 pytest + managed channel 替代测试。

### R3 — 权限、安全与 web_search 测试收敛

- 状态: TODO
- 步骤: 保留审批 owner/first-wins/secret、租户 scope、敏感写和 provider fail-loud，删除重复 handler、真网络与 card 文案布局契约。
- 验证: 权限/diagnostics/web_search 最窄 pytest + permission 替代测试。

### R4 — 全切片与替代保护复核

- 状态: TODO
- 步骤: 运行 M6 全切片、替代测试、ruff 与 diff 检查，记录最终处置数量和证据。
- 验证: 所有指定测试与替代保护全绿。
