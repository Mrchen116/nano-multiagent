# refactor-406 — 验收报告

> 对齐: motivation.md 用户侧验收标准（Requirement / Scenario 矩阵）  
> 审查对象：unit/refactor-406，HEAD 846b0c9c，M1+M2 合并完成  
> Review Round: 1  
> Reviewer: reviewer-r1  
> 日期: 2026-06-14

## Verdict

**pass-with-issues**

所有 15 条必验 Scenario（除 R-PA-2 因 GIVEN 前提不满足标 inconclusive）均通过。全测试树 2582 passed / 1 skipped 零失败。标记 inconclusive 的 Scenario 是因为 e2e 环境没有独立外部通道，属前提条件不满足，非实现缺陷。

## 澄清记录

无需澄清，验收口径清晰。

## 用户旅程体验

### Journey 1：Coding CLI 工具调用 + 模型选择（R-CLI-1/2）

- 环境：worktree 内隔离 IM_PORT=53252
- 操作：`PYTHONPATH=src python3 -m coding_cli.main --model kimiCoding:K2.6 --llm-base-url http://127.0.0.1:4000 --text "请读取 README.md 前 5 行"`
- 观察到：`submit_response` → `run_status queued/running` → `tool_start` (read, presentation 含 label/summary) → `tool_end` → `assistant_message` → `run_status completed`。完整流式事件，工具调用正常，presentation 字段存在。最终回复："README.md 文件的第一行是：`# nano-multiagent`"

### Journey 2：Web IM 消息收发 + 权限机制（R-PA-1/3）

- 操作：POST 创建含用户+agent 的 conversation，POST 发消息"你好，请说一句话回应我"
- 观察到：约 1.5 秒后 agent 回复"你好！很高兴能在这里帮助你，有什么我可以为你做的吗？"，delivery_status=completed，token_usage 字段存在
- 权限机制：发"请用 bash/write 工具"消息，auto_mode_gate 自动 allow（workspace 无限制配置），工具正常执行，文件成功创建。权限卡 API endpoint 存在（`POST /im/v1/conversations/{id}/permissions/{request_id}`），broker 机制保留，行为与重构前一致

### Journey 3：Agent 配置查看与保存（R-CFG-1/2/3/4）

- R-CFG-1 节点能力：models 3 个（kimiCoding:K2.6/volcanoArk/codex_oauth），skills 39 个，tools 12 个（含 default_on 标记），features 4 条（memory_curation/skill_creation/cron_scheduling/heartbeat），platform_default_model=kimiCoding:K2.6。字段完整
- R-CFG-2 跨 workspace：default-agent 和 Arch 均有独立 workspace，node capability 中 skills 来自全局 skill 目录（均可见），各 agent 配置已分离
- R-CFG-3 配置保存：PATCH agent config，tool_allowlist=[read,bash]、features={memory_curation:false,skill_creation:true} → 读回完全一致，profile_version 递增（1→2）
- R-CFG-4 prompt 预览：heartbeat=false 时 section_count=9、prompt_len≈6800；heartbeat=true 时 HAS_HEARTBEAT=True、section_count=9；cron=true 时 HAS_CRON=True、section_count=10、自定义提示词出现。预览随开关变化，组合产生不同结果

### Journey 4：Gateway 生命周期（R-GW-1/2/3）

- R-GW-1：Gateway 启动后节点状态=online，relay_enabled=true，last_heartbeat 正常更新
- R-GW-2：kill Gateway 进程 → 节点状态=offline（即时感知）；手动重启 --foreground --auto-bind → 节点状态恢复=online（约 8 秒）
- R-GW-3：default-agent 和 Arch 分别跑对话，JSONL 落位：
  - default-agent: `/.../default-agent/chat_history/sess_e35fe390160d3447.jsonl`
  - Arch: `/.../Arch/chat_history/sess_d3e4ee50382b0d41.jsonl`
  - 互不混写 ✓

### Journey 5：定时与自动化行为（R-CP-1/2/3）

