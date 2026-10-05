# feat-578 — 原生媒体路径续验 R8

> 2026-10-05 14:25–14:42。Validation snapshot:旧包 b8f9a9bc6 导出续接 → native2505c9772（caller安装/启动PID92311）；checkout HEAD43b7778c4。独立产品 reviewer 使用 change-reviewer；用户指定 GPT-6.1 Sol。只验原生产品旅程，报告不修改实现、不提交。沿用 R7 已绿范围及 scoped 原生视觉证据。

## J38 旧包 TXT 导出续接与安全安装断点

fresh Simulator 截图显示本次 390 的系统 Save Files Sheet，目录为仅本次合成夹具的 578 Test Files；Mac 可操作。点击保存后系统明确提示同名 `578-synthetic-r7.txt` 已存在；选择“保留两者”，随后返回 Quick Look，仍显示三行合成文本和 `578-TXT-R7`。关闭预览返回 578review，composer 为空、发送禁用，无在途写入，已交接 caller 安全安装新候选。

这是原生系统保存操作及完成返回的直接证据，实际落盘文件与 bytes/hash 仍待 caller 只读核对；不把返回预览单独当作文件内容已验证。旧包为 b8f9a9bc6。caller随后只读核实新增 `578-synthetic-r7 2.txt` 为83bytes且SHA与原合成TXT一致，实际导出闭环完成。

## 本轮裁决

**inconclusive，进行中。** 本轮没有新原生UI fail；S10 TXT/PDF导出已闭环，S11超限/上传失败/逐项保留/仅文字/重试/冷却分支已完成，其余精确欠缺保留。S29/S30 按用户安排后置，保留真实设备证据门禁。

## 最新 S1–S30 合并表


