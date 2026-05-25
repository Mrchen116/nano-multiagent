# M5: fix-persistence-and-create-page

## 目标

修复 round 1 reviewer 发现的 4 个 issue:
1. (ISSUE-2, blocking) features/custom_prompt 未在 IM PATCH /config 持久化
2. (ISSUE-3, major) features 门控未真正影响组装(被 ISSUE-2 遮蔽;根修后验证)
3. (ISSUE-1, blocking) agent-create 页未迁移到 Behavior card 新设计
4. (ISSUE-4, minor) capabilities default_system_prompt 仍旧格式

## 退出标准

1. PATCH /im/v1/agents/{id}/config 接受并持久化 features/custom_prompt;GET 能读回
2. 重启 IM+Gateway 后 features/custom_prompt 仍保持(通过 Gateway config.yaml 写回)
3. features 门控有效:带 memory 工具的 agent,memory_curation on→prompt 含 core.memory_guidance,off→不含
4. agent-create 页 Behavior card 含 Custom Instructions textarea + Features 开关组(按 capabilities.features 渲染)+ Group Reply Policy + Preview
5. capabilities default_system_prompt 更新为段式结果或废弃(明确查清后定)
6. 全量测试与基线 diff: 新增 failed 数 = 0

## 测试策略

- R1 (IM PATCH/GET 字段修复): HTTP 入口测试 — PATCH 含 features+custom_prompt → GET 读回一致
- R2 (AgentConfigResponse 新增字段 + to_agent_config_response 更新): 单元测试
- R3 (Gateway 收 agent-update 写回 config.yaml): 集成测试 — sync_agent 含 features 字段后 config.yaml 含对应内容
- R4 (ISSUE-3 features 门控验证): 单元测试 — memory_curation on/off 时 section 出现/不出现
- R5 (ISSUE-1 agent-create 页 Behavior card): 浏览器验收 + 组件/交互测试
- R6 (ISSUE-4 default_system_prompt): 确认无消费方则废弃该字段或更新

## UI 状态矩阵 (agent-create Behavior card)

| 状态 | 覆盖情况 |
|---|---|
| default (无 capabilities) | loading spinner |
| capabilities 返回 features 列表 | Features 开关组渲染 |
| feature available=false | checkbox 禁用 + tooltip |
| Custom Instructions 空 | 可选，不报错 |
| Custom Instructions 有内容 | 随 draft 传入 create payload |
| Group Reply Policy | Select 保留 |
| Preview 折叠 | 按 aria-expanded 模式 |
| mobile viewport | N/A (create 页非核心移动场景) |

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | IM PATCH/GET — UpdateAgentConfigRequest 加 features+custom_prompt 字段 | DONE |
| R2 | AgentConfigResponse 加 features+custom_prompt + to_agent_config_response 更新 | DONE |
| R3 | 验证 Gateway sync_agent features 写回 config.yaml 链路 | DONE |
| R4 | ISSUE-3: 验证 features 门控真正影响 assemble_system_prompt | DONE |
| R5 | ISSUE-1: agent-create-page Behavior card 重构(Custom Instructions + Features + Preview) | DONE |
| R6 | ISSUE-4: capabilities default_system_prompt 废弃/更新 | DONE |
