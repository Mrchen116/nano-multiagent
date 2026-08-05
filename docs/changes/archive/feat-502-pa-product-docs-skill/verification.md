# Verification Report: feat-502

> Validation snapshot: `e6f8b617a7beb1dc68e1a116f368eaf05c764606 → ea59765053a8bc8fb253f5b3f1ae3dc6d73cda0b`

> Post-review note: 本报告保留最初单文件实现及其 corrected-delta 的独立 verification 记录。用户随后撤销“无 `read` 可达”要求；最终资源形态与有效证据以 `Post-review revision verification` 和文末 `Final post-review delta reconciliation` 为准，其他关于“单文件 / 无 read / 50,000 字符”的结论不再描述 PR 当前树。

## Summary

- Mode: `full`
- Delta range: N/A
- Focus issues: N/A
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 milestone；5/5 requirements |
| Correctness | 17/17 scenarios mapped |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- Tasks: M1 的 R1 Red、R2 Green、R3 Verify 均已完成。`tasks.md:3-5` 的三个 roadpoint 分别由 `progress.md:14-60` 的 Red/Green、影响面和隔离真栈证据支撑；本轮又在 `validated_at` 上独立复跑了 39 个聚焦/IM 创建测试、9 个显式选择/skill gate/架构测试、Ruff、docs-check、diff check 和 skill validator，全部通过。
- Spec 覆盖：5 条 Requirement 均有实现投影。产品手册供给/默认选择由 `bootstrap.py:74-121`、`upstream_reporter.py:123-142` 和现有 IM 选择链完成；全部内置 skill 刷新由 `bootstrap.py:30-71,99-120` 完成；产品问答、版本与现场证据边界由 `nanoassistant-docs/SKILL.md:8-14,175-186,219-319` 完成。
- Milestone 退出标准：worker 轨的安装、恢复、保护、可发现性、`default_on`、无 `read` 完整可达性和容量边界均有永久测试（`test_builtin_skill_bootstrap.py:26-254`）。reviewer 轨的真 IM/Gateway/LLM 旅程已有一次实施期真栈证据（`progress.md:43-54`），全部用户场景由并列的 `change-reviewer` gate 独立验收，不用单元测试伪造模型触发结论。
- Prototype / Reference 覆盖：N/A。`design.md` 明确无前端改动且不产出 prototype（`design.md:113-120`）；手册设计明确拒绝 references/read 第二跳（`design.md:93-101`）。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试 / 证据 | 状态 |
|---|---|---|---|
| 产品说明书作为可关闭的默认 PA skill / 新建 Agent 默认启用 | `src/personal_assistant/reporter/upstream_reporter.py:123-142`; `src/IM/api/routes/nodes.py:244-263`; `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:31-36,374-386` | `test_builtin_skill_bootstrap.py:172-229`; `test_agent_create_contract.py:126-190`; `agent-create.test.tsx:282-361` | covered |
| 同 Requirement / 默认 skill 集合获得手册 | `src/personal_assistant/gateway/agent_config_sync.py:195-203`; `src/personal_assistant/builtin_skills/bootstrap.py:99-121` | `test_gateway_im_config_sync.py:899-934`; `test_builtin_skill_bootstrap.py:172-254` | covered |
| 同 Requirement / 升级不改写已有显式选择 | installer 只写全局 skill root：`bootstrap.py:74-121`；IM profile 继续是选择真值：`src/IM/api/routes/agents.py:181-205` | `tests/im_service/unit/test_gateway_node_persistence.py:83-128`; `progress.md:43-54` | covered |
| 同 Requirement / 用户关闭后不再使用，可重新开启 | 详情页直接按 profile 选择并保存：`agent-detail-page.tsx:1735-1749`；`skill_view` 以 session skills gate 强制 | `tests/unit/test_skill_view.py:193-221`; 实施期真栈仅启用手册后成功调用：`progress.md:43-54` | covered |
| 随包内置 skills 与当前 PA 版本一致 / 升级刷新全部内置 skills | 稳定排序枚举包内直接子目录并逐项同步：`bootstrap.py:99-120` | `test_builtin_skill_bootstrap.py:26-59,147-158` | covered |
| 同 Requirement / 本地修改的内置 skill 被完整替换 | 目录级 staging/rename：`bootstrap.py:30-56` | `test_builtin_skill_bootstrap.py:42-59` | covered |
| 同 Requirement / 非内置用户 skills 保持 | 安装器只处理当前包声明的名称：`bootstrap.py:99-120` | `test_builtin_skill_bootstrap.py:61-71` | covered |
| 同 Requirement / 刷新不改变 Agent skill 选择 | 同步实现无 IM/profile 依赖：`bootstrap.py:5-16,74-121`；配置依旧从 profile/runtime 流入 | `test_gateway_node_persistence.py:83-128`; `test_gateway_im_config_sync.py:937-970` | covered |
| Agent 按需用说明书 / PA 对话入口询问产品能力 | frontmatter 触发描述：`nanoassistant-docs/SKILL.md:1-4`；完整手册：`nanoassistant-docs/SKILL.md:6-319` | `test_builtin_skill_bootstrap.py:172-254`；真模型完成 `skill_view(nanoassistant-docs)` 并回答：`progress.md:43-54` | covered |
| 同 Requirement / 普通任务不触发 | 触发描述仅列 PA 产品问题，正文不入每轮 prompt：`nanoassistant-docs/SKILL.md:1-4`; 候选注入依旧复用 Kernel skill 链 | 按 design 由 reviewer 真模型旅程验收；本 unit 未加随机模型行为的伪回归测试 | covered |
| 同 Requirement / 超出 PA 手册边界 | `nanoassistant-docs/SKILL.md:14,26,310-319` | 手册本体契约 + reviewer 用户旅程 | covered |
| 回答与用户使用的 PA 版本一致 / 基础问答无需联网 | 随包自包含手册与离线规则：`nanoassistant-docs/SKILL.md:8-14`；只需 `skill_view` 可取全文 | `test_builtin_skill_bootstrap.py:216-254`；真栈工具轨迹只有 `skill_view`：`progress.md:43-54` | covered |
| 同 Requirement / 明确询问最新版或升级差异 | `nanoassistant-docs/SKILL.md:10-13` | 手册本体契约 + reviewer 用户旅程 | covered |
| 同 Requirement / 远端信息不可用 | `nanoassistant-docs/SKILL.md:12-13` | 手册本体契约 + reviewer 用户旅程 | covered |
| 产品说明与现场状态有证据边界 / 询问当前配置或运行状态 | `nanoassistant-docs/SKILL.md:10-13,167-173,219-228` | 真栈回答区分 started 与 Gateway ready：`progress.md:43-54`；reviewer 覆盖其余现场旅程 | covered |
| 同 Requirement / 现场行为与说明书不一致 | `nanoassistant-docs/SKILL.md:11-13,306-308` | 手册本体契约 + reviewer 用户旅程 | covered |
| 同 Requirement / 说明书没有覆盖答案 | `nanoassistant-docs/SKILL.md:13-14,310-319` | 手册本体契约 + reviewer 用户旅程 | covered |

