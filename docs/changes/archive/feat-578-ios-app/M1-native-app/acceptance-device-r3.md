# feat-578 — 物理 iPhone 媒体权限窄复验 R3

> Mode targeted；独立 `change-reviewer`；2026-10-08 01:45–01:52 +08。`executed_base = validated_at = d17e70c4f1b9ca87dddea963711bb6648011ee79`（已安装候选原生源码版本）。本轮 checkout `df448f49b5e91a0282abe6cc7afaa7b39b9604c5` 为其后的文档提交，独立确认 `src/IM/ios/` tree diff empty。不把之后的仓库版本冒充本轮送装版本。

## Verdict

**Full verdict: fail；本轮 targeted 媒体范围 pass；DEV2-01 closed，新增问题0。** 新包实际 Save Image 只请求“add to your Photos”，没有重新请求 full/read access；允许仅添加后，系统 PhotosPicker 可定位刚保存的合成图，取消和移除不发送，重新选择后单次原生发送，图片再次原生预览与系统分享均完成。此结论来自手机结果，不由权限声明或安装 success 代填。

[Device R2](acceptance-device-r2.md) 的旧包/full-access弹窗和保存未确认事实保留，历史报告已单独提交 `df448f49b5e91a0282abe6cc7afaa7b39b9604c5`。本轮仅补媒体失效范围，普通 Files、@/slash、账号切换、真实回复/统计等未失效结果沿用 R2；[Simulator R5](acceptance-simulator-r5.md)/[R6](acceptance-simulator-r6.md) 原矩阵保持原 scope。S2完整中文软件输入/实体操作/VoiceOver、S29完整物理功能范围及S30同网/自然到期仍 inconclusive，不能宣称Full完整通过。

## 固定包与安全边界

- 私有 `device-private/signed-package-receipt-r2.json` 独立核对：native source `d17e70c4f1b9ca87dddea963711bb6648011ee79`，47项App源/资源与2项Config hash记录；executable SHA256 `e1e854a81ab8e13019fb895cdeb3605bfedc5c9805bee598bcdd2acd16605e3a`；bundle `win.nanoim.ios`。receipt声明 Add purpose key为 `NSPhotoLibraryAddUsageDescription`，read/write purpose key absent；这是包身份/声明辅助证据，不是运行时授权结果。
- 私有 `device-install-r2.json` 实际 outcome success，原地安装保持原App/profile，profile到期仍 `2026-10-13T11:31:19Z`，未延长签名。本轮没有自行安装/构建/重启，不宣称手机二进制读回SHA。设备身份/container UUID/Apple凭据/照片截图不入repo。
- 实际手机仍15 Pro Max/iOS26.4/普通字体/696×1532镜像窗口。仅 `com.apple.ScreenContinuity`，fresh实图坐标与批后AX；AX仅Mac容器。QuickLook初始工具栏不可见时用当时AX明确暴露的标准窗口 Raise恢复，再核稳定实图，不盲点动画位置。
- 唯一聊天为 R2已观察的 user-only `578 Phone Media R1 Files` / `c_j58iaual`，唯一可选择照片为480×320青绿/金色合成图。未读未知聊天、私人照片内容/相册列表/文件/联系人，未外发平台。系统照片网格/分享建议含其它私人缩略图时，不读取/解释/操作它们，只定位明晰的合成缩略图或退出；没有打开Collections或探索相册。
- 本轮新增的权限为**仅添加**，正常授权合成图片保存路径；之前 read/full access拒绝没有改成允许。实际系统提示只含添加文字与Allow/Don't Allow，没有私人预览。这一低敏仅添加不读取现有库，不当作扩大敏感读取权限；没有进入系统设置、授予full/read、保存密码或改网络/签名/生产。

## 实际旅程

### J-DEV3-01 同历史、单次保存与实际仅添加权限（01:45–01:47）

从caller交回的English Chats独立截图开始：三个授权聊天实际存在，Files摘要为R2原生marker。进入Files群，实际原API-seed合成正文/PNG/TXT与R2原生消息仍可见，未要求再登录，输入为空。API-seed仍仅作已授权接收前置，不算本轮发送。

点已知PNG文件名，QuickLook实际同青绿/金色3:2图；标准窗口Raise后显示标题/关闭/分享工具栏，关闭稳定的X。消息显式Share按钮实际可用，点击出现系统share sheet，`578-phone-r1` / PNG Image /1KB；不选任何建议收件人。**单次 Save Image** 后真实系统弹窗为：`“Nano IM” would like to add to your Photos.` / `Save images you choose to your photo library.`，仅Don't Allow和Allow；没有旧R2 full Photo Library access文字或私人预览。

点击Allow，01:47实际回同聊天，未再保存。仅看到sheet消失不立即认定保存成功；继续J02实际重新选取证实。原旧包DEV2-01现象由本轮新证关闭，不根据caller实现解释归因。

### J-DEV3-02 保存后选择、取消及草稿移除（01:47–01:48）

