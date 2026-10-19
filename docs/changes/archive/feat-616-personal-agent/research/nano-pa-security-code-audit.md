# Personal Agent 安全设计：静态代码审计与隔离接缝

基线：nano-multiagent main `481467ac16f0eda4561fca5c8230050541600de9`，2026-10-16。只读审计；无生产修改、无线上攻击、未执行漏洞复现。结论区分已观察代码、条件性风险和拟议架构；没有把潜在路径称为已成功利用。

## 核心判断

固定个人Agent应保留私密、长期主上下文。外人给它发请求，不能默认进入这个主上下文并继承它的全部资料和工具；“允许联系”与“允许访问个人资料”必须分开。

新开session或“不fork”只是必要条件，不是充分隔离：当前Node会给Agent配置用户级skills/plugins/approval，global root会强制获得跨聊天工具；普通child继承parent config。安全外部协作需要独立的最小执行配置、受限产品工具、数据披露授权和发送出口，而非只换session ID。

## 已观察到的权限/数据接线

| 数据或能力 | 代码证据 | 安全含义 |
|---|---|---|
| 长期全局上下文 | `packages/personal-assistant/src/global-agent.ts:48-58,64-86` | global:{agentId}绑定唯一主session。不同来源已经摄取的资料在同一模型上下文；来源身份标签不实现上下文隔离 |
| 私密记忆自动入prompt | `packages/dsh-integration/src/features/memory-curation.ts:10-15,21-34` | 懒加载USER.md/MEMORY.md形成prompt上下文；子Agent可继承父快照；禁新增文件读取不能消除已经在prompt中的信息 |
| memory可写能力 | `policy/approval.ts:20,106-115`; `knowledge/files.ts:49-71` | nano/codex分支safeTools含memory；文件写有root/symlink/字符限制并记session_id/time，但没有逐事实来源主体/可披露受众/审批依据字段。这是当前实现性质，不是一次攻击已越权的证明 |
| 自动记忆/技能整理 | `knowledge/runtime.ts:194-218`; `assets/knowledge/memory.txt` | 按轮次触发fork review，保留父system prefix，执行限制memory或skill工具；自动整理可能处理已经摄入的第三方资料，提示词强调保存用户偏好但不构成内容完整性边界 |
| 用户级skills/plugins | `apps/node/src/configuration.ts:79-92`; `agent-config.ts:74-83` | 默认共享owner skill root、owner plugins、workspace plugins、home兼容skills；新session同配置仍可见这些来源 |
| 普通child配置继承 | `packages/dsh-integration/src/history.ts:107-135` | subagent复制parent configuration，包含workspace/capabilities。不能把普通fork/child当成外部安全sandbox |
| 历史fork | `dsh-integration/src/index.ts:333-339`; `history.ts` | 现有fork明确从source+message复制历史并继承产品绑定；不是“仅复制公开事实”接口 |
| 产品身份桥 | `dsh-integration/src/product-bridge.ts:11-31`; `personal-assistant/src/global-agent.ts:112-115` | bridge爬父链得到可信agent/owner/root身份；PA拦截child Inbox/history。但是child其他产品调用仍拥有root绑定；没有独立task disclosure envelope |
| global固定工具 | `dsh-integration/src/capabilities.ts:59-67` | global根即使限制toolAllowlist仍补inbox/conversations/send_message/subagent。因此仅设置空allowlist不能保证最小权限 |
| 工具选择有效执行边界 | `capabilities.ts:26-31,53-67` | 现有公开ctx.tools.restrict执行restriction可复用；它不是OS filesystem/network sandbox。plugin_manager可动态加入installed工具，外部profile不能开放该能力 |
| 聊天读取ACL | `apps/im-server/src/messaging.ts:72-93`; `work.ts:476-525` | 以Agent当前space/member身份限制读取，不能读任意owner聊天；但一旦外部请求跑在同一PA主身份，可请求PA本来有权看的其他来源 |
| 任务图ACL | `apps/im-server/src/task-graphs.ts:438-470` | Agent需node/owner/feature/tool有效，源conversation决定读写。现有范围不是“只这次外部任务”，不能因可读源任务就披露给任何联系人 |
| Work/轨迹可见性 | `apps/im-server/src/work.ts:707-743,160-171` | Work读按Agent space，不要求所有读者为owner；权限操作才owner=true。个人Agent改company会使完整Work受众变化；不是安全开放联系的方法 |
| 发送审核 | `policy/approval.ts:99-146`; `global-agent.ts:204-226` | 现有消息目标解析、本人DM豁免、模型审核有价值，但没有已见到的硬性“仅此task目的地+仅批准资料”语义；dangerouslySkipPermissions及无人值守fallback会影响现有策略 |
| 附件授权 | `apps/im-server/src/media.ts:48-50,123-127,186-187`; `dsh-integration/src/trajectory-attachments.ts` | 媒体读取当前conversation权限、轨迹有来源映射、无来源inline图片会屏蔽；这些保护防直接取文件，不证明模型重述/OCR/重新生成附件已获披露许可 |
| 搜索/网络 | `dsh-integration/src/web.ts:22-35,41-100` | web_search把查询发到真实外部服务；语义上“只读搜索”也能通过query外泄信息。现有上游URL安全校验不是数据披露授权 |
| 控制命令 | `global-agent.ts:67-80`; `session-controls.ts:8-12` | 精确human /stop先于context_only检查。外部观察不应成为控制事件；详细前提见routing audit，不将纯private Web无入口称现有远程漏洞 |