### 刷新失败扩展契约

Gateway delta 还要求“单项失败恢复旧完整目录并继续启动”。实现在 staging 切换失败时移除不完整新目标、把 backup 原子改回原名，再由外层记录 skill 名和异常并继续枚举（`bootstrap.py:45-71,110-120`）；故障注入测试同时断言旧主文件、旧额外文件、后续 Lark skill 成功与可观测错误（`test_builtin_skill_bootstrap.py:74-111`）。

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1 全部随包内置 skill 由 PA 托管，以整目录替换 | 是 | `src/personal_assistant/builtin_skills/bootstrap.py:99-120`; 只枚举包内含 `SKILL.md` 目录，非内置名不被扫描 |
| D2 同文件系统 staging + backup，单项失败恢复并继续 | 是 | `bootstrap.py:30-71,110-120`; `test_builtin_skill_bootstrap.py:74-111` |
| D3 单份自包含 `nanoassistant-docs/SKILL.md`，无 `read`，低于 50,000 字符结果预算 | 是 | 包内目录只有 `SKILL.md`，文件 20,233 bytes；`test_builtin_skill_bootstrap.py:233-254` 断言全文相等及序列化结果低于 tool budget |
| D4 已安装手册优先，现场要核实，只在明确询问最新版时查官方远端 | 是 | `nanoassistant-docs/SKILL.md:8-14`，并在模型、Gateway 与排障章节重申现场证据边界（`:167-173,219-228,280-308`） |
| D5 不改 IM/前端，复用现有 `default_on` 和显式 allowlist | 是 | unit 实现 commit 只改 PA 包资源、installer、lifecycle 文案和聚焦测试；既有链路在 `upstream_reporter.py:123-142`、`nodes.py:244-263`、`agent-create-page.tsx:31-36,374-386` |
| 生产 owner 仍是 Gateway foreground lifecycle，runtime 构建前刷新 | 是 | `src/personal_assistant/gateway/process_lifecycle.py:39-56,120-148` |
| 不改 Kernel 公共契约，不新建平行发现/配置机制 | 是 | 复用 `build_pa_kernel`、`list_skills`、prompt preview 和现有 `SkillViewTool`；无 `src/agent` / `src/IM` 产品改动 |
| 跨包依赖和注释/docstring 规范 | 是 | `src/personal_assistant` 新生产代码未 import `agent.core` / `agent.platform`；两个架构 contract 测试通过；public installer/lifecycle 入口的 docstring 已更新（`bootstrap.py:74-90`; `process_lifecycle.py:39-44`） |