- R-CP-1 heartbeat：单测 35 passed（scheduler + prompt 逐字节 golden）。HEARTBEAT.md 空 template 时 Gateway 静默不触发（正确行为）
- R-CP-2 cron：单测 109 passed（cron 工具闭包直连 CronExecutionService，排队/路由/回投行为全覆盖）
- R-CP-3 群聊 @ mention：创建含 3 方的 group conversation，发"@default-agent 你好！"，约 10 秒后 default-agent 回复"你好！有什么我可以帮你的吗？"，正确路由到被 mention 的 agent

### Journey 6：外部产品装配证明（R-NEW-1）

- 跑 `tests/contract/test_sdk_two_layer_assembly.py` + `test_sdk_kernel_wiring.py`：20 passed，含闭包副作用工具 + presenter 验证
- 外部应用仅 import `agent.sdk`，build_kernel + create_session 两层装配，工具调用一轮跑通

## 问题清单

| # | 严重度 | 现象 | Regression Relation | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| 1 | minor | R-PA-2 GIVEN 前提（外部消息通道独立于 IM）当前 e2e 环境不满足，channels/ 中只有 web_relay_adapter（依赖 IM WebSocket），无法完成"IM 离线时外部通道收消息"的旅程 | unrelated-existing（旧行为如此） | out-of-unit | 能力域不在 refactor-406 范围内（本 unit 不新增外部通道），非本次 Scenario GIVEN 前提本身的缺陷，只影响该条 Scenario 标 inconclusive，不影响整体产品可接受性 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**需要更新** — L76 注释"refactor-406 决策1：products 层解散→消费者工厂"已加，但 L165/178/179 的 `AGENTS.md` 中仍描述 products 层（见下）
- [x] `docs/specs/kernel/spec.md`（长青内核契约层）：**需要更新** — L46 仍用旧签名 `build_kernel(product_profile, llm_config, can_use_tool, repo_root, host_capabilities)`，应更新为新签名 `build_kernel(llm, tools, hooks, can_use_tool, workspace_config_dirname)`；`host_capabilities` 已删除（决策 9），spec 未反映
- [x] `docs/specs/gateway/spec.md`：无需更新（已检查，无旧引用）
- [x] `docs/specs/cli/spec.md`：无需更新（已检查，build_kernel 只提概念不带参数）
- [x] `AGENTS.md`：**需要更新** — L165 `products/         # 产品 profile：local_coding, personal_assistant` 目录已解散；L178 `agent 内核四层：core→platform→products→sdk` 应更新为三层（core→platform→sdk，products 解散）；L179 依赖方向描述同步
- [x] `docs/SPEC_GUIDE.md`：无需更新

> 长青契约层写回由 orchestrator §7.0 收尾归并处理，reviewer 只标记"是否已反映增量"。

## 验收标准覆盖

### Requirement: Coding CLI 的现有 Agent 工作流保持可用 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户在 Coding CLI 完成带工具调用的任务 | motivation.md §R-CLI-1 | --text 模式非交互式，观察流式事件、tool_start/end、最终回复 | Journey 1：完整事件序列（submit_response→tool_start read→tool_end→assistant_message→completed），工具调用成功 | pass | |
| 用户选择已配置模型启动 CLI | motivation.md §R-CLI-2 | --model 参数启动，观察正常运行 | --help 确认参数存在，--model kimiCoding:K2.6 正常启动并使用该模型 | pass | |
| 用户在 CLI 运行中切换模型 | motivation.md §R-CLI-3 | 验证 kernel.reconfigure_llm 在 SDK 上可用 | agent/sdk/kernel.py:L1025 reconfigure_llm 存在；commands.py:L511 调用该方法 | pass | 交互式 /model 命令无法自动化测试，以代码路径确认 API 存在作为补充证据 |

