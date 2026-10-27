# PR #414：定向审查与拆分建议

审查版本：`66b49e4e0fa6be17a87466ef04fa2cbf1d4007f7`。
比较基线：`85910853ebe4a7a22c5b761029cf46da2f78cd5a`（PR metadata 中的 main）。
PR：https://github.com/Mrchen116/nano-multiagent/pull/414

## 结论

建议暂不合入当前大 PR。从 main 建独立分支，按行为和依赖拆取改动，不只是把已有大分支拆成几个 commit。当前 PR 涉及 122 个文件、8,764 行新增；问题不在行数本身，而在于把 PA 服务行为、执行权限、持久数据权威、记忆遗忘、消息投递和调度协议同时改变。

第一步做通用 PA 服务指导、持续负责与受限主动准备；新记忆后端、统一 personal_context、关注项通知协议都不是这一目标的先决条件。现有实现的“执行子 Agent”也不能原样先合入，因为它不支持用户要求的二级委派和相关 Skills。

这是静态代码与测试/评测材料的定向审查，不是全部 122 个文件的安全认证。已核对上述 head 的 GitHub Actions CI 为 success；没有在本环境重跑 Nano 整仓测试或真实模型端到端测试。附带脚本只对两段纯逻辑做合成最小复现，不冒充项目测试通过。

## 发现 1 — P1：执行子 Agent 的能力被削到无法承担完整工作

位置：`packages/dsh-integration/src/personal-delegations.ts`，`permitted`、`configure()`。

源码：
https://github.com/Mrchen116/nano-multiagent/blob/66b49e4e0fa6be17a87466ef04fa2cbf1d4007f7/packages/dsh-integration/src/personal-delegations.ts

执行角色的固定白名单只含 read/glob/grep/write/edit、web_search/web_fetch、send_message、notes/history/new_context/get_context_remaining。guard 拒绝其他工具。返回配置又设为 `skillRoots: []`、空的 skill allowlist，以及全部 Feature=false。

因此，执行者不能再开子 Agent、不能加载相关 Skills，也不能运行命令/测试或调用日历等业务工具。它能做部分文本研究与文件处理，但超出此范围都要请求父 PA 代做。这与“一个独立长期事项由原执行者完整负责，必要时继续二级分工，主 PA 保持沟通”不一致；开发只是最容易验证这个缺口的一个场景，问题同样影响通用领域工作。

建议：观察者与实际执行者分开约束；执行者复用原生执行能力，在父任务授权范围内获得相关工具、Skills 和工作目录，允许进一步委派但不能扩大权限。不得为修复此问题简单放开全部私有历史、全盘文件或主人代表发送能力。最小验收必须包含“执行者实际加载 Skill、实际创建下级、下级完成并回传”，不能只检查 spawn 成功。

## 发现 2 — P1：记忆摘要按字符切断，可能把例外/限制变成相反含义

位置：`packages/dsh-integration/src/knowledge/personal-memory.ts` 的 `project()`（189–198 行）；`query()` 的 search 内容也按 400 字符截断。

源码：
https://github.com/Mrchen116/nano-multiagent/blob/66b49e4e0fa6be17a87466ef04fa2cbf1d4007f7/packages/dsh-integration/src/knowledge/personal-memory.ts#L189-L231

`project()` 先按更新时间排序、把记录拼接，再执行 `.slice(0, limits[target])`。输出没有被截断的标记或要求读取完整记录的结构标记。`features/memory-curation.ts` 又将这个投影直接注入个人背景。

合成复现：完整事实是“工作讨论优先安排在上午，但仅限周五；其余工作日仍优先下午。”当前投影预算边界可以刚好截在“上午”，于是模型收到的背景失去后半句限定。详细记录还在，不等于当前模型输入没被误导。现有存储测试检查了投影长度，但这个条件不变性需要独立断言。

建议：本轮不切换记忆权威。将来再做 v2 时，至少以完整记录为选择单位；放不下则保留引用/明确不完整标记，并在相关行动前读取完整记录。若采用模型摘要，也必须测否定词、例外、时间范围和实体归属是否保留，不能把长度达标当语义正确。