### Prototype / Reference Contract

N/A. 本 unit 没有前端原型或 reference artifact；单文件手册本身就是 design 批准的运行时资源。

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（提 PR 前必须修）

- None.

### SUGGESTION（可以修）

- None.

## Post-review revision verification

### Scope and verdict

- Verification mode: changed-scope full verification for the product-manual resource shape.
- Verdict: **pass**；0 CRITICAL / 0 WARNING / 0 SUGGESTION。
- Changed atoms: `nanoassistant-docs` 的入口/正文分工、`read` 工具前提、Gateway 产品问答 delta、design D3/D4/D5、milestone 测试与 reviewer journey。
- Retained atoms: 内置目录托管与原子替换、共享 root 锁、失败恢复/继续、Lark bundle、IM default-on/显式选择和远端/现场证据边界。

### Requirement and design alignment

| 项目 | 最终实现 | 验证 |
|---|---|---|
| 产品问题按需读取 | `SKILL.md` 仅保留触发后的回答规则、来源边界和七主题路由；入口明确禁止默认加载全部资料 | 真实模型先 `skill_view`，再只 `read(references/getting-started.md)`，没有读取其他专题 |
| 随安装版本离线回答 | 七份 references 全部位于随包 `nanoassistant-docs/` 内，不依赖源码仓 current docs 或远端服务 | 安装测试逐份比对包资源与目标 root；真实模型不提供网络工具仍完成回答 |
| 工具前提 | 正常 PA Agent 默认启用 `skill_view` 与 `read`；用户显式关闭 `read` 后不保证详细手册可读，真白名单契约不变 | 配置与 prompt preview 测试断言默认 Agent 同时具备两工具；Gateway canonical/delta GIVEN 已同步 |
| OpenAI 式渐进加载 | metadata 负责触发，精简入口负责来源和路由，一层 references 负责互不重复的专题正文 | 官方 `quick_validate.py` 通过；入口 38 行 / 3,510 bytes，全部七份 reference 被直接链接且各少于 100 行 |
| 内置资源完整刷新 | 安装器仍以整个 skill 目录为替换单元，因此 references 随版本一起覆盖并清除旧文件 | `nanoassistant-docs` 加入 managed-directory replacement 参数集；安装后逐份内容一致 |
| D1/D2/D5 未扩张 | 没有新增 Kernel API、helper、MCP、scripts、assets、PA UI metadata 或前端/API seam | unit diff 无 `src/agent` / `src/IM` 生产改动；contract 136 passed |

### Validation evidence

- Skill validator: PASS，`Skill is valid!`。
- Focused bootstrap: 15 passed。
- Capability / `skill_view` / `read` / default-tool focused set: 72 passed，2 个第三方 warning。
- PA unit suite: 838 passed，2 个第三方 warning。
- Contract suite: 136 passed。
- docs-check: 203 maintained Markdown sources / 66 required routes。
- Ruff check / Ruff format-check / `git diff --check`: PASS。
- Real-model forward test: terminal `completed`; calls were exactly `skill_view(name=nanoassistant-docs)` then `read(.../references/getting-started.md)`; answer correctly stated IM → Gateway → bind/chat and that `Gateway started` is not readiness evidence.

### Historical gate invalidation

