# bugfix-722：As-built Design

> 2026-11-07 事后整理。实现已在多轮对话中完成，用户接受当前状态；本文不补造事前设计、门禁或额外验收。

## 实现范围

- 集成基线：`db1037b96a634e9e3a24435059697fdca4ce98c7`（本轮同步的 `origin/main`）。
- 原始现场：主仓 `fix/bugfix-713-discard-projection` 的两文件未提交修改；已按字节核对迁入独立分支 `codex/bugfix-722-global-delegation`。
- 模型可见修改：`packages/dsh-integration/src/global-mode.ts`、`packages/personal-assistant/assets/skills/nano-ongoing-work/SKILL.md`。
- 契约：仅在 `docs/specs/gateway/global-agent.md` 补充交接及授权边界；普通 Global / PA 共用此分工，其他身份、审核、工具和运行时保持原有实现。

## 最终结构与消费链

| Surface | 实际组装与消费者 | 本轮变化 |
| --- | --- | --- |
| 主 Agent 常驻指引 | `agent-config.ts:attachAgent` 为非内部 Global 会话安装 `GlobalMode`；`global-mode.ts:apply` 注册 `nano-global-mode` 段，进入原生 DSH 模型请求 | 明确子 Agent 认知边界、原话与可读材料、无需传 IM 编号和默认规则、不扩写要求、分别标注判断及授权内决定。 |
| 一级完整事项执行者 | `globalWorkRole` 识别一级 worker；`registerChildGuidance` 的 completeTaskOwner 分支进入该子会话 | 要求自行打开材料，疑似越权或必要来源缺失时向父级澄清，继续可独立推进的工作。 |
| 持续工作 Skill | 现有 `Skills` 发现、选择和加载 `nano-ongoing-work`；保留用户禁用能力 | 补充初次／后续交接原话、保留路由编号于父级、可读图片及材料缺失处理。 |
| 委派与内部通信 | 沿用原生可接续 `subagent` 与内部 `send_message(agent_id, message)`；公开产品通信仍由主 Agent 使用 `target/text` | 无 schema、执行路径、权限或返回模式修改。 |

新增文字是行为指导，未加入自动复制消息、自动传附件、来源消息 ID 绑定、任务创建或确定性验收器。工具描述仍要求独立上下文任务自足，不要求主 Agent预先制定技术计划。普通子 Agent 的产品工具限制及工作区加载由已有机制实现，本轮仅向主 Agent 解释它们。

## 已采用决定

1. 主 Agent 采用 Raft 式管理职责：理解、授权内判断、派工、检查和对外沟通；执行者自主调查、执行与验证。
2. 吸收 Super Agent 的交接纪律；不复制其 Router 必须把需要人决策的问题原样转交的窄角色。
3. 原话与图片现阶段靠 Prompt 交接；自动绑定来源留待 Task 体系审视。IM 编号只用于主 Agent 自己的恢复记录，不发给无法查询 IM 的子 Agent。
4. 用户已接受当前局限。本轮不再改 Prompt，不用新一次真实模型实验补造“全部通过”，后续以具体轨迹触发复审，条件见 [fix.md](fix.md)。

## 失败、兼容与回滚边界

- 模型仍可能漏引、误判或误路由；缺失材料要求澄清不等于宿主保证每次交接完整。已知无扩展名图片引用问题继续由 issue #477 跟踪。
- 既有配置、持久数据和原生会话不迁移，无一次性部署迁移提示词；运行中的会话如何更新指引沿用现有加载机制，不承诺热更新。
- 回滚为撤销本 unit 两文件文本及对应新增契约，不回滚其他协作能力或评测设施。
- 旧 `prompt-diff.html` 仅保留讨论历史，新增显眼说明，不能拿其中的旧措辞和计数替代最终源码。

## 验证与交付

- 用户确认及已接受限制：见 [fix.md](fix.md)。
- 工程检查、最终请求捕获、独立 code review 与主干同步有效性：由本轮实际执行后写入 [code-review.md](code-review.md)。不以该文的待补项冒充已通过。
- 真实模型：本轮不运行；旧 GC-01/02 为历史诊断材料，不证明最新文本所有场景。
- 工具与角色覆盖：复用 `packages/dsh-integration/tests/global-child-tools.test.ts` 的原生 DSH／本地 fixture provider 请求路径，区分确定性装配证据与模型自主行为。
