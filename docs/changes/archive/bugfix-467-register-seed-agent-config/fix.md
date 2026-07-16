# bugfix-467: node.register 播种 agent skills/tool_allowlist，消除 reconcile 空壳碾压

## Relations

- Closes: #201
- Related: #203（工具链三缺口，独立 unit 处理）、refactor-463（问题发现现场，非引入方）

## 原始报告

> 为啥我这个agent没开这些skill，也能/出来。http://100.92.244.68:51799/settings/agents/plato显示没开这些skill

> edit工具，missing required tool args 是为啥？是模型弄错了吗？是不是工具描述写的有问题？

> 那肯定是错了呀。为什么没有工具呀？

> 理论上是应该要有工具的呀。是不是重构弄错了？

> 查明原因。如果重构引入的，帮我修。如果不是，提issue

> 分析是哪个/哪些unit导致的问题，之前没有这一系列的问题，包括skill，tool的问题

> 空 = 零工具没问题啊，问题是为什么空吧

> 我觉得这种你这种设计可能不太合理。其实是不是除了我们这种worktree测试场景，其他场景都遇不到？是的话就改我们测试。首次保存就V2也让用户很疑惑

> 好这个不错。

GitHub issue：https://github.com/Mrchen116/nano-multiagent/issues/201 （含完整机制链与真栈实测证据）

## 澄清记录

- Q1: 修复语义——PR #195 的「空 allowlist = 零工具」是否需要回退？
  A(原话): 空 = 零工具没问题啊，问题是为什么空吧
  Agent 解读: 语义保留不动，修复对象是「空是怎么来的」。

- Q2: 修复路线——「reconcile 跳过空碾压 / v1 空壳 vs v2 用户写过的空 启发式」还是「只改测试」？
  A(原话): 我觉得这种你这种设计可能不太合理。其实是不是除了我们这种worktree测试场景，其他场景都遇不到？是的话就改我们测试。首次保存就V2也让用户很疑惑
  Agent 解读: 用户否定启发式。但「只有测试场景遇到」不成立——生产上「yaml 新增 agent 首次接入已有 IM」与「IM DB 重建」同样触发，且主 config 历史上被静默抹空过一次（R4-era 验收栈会话 tools=0 为旁证）。只改测试不充分。

- Q3: 那改成什么？
  A(原话): 好这个不错。（针对「node.register 携带 per-agent skills/tool_allowlist，IM 按 first seen wins 播种，mirror 出生即真值，不需要任何启发式」方案）
  Agent 解读: 用户拍板注册播种路线。

## 现象 / 复现

环境：全新 IM（空 DB）+ Gateway，其 config.yaml 中 agent 配了非空 `skills` / `tool_allowlist`（如 plato 配 3 个 skill、11 个工具）。worktree e2e、CI、新部署、yaml 新增 agent 首次接入已有 IM、IM DB 重建后重连，都是同一环境形态。

1. **skills 显示分裂**：聊天页 `/` picker 列出全部 capabilities 技能（应只列 enabled 的 3 个）；设置页 `/settings/agents/plato` 显示全部未启用。
2. **工具全灭**：该 agent 全部 LLM 请求不含 `tools` 字段（proxy 日志实测 31/31 请求 tools=0）；模型按训练惯例自由发挥调用 `edit(path, old_string, new_string)`，与 schema `oldText`/`newText` 不匹配，每次报 `missing required tool args`，原地重试死循环，任务卡死。
3. **真值源被毁**：reconcile 把抹空的配置 persist 回 config.yaml（skills 键丢失）；之后某次 token 刷新又用启动时旧 config 对象写回，文件与内存状态分叉。
4. **设置页 tools 假象**：detail 页显示 11 个默认工具全亮（useDefaultOn 旧语义渲染），与实际零工具矛盾——该缺口归 #203 处理，不在本 unit。

实测证据（worktree ephemeral IM，refactor-463 分支，main 同逻辑）：
- `GET /im/v1/agents/plato/config?source=mirror` → `skills: []`、`tool_allowlist: []`、`profile_version: 1`
- `GET /im/v1/agents/plato/config?source=live` → 同样全空（16ms 返回，非超时回退）
- 此时 config.yaml 文件里 plato 仍有 3 个 skills / 11 个 tools

## 根因

**直接机制链**：`node.register` 只上报 `agent_id` + `workspace_root` → IM「first seen wins」建空壳 profile（skills/tool_allowlist 空，v1）→ Gateway 连上后 `reconcile_all_agents` 全量对账，本地内存版本视作 0（yaml 加载的配置无 version 概念），IM 空壳 v1 必赢 → 内存 skills/tool_allowlist 被抹成 `[]` 并 persist 回 yaml → 会话能力投影 `resolve_enabled_tools`（语义：空=零工具）→ LLM 请求零工具声明 → 模型无 schema 自由发挥 → edit 参数名惯例冲突死循环。slash picker 侧则是「空白名单=全部技能」语义把被抹的空白名单渲染成全量。

**为什么这种错能进来**：reconcile（feat-394/M12）的设计假设是「IM 里的 profile 是完整真值」，但注册路径从未向 IM 播种 skills/tool_allowlist——该假设在持久 IM（用户在 UI 保存过，mirror 有真值）下碰巧成立，在全新 IM 下必然不成立。测试盲区：e2e/验收旅程未覆盖 edit 的真栈调用，且 K2.6 无 schema 时按惯例自由发挥的 read/bash 参数名恰好兼容，零工具声明被长期掩盖（R1-era 验收栈会话 tools=14 是 reconcile 404 跳过的偶发幸存，R4-era 已全为 tools=0）。