### Requirement: 个人助手的消息处理能力保持可用 — 组内结论: pass（R-PA-2 inconclusive）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户经 Web IM 向 Agent 发送消息 | motivation.md §R-PA-1 | 真实 IM API 发消息，观察 agent 回复 | Journey 2：1.5 秒后 agent 回复，delivery_status=completed，token_usage 存在 | pass | |
| IM 暂时离线时 Gateway 保持本地自治 | motivation.md §R-PA-2 | GIVEN 需配置独立外部通道 | e2e 环境仅有 web_relay（依赖 IM），无独立外部通道，无法完成旅程 | inconclusive | GIVEN 前提不满足，不是实现缺陷；参见问题清单 #1 |
| IM 中工具调用需用户授权 | motivation.md §R-PA-3 | 发需要 bash/write 的消息，观察权限机制 | auto_mode_gate 按配置自动 allow，工具执行成功；权限卡 API endpoint 存在，broker 机制完整 | pass | PA 没有 can_use_tool，broker 停在 future 等 IM 卡点击；本次未展示 ask 态（workspace 无限制），权限路径结构保留 |

### Requirement: IM 中的 Agent 配置与能力选择保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户创建 Agent 时查看节点能力 | motivation.md §R-CFG-1 | GET /im/v1/nodes/{id}/capabilities | Journey 3：models/skills/tools/features/platform_default_model 字段全部存在，内容完整 | pass | |
| 用户编辑不同工作区的 Agent | motivation.md §R-CFG-2 | 查看 node capabilities 及 workspace 差异 | default-agent 和 Arch 各有独立 workspace_root，chat_history JSONL 分离 | pass | skills 来自全局目录，两 agent 相同；跨 workspace skill 差异需在 workspace 下放不同 skills 才可观察，当前 e2e 无此前提 |
| 用户保存既有 Agent 配置 | motivation.md §R-CFG-3 | PATCH agent config → GET 回显 | Journey 3：tool_allowlist/features 保存后读回完全一致，profile_version 递增 | pass | |
| 用户在 Agent 设置页预览 system prompt | motivation.md §R-CFG-4 | POST prompt-preview，切换 heartbeat/cron 开关 | Journey 3：heartbeat=off → section_count=9；heartbeat=on → HAS_HEARTBEAT=True；cron=on → section_count=10 + HAS_CRON=True；custom_prompt 出现 | pass | |

### Requirement: Gateway 的现有运维方式保持不变 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 运维者按现有配置启动 Gateway | motivation.md §R-GW-1 | e2e-up.sh 启动，观察节点注册上线 | Journey 4：节点 status=online，relay_enabled=true，auto-bind 成功 | pass | |
| 运维者停止或重启 Gateway | motivation.md §R-GW-2 | kill → 验证 offline；重启 → 验证 online | Journey 4：kill 后节点 offline；--foreground 重启后约 8 秒恢复 online | pass | |

### Requirement: 新产品可通过 SDK 独立装配 Agent — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 产品开发者接入新的 Agent 产品 | motivation.md §R-NEW-1 / design.md S5.1 | test_sdk_two_layer_assembly.py + test_sdk_kernel_wiring.py | Journey 6：20 tests passed，含闭包副作用工具 + presenter 验证，未 import 内核内部 | pass | |
| 新产品逐步增加自身能力 | motivation.md §R-NEW-1 / design.md S5.2 | 同上 + boundary contract | test_agent_sdk_boundary_contract 绿，coding_cli 零 agent.core/platform 内部 import | pass | |

### Requirement: 个人助手的定时与自动化行为保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 定时任务（cron）建立并触发 | motivation.md §R-CP-2 | cron 单测 | 109 passed，含工具闭包直连 CronExecutionService + 排队/路由语义 | pass | 单测覆盖完整 cron 行为，与重构前一致 |
| Agent 心跳自主活动 | motivation.md §R-CP-1 | heartbeat 单测 + prompt golden | 35 passed（scheduler + openclaw prompt verbatim + skeleton 重现 golden）；HEARTBEAT.md 空 template 时 Gateway 静默 | pass | 静默是正确行为（无 schedule），heartbeat 机制完整 |