## 发现 3 — P1：查询回执把未交给模型的后续消息也计为已检查

位置：`apps/im-server/src/personal-attention.ts` 的 `query()` / `receipt()`（67–103 行）。

源码：
https://github.com/Mrchen116/nano-multiagent/blob/66b49e4e0fa6be17a87466ef04fa2cbf1d4007f7/apps/im-server/src/personal-attention.ts#L67-L103

实现先将所有可读数据库行写入 seen，并据此计算 complete；返回消息时，才按 query 对正文做 includes 过滤。因此，“数据库扫描过”和“模型获得并能够核对过”混在同一个回执里。

合成复现：
- m1：周五会议的材料我还没发。
- m2：改到周四了，而且材料已经发完了。
- query：会议。

返回结果只有 m1，seen 包含 m1/m2，source_coverage 是 complete；receipt 对 m1 的来源和当前 watermark 校验仍通过。模型可能据旧陈述形成催办建议，而用于证明核对完成的回执实际上没有保证最新更正被提供。后续实际模型是否另查聊天未知，不能把它必然另查当接口正确性保证。

建议：移出本轮聚合查询和通知回执链。未来如保留，区分已扫描、已返回、被过滤、内容被截断与语义待核对；检索命中后需读取关联线程的后续变化。不能把 SQL 走到末页当成已核实当前事实。

## 额外的上线风险（不是一概声称 Bug）

### 记忆权威切换与回退

`personal-memory.ts::execute()` 对已有非空 USER/MEMORY、但没有 records 的 workspace，会拒绝非 migrate 写入；`KnowledgeRuntime.personalMemory()` 按 PA 身份选择新存储。现有 PA 不是在保留旧写入行为的前提下任意试用新功能。

部署文档已有备份、显式迁移和恢复要求，这是正面的保护。但其同时说明 records 迁移后成为唯一权威，回退旧程序前必须暂停 PA，旧代码不能继续独立写 USER/MEMORY。由此可见，这不是简单关闭 Feature 就可回退的 prompt 更新。

来源：
https://github.com/Mrchen116/nano-multiagent/blob/66b49e4e0fa6be17a87466ef04fa2cbf1d4007f7/docs/changes/archive/feat-665-general-personal-agent/deployment-prompt.md

### 遗忘影响整个运行树

`personal-memory-context.ts` 会在遗忘后清理上下文/notes、限制旧 history，并给全部后代执行写 invalidated、interrupt/cancel。采取保守边界是为了防止旧上下文继续使用被遗忘事实，不应简单删除保护；但“忘记一条信息”影响全部无关进行中工作，是必须单独说明、验证恢复的产品变化，不宜混进日常 PA 指导升级。

来源：
https://github.com/Mrchen116/nano-multiagent/blob/66b49e4e0fa6be17a87466ef04fa2cbf1d4007f7/packages/dsh-integration/src/knowledge/personal-memory-context.ts

### P2：只读快照变成高频磁盘写入

在 records 模式下，`snapshot()` 每次都会 writeProjections，没先判断内容/版本是否改变。它又在 agent/pre-step 和 PA system-prompt/assemble 路径中被调用。这是无变更也重复加锁和原子写文件的代码路径；未实测实际延迟、写入量或缓存命中变化，不夸大为已导致硬盘/延迟故障。以后做新存储时应按 revision/失效刷新，读取正常快照不反复重写。

### personal_context 已成为硬依赖，不是可随手删的辅助工具

`features/personal-proactivity.ts` 要求先查询聚合上下文；personal_attention 保存 query_receipt_id；主动通知读取 coverage/watermark。删一个注册名不会解除完整依赖。当前查询从选定会话最早行分页，默认 5 个近期活跃会话，并在 watermark 变化时让 cursor 失效。大聊天的成本/可完成性必须测，不能把“少一次 tool call”的初衷当成已实现收益。

## 测试证据应该怎样看