**回归引入点定位**：
- 根因引入：`2e7256ae7`（feat-394/M12，06-08）首次引入 reconcile 覆盖语义。
- 症状激活：`90c8b82eb`（feat-430/M1，06-27）slash picker 走 source=live 激活 skills 显示分裂；`69cf5c80b`（PR #195，07-15）`resolve_enabled_tools` 从「空→默认工具集 fallback」翻转为「空=零工具」激活 tools 全灭（该语义保留，不回退）。

**原始设计意图追溯**：reconcile 来自 feat-394/M12 决策 F——断线期间的 `config.sync` 增量推送会丢，丢一次就永久停在旧配置，所以 WS 连上后按 profile_version 取大收敛，保证「IM 是权威，丢的推送最终补上」。**修复必须保住的不变量**：用户在 UI 的修改——包括特意清空（v2+ 的空 `[]`）——必须在 Gateway 重启/断线后正确收敛到内存与 yaml；不得为消症状引入「空值永不覆盖」类规则破坏该收敛。

**修复方向（已与用户对齐）**：把空壳消灭在源头——`node.register` 携带 per-agent `skills` / `tool_allowlist`，IM 按既有「first seen wins」模式（同 `agent_workspaces`）在建 profile 时播种，mirror 出生即真值（v1 就是 yaml 真值，无空壳、无启发式）。约束：
- 只在 profile **创建时**播种；已存在的 profile 不被注册负载覆盖（否则用户在 Gateway 离线期间特意清空后，重连会被播种回填，破坏上述不变量）。
- reconcile 的版本比较规则不动；`resolve_enabled_tools`「空=零工具」语义不动。
- 本 unit 之前已存在于旧 DB 的空壳 profile 不在处理范围（一次性 UI 保存即可修复），不引入 version 启发式。
- token 刷新 persist 持有启动时旧 config 对象导致文件/内存分叉的问题，另起独立 bugfix 处理（Refs #201）。

## 修复

把空壳消灭在源头：

1. `src/personal_assistant/reporter/upstream_reporter.py` 的 `UpstreamReporter.send_register()` 在 `node.register` 帧中新增两个 per-agent 映射字段：
   - `agent_skills: {agent_id: [skill_id, ...]}`
   - `agent_tool_allowlist: {agent_id: [tool_name, ...]}`
   值直接来自本地 `AgentWorkspaceConfig.skills` / `tool_allowlist`，因此 mirror 出生即 yaml 真值。

2. `src/IM/ws/gateway_handler.py` 的 `_handle_register` 解析上述两个字段并透传给 `GatewayNodePersistence.register()`；缺失或格式异常时降级为空种子，不影响旧 Gateway 兼容。

3. `src/IM/infra/gateway_persistence.py` 的 `GatewayNodePersistence.register()` 新增 `agent_skills` / `agent_tool_allowlist` 参数，仅在 `existing is None`（profile 首次创建）时使用种子值写入；已存在 profile 保持现有 skills / tool_allowlist 不变，保护用户在 Gateway 离线期间特意清空的收敛。

不变量保留：
- reconcile 的版本比较规则未动。
- `resolve_enabled_tools`「空=零工具」语义未动。
- 未引入 v1/v2 启发式区分空壳 vs 用户清空。

相关提交：
- `7a5b8bd82` test(bugfix-467/M1/R1): 注册播种 skills/tool_allowlist 红测试
- `573dd6185` fix(bugfix-467/M1/R2): node.register 携带 skills/tool_allowlist 并在 IM 创建 profile 时播种

## 验证

- 单测：
  - `tests/unit/personal_assistant/test_gateway_upstream_reporter.py::test_send_register_includes_agent_skills_and_tool_allowlist`
  - `tests/im_service/unit/test_gateway_node_persistence.py::test_register_seeds_skills_and_tool_allowlist_on_create`
  - `tests/im_service/unit/test_gateway_node_persistence.py::test_register_does_not_overwrite_existing_profile_skills_and_tool_allowlist`
  - `tests/im_service/unit/test_gateway_handler.py::test_register_parses_and_seeds_agent_skills_and_tool_allowlist`
  - 相关套件共 76 passed。

- Live 真栈验证（worktree ephemeral IM + Gateway）：
  - 启动：`cd .worktrees/bugfix-467-M1 && ./scripts/e2e-up.sh`
  - `GET /im/v1/agents/plato/config?source=mirror` 返回 `skills: ["change-spec-author", "change-design-author", "change-orchestrator"]`、`tool_allowlist: ["read", "write", "edit", "bash", "agent", "task_stop", "web_fetch", "web_search", "skill_manage", "skill_view", "memory"]`、`profile_version: 1`，mirror 出生即真值。
  - `GET /im/v1/agents/plato/config?source=live` 同样非空，reconcile 后 live 源也保持真值。
  - 原始症状（mirror v1 空壳 skills=[] / tool_allowlist=[]）消失。
  - 证据文件：`docs/changes/bugfix-467-register-seed-agent-config/M1-fix/evidence/plato_config_curl.json`
  - 收尾：`./scripts/e2e-down.sh`
