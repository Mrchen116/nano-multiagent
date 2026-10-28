# 证据、出处与不能推出的结论

## 证据层级

A：项目自己的公开实现或官方产品文档。B：研究者的一手黑盒实验／社区提取的运行材料。C：独立复刻，只证明复刻自己的实现。U：用户提供的本地调研，本文保留其版本与限制，未重新执行用户本机实验。

## 核心来源

| 编号 | 材料 | 此次实际使用的内容 | 边界 |
|---|---|---|---|
| S1 | [Dhravya Shah 的 Instinct 实验](https://supermemory.ai/blog/reverse-engineering-instinct-memory/) | One-pager 的 Life Context / Autonomy Calibration / Channel Communication Style；Markdown 的 id/type/aliases；目录与更新观察 | B。没有官方源码；One-pager 的完整生成提示、来源选择、固定调度未知。检索行为不能证明绝对没有其他后端。 |
| S2 | [Rohan Adwankar 的沙盒实测](https://rohanadwankar.github.io/posts/platforms.html#instinct) | /memory Git 文档库；实体与知识当前态、时间线与交流经历的分工；文件变大时的索引惯例 | B。账户快照，不是所有用户固定结构；Git 作者不能证明哪种运行身份有写权限。 |
| S3 | [Muse 初始 MEMORY.md](https://github.com/asgeirtj/system_prompts_leaks/blob/main/Meta/muse-agent/MEMORY.md) | Facts / Preferences / Commitments 三栏的稀疏初始模板 | B。不是成熟用户的完整常驻上下文，不能据此声称其他文档都不注入。 |
| S4 | [Muse USER.md](https://github.com/asgeirtj/system_prompts_leaks/blob/main/Meta/muse-agent/USER.md) 与 [PROACTIVE_PREFERENCES.md](https://github.com/asgeirtj/system_prompts_leaks/blob/main/Meta/muse-agent/PROACTIVE_PREFERENCES.md) | 人物背景与主动通知主题、时机、表达方式有各自文件 | B。字段用途有直接材料，但未获得完整生产注入算法。 |
| S5 | [Muse self_improvement.md](https://github.com/asgeirtj/system_prompts_leaks/blob/main/Meta/muse-agent/docs/self_improvement.md) | 有新信号时的定期记忆维护、关系维护、夜间反思分开描述；后台不取代前台记录 | B。快照中的周期是产品说明，未独立运行调度器验证。不同镜像的相同文件不是两份独立证据。 |
| S6 | [Muse 社区系统提示 §7](https://github.com/RomanSlack/Meta_Muse_Agent_System_Prompt_Tools/blob/0f037a518b68d92bbc29f3ae95a8745852ed5cd5/system-prompt-master.md) | 提示规定何时读写记忆、人物／群体笔记与及时纠正 | B。整理版、未获官方认证；不是本文建议原样照搬的系统提示。 |
| S7 | [Dots Dreamer](https://github.com/asgeirtj/system_prompts_leaks/blob/main/OpenAI/dots/dreamer.md) | 后台研究、父会话读取、用户笔记／研究笔记／行动清单分离；按检查点接续；不直接修改正式用户笔记，不直接联系用户 | B。最近两小时是研究覆盖目标，不等于两小时一次的已验证调度。首次约四周的研究范围不是 Nano 的默认全历史导入。 |
| S8 | [Dots 官方 Tasks and memory](https://learn.chatgpt.com/docs/dots/tasks-and-memory) | 个人笔记、历史上下文与后台研究有不同职责；研究发现交给主助手 | A。未公开完整主助手常驻记忆模板。不能用 Dreamer 推断它。 |
| S9 | [Raft 的工作区／记忆指导](https://github.com/botiverse/raft-source/blob/a98ae003246a0360872a77d76dec2fccd0347ef7/packages/shared/src/raftCliGuide.ts#L537-L606) | Role / Key Knowledge / Active Context；领域知识、工作历史、频道背景、其他 Agent 协作 | A，固定快照。适合独立数字员工；其示例 user-preferences 仍须按 Nano 的多人关系收窄。 |
| S10 | [memoryrepo](https://github.com/supermemoryai/memoryrepo/blob/main/src/server/memory.ts) | 入口＋主题文件；在线文档编辑与 Dreamer；冲突重读；读源再整理 | A，仅指该开源实现。不是 Instinct 源码；一行一条、远端推送不照搬。 |
| S11 | 用户附件《【开源agent关键设计总结】 memory.md》 | Codex 分层与工作摘要，Claude Code 的 Why/How to apply、Auto-dream 触发与输入，Hermes 与 Raft | U。特别是 Claude Code 2.1.283 的本地功能门控与“24h＋五个会话”，没有重新在用户电脑上验证。 |
| S12 | [Nano 上下文接入](https://github.com/Mrchen116/nano-multiagent/blob/a5724f2124acc345783f5b91f293f62204881902/packages/dsh-integration/src/agent-context.ts) 与 [锁定依赖](https://github.com/Mrchen116/nano-multiagent/blob/a5724f2124acc345783f5b91f293f62204881902/packages/dsh-integration/package.json) | notes/history/new_context/get_context_remaining；使用 rc.5 的上下文引擎 | A，代码读取，未执行。 |
| S13 | [dsh-agent-context rc.5 README](https://github.com/Mrchen116/dsh-agent-context/blob/v0.3.0-rc.5/README.md) | 换窗不调用摘要模型；原始持久事件仍在；window ID 与 event seq；history 不读取活跃项；子会话 namespace 不同 | A，固定快照的公开契约。生产历史导出适配仍需故障、权限和跨窗测试。 |

## 本轮不能冒充竞品结论的设计决定

- PA 与独立专家的八栏入口、具体目录 profile、工作记录触发条件是针对 Nano 的选择。
- 不再设 cases 强制目录；不是否认情景经验，而是用时间／工作标识提供可判定的记录位置。
- 24h 的整理间隔、10 分钟静默优先、单主体串行作业是初始工程配置，不是共同最优值。
- 用 session+事件序号作为增量位置，是对 Nano Global 模式的适配，不是已证明 Dots 采用同样算法。
- 从文件里查信息与权限隔离是两回事；当前共享 OS／shell 不能仅靠提示实现强隔离。