本表取R6及本轮最新实证，替代旧状态用于交接。inconclusive仅代表列明剩余分支未完成，不等于产品已确认失败。已经完成的注册、群管理、节点离线、绑定异常、容量及策略失败不再留作欠账。
| Scenario | 当前状态 | 已完成证据 / 精确剩余范围 |
|---|---|---|
| S1 四入口与返回 | pass | R1/R2四入口及任务/Work/账号导航；R3–R6反复跨页自然返回，原生管理无需Safari。 |
| S2 输入与辅助操作 | inconclusive | P6已完成390/430普通及大字体、三行composer、长配置滚动/主按钮可达；真正中文IME组合输入、软件键盘遮挡、VoiceOver导航、正文代码复制仍需支持的操作方式/真机。 |
| S3 登录注册恢复 | pass | R7 J35真实注册→只见本人待批准→普通成员批准后刷新空聊天；b8f9保数据重启恢复相同有效账号，结合前轮错误登录/停用状态。 |
| S4 暂时失败与切换 | inconclusive | 前轮A→B隔离/停用踢出/真实断线恢复；R7 429倒计时、503区别密码错误、字段保留及正常恢复均完成，中文窄修已闭环；退出后迟到附件响应隔离仍缺。 |
| S5 建聊群管理 | pass | R7 J29搜索真人/建私聊，专用群添加成员→确认移除→两人仍为群→确认解散后撤销访问/列表消失；前轮Agent私聊/群改名证据保留。 |
| S6 偏好已读 | inconclusive | R1改名置顶、R5静音保存重开、静音不丢消息、历史阅读不被新消息强拉底已完成；精确可见域已读推进仍缺；前台跳转见S27。 |
| S7 发送提及历史 | inconclusive | R1文字/slash；R5 65条分页加载001–005保持早期位置、实时066不抢滚动、按聊天隔离草稿与真人发送收件方可见完成；有效群提及及配置分界线未完整实证。 |
| S8 不确定发送重连 | pass | R5 J24真实POST后端201但回执丢失，输入保留/发送锁定/明确核对；恢复手动核对后同message ID仅一条、输入清空，收件方GET两次COUNT1。 |
| S9 复制fork蒸馏 | inconclusive | R6 J27来源/执行Agent/global选择保持、生成可编辑正确草稿、不自动发送，R5-02/R6-01已关闭；长按复制/fork受现CUA动作能力限制，离线/跨Gateway限制分支未完成。 |
| S10 附件接收导出 | inconclusive | R2照片上传/比例预览；R8 TXT/PDF系统选择、取消、发送、QuickLook、Share→SaveFiles及实际bytes/hash闭环；主动图片粘贴仍缺（本轮明确禁用host paste）。 |
| S11 附件失败权限 | inconclusive | R5撤权后清缓存/禁用/列表移除；R8新包12MiB真实server413保留/移除/禁发，9MiB正常上传发送，one-shot503逐项失败/原PDF保留/仅文字无附件/原文件重试，429倒计时禁提前重试与恢复均完成；下载失败、外站凭据边界及迟到响应账号隔离仍缺实证。 |
| S12 过程统计结果 | inconclusive | R1/R2真实工具/审批/主子执行及指标、运行计时持续增长和最终耗时回看稳定已完成；未知指标与全部后台返回顺序/最终性分支未完整实证。 |
| S13 审批确认 | pass | R2真实allow_once、Deny、暂停节点后等待确认/禁重复、恢复已处理及实际回复。 |
| S14 任务与回聊 | inconclusive | R1/R2 DAG/探索/子层级/非成员私聊隔离/回聊引用，R3清除搜索无需Return已关闭；失效关联与完整节点关系字段覆盖仍需补，不能把S7聊天分页替代此项。 |
| S15 Work主子历史 | inconclusive | R2真实主执行→子执行1641及统计、普通成员可读但不能配置/回私聊；历史轮次及分页明细未完整完成。 |
| S16 节点创建路径 | pass | R1/R5正常创建/模式双节点保持/目录确认/唯一性/重复ID/草稿保护；R7普通空文件路径被拒、真实离线说明并禁创建、新普通成员无设备引导且不能用他人节点，全部创建欠缺已补。 |
| S17 完整配置 | pass | R5各字段保存重开、备用顺序、工具/特性、显式空Skills与默认发现、只读归属和稳定预览；R7离线能力目录明确不可用/保留既有配置/提供重读，不虚构在线模型。预览不主张逐字节比对。 |
| S18 冲突pending权限 | pass | R1/R2非owner/冲突，R3暂停后pending→重读确认；R5 J19真实IM版本409保草稿/重读服务器值/选择继续/保存确认且反馈自动入视口，R4-01关闭。 |
| S19 Skills心跳Cron | pass | R2真实Skill来源/用量/会话toolcall标识展开，R3指定Cron确认删除/文档，R5心跳开关间隔时段保存重开；R7 Cron离线不等于空任务、HEARTBEAT无法读取说明补齐离线区别。 |
| S20 通道凭据 | pass（本轮凭据旅程） | R4专用飞书新增、已保存Secret不可读、保留、同现有Secret替换、改AppID强制替换/空值禁止提交均真实完成；不冒充平台换密钥。 |
| S21 通道生命周期 | inconclusive | R4实际connected→停用applied/实际停用→确认删除空列表完成；离线/停止失败重试、重连、受限/未知权限以及聊天历史保留分支未完成。 |
| S22 绑定 | pass | R2双端接受→等待→设备确认→完成；R7当前账号/测试设备检查、明确拒绝后归属不变、过期清秘密输入并提示重新发起。caller确认两测试operation未造node。 |
| S23 节点管理 | pass | 前轮别名/节点创建/非owner边界；R7中继与上报off保存重开→恢复on，真实第二节点offline与主online并存→恢复online，未动生产。 |
| S24 个人资料语言 | pass | R1/R2中英与中文错误修复，R6 J28显示名及默认设备保存退出重开保持，再恢复原值；只读身份字段可见。 |
| S25 公司管理 | inconclusive | R1批准/停用/最后admin拒绝、R2普通成员限制及客户端被停用；分页与被停用成员名下机器资格未完整实证。 |
| S26 策略容量 | pass | 前轮管理员全部策略保存/普通成员只读；R7服务与owner容量UI和实际API一致，精确单次503保32草稿→放弃回31，真实policy全字段仍baseline。 |
| S27 提醒前后台 | inconclusive | R1轻提示、R5静音，R6总开关off保存重开并恢复on；本轮未捕捉可点击banner，不能判失败。跳转、后台重放去重及回前台一致性仍缺；不再额外发无目标探测消息。 |
| S28 后台边界说明 | pass | R1帮助和权限边界有效，未声称免费签名具备保证后台推送。 |
| S29 真机首次安装 | inconclusive / 按用户安排后置 | 未用Simulator、Release archive或未签名IPA冒充物理iPhone免费签名安装。需用户Apple账号/协议/手机信任与实际主屏幕打开。 |
| S30 同网续签恢复 | inconclusive / 按用户安排后置 | Mini AltServer、手机配对Wi-Fi sync、同网拔线刷新及自然过期恢复未完成；不能由文档/构建替代。 |


## J39 新候选 PDF 选择、取消、发送与导出

caller原地安装/启动 native2505c9772 / PID92311，未清数据，base62009。fresh原生进入578review仍见原TXT。Files仅浏览578 Test Files，选中PDF后返回上一层并关闭选择器，聊天仍只有原TXT、无待发附件、发送禁用。重选 `578-synthetic-r7.pdf` 并打开，待发区文件名/移除及可发送可见。真实keyboard输入 `578801 PDF acceptance`（未paste/未setValue），发送后已完成、图文顺序正确、输入和待发区清空。Quick Look实际显示两页及578-PDF-R7。主动Share→保存到文件→同名确认“保留两者”→返回预览。

caller只读辅助核实新增 `578-synthetic-r7 2.pdf` 为2038bytes，SHA256 `213457eba195e3687141735841f693fdc2d082e2e6155322b017935080978ee3` 与原PDF一致；真实completed消息唯一，message_id `e0f9dd14755d44ce8439db1e71c9a90e`，恰1个PDF附件。此辅助证据对应实际原生操作，不替代UI结果。TXT/PDF导出分支完成；主动图片粘贴尚未完成，因此S10整体仍inconclusive。

## J40 12MiB策略路径（待环境核对）

