# feat-578 — 通道反馈与停止恢复复验 R6

> Mode targeted；change-reviewer；`executed_base = validated_at = 383a5a9b15694af404ecb0ca0ddab8ff45bb62fd`。2026-10-07 01:42–01:55:55 +08实际390 UI。caller原地更新保fixture，不清数据；实际bundle98E59660-D972-41A0-9C6B-895C47F61A0F/NanoIM.app，本轮独立核binary SHA256 `0ccbd835e5eebc820f1f15eb6bd9b367db2c2f42c66b84e9537ef5d081f328cf`、debug.dylib `cff4f59060f56825aabc8d0edf50a8201c77e8325fbdf53c1bde66363ffb87ae`。
> 本轮先沿用R5同一e2e通道ch_b9279f22fb2a4d9cbcb415774963b739及owned节点/原IM45154/62008。原Gateway53159正常退出形成真实offline；caller集中恢复、控制真实stop异常。第一个通道自动恢复并完成终态后，caller仅增加同dedicated Bot的第二受控通道，验证持续失败/manualRetry，详见J05。reviewer只实际原生操作/报告，不自行重建资源、重装/构建/测试或操作手机；不读未知旧c81，不改真实飞书权限、生产、账号、secret或外发。本轮时间戳均为2026-10-06 UTC，界面本地日期为10月7日+08。

## Verdict

**Full verdict: fail；本轮targeted范围pass，新增问题0。** R5 SIM5-01真实闭环；S21已补齐反馈保留/明确重读、真实停止失败、自动恢复、持续失败回执、在线单次原生Retry、停止确认后空列表及删除后历史。R5失败记录不改写，当前结果由新证据关闭。

合并矩阵中S1、S3–S28共27项在当前可达范围pass；S2输入/AX已证，完整VoiceOver只能随真机后置，S29/S30同样user-deferred/inconclusive。因此当前可执行的模拟器缺口已补齐，不能宣称Full完整通过。S13当前global Work人工pending子条件按独立范围报告not-applicable，并非实际测过默认展开；真实平台收发、物理VoiceOver、同网真机及自然续签到期不由受控fixture推断。

## 实际旅程