`+`→Photos，实际系统PhotosPicker显示 `Private Access to Photos`，说明图库显示于此，但Nano IM只能访问用户选择的项目；首项明确为新青绿/金色合成图。这同时证明合成图片已进入系统照片可选择路径，不需要full/read授权。其它网格内容不阅读，不点开，不进入Collections。

第一次按X无选择取消，实际返回原聊天、无pending附件、composer空、Send disabled、仍原历史。第二次重新打开，fresh实图同合成缩略图位置；**仅点该合成图**，实际返回App单项青绿/金色pending缩略图与移除X、Send active；没有自动发送。点击移除，实际pending项消失、composer空、Send disabled，没有新消息。

再次通过相同选择器只选择同一合成图，actual单项pending缩略图；没有重复保存、没有未知项选择或私人图片预览。Photos选择/取消/草稿移除子分支 **pass**。

### J-DEV3-03 原生单次发送与再次打开（01:49–01:51）

聚焦composer，核实完整draft `DEV-R3 native photos save select send synthetic only` 和唯一合成图；01:49唯一箭头发送。输入与pending项消失，Latest后actual Test User /1:49AM /Sent、完整marker在图片上方，3:2青绿/金色图以及 `photo-C3575437.jpg` 附件。系统照片路径生成JPEG，不写成原PNG字节保持或猜转换组件。

点**新发**inline图，actual Image /Done原生sheet，完整3:2图；Done返回。点新JPEG文件名，actual系统QuickLook同合成图，Raise后标题 `photo-C3575437` /关闭/分享工具栏，关闭。点击消息显式Share，actual系统面板同文件、JPEG Image /3KB与合成缩略图；直接取消，没有再保存、选择收件人/外部服务或分享私人物件。空composer/Send disabled实际可见。

caller仅只读 `device-private/native-r3-photos-readback.json` 补强数量与内容：marker1条；message `d396ef3d8d8d40ea84ad8b860121eab2`，resource `9f6dd12104404e31adc9012873d30ca2`，文件 `photo-C3575437.jpg` /image/jpeg，SHA256 `e20a714ed7edcb3a7fc87237a1cc4cb9c4600f7efa9bc754f9a84f0c1eb3fb18`，实际解码480×320、青绿/金色上下半图与fixture一致。JPEG与PNG不逐字节相同；R2 Files原样字节证据另保留。receipt独立可读 marker_count1、isolated resource inventory13、所有resource内容hash属于原两合成文件或这张已选JPEG。没有API代发；API健康/readback不代替上述发送/再开UI结果。

### J-DEV3-04 安全交还（01:52）

取消share sheet→actual原消息与空输入→原生返回。01:52实图A English Chats /All/空搜索、三个授权聊天，Files最新摘要为R3 marker，无sheet、系统菜单、选择器、待发项/草稿/修改表单。明确交还唯一GUI给caller，后续没有GUI动作。

保存的合成图与仅添加授权Allow是本轮已授权正常产品结果，未删除合成图或去系统设置改回read权限；read/full拒绝保持。既有前台提醒、语言、节点配置、连接origin、服务器历史没有改动；本轮未启动服务。

## Reference Artifacts Reviewed

期望来源为 [spec](../spec.md) R4/S10/S11、[design](../design.md) P1/P6原生附件/比例/明确动作与[prototype](../prototype.html)附件路径，R2媒体截图/结果作旧版本基线。actual evidence为J01–04本轮CUA截图/AX输出；696×1532镜像窗口/手机15 Pro Max/普通字体/English/旧授权历史→系统添加弹窗→PhotosPicker→pending→Sent→原生Image/QuickLook/share→root。

| Required contract | Actual product evidence | Comparison conclusion |
|---|---|---|
| S10原生保存授权附件；分享由显式动作触发 | J01单次Share/Save Image，仅添加弹窗；J02刚保存图进入可选择系统路径 | match，旧full-access负担DEV2-01 closed |
| S10系统照片选择、取消不发送、pending可辨/移除 | J02Private Access仅所选项说明、X取消empty、合成pending→removeempty | match；不以全相册授予通过 |
| S10图文比例/顺序、新消息再次打开 | J03 actual Sent marker→3:2JPEG，新图Image/Done、QuickLook和JPEG分享面板 | match；JPEG不是PNG原字节 |
| P1/P6详情/主操作/返回/隐私边界 | 空/图片draft/Sent状态，显式Share、Done/X/Send可辨，详情无全局Tab，J04安全根页 | 当前窄范围match；未新证软件键盘/大字体/完整VO |

## 问题处理

| Issue | Latest state | Evidence / action |
|---|---|---|
| DEV2-01 /旧minor /relation unclear | closed | 新固定包J01仅添加、不出现full/private预览；J02实际保存后安全重新选取，J03成功send/再开/share。不改写R2旧事实，不以声明静态核对闭环 |
| 新blocking/major/minor | 0 | 没有新增UI失败或实现归因；本轮targeted不需继续修复循环 |

## 最新Scenario覆盖