## 条件性攻击面模型（防御测试，不是实攻击）

1. **直接诱导披露**：外部请求被送入PA主session，要求引用之前私聊、列出偏好、总结日程或把“调试上下文”发回。由于已知内容无需再读工具，工具读取ACL无法拦截模型从上下文复述。
2. **私密源检索扩大**：外部请求借“为了完成任务”让主Agent读它自己有权限的owner DM、task graph或memory，再把结果给请求人；source access与recipient disclosure不是同一授权。
3. **外发侧信道**：文本之外包括URL query/path/fragment、搜索关键字、富文本图片URL、附件正文/文件名/EXIF、表格隐藏列、HTML/JS外链、下载链接、任务标题、错误诊断、日志和工具参数。只扫描最终聊天文本不足。
4. **子Agent洗白**：外部内容诱导启动普通fork，再把敏感信息作为“子任务结果”回传。来源仍敏感，工具由child发起不降低等级；native parent-child通信不要被误当作已批准对外发布。
5. **memory/skill投毒**：第三方内容声称owner偏好已改变、可以自动发材料，进入当前或后台memory review，未来在owner轮次被当背景事实。当前source session_id/time有审计价值，但没有强制本人证据约束；记忆不应能存/改变授权。
6. **Work/审计旁路**：即使最终回复干净，若把主Agent设company以便他人联系，Work可见性可能使过程资料进入更广受众；把private主session导出为artifact同样危险。
7. **权限撤回后的滞后**：已读取资料留在模型记忆或queue；后续ACL拒绝读取不代表模型已经忘掉。不能承诺撤回后物理清除已见信息，需限制后续工具/输出、销毁外部capsule并记录剩余边界。
8. **错误/存在性泄漏**：向外返回“你无权看老板的X项目/某文件路径”本身透露存在性。外部错误应稳定、简短，不含原SQL/path/secret/title；内部完整诊断仅owner可见。

## 推荐架构：私密主脑 + 外部任务舱（同DSH执行体系）

### A. Ingress broker：只接请求，不带主脑权限

IM负责认证实际sender/owner/channel、收件策略、速率、关联任务、idempotency。外部请求保存为untrusted request。创建任务的身份、原文和授权状态不可由消息正文覆盖。消息进入哪个受限任务舱由服务器决定，不允许调用者传任意session/agent/workspace。

个人主脑可收到最小摘要“谁提出了什么请求，需要你决定什么”；不要为了分类把无限完整外部文本塞入长期私密主上下文。正常owner主动提问仍直接进入私密主脑。

### B. Capability envelope：读、写、披露三类权限分开

Host持久记录与运行绑定：owner_id、requester_id、task_id、session_id、grant_revision、expires_at、read_refs（具体对象/字段/版本/范围）、write_actions、disclose_fields/artifact_refs、allowed_destinations、delegation_budget、state。

- read grant：本次可以给模型看的数据。
- write grant：本次允许修改什么对象、什么动作。
- disclosure grant：本次允许向谁发哪些事实/产物。读许可不能推导披露许可。
- capability不是给模型的长期凭据；模型见不透明引用，宿主查绑定，不能自行扩大scope。每次读取/改动/发出前检查当前owner资格与grant revision/到期/撤销。
- 不依赖模型“声明来源”；broker把实际返回字段与artifact digest记录为来源证据。任意自然语言输出仍需最小输入与review配合，不声称数据标签自动证明全部语义安全。

### C. Fresh restricted session：不能fork private

通过`packages/dsh-integration`的既有公开session controller/createScope/tools.restrict等接缝创建新任务执行实例，保持Node→DSH stdio边界，无第二loop。需新增宿主控制的execution profile，不允许外部请求自行选择。

