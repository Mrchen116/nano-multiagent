# feat-665 — 独立产品验收

## Round 1（2026-10-26，11:48–12:06 UTC）

> Validation snapshot: `783ff080f4a110780d78473e95d0bc391c64c50f` → `783ff080f4a110780d78473e95d0bc391c64c50f`。只读真实产品与公开 API，不读取实现定位根因。后续修复不得追溯替换本轮版本。

## Verdict

**fail**。真实草稿采用、私人文件交付/版本保留和原执行者更正已可用；关注卡的“忽略本条”不能保存，必须改为新文字请求才能关闭。其余必验项的缺口不能用这几个局部成功、checked-in 场景或自动 runner 成功代替。完整验收仍需下表中的未覆盖旅程及原生专项前置。

## 环境与证据

- 独立 daily 栈 `/tmp/pa665-acceptance`，IM/Web `http://127.0.0.1:57216`，node `wt-pa665-acceptance-72858`；清单 `.e2e-daily.json`。
- PA `pa_976c59dba056`；主人私聊 `c_352de4d4bcd4`；研发日常 `c_chmxw7nc`；测试用户 nano。清单及实际 Work 的主模型为 `codexOAuth:gpt-6-astra`，清单 effort medium，审核 Luna。P/E/Q 清单 Sol/high。
- 主 session `d76bc36a-bbe7-41a6-a753-8ce032e2dd61`；文档 child `d78f6cee-522c-433c-943f-4a7cf05d8f63`；旅行 child `ee387232-aa2e-47d4-9ffc-fa87d7e1a2d7`。
- 黑盒取证复用 `IMClient` 与 eval 的 `capture`，保存完整分页 Work/child/timeline，不导入产品内部。原始本机证据 `/tmp/pa665-review-evidence/`，浏览器截图与下载 `/tmp/pa665-acceptance/.playwright-cli/`。不提交运行数据和截图缓存。
- Web 使用独立 Playwright session `pa665-review`；桌面 1280×720、窄屏 390×844。初始聊天 GET 重定向到未启动的 4173；caller 完成前端构建后相同入口返回 200。本轮真实 UI 观察从 11:51 UTC 开始，未把之前网络失败当产品行为失败。
- 11:50 UTC 注册第三方测试用户被正式注册接口限流（429，retry_after 754）；12:03 UTC 自然恢复后，经正常 company/join 和主人批准建立合成同事与观察群 `c_dsb56ymk`。没有修改限流或伪造第三方身份。专项故障、并发维护、native restart/guard 前置未由本轮 caller 提供。
- `/Users/czj/Repos/LLM_PROXY/logs/session` 中未找到上述 root/child session 文件。本轮 Work 不是最终 provider request，因此涉及输入最小化/最终上下文的断言仍为 inconclusive。

## 用户旅程体验

聊天清楚区分 A 文档交付和 B 机制解释。B 用 A/B 与孤立 C 的例子解释两票多数和日志检查，未强迫生成额外学习材料。A 在原执行者仍处理时接收预算 800→600 的更正，主 PA 继续响应并交付另一项结果；后来同一执行者再改为 500。

草稿卡沿用现有聊天样式，字段可编辑，主要按钮明确标示目标研发日常输入框。将正文改为“轻记材料已整理好，请查收。请只核对预算。”后点击采用，进入正确会话并聚焦该文本；页面仍是 No messages yet，同期 API `items=[]`。这条从编辑、采用到待发送的流程可理解且可用。证据 `page-2026-10-26T11-52-06-476Z.yml`、`page-2026-10-26T11-52-13-233Z.png`；卡消息 `13dfabd253e6415e9bc60f73f29ece59`。

文件交付使用可点击下载按钮，600 元版、500 元版和旧版入口区分清楚；实际点击均下载成功，字节与真实发布回执一致。首稿却包含“后续由父 agent 验收并发布”“未上传文件”，把制作过程混入用户成果；用户明确要求后第二版删除，属局部质量问题。新版消息和旧版下载都不依赖机器路径。

关注卡在桌面和窄屏都能读出原因、下一步及“稍后处理/忽略本条”两个动作，无横向溢出。实际点击后展示 Choices submitted，仅能证明请求已交给 PA；后台不能保存忽略，稍后 PA 才说明失败。用户需要再发自然语言才能完成原操作，因此这个反馈闭环不具备可交付性。截图 `page-2026-10-26T11-55-14-746Z.png`（桌面）、`page-2026-10-26T11-57-27-056Z.png`（窄屏）。

## Reference Artifacts Reviewed