### Requirement: 群聊中的协作行为保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Agent 在群聊中引用成员 | motivation.md §R-CP-3 | 创建 3 方群聊 + @mention 实测 | Journey 5：@default-agent 消息后约 10 秒 agent 正确回复，routing 正确 | pass | |

## 全测试树

`pytest -m "not e2e"` → **2582 passed, 1 skipped, 0 failed** (99.38s)

## Side Findings

- `docs/specs/kernel/spec.md` L46 仍描述旧 `build_kernel(product_profile, ...)` 签名和 `host_capabilities` 参数，与已实施的 refactor-406 不符；应由 orchestrator 收尾归并时更新。这是文档滞后，不是实现问题。
- `AGENTS.md` L165/178/179 仍描述 `products/` 四层架构，与实际三层（products 解散）不符；建议随 PR 合并时更新。

## Highest Required Action

`pass`（主要问题均为文档同步滞后，无 fix-implementation 项；R-PA-2 inconclusive 因 GIVEN 前提不满足，非实现缺陷）

---

> **Orchestrator note (round 1 routing)**: reviewer=pass / verifier=pass，但 **change-code-review 抓到多条 CONFIRMED in-unit 行为回归**（verifier 的 delta-spec 符合性 + reviewer 的 happy-path 旅程 scope 外）。路由 = **fix-implementation（round 1）**，§6.FL① 复用 m2-worker。根因：新 build_kernel 未接全 bootstrap_product 原有的 skill/tool/hook 发现（config_resolver / 工作区 .nano/tools / user roots），M2 的 skill_search_roots 仅补 PA list_skills 一处。
>
> **Fix 清单（round 1）**：
> 1. [CONFIRMED 决策2 违背] 工作区 `.nano/tools` 运行时工具发现丢失——build_kernel 未调 build_tool_registry/load_tools_from_directory。
> 2. [CONFIRMED 行为回归] 用户级 hook/tool 目录发现丢失（`~/.nanoassistant/hooks`、`~/.nanocode/tools` 等，旧 config_resolver.user_*_roots 路径）。
> 3. [CONFIRMED 决策8 同源违背] assemble_prompt_preview 经 runtime._config_resolver（2 层路径恒 None）解析技能 → skill_ids 非空时技能段恒空白；应复用 list_skills 的 _WorkspaceDirnameSkillResolver。
> 4. [CONFIRMED 行为回归] SkillManageTool 的 registry 锚 repo_root、非 per-session workspace_root，且无 extra_roots → 多 agent 共享同一 skill 目录 + skill_manage list 与 list_skills/IM 展示三套 registry 不对齐。
> 5. [CONFIRMED 行为回归] self_evolution 配置（config.yaml）不再读入 session metadata → self_improvement hook 拿 {} → 硬编码默认覆盖用户 skill_nudge/memory_nudge/enabled。（ver-configdrop 簇）
> 6. [CONFIRMED 行为回归] CLI `~/.codex/skills` compat skill root 丢失——build_cli_kernel 未传 skill_search_roots。（ver-configdrop 簇）
> 7. [CONFIRMED correctness] runtime close_session 漏清 `_session_prompt_slots` → 长期运行内存泄漏（本 unit 新增 PromptSlots 引入）。
> 8. [CONFIRMED docstring] kernel.py list_models is_default docstring 错（实现正确=catalog default，仅注释把 active model 写错）——trivial。
>
> **out-of-unit / 不修**：fork_session 不继承源 session（预存在、main 同样，非本 unit 引入，单独 issue 跟踪）；R-PA-2 inconclusive（e2e 无独立外部通道，能力域不在本 unit）。
> **cleanup/altitude（记 PR body 已知事项，本轮不阻塞）**：LLMConfig 解析/active_provider 重复、resolve_effective_tool_allowlist 死函数、assemble_prompt_preview 双 render、list_skills/list_models 无缓存每次重扫、project_tools 静态列表（决策风险2 保守，已注释）、pa.cron/pa.heartbeat 段名在 core FEATURE_REGISTRY。