Round 1 的最小工具问答证据依赖旧的单文件资源，已被本节真实模型轨迹替代。Round 1 的 IM 默认选择/关闭、普通任务不触发、范围边界、全部内置资源刷新、非内置保留和 profile 不改写证据不依赖正文存放位置；安装器本来就以完整目录为替换单元，因此新增 references 没有使这些 gate 失效。

## Corrected Delta Reconciliation

> Validation snapshot: `e6f8b617a7beb1dc68e1a116f368eaf05c764606 → a69e1bf9ae0d2aa70d361f8a97d0de3b8eb9377a`

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/gateway/agent-capabilities.md:5-7` — ADDED `PA 产品说明书按需回答产品问题` | 随包单文件手册的精确触发描述与 PA 范围规则在 `src/personal_assistant/builtin_skills/nanoassistant-docs/SKILL.md:1-14`，完整产品面在 `:16-319` | `tests/unit/personal_assistant/test_builtin_skill_bootstrap.py:373-455`；真 IM/Gateway/LLM 验收 `acceptance.md:18-31,74-96` | aligned |
| `specs/gateway/agent-capabilities.md:9-13` — 在 PA 对话入口询问产品问题 | 候选触发描述与手册正文分工保持按需 `skill_view`：`nanoassistant-docs/SKILL.md:1-14,175-186` | 只开启手册 + `skill_view` 的真模型产品问答调用成功：`acceptance.md:20,25-26,78` | aligned |
| `specs/gateway/agent-capabilities.md:15-18` — 普通任务不加载手册 | skill 正文不常驻 system prompt，只以产品问题触发描述候选：`nanoassistant-docs/SKILL.md:1-14,175-180` | 已启用手册的真模型完成算术题且无工具轨迹：`acceptance.md:27,79` | aligned |
| `specs/gateway/agent-capabilities.md:20-23` — 基础问答离线可用 | 手册明确以已安装版本为默认来源且基础问答不联网：`nanoassistant-docs/SKILL.md:8-14`；全文自包含 | `test_builtin_skill_bootstrap.py:434-455` 断言仅 `skill_view` 返回未截断全文；真栈无网络工具闭环 `acceptance.md:26,30,86` | aligned |
| `specs/gateway/agent-capabilities.md:25-29` — 最新版与本机版本分开回答 | 远程查询仅在明确最新/升级问题触发，并要求区分官方远程与已安装版：`nanoassistant-docs/SKILL.md:10-13` | 有/无远程工具的真模型路径均正确限定版本：`acceptance.md:30,86-88` | aligned |
| `specs/gateway/agent-capabilities.md:31-35` — 现场状态以实际核实为准 | 现场核实、产品规则/观察分离与有界不确定性规则：`nanoassistant-docs/SKILL.md:11-14,167-173,219-228,280-319` | 真模型区分会话工具观察与产品规则，且对未覆盖能力不编造：`acceptance.md:31,90-96` | aligned |
| `specs/gateway/agent-capabilities.md:39-41` — MODIFIED `PA 内置 skill 启动自举` | Gateway foreground 在 runtime 构建前调用包资源同步：`src/personal_assistant/gateway/process_lifecycle.py:39-56,136-148`；全包枚举和目录级切换：`src/personal_assistant/builtin_skills/bootstrap.py:49-90,93-141` | 本轮在 final tree 实跑 bootstrap/Lark/profile 相关集：64 passed；真启动验收 `acceptance.md:18-29,65-72` | aligned |
| `specs/gateway/agent-capabilities.md:43-46` — 新安装发现产品手册与完整 Lark bundle | 直接枚举所有含 `SKILL.md` 的随包子目录并同步：`bootstrap.py:118-140`；全局 root 能力投影 `src/personal_assistant/reporter/upstream_reporter.py:123-142` | `test_builtin_skill_bootstrap.py:62-75,315-359,373-455` | aligned |
| `specs/gateway/agent-capabilities.md:48-52` — 升级刷新全部随包内置 skills | staging 复制包内完整目录、旧目录备份后 canonical rename：`bootstrap.py:49-80` | `test_builtin_skill_bootstrap.py:78-94`；真 Gateway 两次刷新 `acceptance.md:21,25,29,69-70` | aligned |
| `specs/gateway/agent-capabilities.md:54-58` — 非内置用户 skill 保持不变 | installer 只触达当前包声明的同名目录：`bootstrap.py:118-140` | `test_builtin_skill_bootstrap.py:97-107`；真栈 `my-custom-skill` 保持：`acceptance.md:21,25,71` | aligned |
| `specs/gateway/agent-capabilities.md:60-64` — 刷新失败保留旧完整目录并继续启动 | 切换失败恢复 backup，外层逐项记录 skill 名/异常并继续：`bootstrap.py:64-90,130-140`；Gateway 外层不阻断启动 `process_lifecycle.py:39-56` | 故障注入同时断言旧主文件、旧额外文件、后续 skill 成功与日志原因：`test_builtin_skill_bootstrap.py:110-147` | aligned |
| `specs/gateway/agent-capabilities.md:66-71` — backup 清理失败不遮蔽新版本 | staging/backup 均在 `root/.archive`，canonical 切换成功后 cleanup 异常只告警：`bootstrap.py:49-90`；正式 discovery 剪枝 `.archive`：`src/agent/core/skills/registry.py:41-58` | cleanup 故障注入后用正式 `SkillRegistry` 断言 canonical 新版本唯一发现且原因可观察：`test_builtin_skill_bootstrap.py:150-189` | aligned |
| `specs/gateway/agent-capabilities.md:73-78` — 共享 root 的并发 Gateway 刷新保持完整版本 | root 上稳定文件锁以 `fcntl.LOCK_EX` 串行化 `for source` 的整次 bundle：`bootstrap.py:35-46,118-140`；后一进程的单项失败会恢复其取得锁后备份的先成功 canonical，不跨锁回滚 | 完整 bundle 只进一次锁作用域：`test_builtin_skill_bootstrap.py:192-230`；真跨进程争用、第二刷新在释放前不进入切换且最终 canonical 完整：`:232-312`；单项失败恢复：`:110-147` | aligned |
| `specs/gateway/agent-capabilities.md:80-84` — 显式 skill allowlist 不因资源刷新改变 | installer 仅写全局 skill root，不依赖 IM/profile：`bootstrap.py:93-141`；现有 profile 仍是选择真值 | IM 重注册不覆盖已有 skills：`tests/im_service/unit/test_gateway_node_persistence.py:83-128`；真刷新后显式关闭保持：`acceptance.md:28-29,62,72` | aligned |
| `specs/gateway/agent-capabilities.md:86-91` — 显式 allowlist 的飞书 Agent 获得完整 bundle | 静态启动与 managed channel 都复用 `lark_skill_names()` 并只向非空列表补齐：`src/personal_assistant/config/local_store.py:681-714`; `src/personal_assistant/gateway/channel_manager.py:155-192`; `agent_config_sync.py:268-350` | 启动补齐 `test_gateway_launch.py:200-234`；managed 幂等补齐 `test_gateway_im_config_sync.py:602-684`；activation 幂等 `test_channel_manager.py:264-283` | aligned |
| `specs/gateway/agent-capabilities.md:93-98` — 空 skill allowlist 保持默认发现语义 | 静态加载和 managed 调和都在空列表上不物化：`local_store.py:699-711`; `channel_manager.py:173-186`; `agent_config_sync.py:334-339,423-443` | `test_gateway_launch.py:237-260`; `test_gateway_im_config_sync.py:687-724`; `test_channel_manager.py:264-283` | aligned |
| `specs/gateway/agent-capabilities.md:100-106` — 静态 Feishu Agent 的 IM profile ingress 保留 bundle | `config.sync` 在应用前以静态 channel 身份判定并补齐 profile：`agent_config_sync.py:420-443` | `test_gateway_im_config_sync.py:727-815`；connect/reconnect 全量调和 `test_gateway_reconcile_on_connect.py:386-426` | aligned |
| `specs/gateway/agent-capabilities.md:108-112` — 用户明确请求独立 Lark 事件监听 | 随包 `lark-event` 只在明确独立监听时启用，并保留 Gateway 对普通飞书入站/回复的所有权：`src/personal_assistant/builtin_skills/lark-event/SKILL.md:1-20`；`lark-im/SKILL.md:13-21` | bundle manifest/完整安装：`test_builtin_skill_bootstrap.py:324-359`；本项为已有 Lark 运行契约，unit 未改其实现 | aligned |
| `specs/im/agents-nodes.md:5-7` — ADDED `PA 产品说明书 skill 可默认启用和关闭` | 全局 PA skill 投影 `default_on=true`：`upstream_reporter.py:112-142`；IM create/detail 沿用现有 capabilities/profile 选择链：`src/IM/api/routes/nodes.py:244-263`; `agent-create-page.tsx:31-36,374-386`; `agent-detail-page.tsx:1735-1749` | 手册 capability default-on：`test_builtin_skill_bootstrap.py:404-430`；真 UI 创建/关闭/恢复：`acceptance.md:25,28-29,56-63` | aligned |
| `specs/im/agents-nodes.md:9-12` — 新建 Agent 默认选中产品手册 | Gateway 上报手册的 `default_on=true`，IM API/UI 把 default-on 名称物化为创建选择：`upstream_reporter.py:123-142`; `nodes.py:244-263`; `agent-create-page.tsx:31-36,374-386` | `test_gateway_upstream_reporter.py:136-149`; `agent-create.test.tsx:282-361`；真 UI 验收 `acceptance.md:25,60-61` | aligned |
| `specs/im/agents-nodes.md:14-18` — 已有显式选择不因升级改变 | 资源 installer 不写 profile；IM 已有 profile 不被 Gateway 重注册种子覆盖 | `test_gateway_node_persistence.py:83-128`；真升级/重启后产品手册仍未选中：`acceptance.md:28-29,62` | aligned |
| `specs/im/agents-nodes.md:20-23` — 用户关闭或重新开启产品手册 | 详情页直接以 `draft.skills` 为选择与保存真值：`agent-detail-page.tsx:1735-1749`；会话级 `skills` metadata 限制 `skill_view` | 未启用的 skill 被工具强制拒绝：`tests/unit/test_skill_view.py:193-221`；真 UI 关闭后无调用、重开后恢复：`acceptance.md:28,63` | aligned |

### Uncovered Observable Behavior

None. Final unit runtime diff only adds the packaged manual, changes packaged built-in names from missing-only installation to managed full-directory synchronization (including root-wide serialization, `.archive` discovery isolation, recovery/logging), and updates the lifecycle success wording to “synchronized”; these behaviors are covered by the two delta Requirements and their Scenarios. IM, Kernel, and Lark selection/channel mechanisms are reused unchanged rather than extended with an uncovered parallel behavior.

Outcome: aligned

# Round 2

> Validation snapshot: `e6f8b617a7beb1dc68e1a116f368eaf05c764606 → b4dc3bbaf2471a383627b17c373c5135fe2c6f2a`

## Verification Report: feat-502

### Summary

- Mode: `targeted-closure`
- Delta range: `ea59765053a8bc8fb253f5b3f1ae3dc6d73cda0b..b4dc3bbaf2471a383627b17c373c5135fe2c6f2a`
- Focus issues:
  - backup cleanup failure leaves old skill discoverable ahead of canonical directory
  - concurrent Gateways with different config but shared HOME can roll successful refresh back to old directory
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 1/2 focus issues fully closed |
| Correctness | 1/2 focus issues fully protected |
| Coherence | Followed |

0 critical issue(s), 1 warning(s) found. Fix before PR.

## Targeted Closure

### Focus 1: cleanup 失败后旧版 skill 被优先发现

**Closed.** staging 与 backup 现在都位于 skill root 下的 `.archive` 隔离目录（`src/personal_assistant/builtin_skills/bootstrap.py:49-63`）；现有 `SkillRegistry` 在递归扫描时明确剪掉 `.archive`（`src/agent/core/skills/registry.py:41-58`）。故障注入测试让 backup 删除真实失败后，通过正式 `SkillRegistry` seam 确认发现位置仍是 canonical `nanoassistant-docs/SKILL.md`，且描述来自新版（`tests/unit/personal_assistant/test_builtin_skill_bootstrap.py:115-154`）。

### Focus 2: 共享 HOME 的并发 Gateway 可把成功刷新回滚为旧版

**Implementation closed; permanent regression coverage remains incomplete.** `install_builtin_skills()` 现在以 destination root 下稳定的 `.builtin-skills-sync.lock` 作为用户全局锁文件，用 `fcntl.flock(..., LOCK_EX)` 获得跨进程排他锁，并在整个内置 bundle 的目录切换期间持有（`src/personal_assistant/builtin_skills/bootstrap.py:35-46,118-140`）。本轮一次性双进程检查确认：第二进程在第一进程释放锁前不能获得同一 root 的锁，释放后才继续（`CROSS_PROCESS_ROOT_LOCK_PASS`）。这一局部串行化复用现有 PA root，未新建跨包或跨机机制，不触发 full verification 升级。

## Coherence

- `.archive` 复用 Kernel 已有的归档隔离约定，没有为临时目录再造发现排除规则；符合 design D1/D2 对整目录替换、失败恢复和成功项不回滚的约束（`docs/changes/feat-502-pa-product-docs-skill/design.md:75-91`）。
- 锁仅位于 `personal_assistant.builtin_skills` 内，没有增加 `personal_assistant → agent.core/agent.platform` 依赖；针对性架构 contract 5 tests 通过。
- 受影响代码 Ruff check 和 format-check 通过。

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（提 PR 前必须修）

- `tests/unit/personal_assistant/test_builtin_skill_bootstrap.py:157-193` 只把 `_builtin_skill_sync_lock` 替换为观察 context manager，再断言私有 `_sync_skill_directory` 在 context 中被调用；它没有观察两个进程不能交叉切换这个运维结果，而且 `_builtin_skill_sync_lock` 即使退化为 no-op，该测试仍会通过。这不满足 `docs/development/testing.md:9-20` 的可观察 seam 和“不测私有实现细节”要求，也没有把本轮并发回滚失败原因留在永久回归门禁中。请把该测试改为确定性的双进程行为测试：一个进程持有同一 target root 的刷新锁/进入切换段时，第二个进程不得进入切换段，释放后才能继续；或直接编排原始交叉并断言最终 canonical 目录仍是当前包版本。保留在现有 bootstrap 测试 owner 中，不需要增加另一层重复测试。

### SUGGESTION（可以修）

- None.

# Round 3

> Validation snapshot: `e6f8b617a7beb1dc68e1a116f368eaf05c764606 → ffb7ec40b2a17ff196a6b9059e1c0a6ede3847ab`

## Verification Report: feat-502

### Summary

- Mode: `targeted-closure`
- Delta range: `b4dc3bbaf2471a383627b17c373c5135fe2c6f2a..ffb7ec40b2a17ff196a6b9059e1c0a6ede3847ab`
- Focus issues:
  - Round 2 WARNING: root-lock regression test mocks private helper and would pass if real `fcntl` lock became no-op
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 focus issue closed |
| Correctness | 1/1 focus issue protected |
| Coherence | Followed |

All checks passed. Ready for PR.

## Targeted Closure

### Focus: root lock 回归测试只验私有 helper

**Closed.** 新测试通过公开 `install_builtin_skills()` 分别启动两个 `spawn` 子进程（`tests/unit/personal_assistant/test_builtin_skill_bootstrap.py:30-58,191-217`）。第一个 installer 已进入真实 skill 切换段后，父进程对同一 root 锁文件执行 `LOCK_EX | LOCK_NB`，必须收到 `BlockingIOError`，因而直接观察到操作系统级跨进程 lock contention（`:218-232`）。若生产 `fcntl` 锁退化为 no-op，父进程会立即获锁并在 `assert root_lock_is_held` 失败；结论不再依赖 mock 的 context-manager 调用或私有 helper 调用次数。

测试随后启动第二个 public installer，在第一个释放切换段后等待两者完成，断言两个进程都以成功结果退出，最终 canonical `nanoassistant-docs/SKILL.md` 是当前包内容，且锁已可再次获取（`:234-263`）。这一可观察 seam 同时保护“切换期间真实互斥”、“第二 installer 最终完成”和“两进程后 canonical 内容不回滚”三个运维结果。对 `_sync_skill_directory` 的局部替换只用于把第一个真实切换段确定性暂停，不是测试结果的观察点。

## Verification Evidence

- 定向双进程测试连续运行 5 次：5/5 PASS，单次约 0.95–1.36s。
- 整个 `tests/unit/personal_assistant/test_builtin_skill_bootstrap.py`：13 passed。
- Ruff check：PASS；Ruff format-check：1 file already formatted；`git diff --check` 对本轮 delta：PASS。
- 归属合规：测试继续放在现有 bootstrap owner 文件，保护的是稳定的跨进程运维边界；未新建 milestone 命名文件，也未在 integration/e2e 层重复同一失败原因。

## Coherence

- 此 delta 只替换不足的回归测试并追加证据记录，未改变产品实现、spec/design 映射、依赖方向或用户可观察行为，因此不需要升级 full verification。
- `spawn` 进程在当前 macOS/Python 门禁中稳定运行；超时与 `finally` 回收确保失败时不留子进程。

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（提 PR 前必须修）

- None.

### SUGGESTION（可以修）

- None.

# Round 4

> Validation snapshot: `e6f8b617a7beb1dc68e1a116f368eaf05c764606 → 1c90dffdac7d873fa81a005aaa4f01ba29127531`

## Verification Report: feat-502

### Summary

- Mode: `targeted-closure`
- Delta range: `ffb7ec40b2a17ff196a6b9059e1c0a6ede3847ab..1c90dffdac7d873fa81a005aaa4f01ba29127531`
- Focus issues:
  - code-review confirmed: prior process-liveness assertion did not permanently protect whole-bundle lock scope
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 focus issue closed |
| Correctness | 1/1 focus issue protected |
| Coherence | Followed |

All checks passed. Ready for PR.

## Targeted Closure

### Focus: 跨进程证据未单独保护整个 bundle 的锁作用域

**Closed.** 新增 scope 测试从公开 `install_builtin_skills()` 入口运行完整刷新，在一个 root-lock context 内观察每次 skill 目录切换；任何切换移到 context 外都会立即失败，而 `lock_entries == 1` 明确防止实现退化为逐 skill 重新加锁（`tests/unit/personal_assistant/test_builtin_skill_bootstrap.py:192-229`）。它保护的是已有 root-lock 的完整 bundle 作用域，没有改变 production 实现。

现有跨进程测试保护另一个失败原因：第一个公开 installer 进入真实切换段后，父进程的 `LOCK_EX | LOCK_NB` 必须被操作系统拒绝，第二个 installer 在释放前不得进入切换段，释放后两个进程均完成且 canonical 手册仍是当前包版本（`tests/unit/personal_assistant/test_builtin_skill_bootstrap.py:232-312`）。该证据会防止 `fcntl` 锁退化为 no-op，scope 测试则防止真实锁仍存在但锁域被缩窄；两者互补，不重复同一失败原因。

## Verification Evidence

- 两项定向测试联合连续运行 5 次：5/5 PASS，单轮约 2.00–2.33s。
- 完整 `tests/unit/personal_assistant/test_builtin_skill_bootstrap.py`：14 passed（约 2.98s）。
- Ruff check：PASS；Ruff format-check：1 file already formatted；`git diff --check` 对本轮 delta：PASS。
- Delta 仅修改既有 bootstrap unit-test owner 与 unit 证据文档，`src/` 无变更。测试仍位于能暴露 installer 并发失败的最低现有层，未新建平行文件或跨层重复。

## Coherence

- scope 测试的注入 seam 只用于确定性观察整次公开 installer 调用的 root-lock 边界；它不再独自充当真实锁有效性证据，真实运维结果由独立的 OS 跨进程测试承担。
- 本轮 delta 没有修改 spec/design 映射、产品行为、依赖方向或跨进程协议，无需升级 full verification。

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（提 PR 前必须修）

- None.

### SUGGESTION（可以修）

- None.

## Final post-review delta reconciliation

| Delta item | Final implementation and evidence | Outcome |
|---|---|---|
| Gateway ADDED `PA 产品说明书按需回答产品问题` | `SKILL.md` 提供精确触发、来源边界和七主题路由；`references/*.md` 覆盖要求中的全部产品面。场景 GIVEN 已同步为产品 skill + `skill_view` + `read`；真实模型完成入口到单一专题的渐进读取 | aligned |
| Gateway MODIFIED `PA 内置 skill 启动自举` | installer 仍完整替换每个包内目录；`nanoassistant-docs` 的七份 references 作为同目录资源随包复制、升级覆盖和旧文件清理。原事务/锁/失败恢复测试继续通过，产品手册也加入 managed replacement 测试 | aligned |
| IM ADDED `PA 产品说明书 skill 可默认启用和关闭` | skill 名、frontmatter、global-root default-on 和显式 profile 语义未变；资源拆分不改变 capability/UI/API | aligned |

最终 delta 与 canonical Gateway/IM specs 一致，没有新增 Kernel 或 CLI delta，也没有遗漏新的用户可观察行为。