各Scenario期望来源仍为spec对应行与design P1–P6。未失效行的实际证据均按[R2逐项矩阵](acceptance-device-r2.md)与其R5/R6引用精确retained，不将文档包更新扩大成全部真机重验。R4本轮覆盖在J01–03补齐；S13当前global Work人工pending子条件原not-applicable裁决保留。

| Requirement / Scenario | Latest result | Actual new evidence / retained boundary |
|---|---|---|
| R1 /S1 四入口与返回 | pass | R2/root导航与R1图标原证据retained；J01/04附件下级返回 |
| R1 /S2 键盘/长内容/辅助操作 | inconclusive | R2输入/clipboard/软件键盘限制未失效；完整中文IME/实体操作/大字体/VO仍open |
| R2 /S3 登录/注册/恢复 | pass | R2 B/A实际登录与普通恢复及prior資格scope retained；本轮实际A历史仍在，不重跑登录 |
| R2 /S4 暂时失败/退出切换 | pass | R2 A→B→A清草稿/缓存、历史保留及prior故障scope retained |
| R3 /S5 找人/建聊/群设置 | pass | R2真实Agent原生建聊与prior群管理scope retained |
| R3 /S6 偏好/已读 | pass | prior有效scope retained，无新偏好写入 |
| R3 /S7 发送/提及/命令/历史 | pass | R2直接候选/头像/draft/真实发送retained；J03新增仅合成照片单次消息 |
| R3 /S8 不确定发送/重连 | pass | prior有效故障scope与R2普通后台恢复retained；本轮未构造断网 |
| R3 /S9 Copy/fork/蒸馏 | pass | 原模拟器scope retained；R2物理clipboard正确性限制未关，不冒充新pass |
| R4 /S10 上传/接收/导出 | pass | J01–03关闭物理Save Image/Photos选择→pending移除/取消→send/再开/share；R2 Files及prior主动Paste范围retained；实体phone clipboard未新证 |
| R4 /S11 附件失败/权限改变 | pass | 原服务端限额/失败/撤权scope retained；R2拒绝read/full后新版本仅添加/所选项访问路径J01–03实际恢复；没有扩大成全部物理限额故障 |
| R5 /S12 过程/结果 | pass | R2真实peer思考/统计及prior工具/子任务scope retained |
| R5 /S13 审批提交/确认 | pass | prior当前可达范围retained；global Work人工pending子条件not-applicable，不物理造审批 |
| R6 /S14 任务层级/关系/回聊 | pass | priorscope retained；R2物理Tasks仅空页不代图 |
| R6 /S15 全局Work轨迹 | pass | priorscope retained，没有新物理Work |
| R7 /S16 节点创建/路径 | pass | priorscope retained，无新Agent创建 |
| R7 /S17 完整配置/预览 | pass | R2代表只读长表单与prior保存/预览scope retained |
| R7 /S18 冲突/确认/权限 | pass | priorscope retained，没有配置写入 |
| R7 /S19 Skills/心跳/Cron | pass | priorscope/R2分组只读retained，没有删除/执行 |
| R8 /S20 通道凭据 | pass | priorscope retained，没有外部secret操作 |
| R8 /S21 通道生命周期 | pass | R6持续failed/回执/单次Retry/真实stop/历史闭环retained |
| R9 /S22 绑定 | pass | priorscope retained，没有新绑定 |
| R9 /S23 节点配置/状态 | pass | priorscope/R2owned在线状态retained，没有节点保存 |
| R10 /S24 账号/语言 | pass | R2English→中文→English保存/返回/登录保持retained |
| R10 /S25 公司准入/停用 | pass | priorscope retained，B fixture准备不作原生审批 |
| R10 /S26 策略/容量 | pass | priorscope retained，无策略修改 |
| R11 /S27 提醒/返回 | pass | priorbanner/未读及R2普通后台恢复retained，没有新锁屏banner |
| R11 /S28 后台限制说明 | pass | R2手机actual完整帮助/边界retained |
| R12 /S29 首次安装 | inconclusive | 签名/安装/图标启动/已验普通业务/到期帮助子分支retained；J01–03新增媒体，不据此覆盖S2完整物理功能 |
| R12 /S30 同网续签/自然到期恢复 | inconclusive | caller推进，reviewer没有AltStore/Mini/真实到期旅程，不用新包安装替代 |

R1/R12组内仍fail；R2–R11按原有效范围及本轮关闭的R4为pass。总矩阵保持S1/S3–S28共27项当前可达范围pass，S2/S29/S30 inconclusive。物理证据限制单列，不降低Full门槛。

## 上层文档同步与交接

- [x] `SPEC.md`：无需更新，本轮不改架构。
- [x] `docs/specs/im/`：最终行为归并由orchestrator负责，本轮reviewer不改canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

仅提交本报告，不push，caller的progress/readiness与output保持。`highest_required_action = pass`针对本轮targeted；`issues_count = 0`；`gh_issues_filed = 0`；`needs_re_review = false`针对DEV2-01及受影响媒体。Full仍fail，剩余S2可观察实体/软件键盘/VoiceOver与S29完整范围、S30真实同网/自然到期不由本轮完成声明覆盖。