- J-SIM6-01 失败反馈保留/明确重读：新包启动Chats→Agent→明确e2e/管理者Test User/设备离线→外部通道，last-known“正在重连”、已有8satisfied、本地最后时间01:33与真实offline说明分开。实际暴露Scroll Down到原生重连，单次action_at17:43:15.637Z。实际Scroll Up后17:43:22.151Z完整红色中文“节点离线，恢复在线后请重试通道操作。”及“重试”按钮可读；17:43:37.000Z实际AX/截图仍同反馈（action+21.36秒，跨至少两个3秒poll窗口），没有第二次提交来保持它。17:43:42.283Z只点击error卡“重试”明确重读，error及按钮实际消失，last-known正在重连及一般offline说明仍在，不把重读成功显示为节点恢复。**SIM5-01 closed/pass**；原R5实际失败事实保留，caller关于poll根因不作为本轮UI替代。中文reconnecting标签实际可读，也不扩大为自然WS连接成功。接着READY resume，等caller恢复原config/manifest的新ownedGateway。
- J-SIM6-02 同节点恢复：caller同config/data/manifest真实重启Gateway新PID60285，旧53159gone；IM45154保持，bindingcheck仍offline，未换另一Gateway或新建第二通道。01:45实际页面从last-known→“实际连接状态、正在重连”，一般offline说明消失，本地更新时间01:44、8satisfied当前可见，期望启用/config1 applied保持。只是恢复实际上报能力，非自然WS已连接。原e99实际scope完整链路retained，无需再重连重复。随后READY delete，等caller精确arm单次stop异常；当前通道active且未删除。
- J-SIM6-03 单次确认Delete/停止失败暂未证：caller宣告精确dedicated Bot feishu:e2e/Gateway60285一次真实stop_invalidated异常已arm。实际底部“删除通道”→确认popover“删除通道并停止连接？聊天历史保留。”→唯一确认at17:46:32.897Z。即时截图仍原通道；17:46:43.195Z实际完整AX及实图已“暂无通道”，没有实际捕捉到failed/原因/Retry回执。reviewer未点Retry/重连、未启停Gateway、未追加删除或重建通道，不能把这次empty结果写成停止失败/原生Retry闭环。立即通知caller只读核fault consumed/throw/最终stopack链路，区分前置未触发与真实停止后的合法消失；该失败分支暂inconclusive，不猜产品根因。
- J-SIM6-03辅助核对：caller私有runner真实事件精确17:46:33.639 stop_failed_once→17:46:34.144 stop开始→17:46:36.200真实完成，IM durable removal applied_at17:46:36.207。caller另核现行自动retry0.5/1/2秒，共三次；一次故障在首轮自动retry即自愈，未满足可观察的持续failed前置。由此43秒empty是实际停止后的合法终态，不列回执凭空丢失或产品失败；**自动恢复分支pass**，持续failed/manualRetry仍未证。下一fixture只held失败至真实自动重试耗尽再解除，产品383不变；旧已终态通道不可伪恢复，caller准备同dedicatedBot第二受控channel，不由reviewer重建/修改真实平台权限。
- J-SIM6-04 删除后历史独立阅读：01:47从empty通道返回详情→Agent→Chats，实际同`578 Simulator Channel History`/c_0kwwnqvh仍在。打开后两条完整`UX-SIM4-S21-HISTORY-01/02`正文与R5删除前完全一致，Test User/01:22/已发送可读；Send disabled/空draft。caller只读确认同两messageID与全row SHA都和baseline相同（私有0600 receipt）；这只是已seed受控外部影子历史的真实删除后可读性pass，非本轮真实飞书消息/LLM。随后实际回Chats全部/空搜索，无sheet/附件/draft，等待caller精确持续失败前置。
- J-SIM6-05 持续失败回执：caller旧60285正常退出，启动同config/data/workspace新ownedGateway61290，IM45154不变；同dedicated Bot e2e新唯一通道ch_3c300f51ce6241abbe1d27bc1a1b9df3/v1，原ch_b927已真实applied终态不能恢复，history保持。产品383源码/binary不变，无新安装；private runner held条件只对该adapter持续抛异常，包括初次和三次自动retry，不直接伪造IM/removal UI值。01:52实际e2e/ownerTestUser/在线，期望启用/1applied/实际正在重连/01:50/8satisfied；不重复旧权限旅程。READY held_delete后caller set条件；实际同原生Delete→明确停止连接/历史保留确认，唯一confirm17:53:32.966Z。等待6秒（超过自动0.5/1/2秒耗尽窗口）后fresh实际17:53:51.430Z原回执：飞书、App ID后缀9dd15、删除状态failed、删除版本12，“通道正在删除；等待节点实际停止连接。”；红色“runtime_stop_failed: 受控验收：通道停止暂时失败，请重试停止与删除。”和真实按钮“重试停止与删除”。action+18.46秒保持，未提前空列表，未点Retry/重连或暂停节点。通知caller权威核四次held及耗尽/解除条件，待明确允许后执行一次nativeRetry。
- J-SIM6-06 在线单次手动Retry：caller只读确认原始+0.5/1/2秒三次自动重试共四次真实held异常、重试已耗尽，API仍failed/runtime_stop_failed/版本12；随后解除私有故障，保持同Gateway61290在线，没有代点Retry或重送manifest。17:54:47.585Z fresh实图仍保留同failed回执/原因/版本12/“重试停止与删除”（原确认+74.6秒，解除故障不会提前消失）。17:54:53.927Z只点一次该按钮，即时仍为等待停止的回执，无重复提交；17:55:12.484Z fresh实际“暂无通道”，加号重新可用，失败原因/Retry已消失。caller只读对账：真实`stop_real_completed` 17:54:56.037976Z→IM removal `applied_at` 17:54:56.044027Z，均早于本轮实图empty；精确通道POST retry200唯一一次，manifest12/applied/error null。**持续失败/明确原因/回执保持/单次手动Retry/实际停止后终态pass**，不把API代删当原生操作。
- J-SIM6-07 最终历史与交还：从empty通道返回Agent详情→Chats→同已许可c_0kwwnqvh。17:55:47.035Z实际两条HISTORY-01/02完整正文仍可读，Test User/01:22/已发送，空composer/Send disabled。caller只读同两IDs `fd0efbfdf74348aca198dbe99a8f6904`、`b866dea63f29449fb738cd655ebf2f61`，两行全字段SHA256仍为`63b952b227f659a1ba064cdcba82728292d71757862cdf2db74737f6f2e46af2`，与删除前baseline相同。17:55:55.300Z实际返回Chats全部/空搜索，无draft、附件、sheet或表单dirty，停止UI并交还caller。此历史是明确受控repository种子，不扩张为真实飞书送达/LLM执行。

## 故障条件与辅助证据边界

