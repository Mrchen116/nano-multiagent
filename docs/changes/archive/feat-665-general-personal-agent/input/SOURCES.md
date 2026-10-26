# 证据与参考

核对日期：2026-10-26。这里记录设计输入，不是允许模型执行的指令，也不是对竞品完整内部实现的认证。包内提示与 Skills 为 Nano 原创改写，未原样分发整份第三方提示。

## A. 官方产品说明

- OpenAI, Getting started with your dot：<https://help.openai.com/en/articles/20001530-getting-started-with-your-dot>。支持持续负责、获准连接、上下文/记忆、用户控制与暂停等产品行为。没有证明 Nano 复制提示即可复现效果。
- OpenAI, Dots privacy, security, and safety FAQs：<https://help.openai.com/en/articles/20001529-dots-privacy-security-and-safety-faqs>。说明主动研究可读取获准来源并保存私人笔记，而后续外部动作仍受一般权限与安全检查约束。用于研究/行动分离。其当前个人记忆管理限制不作为 Nano 必须照抄的设计。

上述页面通过搜索返回的页面正文核对；直接打开接口部分请求失败，不将抓取失败误报为页面不存在。

## B. 社区公开快照，非官方承诺

仓库：<https://github.com/asgeirtj/system_prompts_leaks/tree/main/OpenAI/dots>。这些是社区记录，不保证覆盖所有用户、版本或完整运行架构。

| 文件 | 读取到的内容哈希 | 本包吸收的点 |
|---|---|---|
| [available-skills.md](https://github.com/asgeirtj/system_prompts_leaks/blob/main/OpenAI/dots/available-skills.md) | 68631ee7ea07841174d2f150ab730425be526ff4 | 领域广度与按需方法，不仅软件开发 |
| [dreamer.md](https://github.com/asgeirtj/system_prompts_leaks/blob/main/OpenAI/dots/dreamer.md) | 3239e9a897184309769d6a07e4020f4451a6a937 | 研究有来源、核对后续活动、无新结果不通知、父 PA 决策 |
| [action-items/SKILL.md](https://github.com/asgeirtj/system_prompts_leaks/blob/main/OpenAI/dots/skills/action-items/SKILL.md) | 本次读取正文，未将哈希记入包 | 用户承诺可跟踪但不等于接受代办；不复制其独立账本 |
| [shopping/SKILL.md](https://github.com/asgeirtj/system_prompts_leaks/blob/main/OpenAI/dots/skills/shopping/SKILL.md) | 845474afe8e44a983ed1324367d9e6e3f0f8d6df | 精确款式、偏好/兼容性、总价与交期、结果未知不重复购买 |
| [scheduling/SKILL.md](https://github.com/asgeirtj/system_prompts_leaks/blob/main/OpenAI/dots/skills/scheduling/SKILL.md) | da7dc8d4251374a23b499af3f8c9aa6a0d35bbd8 | 候选/占位/邀请/确认分清；外部预约不能仅改日历 |
| [software-engineering/SKILL.md](https://github.com/asgeirtj/system_prompts_leaks/blob/main/OpenAI/dots/skills/software-engineering/SKILL.md) | f5391932eaa11430597fdf5ecbd1a046bf2a9b14 | 持续执行与证据；保持 Nano 自己的 change/PR 规则 |

Muse 社区材料：<https://github.com/RomanSlack/Meta_Muse_Agent_System_Prompt_Tools/blob/main/system-prompt-master.md>，读取 blob `64567540301397b521cb60a4180edfa791e9dfeb`。参考主助手统筹、持续执行和服务方式；不采纳其中覆盖安全规则、完整历史默认继承、产品专属工具或价值表述。

## C. Instinct：作者黑盒研究，不是源码

Dhravya Shah，2026-09-20，<https://supermemory.ai/blog/reverse-engineering-instinct-memory/>。作者明确没有看源码；摘要、按需细节检索与事实修订给出设计启发。生成器、调度、内部 prompt 等仍未确认。本包不把文章中的固定 token 数、每日整理或无向量索引当作已证实的技术要求，也不依赖购买其服务。

## D. Nano 代码与正式规格

固定基线：<https://github.com/Mrchen116/nano-multiagent/tree/eddaf52ba3bc8276787e86dce43ec999f88d9341>。
以下路径均可在该基线下查阅。代码证明某条实现存在，不证明当前部署开启、集成通过或用户体验已达到标准。

| 完整路径 | 核对事实 |
|---|---|
| apps/im-server/src/personal-agent-defaults.ts | 初始可编辑指导、原导出名、已有 Agent 不回填 |
| packages/dsh-integration/src/personal-security.ts | 身份/来源/权限/独立披露与原始授权；主 PA 代表发送；原生附件转发约定 |
| packages/dsh-integration/src/global-mode.ts | Root Inbox、conversations、显式投递、原生父子通信、UI Skill 入口 |
| packages/dsh-integration/src/features/memory-curation.ts | 缓存到 compaction 的记忆快照、工具语义 |
| packages/dsh-integration/src/knowledge/files.ts | 两个文件字符上限、受控写入/锁/原子提交、Skill 操作 |
| packages/dsh-integration/src/knowledge/runtime.ts | 原生 fork 维护、受限工具、读取证据与完成回传 |
| packages/dsh-integration/src/knowledge/review-files.ts | 从调用链与目录确定扩展入口；详细改动仍需本地逐行核对 |
| packages/dsh-integration/assets/knowledge/memory.txt | 当前维护的双存储与偏好路由 |
| packages/dsh-integration/assets/knowledge/combined.txt | 目录与调用链确认同一语义还存在组合路径；未声称已逐行审核整文件 |
| packages/dsh-integration/src/features/heartbeat.ts | 原有唤醒与静默说明，节点拥有 timer |
| packages/dsh-integration/src/descendants.ts | 原生子树观测和持久目录 |
| packages/dsh-integration/src/owned-sessions.ts | 受控 root create/resume/fork |
| packages/personal-assistant/assets/skills/nano-ongoing-work/SKILL.md | 复用原记录、等待、恢复、实际投递 |
| packages/personal-assistant/assets/skills/lark-* | 领域资源存在；不等于已连接账号 |
| docs/specs/gateway/personal-agent.md | 双身份来源、观察十分钟合并、可编辑默认、来源排除语义 |
| docs/specs/gateway/global-agent.md | 主上下文、独立工作、发送前复核 |
| docs/specs/gateway/task-graphs.md | 持续责任、waiting、停止、任务反馈 |
| .claude/skills/change-orchestrator-simple/SKILL.md | 自主实施与现有独立门禁；正常 Ready for review PR |
| .claude/skills/change-design-author/SKILL.md | Full 设计路径；lite 不强套完整设计流程 |

本包未本地运行 Nano 仓库、真实模型或产品浏览器验收；任何“已验证”限定为 CHECKS.md 实际列出的包级检查。