N/A。design 明确复用既有 IntelligentUI / ComposeMessage / ToAssistant，不新增页面或 prototype；仍已独立观察实际聊天、采用、反馈与文件下载体验。未评价原生 iOS 界面。

## 问题清单

| # | 严重度 | Regression Relation | 期望 / 实际 / 证据 | Recommended Action / 理由 |
|---|---|---|---|---|
| PA-1 | major | direct | 实际关注卡 `789923e746f34f5cb37711e4e894d7df` 两次“忽略本条”生成 `0701eb1bd4a84a7d8cd616aa49896440`、`8f0f0516d5d640b08834b5c5df4a34c0`，两者 interaction_reply 均携带正确 source_message_id 和 attention `cfd69f05-6c9f-4a85-8097-654268fb4369` rev1。第一次正确目标 dismiss 返回 `attention_feedback_target_mismatch`；模型后续重试仍失败，用户收到“关注项尚未成功关闭”。`feedback-after.json` tool_results 中 call `call_940b9f96ff52402684fb1649a9f06e59` 及后续两次调用。 | fix-implementation。按钮不能完成核心控制动作；需要重新以文字授权才能成功不是按钮旅程通过。 |
| PA-2 | minor | unclear | 初次下载文件中有“父 agent”“未上传文件”等制作过程文字，与“附件已交付”产生不必要解释成本。`artifact-v1.md`；用户要求后 `artifact-v2.md` 已清理。 | Side finding；完善交付稿检查，不阻断文件功能，也不据此扩大为实现归因。 |

Highest Required Action: **fix-implementation**。尚未对外创建 GitHub issue。

## 已观察的决定性结果

**本轮最终归档**：完整分页主/子Work和owner/研发群/真实同事观察群 timeline 见 `round1-final.json`；12:06 UTC 主PA idle，旅行及文档均已交付。

1. **原执行者更正**：初始请求 `22c8e416dcca49b5a257b4f38725d153`，更正 `07a0f4bf6bda47f1b4e4546ddc93aa39`。原 child 收到 `send_message` 回执 `e4f822cd-fe19-4f16-b470-ae8439a279a6`，最终文件实际为 600 元。非失败/重启覆盖。
2. **文件 v1**：artifact/resource `9c2c8aa34e6b47cab27fe3b0d53f167c`，1658 bytes，SHA-256 `69da8e145b7f721a2cf25b08a95d6de797effccc4d5cc9cfbd03a0c6a8849611`。浏览器下载文本包含姓名陈示例、项目轻记、600 元和缺失资格编号，未编造编号或签字。
3. **文件 v2**：同 artifact_id，version 2，resource `d2da1dc97bdf471d8b838a8de8cdc632`，1534 bytes，SHA-256 `4d05ef314c811de933f92858c381b21b4342d4a517f8e4eaabc1efcadffbeede`。浏览器下载是 500 元，旧入口再次下载仍为原 v1 哈希；匿名请求 v2 返回 401。证据 `artifact-v1.md`、`artifact-v2.md`、`feedback-after.json`、`unauth-artifact.json`。这不证明外发副本权限或结果未知重试。
4. **文字忽略与旧卡**：新文字消息 `6e3f10ee957a457ca42aa2bb5a891b6b` 对同一项 dismiss 成功，rev2/status dismissed；随后实际点击 rev1 的“稍后处理”，PA读取当前 dismissed，说明旧卡不能恢复，不创建该关注的提醒。`before-reminder.json`、`reminder-state.json`，Work seq324 为 dismissed 结果。独立的新材料提醒不能算旧卡产生的副作用。

## 验收标准覆盖

每行对应首文档的一个 Scenario。表中局部通过不提升整行；未运行/缺前置统一使用 inconclusive，并注明边界。

