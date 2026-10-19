# Instinct：外部联系人与个人记忆的安全边界

核查日期：2026-10-16。对象是 Noah Shinn 创办、Spear Street Technology, Inc. 运营的 [Instinct](https://instinct.com/)，不是 Deep Instinct、Instinctools、销售辅导工具，亦不是第三方 Open Instinct 开源仿制品。本次仅审阅公开资料，未登录、联系厂商或攻击服务。

## 核心判断

Instinct 已公开描述一个值得借鉴的产品边界：群聊里创建共享 agent，个人 agent 保留个人账户访问权，群与个人之间通过权限检查交换信息；可信联系人也有不同授权范围。但公开材料还不足以证明：个人记忆／one-pager 从不进入对外上下文、权限在模型外以资源级 ACL 强制执行、所有出口均受同一检查器约束。

最准确的结论是“有公开的隔离与授权设计，尚缺可验证的端到端保密保证”，不是“只有一句 system prompt”，也不是“问题已经解决”。早期存在用户自测的邮件指令注入；后来有一位用户报告相同测试不再成功。不能把旧失败当作当前必然漏洞，亦不能把单个成功拦截推广为通用安全性。

## 1. 群聊：已知的产品机制，与不能推出的东西

### 2026-10-05 创始人公告

原帖：[Noah Shinn，Instinct in group chats](https://x.com/noahrshinn/status/2107161132192690558)。X 直接读取失败；通过[原帖镜像](https://twiscan.com/en/x/noahrshinn/2107161132192690558)读取完整文字，并用当日新闻核对事件。

官方原文短引，共 22 个英文词：

> The group’s Instinct has no direct access to your personal accounts.
> Your Instinct checks your permissions before sharing information or taking action.

其余内容意译：为整个群新建一个 Instinct；非注册用户也能参与。个人 agent 在连接群 agent 前询问；用户选择可信群并可撤销信任。新成员加入时，个人 agent 尚未发送的回复会暂停，直至用户授权向扩大后的群分享。公告时为 early access，承诺之后扩大开放。

**重要限定：**
- “无直接个人账户访问”不等于“群模型永远接触不到任何个人数据”。经过允许的答案、文件、推断都可能成为群上下文。
- 原文是检查权限，不能改写成“每一次分享或行动都会重新弹窗问用户”。已有授权可能满足检查；公开材料没给出所有默认规则。
- 公告没有描述独立进程、独立数据库、独立 memory namespace，或是否会注入 owner profile／one-pager。
- 暂停待发回复只处理未来披露；它没有承诺撤回已发送消息、销毁群记忆、阻止成员截图或转发。
- 没有公开字段协议说明是传 free/busy、结构化最小答案、自然语言摘要还是完整记录。以上不能擅自补齐。

## 2. 可信联系人网络：准入和范围是两道不同问题

[2026-09-09 官方公告](https://x.com/noahrshinn/status/2097794967574028448)；[可读镜像](https://twiscan.com/en/x/noahrshinn/2097794967574028448)：agent-to-agent 协调只面向 Trusted Person network。该声明针对所发布的网络功能，不能解释成任意外部邮件、网页、短信都无法被 agent 接触。

[2026-09-23 官方更新](https://x.com/noahrshinn/status/2102896414514688212)；[可读镜像](https://twiscan.com/en/x/noahrshinn/2102896414514688212)：邀请链接让对方发起连接请求，而非自动获得访问权。每个连接仍须明确批准；可以生成新链接、使旧链接失效。此更新也引入 agent 间原文件传递：收件 agent 的 workspace 接收文件，可继续分析或编辑；官方声称传递端到端加密。

可引用短句："Every connection request still requires explicit approval on your end."（11 词）

**边界分析：**允许联系不应等同于允许查询全部个人信息；传输加密保护路上的文件，不决定收件人的合法用途，也不保证收件模型不被文件中的指令影响。公告未解释密钥管理、密钥持有者、服务器是否可解密、授权撤销后的已交付副本处理。因此不能从“E2EE 文件”推导“整个 agent 网络和所有记忆端到端加密”。

## 3. 创始人怎样描述执行和权限层

2026-09-28 的 Invest Like the Best 第493期是最完整的公开口头说明。[原节目视频](https://www.youtube.com/watch?v=Am7IWP8IpEc)；[第三方逐字转录](https://pod.wave.co/podcast/invest-like-the-best-with-patrick-oshaughnessy-48a998b1-8bc3-4e91-9c00-6d2f4d646fdd/noah-shinn-building-instinct-the-personal-agent-invest-like-the-best-ep493)。以下属于创始人陈述，经转录读取，未独立验证底层实现。

- 约10–12分钟：不同关系不同访问范围；配偶可广泛分享，同事可仅看到工作日历或有限的邮件内容。越界探询会通知本人；还借助真实关系中的信任代价来约束。
- 约27–29分钟：进入 agent 的文字、媒体先经过内容防护；与主 agent 分离的监控系统可在后续行动前拦截、暂停、批准或否决。
- 约67–71分钟：承认早期版本缺少这些防护；称后来重建了系统并持续进行对抗测试。

**不能从这段话证实的内容：**监控器是否是确定性策略引擎还是另一个模型、是否检查所有工具／browser／URL／附件出口、是否在 retrieval 前做 ACL、参数与收件人是否绑定一次授权、失败时是否默认拒绝。社交代价也无法解决朋友账号被盗。

## 4. 隔离与身份：存在官方宣称，但缺少公开规格

[2026-09-23 创始人回应](https://x.com/noahrshinn/status/2102896837522804954)；[可读镜像](https://twiscan.com/en/x/noahrshinn/2102896837522804954)。他把一则陌生财务文件事件解释为虚构姓名的幻觉，并否认跨用户泄露；称使用隔离沙箱、短期本地凭据与身份签名的工具执行，另有小模型在输出／行动前识别幻觉。

这能证明厂商公开声称这些机制，不能证明事件已经被独立取证排除。未发现公开的签名格式、主体绑定规则、重放防护、联系人账号恢复与失窃处理，或可信联系人的身份如何传入各子任务的规范。没有发布可用于复现的外部审计结果或泄漏率。

**与问题直接相关的区别：**跨租户隔离防止甲的进程直接读乙的存储；它不自动阻止乙自己的 agent 受甲的消息影响后，合法读取乙的数据再错误发给甲。

## 5. 观察与测试记录

### A. 早期受控注入与后来的单个复测

[Alex Cohen 原始报告，2026-08-22](https://x.com/anothercohen/status/2091251836917350512)由多处引用；原帖直接读取失败。更可用的第一手后续是 [Peter Yang，2026-09-02](https://creatoreconomy.so/p/instinct-vs-grok-bot-vs-chatgpt-vs-hermes-which-ai-agent-can-you-trust)。Yang 描述 Cohen 用新 Gmail 给自己的主邮箱发消息，让 Instinct 根据邮箱总结待办，agent 确实执行。Yang 之后亲自重复测试并报告看起来已经修复，文中附复测截图。

这个实验使用的两端邮箱均属测试者；它展示的是低信任邮件内容曾被当成任务授权，并非攻击者攻破服务器。它不是当前群 agent 或 Trusted Person 网络的测试。复测未给出多轮自适应攻击、样本量或失败率；也没有证明所有变体被修复。

可引用 Yang 的短句："I tried Alex’s test myself with Instinct and it looks like this issue has been resolved"（16词）。

### B. 权限体验观察，不是实现审计

[Emma Burrows 的本人使用观察](https://www.linkedin.com/posts/emma-burrows_agent-permissions-are-kind-of-my-thing-so-activity-7508857062722998274-gdKd)：她认为受信任联系人准入有确定性门槛，而联系人具体能看什么似乎靠自然语言规定。她明确用推测语气讨论，不确定是否还有硬技术边界。合理引用方法是“使用者提出了尚未解决的实现问题”，不可写成“已证实 Instinct 仅靠 prompt”。页面抓取只显示相对时间，未核实绝对发帖日。

### C. 分享对象合法也会过度分享

[Business Insider 报道的 AOL 转载](https://www.aol.com/articles/couples-using-viral-ai-agent-090001000.html)记载 Luba Yudasina 让自己的 agent 与男友的 agent 协调惊喜，结果把惊喜透露了。该用户[公开帖的镜像引用](https://twiscan.com/en/x/yoheinakajima)标注2026-09-15。这是小规模个人报告，没有完整日志；但它提示“已信任的对象”仍不等于“任何目的的信息都能分享”。不是陌生人窃取账户的证据。

## 6. 记忆 one-pager 为何使问题更难

[supermemory 创始人 Dhravya Shah 的2026-09-20黑箱研究](https://supermemory.ai/blog/reverse-engineering-instinct-memory/)推断：回答模型有 profile、约4,250-token的记忆概览、对话压缩与任务索引；底层可见 git 管理的 Markdown，主会话似乎只读，后台更新。作者明确未见源码，并承认生成逻辑、后台模型／prompt、冲突处理和忘记机制未知。其商业产品是类似记忆服务，应保留利益关系和黑箱限制。

**我们的推论，非其测试结果：**如果私人 one-pager 已预先注入对外回答模型，仅锁住 memory_search 工具并不能保证保密，因为信息已进入上下文。只读记忆减少直接篡改，不阻止复制泄露；后台摘要若不保留来源和权限，也可能把第三方文字变成以后被信任的“事实”。此研究没有比较 owner、trusted-peer 与 group 三类上下文，因此不能据它认定 Instinct 对外窗口也注入同一份概览。

## 7. 法律文件能确认的数据事实

[隐私政策](https://instinct.com/privacy-policy)与[服务条款](https://instinct.com/terms)均标注2026-08-26更新。

- 政策承认可处理获准访问的私人通讯、账户与敏感内容；可能与代理行动所涉及的第三方分享。
- 一般训练使用默认允许，设置中有向后生效的退出，但保留安全审核例外；Google Workspace API 数据另有不用于训练／改进模型的承诺，也限制第三方AI二次使用。
- 断开连接不会自动删除已经收集的数据；Workspace 有删除外部索引数据入口。
- 条款区分 Vault 材料用途并排除训练；也说可能设置操作确认／防护，但不保证阻止错误动作。

政策条款属于数据处理承诺，不是外部联络人的访问控制实现。训练退出、删除索引与撤销联系人的分享授权是不同控制，不能互相替代。公开文件未给出所有个人记忆派生物、备份与群副本删除的时间表。

## 8. 不应拿来当证据的材料

- [Open Instinct](https://github.com/mariagorskikh/open-instinct/blob/main/docs/research/REQUIREMENTS.md)明确是参考商业 Instinct 的第三方项目。它的六层角色、beforeToolCall、stranger 无记忆、默认金额等属于自己的设计，不能归给商业 Instinct。该项目的资料索引可用于找原始来源，不能当原厂源码。
- [Personal Agent Bench 的拆解](https://personalagentbench.com/agents/instinct/)声称观察到审批卡、填充型 Vault、委派 sandbox 等，但不公开原始材料；其任务分数使用替换模型重建的 runtime，非生产客户端端到端安全测试；站点由另一个 agent 厂商 Zentor 运营。它也明确没得到主指令全文、生产模型或控制面 schema。最多作为低到中可信度的补充线索。
- [该站安全文章](https://personalagentbench.com/is-instinct-safe/)说其所列事故没有陌生触发者，却遗漏 Cohen 的早期受控陌生邮箱测试。不能用其一句结论否定该独立报告。
- 隐私条款评分不是泄密实验；模型自己声称某权限存在、某资料被删除，也不是独立证明。

## 9. 给产品／架构讨论的结论（建议，不是 Instinct 已实现功能）

1. 将“谁能对话”“能检索什么”“能披露什么”“能采取什么动作”分开授权。
2. 对外 agent 使用独立上下文，默认不注入完整私有 one-pager。由可信数据代理返回授权后最小字段，例如空闲时间而非日历标题／原因。
3. 授权应绑定实际主体、资源、字段、动作、目的、时间与受众版本，在模型外强制执行。自然语言可以表达意图，但不要让它成为唯一边界。
4. 个人 agent 的工具访问与外发分别审查；工具失败、未知身份、无法验证grant时默认拒绝。群成员变化使旧批准失效。
5. 保留来源和权限标签，摘要、缓存、子代理与后台记忆写入都继承它们；审批不应仅保护普通消息，还需覆盖URL、附件、共享页和间接委派出口。
6. 用完全合成的金丝雀秘密验证陌生人、被盗好友、多轮询问、群扩员、撤权、后台记忆污染和跨工具出口。用户授权后方可针对其自有测试环境运行。

**尚需厂商回答的最关键问题：**对外请求最终触发的模型，实际能看到哪份 profile、one-pager、压缩对话和记忆？权限是检索前由服务端过滤，还是私有模型看完全部内容后自行决定怎么回答？这是公开产品说明尚未回答的核心。