上述 head 的 CI 已成功，不应说这个实现没有做测试。`evaluation.md` 明确写明：58 项中 21 passed、3 blocked、34 not_run；不同版本/配置的证据不能当作同一最终 build 的受控提升。并发维护、遗忘的完整路径，以及若干执行者更正/取消/重启场景仍没有该完整 case 的通过记录。部分原生专项测试存在，因此 not_run 不等于所有层面都没测试。

正确结论是：已有工程验证值得保留，但不足以证明“整包大改比当前 PA 更好且适合一口气部署”。拆分后只要求每片适用场景充分验证，不强迫第一片跑无关的全部 58 项。

来源：
https://github.com/Mrchen116/nano-multiagent/blob/66b49e4e0fa6be17a87466ef04fa2cbf1d4007f7/docs/changes/archive/feat-665-general-personal-agent/evaluation.md

## 建议的拆分

### A：先交付 PA 行为与轻量主动准备

保留/改写：
- `apps/im-server/src/personal-agent-defaults.ts` 的通用服务、主从分工、持续负责、真实交付与适度主动性。
- `nano-ongoing-work/SKILL.md` 中沿用原负责人、更正回传、等待、核验、停止等通用规则。
- `nano-proactive-care/SKILL.md` 中核实原话与后续、做有用私人准备、已处理不再催、无新价值静默的规则。
- 如需保留主动服务 opt-in，仅保留最窄配置及说明；不默认给已有用户开启。

必须适配：去掉尚未实现/本片不带入的 personal_context、personal_attention、query_receipt_id、attention_id、memory upsert/records、Task bind_execution 等硬编码要求。使用此片真正具有的既有能力，不在说明中承诺没有实现的跨重启状态或精确定时。保留原安全审核和配置清空语义。

这片不迁移记忆、不新增资料库、不重写消息投递、不替换调度器。仅凭提示不能保证二级委派/忙闲恢复，实际不支持时如实列到 B，不伪称 A 已完成。

### B：持续执行者与多级协作可靠性

单独处理 `personal-delegations.ts`、`task-native-execution.ts`、Task schema/协议和续跑相关改动。只保留实现目标所需的最小运行时变化；共享文件按 hunk 拆，不整文件照搬。

必须先修复 task 角色无 Skills/无下级委派/无执行工具的问题。验收同时有两个不相关工作、跟进同一个执行 ID、真实下级执行、PA 可接新请求、暂停 A 不影响 B、失败/重启恢复、禁止晚结果复活。保留隐私隔离与原始授权，不用一律全权限继承换取跑通。

如果原生能力已足够，用真实证据证明并不加新管理器；如果有缺口，只修复确认的缺口。

### C：通用领域 Skills

研究、沟通、日程、出行、购物、表单、文档、学习和开发分别按需加载；不引入新运行时。不把这些 Skill 与 memory v2 或统一检索工具绑定。默认描述只承诺当前工具能做的事，外部 provider 未连接就准备方案并说明缺口。

### D：真实文件发布（有需求再做）

`personal-artifacts.ts`、IM media、资源读取和附件权限/版本相关代码独立 PR。这条链有真实价值，但不依赖新记忆和注意力数据库；单独验证文件能打开、权限收窄、受众副本及重试不重复。

### 当前搁置，不作为以上片段依赖

- memory v2 的 records 权威、迁移和全局 forget fence。
- `personal_context` 聚合接口。先用现有工具+Skill，有可复现漏查/重复查成本时才重新论证，不预设必做。
- `personal_attention` 的完整数据库、settings/budget、query receipt 与消息发布联动。私密关注的需求可以保留，等轻量主动性暴露持久状态需求后单独设计，不等于否定这项能力。

## 交付与回退纪律

保留 #414 为工作成果参考，不直接 merge 到小分支。每片从确认过的 main 出发，仅依赖已合并片段；更新其 canonical specs，不混入旧大功能的完成声明。若此分支已在本地或生产写入 records，先盘点和备份；不删除 records、不把短投影当完整备份，也不直接启动旧写入代码。源码拆分不等于已安全完成数据回退。