两次故障均进入真实Gateway manager stop链路：第一次仅异常一次、产品自动重试恢复；第二次私有runner持续异常至原始及三个自动重试耗尽，再解除条件以验证原生手动Retry。没有修改受审产品源码、伪造IM状态或截断真实停止确认。具体故障原因是受控fixture，不宣称自然外部故障复现；实际stop与IM applied时序只用caller权威核对辅助UI闭环。

caller私有0600 receipts `/tmp/nano-feat578-sim-r6-held-removal-failed.json`、`/tmp/nano-feat578-sim-r6-native-retry-receipt.json`只用于上述已知通道/历史，不入repo，不包含报告内token/secret。其准备声明/API成功不替代J01–07实际UI结果。

## Reference Artifacts Reviewed / 当前覆盖

本轮期望spec.md R8/S21及design.md P4通道状态/错误恢复、P6可读反馈与常用操作；390/iPhone14/iOS26.4，792×1679，owner active→offline→online/删除后empty；J01–07均含真实CUA截图/AX。J01明确反馈/保留/手动重读、J02 last-known→actual正在重连、J05–06 failed回执/原因/Retry/终态、J04/J07受控历史实际可读均**match**。J03短暂失败未捕捉事实原样保留，由新held前置J05–06补齐持续失败分支。不用API成功、fixture声明或build替代产品结果。

| Reference / required contract | Actual product evidence | Viewport / state | Comparison |
|---|---|---|---|
| design.md P4：期望配置、实际状态、最后已知状态分开 | J01–02实际offline说明、last-known→actual“正在重连”，本地更新时间；R5八项权限链路retained | 390顶部通道状态，offline→online | match |
| design.md P6：操作失败原因/恢复动作可读 | J01中文错误保留21.36秒、明确重读清旧；J05原因/failed/版本12/Retry实际保留，J06单次Retry后终态 | 长页顶部error及删除回执 | match |
| spec.md S21 / design.md P4：删除等待真实停止，保留聊天历史 | J05–06持续失败未提前消失，实际停止/applied后empty；J04/J07两条完整历史 | failed→empty及已许可历史页 | match |

继承[R5完整30项矩阵](acceptance-simulator-r5.md)，未失效pass保留其原版本/范围；R4设备内主动Paste/中文无binding/heartbeat和R3真banner点击/fork等不重跑。本轮S21由旧fail经J01、J05–07新证据闭为pass。S2完整VoiceOver仍需物理设备（模拟器真实输入/AX部分已证），S29/S30按用户物理后置；current Work pending子条件范围裁决retained，不造pending。S27没有新增marker或声称3秒自然消失已计时。

| 分支 / Scenario | 最新结果 | 最新证据 |
|---|---|---|
| S21 offline具体失败/恢复反馈 | pass | J01单次真实409，21.36秒保留，实际error卡重读清旧而offline状态不伪恢复；SIM5-01 closed |
| S21 状态与权限 | pass | J02同owned恢复/actual中文，R5unknown→受控limited→actual完整8checks retained；不称自然WS已连接 |
| S21 Delete自动恢复/实际停止 | pass | J03一次故障真实自动retry后worker stop完成/applied，actualempty在真实停止之后 |
| S21 持续failed/在线manualRetry | pass | J05实际failed/原因/版本12/Retry跨自动重试耗尽仍保留；J06单次原生Retry，真实stop→IM applied→实际empty |
| S21 删除后历史 | pass | J04/J07同已许可影子history两完整正文，辅助同ID/全rowSHA与baseline完全一致，不算平台发送 |
| S1/S3–S20/S22–S28其余有效范围 | pass retained | 见R5逐项矩阵及其R20/UX/模拟器原证据，未失效不机械重跑 |
| S2完整VoiceOver、S29/S30物理 | inconclusive / user-deferred | 不用Simulator/AX代替物理，未减少Full门槛 |

## 安全断点与文档同步

J07结束17:55:55.300Z实际Chats全部/空搜索，空draft/无附件/secret/表单dirty/sheet；独占UI已交还caller。两受控通道均经真实停止完成删除，caller负责自有runtime清理；reviewer无自行启动服务。本轮当前可执行模拟器缺口补齐，没有追加marker、Skill执行、平台权限修改或外发。仅物理/VoiceOver与真实平台边界保留，不冒充Full全部通过。

- [x] SPEC.md：无需更新，架构未改。
- [x] docs/specs/im/：最终行为归并由orchestrator负责，reviewer不写canonical。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

仅报告写入，caller dirty/output保留，不push；本轮问题0（blocking/major/minor均0），SIM5-01 closed，S21当前可达范围pass，`needs_re_review=false`针对本轮targeted范围。Full仍fail，仅后置物理项目/完整VoiceOver待实际验收；未降低必验门槛。