| Requirement / Scenario（来源均为 spec.md 对应标题） | 真实验证和证据 | 结果 | 尚缺范围 |
|---|---|---|---|
| 个人记忆 / 跨聊天实际使用（M01–M05、M08、M12） | 未独立执行该组；不继承 caller 的成功叙述 | inconclusive | 跨聊偏好、情境例外、同名、第三方、容量、过期事实及最终输入 |
| 个人记忆 / 纠正与维护同时发生（M02、M09、M11） | 原文档预算更正不是后台记忆并发场景 | inconclusive | 真实维护冻结/冲突、共享 Skill 泄漏及下一轮使用 |
| 个人记忆 / 遗忘与关闭（M06、M07、M10） | 未运行故障/旧源重放/关闭能力 | inconclusive | 分层遗忘、失败不可消费、禁用不绕行 |
| 主动帮助 / 承诺、冲突与机会（P01–P04、P13、W09） | 已有私人关注实际建项，不向群交付；是用户直接请求，不等同观察承诺的自主准备 | inconclusive | 真实多来源承诺/冲突/机会、当前事实复核、owner Task 不接管 |
| 主动帮助 / 安静、覆盖不足与紧急自述（P05、P09–P12、P14） | 显式一次提醒已在12:01:17 UTC送达，较计划11:59:24晚113秒并说明延迟；未见重复，静默期间实际可回复交办任务 | inconclusive | 两次真实背景唤醒、静默过渡、第三方紧急、部分覆盖 |
| 主动帮助 / 稍后、忽略与主题抑制（P06–P08） | PA-1；自然语言忽略成功，旧卡不恢复 | fail | 卡反馈修复；独立 snooze 到期恢复；主题抑制已保存仅“商业展销活动”，其他事项仍继续，但未观察后续被抑制来源 |
| 自动观察 / 批次与直接请求（I01–I04） | 真实同事在12:04:03发评审变更，PA在12:05:02正确报告周三→周五/线上、未捏造截止日，保留同事身份和可打开来源，早于十分钟批次；`round1-final.json` | inconclusive | 多人混合来源、完整十分钟批次、镜像去重、分页失败 |
| 自动观察 / 私人研究与来源撤回（I05、I06、S03） | 普通 child 与主消息并行可见，不代表 observer cursor/guard | inconclusive | 真 observer/主 Inbox 并发、来源撤销后读与披露 |
| 多事项 / 并行、更正与恢复（W01–W05） | 文档 child 工作中主 PA交付 B、响应更正，原 child 修改并交付；旅行另委派；见完整 capture | inconclusive | 完整三事项执行绑定、native失败、节点重启与一次送达恢复 |
| 多事项 / 停止、等待与未知结果（W06–W08） | 未执行 native取消/迟到事件/unknown ack注入 | inconclusive | 实际取消、不复活、真实 waiting schedule、未知回执查询 |
| 通用服务 / 多领域与连接缺失（D01–D08） | D05准备稿和D07机制解释满足；D08在12:05:43交付1400元条件式行程，含实际公开检索/官方链接、未订票未读邮件；诚实说明目标日期开放、咖啡店营业/安静性尚未完全核实 | inconclusive | 日历/机构预约/购物/条件取消/受众风格；外部账号无连接时只可判降级 |
| 通用服务 / 可访问的文件与修订 | 主人 Web 实际下载v1/v2及旧v1，字节哈希匹配、匿名401 | inconclusive | 已授权外发冻结副本、另一收件人权限、unknown/retry不重复资源 |
| 通用服务 / 建议、草稿和旧卡（U01–U04） | U03完整编辑采用不发送通过；旧卡不恢复通过；U01两次点击保存失败（PA-1） | fail | 修复后重复点击业务幂等及完整来源解释 |
| 用户控制 / 身份与最小上下文（S01、S02、S04） | 原child交接文本只含对应任务，但不是provider最终输入/guard证明 | inconclusive | 真第三方/其他owner、最终输入、child资源拒绝和重启恢复 |
| 用户控制 / 配置和旧资料（W10） | 当前仅新建daily PA，无旧配置升级/回退前置 | inconclusive | 自定义/空指令保留、同名Skill、迁移幂等和失败恢复 |

## 58 场景入口与分类边界

已读取 `evals/general-personal-agent/README.md`、58场景及显式 adapters；另在当前测试树执行 collect 返回 count=58/live_actions=0（只证明入口收集，不是运行版本行为证据），并将用户旅程与对应 rubric 对照。该套入口明确包含人工/专项 checkpoint；**本轮没有将 collect/dry-run/协议单测或 PA 自述当行为成绩**，也没有产生全58通过率。D05/D07/U03 的上述局部行为证据可复查，但不冒充各 case 完整最终输入与三次独立复放。其余未运行部分保留为 not_run/inconclusive；无专用外部日历/booking账号的 live 部分为 blocked。

本轮单一已使用 PA 不符合 suite 的“每case/repetition新身份”独立比较前提，因此未把连续旅程包装成三次重放或旧版同模型比较；这些仍需 caller 提供独立运行及完整证据再审。

## 上层文档同步

- [x] `SPEC.md`：本轮未观察到新增跨包职责需要独立改写；最终边界由 owner 核对。
- [x] `docs/specs/gateway/`、`docs/specs/im/`：需要在实际通过后依据最终 delta 归并，当前 active 目标不能宣称已成为 current。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新，文档体系未改。

服务由 caller 准备并负责停止；本 reviewer 未启停或改运行配置。12:06 UTC已告知caller可在idle状态升级，后续Round追加，不覆盖本轮失败。最终结束时清理本人创建的浏览器session。