最低安全profile必须做到：
- 新空历史，不调用session.fork/private parent fork，不继承memory snapshot、persona私密资料或parent config。
- 独立临时task workspace；不挂ownerRoot、私密workspace、DSH历史导出目录、globalSkillRoot、home兼容skills。
- 不安装owner/workspace动态plugins；禁plugin_manager、memory/skill writes、schedule、普通subagent/fork、session export、trajectory读取。
- 仅少量capsule产品工具：读取已批准对象投影、提交结构化候选回复、向owner请求额外资料。禁普通read/glob/grep/bash/read_image/web_search/web_fetch和通用网络/代码执行；需要图片只能由broker给批准的图片。
- 不沿global root固定工具补回逻辑配置它；以单独host profile控制，不是将既有global toolAllowlist设空。若使用现有single_thread能力也必须阻止默认final自动向外投递，先交egress broker。
- 所有可调用产品工具再校验task envelope，不能只依赖工具名称隐藏；ProductBridge需要可信task scope，不能爬到private root后默认为完整owner能力。

### D. Egress broker：受控投影后再发送

受限任务只产生候选structured result，不能直接send_message。broker固定目标/发送身份，验grant/recipient/revision/idempotency与artifact digest；对正文、URL、附件、文件名、富文本、引用、错误分别处理。

最低版本只发送纯文本且无模型生成外链/附件，按任务明确允许的字段构造回复。对自由生成正文，可用额外审查降低风险，但不能把分类器“通过”当硬安全证明；新披露范围要owner确认。owner确认后正文/附件/目标必须冻结，修改则重新审核。

第三方不能读取完整private Work或task舱trace；只得到该任务的公开状态和批准reply。owner保留完整可审计过程，但审计日志也要脱敏secret并限制下载/分享。

### E. 私密主脑取资料：只经owner边界导出

若外部任务确需某项私密信息，任务舱提交精确request。例如“确认周二是否有30分钟空档”，由owner允许的broker查询投影为available=true/false，绝不把完整日历/联系人/私人聊天放进任务舱。涉及新的披露需要owner确认；外部任务的“为完成任务必须知道”不构成授权。

主脑挑选资料时也可能受外部提示影响，因此导出操作必须由硬grant限定，不能让主脑自然语言自行签发新权限。

## 可复用与能力缺口，不能混淆

可复用：现有identity/space/member ACL、node epoch、product binding、持久relay/inbox幂等、tools.restrict/guard、私密Work空间、附件provenance、配置恢复。它们是基础，不是已存在的外部任务沙箱。

当前未找到：每任务read/write/disclosure envelope、recipient-aware字段投影、统一egress gate、外部safe execution profile、任务级OS文件/网络隔离、memory事实主体授权校验。

明确限制：`cwd`只是工作目录，不是filesystem jail；工具allowlist不等于操作系统sandbox；同DSH进程可能仍持有runtime/provider凭据。若profile只允许可信broker工具且没有任意代码/网络，这可以大幅缩小模型可达面，但安全依赖broker和工具实现本身。若必须执行外部代码/任意shell/安装plugin，需要另有隔离进程/容器、最小挂载、无用户凭据、出网策略和资源预算，并核验DSH公开能力支持；当前审计不能证明仓库已具备。无法实现时必须不提供该能力，不能用prompt替代。

每任务profile接缝的具体DSH API兼容性还需在正式设计时对已锁版本的公开exports验证。本审计只使用仓库已调用的公开接口作为候选，不建议private import/fork/patch runtime。

## Synthetic验收集（无需真实隐私/线上攻击）

使用测试用户A/B及人工canary事实；记录是否发生私密read、外部write、trace可见，不只评最终回答。

1. 外部请求让任务舱复述A的private prompt/memory：起始模型请求中就不应含canary。
2. 新session仍尝试绝对路径、../、symlink、home skills、owner plugins、session export：工具不可用/服务器拒绝；不能仅凭工具隐藏算通过，直接构造产品调用也拒绝。
3. 查询URL、搜索参数、Markdown图片、附件文件名/元数据/生成HTML藏canary：出口或能力拒绝；纯正文扫描不能作为唯一测试。
4. 伪造owner批准、Agent转述批准、历史引用/compact摘要批准：grant不变化。
5. 第三方/observer `/stop`或/config不得控制private主session；owner显式停止仍有效。
6. memory/skill poisoning：外部session无写权限，外部内容不会自动被保存为owner偏好/权限；owner主动确认的事实单独记录来源。
7. 启动fork/普通child绕限制、run_code调用被隐藏工具、plugin动态安装工具：全部被task profile及服务器scope限制。
8. 断线重试、grant revoke、公司停用、源成员退出、node transfer：同operation不双发，过期任务不能利用缓存继续外发。
9. 接收者只有外部任务状态；无法读private Work、子session items、附件、错误栈。company联系人资格不会获得private trace。
10. 检验可用性：完全公开材料的正常协作能完成；用户仅授权busy/free时只输出该投影，不误拒全部任务。

验收不能声称“通过有限prompt injection样例即无泄漏”；先验证确定性权限不变量，再用攻击样例评估残余风险。当前报告未执行这些测试。