真实选中 `578-within-policy-12MiB-r8.txt`（Files显示12.6MB）并打开，短暂上传中/发送禁用后，待发区保留原文件名、移除按钮和“文件超过服务允许的大小。”，无重试，普通发送禁用。caller交接当前15MiB策略但实际此文件被拒，已请求只读实际POST响应/policy核对，保持失败项不动。尚不能判定客户端fail或服务环境差异；未选择16MiB、未arm上传故障。


J40环境核对完成：caller只读确认当前policy GET15MiB，但真实IM upload路由实际固定10MiB，上游返回413。此为既有IM policy字段与实际边界不一致（Web/原生共用），不是本轮证明的新客户端固定拦截。caller承认先前15MiB允许范围交接为误推断，本次不改后台。12MiB因此构成真实超限拒绝，选择移除后失败行消失且没有消息；16MiB同一超限分支不重复。新增 `578-within-current-limit-9MiB-r8.txt` 9437184bytes正常上传为可移除待发项，keyboard输入578802 legal size发送completed/清空；caller保护资源GET200及SHA一致。不能据此称12MiB合法上传通过。

## J41 单次503：混合附件保留、仅文字与原文件重试

先上传成功原PDF并留待发；正确Files picker即将选择46bytes `578-upload-retry-r8.txt` 时READY，caller只匹配本chat/file_name的POST uploads单次503，未转发，其他HTTP/WS正常。真实打开后失败行保留原文件名、移除/重试与“上传失败，请重试。”；原PDF待发项仍存在，普通发送禁用。keyboard输入578803 text only后普通发送仍禁用、显式“仅发送文字，保留附件”可用，点击后文本completed，正文清空，已上传PDF与失败TXT均仍留待发。点击失败行重试（不重选文件）→原TXT变上传成功项，PDF与TXT两项并存/普通发送启用；普通发送无正文后两附件completed并清空。

## J42 单次429：倒计时、提前禁用与恢复

正确picker/52bytes `578-upload-cooldown-r8.txt`选择前READY，caller只匹配本chat/file_name POST单次429+Retry-After30秒。打开后原文件名/移除保留，提示“上传过于频繁，请稍后重试。”，原生AX等待18秒disabled（同时截图19秒；正常每秒变化），普通发送禁用。实际click disabled等待按钮后仍等待10秒，没有变上传中/成功。到期原行变“重试”enabled，点击不重选即可转为原名待发附件/普通发送可用。keyboard输入578804 cooldown recovered→发送completed、草稿/附件清空。此受控429只证明响应处理，不冒充平台自然限流。

## Reference Artifacts Reviewed / 上层同步

保留 acceptance-visual-r3 scoped 390/430普通与大字体36幅真实屏幕对照，不因本轮媒体结果扩大视觉结论。本轮真实窗口为Nano feat578 390/iPhone14/iOS26.4；系统Files与QuickLook依截图新坐标操作，聊天控件依fresh AX。R8直接截图在CUA会话输出可复核；没有把截图缓存提交仓库。新候选只验受影响媒体范围，未重新全验已绿项。

SPEC.md、docs/specs/IM及开发/原生入口长期文档的最终归并由caller在门禁收口负责；本报告不亲自改canonical。AGENTS.md/CLAUDE.md与文档规范无需因本轮改变。IM policy/实际上传边界不一致作为既有旁发现交给caller，不把本轮后端源代码说明冒充独立UI根因调查。

## 精确剩余及安全交接

S10仅主动图片粘贴未验；S11下载失败/外站凭据边界仍需安全专用夹具，账号切换迟到上传属于S4。其他未绿继续以上合并表：S2 IME/软件键盘/VoiceOver/复制，S6可见域已读，S7有效群提及/配置分界，S9复制/fork/离线跨Gateway，S12未知指标/后台顺序，S14失效关联/节点字段，S15历史分页，S21通道失败/离线/重连/权限/历史，S25公司分页与机器资格，S27点击banner/前后台去重，S29/S30真实硬件后置。新媒体范围没有替代这些证据。

最后页面578review，空composer/发送disabled，无在途写入；未触碰iPhone Mirroring/生产，无LLM或外部真人消息。只写此报告，无实现修改、无commit。服务/proxy/fixture均由caller管理和清理。Overall仍inconclusive，不能过完整产品门禁。

## caller只读辅助收据与明确限度

578803 text only确0附件；随后唯一空正文completed消息恰PDF2038bytes和retry46bytes，两者保护GET200/原SHA一致。578804 cooldown recovered唯一completed且仅52bytes cooldown附件，保护GET200/SHA `b3b1a3aa9bd0c4864a3edb130ea8a4ed7958b3b5bb3723f5778a90f7e6fa7060` 与原一致。429精确消费1次且未转发，control已自动解除。

proxy只记录被注入一次、不记录全部普通转发计数，因此**没有实际完整POST counter证明**。本轮提前重试结论限定为UI disabled、点击后仍等待、到期恢复；已有26项独立原生测试可作为另层实现证据，但不替代本轮运行期请求计数。未重复已工作分支。
