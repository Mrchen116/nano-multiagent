# bugfix-518: Gateway-owned skill distillation

## Relations

- Related: feat-515

## 原始报告

> 我日，这确实是个缺陷。分开一个unit修这个问题。生成skill这个功能应落在gateway侧，而不是IM侧。gateway自己读自己机器的jsonl，去做蒸馏

## 澄清记录

- Q1: Agent 创建请求已发到 Gateway、但响应在返回 IM 前断线的恢复逻辑属于哪里？
  A: 这是 Workspace Root 创建流程的问题，保留在 `feat-515`；本 unit 不改变该 recovery。
- Q2: 从会话生成 skill 时，谁拥有 transcript 的读取和蒸馏执行？
  A: 拥有来源 Agent 的 Gateway 读取自己机器上的 JSONL 并完成蒸馏。**v5 用户澄清**：为保持当前
  prompt/skill 行为，产品允许 Gateway 生成的本机 absolute paths 出现在 IM、browser 和普通聊天消息中，
  但只可用于由 IM 固定到同一 Gateway 的 execution conversation。IM 永远不读取、扫描、解析、生成路径，
  也不以路径决定选择资格。
- Q3: 当用户选中多个来源时如何跨节点？
  A: 一次蒸馏只使用同一个 Gateway 的来源和执行 Agent；跨 Gateway 的会话不得被拼成一次本机蒸馏。

## 现象与复现

1. IM 部署在机器 A，某 Agent 的 Gateway 及其 workspace 部署在机器 B；该 Agent 已完成一个含 kernel session JSONL 的 Web IM 会话。
2. 用户在 Web IM 的 conversation 列表进入“生成 skill”，选择该已完成会话。
3. 现有实现由 IM 根据 AgentProfile 中的 `workspace_root` 在机器 A 扫描 `.nanoassistant/sessions`，并把发现的绝对 JSONL 路径预填到普通聊天消息。

期望：只要来源 Gateway 在线且本机保有该会话记录，用户可以从该会话生成 skill；读取和蒸馏在机器 B 完成。

实际：机器 A 无法访问机器 B 的 workspace，IM 将来源判成无 transcript，或依赖把机器 B 的绝对路径重新经 IM 与聊天消息传递。跨机部署下，用户无法完成“生成 skill”。

## 影响范围

- 使用独立 IM 与远端 Gateway 的用户不能从该 Gateway 的会话生成 skill，即使会话记录实际存在。
- IM 不能拥有或访问 Gateway 本机文件地址；当前由 IM 扫描路径既造成不可用，也把文件系统 owner 放错了。
- 普通聊天、中继消息、已有 workspace root，以及 `feat-515` 的 Agent 创建断线恢复不受本问题影响。

## 根因分析（RCA）

历史会话蒸馏把“选择来源会话”错误实现为“由 IM 解析来源 Agent workspace 中的文件路径”。AgentProfile 保存的 workspace root 属于 Gateway 的本机配置，不是 IM 可访问的共享文件系统；IM 的 repository 因而既扫描了不属于自己的目录，又将扫描结果作为 prompt 字段交给执行 Agent。该边界在单机开发环境中看似成立，部署为 IM 与 Gateway 跨机后即失效。

此前为 Workspace Root 功能补入的 session-log 查询、状态投影和跨节点选择，试图让 IM 继续编排这条文件路径链路，扩大了 `feat-515` 的范围，却没有消除“IM 负责 transcript”的错误所有权。创建 operation 的断线恢复与该根因无关，仍留在原 unit。

## 修复方向

- IM 只负责让用户选择已结束会话、按 Agent owning Gateway 路由一次 prompt 请求和展示结果；它不读取 workspace、扫描 JSONL、解析或生成 JSONL 路径。
- Gateway 以稳定的 conversation / Agent 身份解析自己的 durable session binding，在本机生成当前格式的 distill prompt；后续由该 Gateway 的 execution Agent 按普通聊天执行 `conversation-skill-distiller`，技能写入沿用用户已选择的 agent 或 global scope。
- 一次操作限定在一个可路由 Gateway。来源会话和 execution Agent 不在同一 Gateway 时，Web IM 明确阻止该组合，而不是尝试跨机拼接文件。
- Gateway 无法定位记录、来源正在运行、execution Agent 不具备所需 skill/tool，或 Gateway 离线时，用户在创建 execution conversation 前得到可理解的失败或不可用反馈；不得把暂时的路由/连接问题误报为“无 transcript”。
- 回归覆盖必须在 IM 与 Gateway 文件系统彼此不可见的拓扑下证明完整旅程，并证明 JSONL path 只能由 Gateway 生成、且 prompt 随固定同节点 execution conversation 回到生成它的 Gateway；IM 不得扫描或读取该文件。
