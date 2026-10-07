# feat-578 — 新版物理 iPhone 验收 R2

> Mode targeted；独立 `change-reviewer`；2026-10-08 01:09–01:35 +08。`executed_base = validated_at = 5a46968a05d2d78da4c3ac819886397bcfe0e301`；已安装原生源码版本仍为 `383a5a9b15694af404ecb0ca0ddab8ff45bb62fd`。开始时独立确认 branch `codex/feat-578-ios-app`，两版本 `src/IM/ios/` diff empty。本轮未构建、重装、重启或更改受审实现；报告提交时 caller 的后续 HEAD 不冒充本轮已验版本。

## Verdict

**Full verdict: fail；本轮照片分支及完整物理辅助操作 inconclusive，新增 minor 商业 UX finding 1，blocking/major 产品问题 0。** 原生登录、A→B→A 隔离、真实 Agent 建聊/回复、直接提及/命令、文件上传/移除/发送/再次预览、系统分享面板、后台返回和代表管理入口已得到手机实际 UI 新证据。不能据此称完整物理验收通过：中文 IME、实体键盘/触屏、软件键盘遮挡、Dynamic Type、完整 VoiceOver、手机 clipboard 内容正确性、照片保存/重新选择发送仍未完成；S30 同网续签与自然到期恢复由 caller 另行推进。

[Device R1](acceptance-device-r1.md) 的安全输入断点事实保留。caller 后续恢复镜像窗口焦点并完成 A 登录是本轮前置，不把它改写为 R1 曾通过；本轮独立观察起点为已登录 Chats，随后 reviewer 自己完成 B 和 A 两次原生登录。继承 [Simulator R5](acceptance-simulator-r5.md) 的逐项矩阵及 [R6](acceptance-simulator-r6.md) S21 闭环，保留原版本/原条件，未机械重跑管理矩阵，也未把其模拟器 pass 换成全部真机 pass。

## 环境与证据边界

- caller 交接物理 iPhone 15 Pro Max / iOS26.4、普通字体，镜像窗口截图 696×1532。reviewer 本轮独占 `com.apple.ScreenContinuity`，每批动作后读取 AX，并由 fresh screenshot 决定手机坐标；AX 只暴露镜像 Mac 容器，没有手机控件。正文所述实图来自本轮 CUA 输出，不将私人截图缓存提交仓库。
- 送装包与 R1 相同：Release executable SHA256 `f408d045a30deba2c70447f320563a39d873bf9a5d8b58aaf52ad4f11612da74`，47项源/资源 manifest SHA256 `4539caaede19a8d71c36a1c81250fe8e895a01cb15af0fd11218abf95d002b47`；bundle `win.nanoim.ios`，免费 profile 到期 `2026-10-13T11:31:19Z`。仅引用本机私有 `device-private/signed-package-receipt.json` / `device-install-r1.json`：这是送装与安装回执，**不是手机二进制读回哈希**。设备标识、container UUID、凭据不写入本文。
- caller 集中准备 persistent `runtime-phone-r1`、独立 IM54184、可信 tailnet HTTPS19443、owned online 节点和 `e2e` / `e2e-peer` 两合成 Agents。保持 R1 精确 origin，不降 TLS、不更改网络/签名/生产。A 为 `nano` / Test User 管理员；B 为 `nano-b578` / 578 Synthetic B，独立合成成员。B 的注册/批准及 API 权限核对是准备，不是本轮原生公司审批验收。
- 唯一可读媒体群为 user-only `578 Phone Media R1 Files` / `c_j58iaual`；另有空合成 peer 群 `578 Phone Media R1` / `c_mlk4cab7`。API-seed 图片/文本是前置，不算原生发送。本轮真实新建 DM `c_zraemn7v`，仅给专用 `e2e-peer` 发正常合成消息，没有真人平台外发。
- 文件选择只定位 caller 新建的 iCloud Drive 精确目录 `NanoIM-578-Phone-R2-Fixture`，其中仅 `578-phone-r1.png`（480×320 青绿/金色合成图）和 `578-phone-r1.txt`（77 bytes 合成文本）。不读取私人目录、照片、联系人或未知旧聊天。
- Mirror 证明的是物理手机原生 UI 和镜像操作的实际结果，不等价于实体触屏、中文软件输入法、实体键盘或屏幕阅读器发声。其输入异常不能直接归因为业务 bug。没有借 API 代发、build/CI、caller 成功描述代替 UI。

## 实际用户旅程

### J-DEV2-01 接收、原生预览与系统分享（01:09–01:12）

起点 English Chats 实图显示两个授权 fixture 群。进入 Files 群，看到 Test User / Sent、单条合成 marker、青绿/金色 3:2 图片和 PNG/TXT 文件名。点 inline 图片进入原生 Image / Done sheet，完整比例保留；此 sheet 没有保存/分享动作。点 PNG 文件名进入系统 QuickLook，窗口恢复焦点并点图后实际显示标题/关闭/分享工具栏；两次点击 QuickLook 分享没有出现可观察面板，标题菜单也没有结果，保留这一事实，不推断 iPhone Mirroring 普遍禁止系统分享。

关闭 QuickLook 后，消息附件已下载，旁边显式 Share 按钮可用。点该按钮，**实际系统 share sheet 出现**，文件身份及 PNG / 1KB 可辨；未选择系统建议收件人或外部服务。单次 Save Image 后 sheet 关闭，但没有确认照片保存。下一步出现系统 “Nano IM would like full access to Photo Library” 弹窗；其中有私人相册预览，立即停止读图并选择 Don't Allow，没有扩大相册授权。弹窗来源/因果未定位；不能以 sheet 关闭当作保存成功。

TXT QuickLook 实际内容为三行：`FEAT578 PHONE MEDIA R1`、`Synthetic file fixture only.`、`No private user content.`。回消息点击显式 Share，实际系统面板显示 Text Document / 77 bytes；直接取消，没有另存或外发。接收/图片比例/原生文本预览/显式分享面板子分支 **pass**；Save Image→Photos 重新选取/发送分支 **inconclusive**。

### J-DEV2-02 语言、帮助及代表管理（01:12–01:15）

Me 实际显示 Test User / @nano / Administrator；Profile and language 初始 English，default entry 为在线专用节点。改中文、单次 Save 后实际绿色“已保存”，返回我的后中文保持。提醒与安装前台轻提示初值开启，保持不变；实际说明不暴露正文、仅其他未静音聊天、关闭仍可聊天、后台/锁屏/终止不保证系统推送、返回补历史。

滚动帮助实际看到 Apple 登录/授权不属于聊天凭据，免费签名通常7天，真实到期查看 AltStore，构建日期不等于签名到期，不虚构剩余天数；同 Wi-Fi/配对/Wi-Fi sync、Mini/AltServer 运行、手动刷新后检查到期、自动刷新不保证，失败检查同网/唤醒/信任，过期用相同账号/app ID 恢复、不要删除 App、不删除服务器聊天、不为签名重启 IM/Gateway。只是帮助内容，不是实际续签证据。

我的设备显示自己在线节点及2 Agents；详情显示在线/最近心跳/别名，中继与上报均初值开启，没有修改，Save disabled。Agent 目录实际 `e2e-peer` 为浅紫 E2、`e2e` 为浅棕 E2；同一 peer 的详情、候选、DM头像一致。详情先展示 owner Test User / online / single-thread 与“发消息”，配置/通道/Skills 等分组随后。配置长表单初始模型 loading 后真实回显 `平台默认·deepseek:deepseek-v4-flash`，推理默认 high、备用0，以及名称/描述、群回复策略、Custom Instructions、工具12、Skills/运行特性、提示词预览、心跳关闭/时间字段、Cron关闭等分组可滚动读取；固定顶部 Save 可达且 disabled。没有改配置，也不将代表只读覆盖冒充全部字段保存/冲突矩阵新证。

### J-DEV2-03 原生建聊、真实回复、正文/过程/指标（01:15–01:19）

在 peer 详情单次“发消息”，实际进入新空私聊。镜像 Unicode `typeText` 未成功输入中文，只有不完整 ASCII 残余；清空后没有发送。分步输入并核实 ASCII draft `DEV-R2 reply with python code print(42). No tools.`，Return 后 `Second line.`；实际多行、Return 没有自动发送，编辑器在底部安全区。软件键盘没有出现，不能由此证明键盘抬起布局。

单次箭头发送，实际 human 为“已发送”，peer 后续为 completed，正文 Python code `print(42)` 与 `Second line.`，头像/发送方向/状态可分，过程(1)、11945 tokens、2.0s。展开过程再展开思考，实际可读已报告内容；指标展开/滚动显示 output137、total11945、context11808/262144、cache0(0%)、5%、2.0s。没有工具调用，不虚构工具/子任务旅程。

caller 只读 `device-private/native-r2-message-readback.json` 辅助确认同 marker 仅1条，human `9b76a44d7ccf49b993b951441ad98dc7` 与 peer `f4f832baedea44468cfc3fe9448aecad` completed，真实 execution 有 kernel_message_id / 2042ms / output137 / context11808；这些只佐证实图与没有重复发送，不替代过程界面。

长按回复正文实际出现“复制正文 / Fork”菜单，点复制后出现“已复制正文”toast；代码 Copy 点击没有可观察反馈。尝试镜像粘贴只得到字面 `v`，标准 Mac Edit 的 Copy/Paste/Select All disabled，composer 长按未出现可用粘贴菜单。清掉残余，未发送。**按钮/菜单/toast 可证，复制到手机的正文/代码内容正确性不可证**；保留模拟器 S9 原有效复制证据，不新增物理内容正确 pass。未建立 fork 或蒸馏。

### J-DEV2-04 后台返回、草稿隔离、直接候选（01:19–01:21）

DM 输入并实际核实 `DEV-R2 unsent resume`，保持未发。手机 Home→Spotlight Nano→图标返回，实际同 DM、过程/指标展开和 draft 保留，无重新登录/自动发送。切到空 peer 群，composer 为空；随后回 DM 草稿仍存在，跨聊天隔离可见。本轮短暂后台恢复没有构造断线/迟到消息，不冒充全部 S8/S27 故障覆盖。

空 peer 群，镜像 `typeText('@')` 得到 `2`；删除后用标准 shift+2，actual `@` 立即在输入区上方显示“提及成员”候选，peer 浅紫 E2 及身份可辨，无需进入 `+`。选候选变为 `@e2e-peer `，caret 仍可继续编辑；追加 `DEV-R2 mention draft`、Return、`Still unsent`，实际多行且未发。清空后 `/` 直接出现 effort / Skills 命令列表；选 effort 实际只填入 `@e2e-peer /effort` draft，没有执行或发送。清空；`+` 仅“文件 / 照片”。本轮未新证候选筛选/中间正文替换/中文组合，原有效 scope retained。

### J-DEV2-05 系统 Files、草稿移除、原生实际发送（01:21–01:27）

首次从空 peer 群 Files importer 起于系统 Recents，出现私人文件列表后停止读取，只搜索精确合成目录。第一次搜索输入掉字，清空并核实完整精确目录名，结果唯一；进入后只读2个授权文件，选择 PNG/TXT，单次 Open 后系统显示 “Syncing with iCloud”。没有重复提交或刷新；随后实际回 App 显示图片/文本待发项，Send active。逐个移除 TXT 和 PNG，实际 composer 空、Send disabled、无新消息；caller 只读核 peer 群仍0条。

第二次为 user-only Files 群实际上传，系统起于 On My iPhone，截图动画导致下一次搜索坐标点击选中了一个非 fixture 项。**没有点 Open、没有预览/读取/上传，立即 Deselect All，实图确认无选择**，并告知 caller。待稳定画面再聚焦 Search，核实完整目录查询及唯一结果，进入只含2合成文件的目录。没有继续浏览私人列表；这个操作器安全事件原样记录。

选中两合成文件，实图核对2 checkmarks，单次 Open 后实际待发区先TXT后PNG，图像仍3:2。完整输入并核实 `DEV-R2 native files send only synthetic png and txt`，01:26 单次发送；实际 Test User /“已发送”，marker、TXT、PNG 顺序与待发区一致，无 pending draft。Latest 后完整合成图和文件名可读。**新发** inline 图片原生打开，Chinese 图片/完成 sheet 显示完整3:2；新发 TXT QuickLook 再次显示原三行，随后关闭。

caller 只读 `device-private/native-r2-media-readback.json`：native message `c44c5d8d170d4713879ce288e77d2fb2` / marker count1；新TXT resource `449fa3b7bb4744859f2fbd0707b08eac`、PNG `055c9d9ac5334455868029dd0c73d7c3` 下载字节分别与原合成夹具完全匹配，PNG480×320。隔离 resource 库存11项（含API前置与移除草稿），全部 SHA 属于这两个合成文件，没有私人内容上传证据。仅作为原生 UI 的字节/数量/安全辅助对账，不算 API 代发。

### J-DEV2-06 Tasks、账号隔离与安全交还（01:27–01:35）

Tasks 实际“暂无任务 / 在聊天中让 Agent 建立计划。”与 Search；四个根入口均实际进入，下级页原生返回，详情不带底部全局 Tab，无 Safari。没有物理任务图 fixture，不以空页推断图/回聊通过，沿用 prior 有效 S14 证据。

01:33 A Profile 选择 English，单次 Save 实际绿色 Saved 与 English 文案，返回 Me 实际 English。A Sign out→明确确认“Local session and unsent content will be cleared. Server chat history is retained.”→确认后实际空白登录页，A 页面已移除。标准 AX 暴露的 Raise 恢复镜像焦点；逐字段输入、实图核长度与账号，再**单次** Sign in B。01:34 actual Chats “No conversations / Use + to start a conversation.”；Me 为 `578 Synthetic B / @nano-b578 / Active`。无 A 三个聊天/媒体/待发内容；没创建 B 聊天、没读取他人数据。

B Sign out 同明确确认→actual 空白登录页。单次 A Sign in，01:35 actual English Chats 三个授权聊天恢复：Files 原生 marker、peer completed code摘要、空 peer 群。打开 peer，actual 原 two messages/Completed/Process(1)/11945 tokens/2.0s 保留，composer 仅 `Message…`，Send disabled，`DEV-R2 unsent resume` 已清空。这同时区分一般后台保留 draft 与明确退出清除 draft；服务器历史未删除。

01:35 返回 A English Chats / All / 空搜索，无 sheet、系统菜单、pending附件/草稿或表单修改。明确把唯一 GUI 交回 caller，之后不再操作镜像。caller 后续配置修正/新签名包只属于下一轮；不读实现或据其推断改写本轮结果。

## Reference Artifacts Reviewed

读取 [spec](../spec.md)、[design](../design.md) P1–P6及2026-10-06直接候选/头像修正、[prototype](../prototype.html)、[installation plan](../installation-plan.md)，继承 prior 有效原型比较。实际证据为 J01–06 本轮 CUA 截图/AX输出；696×1532 镜像窗口、普通字体、手机15 Pro Max、English↔中文、empty/normal/selection/permission/background/account-switch 状态。下表只宣称当前可观察子范围，完整九页/多宽/大字体视觉证据仍以有效 prior 报告原 scope 为准。

| Reference / required contract | Actual product evidence | Comparison conclusion |
|---|---|---|
| P1 四入口、原生返回、详情隐藏全局栏 | J02/06 四根入口、profile/config/DM/image/Files原生层级；详情 composer 靠底安全区 | 当前可见结构 match；软件键盘抬起/实体输入 inconclusive |
| P2 图/节点/回聊；P3 Work/子轨迹/审批 | J06 只新证 Tasks 空页；J03 是真实聊天过程/指标 | 图/Work/审批保留 R5/R6 原证据；无新的物理完整 pass |
| P4 管理分组/长表单/状态/主操作 | J02 账号/在线节点/Agent概览、配置分组与固定Save；J06 B独立身份 | 代表页面 match；全部保存/冲突/权限分支 retained |
| P5 前台提醒及免费维护/失败恢复说明 | J02 实际帮助全文与前后台边界、实际到期查看路径，不假造日期或自动必成 | 帮助 match；真实刷新/自然到期 inconclusive |
| P6 登录品牌/标签/实心主操作、连续列表、发送双方/折叠过程、管理可达 | J01–06 English/中文实际画面：深色正文、青绿动作、轻灰表面、三条连续聊天、peerE2浅紫与另AgentE2浅棕、双方消息头像、详情先概览/发消息 | 当前代表普通字体 match；只有3聊天不声称“五条数据首屏”本轮独立验证，大字体不新证 |
| 2026-10-06 @与/直接候选、+仅附件、身份缩写/配色一致 | J04 actual @候选→caret继续编辑→Return保留draft；slash选择只填入；J02/03/04 peer目录/详情/消息/候选同色 | 新版物理可见子范围 match；中文组合/筛选/中段替换 retained未扩大 |
| S10/P1 原生选择、比例、分享由显式动作触发 | J01 PNG/TXT实际share sheet；J05两合成文件上传/移除/单次send/再次预览 | Files/preview/share match；Save Image/full-photo弹窗 DEV2-01，Photos闭环 inconclusive |

## 问题、商业 UX 与安全断点

| ID / Severity / Regression relation | Expected / actual / evidence | Recommended action / rationale |
|---|---|---|
| DEV2-01 / minor / unclear | S10正常单张合成图片导出应有可完成、可理解的授权路径。J01显式 Share→Save Image后出现 full Photo Library access，含私人预览；reviewer拒绝，保存未确认。未定位弹窗来源，也未声称已证明产品保存失败根因 | fix-implementation，由owner核对授权范围与声明/系统行为，随后只对新版本合成图保存→安全重新选取→发送窄复验。实际过宽授权负担是商业/隐私体验问题；拒绝后的未完成路径仍 inconclusive，不能改成 pass |

其余商业观察：直接 @候选靠近编辑器、命令只填draft、两个Agent不同稳定头像、真实结果/过程/指标区分清楚，已闭合此次受影响可见用户体验。Files 首次同步有系统等待，最终成功，不据等待判业务失败。QuickLook分享无结果与显式消息Share成功同时记录，不泛化为系统不可用。copy toast不等于内容正确。Mirror Unicode/clipboard异常、无手机AX和未显示软件键盘是本轮证据限制，没有读代码归因或制造源码修复。

安全事件/断点：拒绝 full Photo Library access后不再打开私人相册；系统文件默认私人列表即停止读取，只精确查询合成目录；动画时误选非fixture立即清选，没有Open/预览/上传，独立UI后由caller资源SHA核对补强安全证明。没有保存密码、扩大权限、外部分享、未知旧聊天、改生产或读取secret。初始English恢复；前台提醒/节点配置未改变。照片授权初次请求被拒绝，保持拒绝，不为了“恢复”去扩大授权。

## 验收标准覆盖

每行期望来源为 [spec](../spec.md) 对应 Scenario 和 [design](../design.md) 契约。`retained` 指 R5/R6 的有效原版本/可达条件，而非本轮真机全量pass。R1 open 未用无关子分支消除；S13 current global Work人工pending子条件沿用已有 not-applicable 范围裁决。

### R1 独立原生入口保持完整功能与自然导航 — 组内结论 fail

| Scenario | Evidence / verification | Result / boundary |
|---|---|---|
| S1 四个入口与原生返回 | J02/06 actual四根入口、下级原生返回，DM无全局Tab；R1图标启动 retained | pass，原矩阵及本轮可见物理子范围 |
| S2 键盘、长内容与辅助操作 | J02长配置/J03ASCII多行/J04Return不发送；中文输入失败于操作器、无软件键盘；复制内容/完整VO/物理大字体未证 | inconclusive；原模拟器输入/AX部分 retained，不用截图替代VO |

### R2 账号会话与公司资格延续既有边界 — 组内结论 pass（原有效范围）

| Scenario | Evidence / verification | Result / boundary |
|---|---|---|
| S3 登录、注册与恢复 | J04有效会话后台恢复；J06 B/A两次原生单次登录正确身份；注册pending/disabled规则 prior retained | pass；B API准备不是原生注册审批验收 |
| S4 暂时失败与退出切换 | J06 A→B→A无A缓存/草稿，回A历史恢复draft清除；暂时失败/迟到规则 prior retained | pass；本轮未构造手机429/迟到回复 |

### R3 聊天、联系人和群管理完整可用 — 组内结论 pass（原有效范围）

| Scenario | Evidence / verification | Result / boundary |
|---|---|---|
| S5 找人、建聊与群设置 | J02/03从真实peer详情原生新DM；群修改/权限/确认 prior retained | pass；无真人联系人/群管理新复验 |
| S6 会话偏好与已读 | 原R5/R6有效偏好、Latest/read scope；本轮授权聊天阅读 | pass retained；无手机偏好/未读新故障 |
| S7 发送、提及、命令与历史 | J03单次真实消息、J04直接候选/多行/跨聊天draft、J05实际附件消息；头像一致 | pass；中文组合仍在S2未证，中段替换/筛选/历史分页按prior范围 |
| S8 发送结果不确定与重连 | J04普通后台回来不重复/不自动发；不确定发送故障 prior retained | pass；非手机断网后新证 |
| S9 消息操作、fork与Skill蒸馏 | J03物理Copy菜单/toast；原R5/R6真实复制/fork/蒸馏scope | pass retained；物理clipboard正文/代码正确性 inconclusive子范围不冒充通过 |

### R4 图片附件使用系统选择、预览与分享 — 组内结论 fail

| Scenario | Evidence / verification | Result / boundary |
|---|---|---|
| S10 上传、接收与导出 | J01分享/接收、J05Files两项移除/send/再开pass；照片保存/再选/发送未完成，DEV2-01 | inconclusive；原模拟器主动Paste等有效部分保留，当前物理Photos缺口open |
| S11 附件失败与权限改变 | 原R5/R6限额/故障/撤权scope；J01系统相册拒绝后安全停止；J06账号切换不带A媒体 | inconclusive于本轮照片拒绝后可行恢复；既有服务端失败/撤权pass保留 |

### R5 真实Agent过程、指标和审批可检查 — 组内结论 pass（原有效范围）

| Scenario | Evidence / verification | Result / boundary |
|---|---|---|
| S12 过程与结果 | J03真实completed/思考/统计逐项实际展开，J06重开仍可辨；工具/子任务prior retained | pass；本轮无工具调用，不扩充工具旅程 |
| S13 审批提交与确认 | 原R5/R6 Chat allow/deny/等待/迟到确认 | pass现行可达范围；global Work人工pending子条件not-applicable裁决retained，未物理制造审批 |

### R6 任务和Agent Work原生保留完整浏览语义 — 组内结论 pass（原有效范围）

| Scenario | Evidence / verification | Result / boundary |
|---|---|---|
| S14 任务层级、关系与回聊 | 原R5/R6图/回聊scope；J06仅实际Tasks空页 | pass retained；新物理图fixture未提供，不以空页代填 |
| S15 全局Agent主子工作轨迹 | 原有效Work/轮次/分页/归属scope | pass retained；本轮没有新增物理Work轨迹 |

### R7 Agent创建与完整配置管理均可原生完成 — 组内结论 pass（原有效范围）

| Scenario | Evidence / verification | Result / boundary |
|---|---|---|
| S16 在线节点创建与路径确认 | prior完整创建/路径/失败/草稿scope | pass retained；本轮没有创建Agent |
| S17 所有配置字段与预览 | J02代表长表单/真实模型/主要Save可达；原保存/预览全字段scope | pass retained；只读观察不当新保存 |
| S18 保存冲突、确认中和权限 | prior真实冲突/确认/权限scope | pass retained；B身份不替代配置权限矩阵 |
| S19 Skills、心跳与定时任务 | J02分组/心跳OFF/CronOFF可读；原Skills/heartbeat/cronscope | pass retained；无新删除/计划执行 |

### R8 外部通道完整管理保持凭据与运行状态语义 — 组内结论 pass（原有效范围）

| Scenario | Evidence / verification | Result / boundary |
|---|---|---|
| S20 新增、编辑与凭据替换 | prior原生凭据管理scope | pass retained；未输入/读取外部secret |
| S21 连接、停用与删除恢复 | R6完整持续失败/回执/单次Retry/实际stop/历史闭环 | pass retained；不机械重跑，无手机真实平台连接新证 |

### R9 设备绑定与节点管理保持双端确认 — 组内结论 pass（原有效范围）

| Scenario | Evidence / verification | Result / boundary |
|---|---|---|
| S22 接受、拒绝与过期绑定 | prior双端绑定scope | pass retained；本轮未新增绑定 |
| S23 节点配置与状态 | J02owned online/最近心跳/中继上报初值；prior保存/离线scope | pass retained；未保存节点配置 |

### R10 账号、公司成员与策略管理完整覆盖 — 组内结论 pass（原有效范围）

| Scenario | Evidence / verification | Result / boundary |
|---|---|---|
| S24 账号与语言 | J02 English→中文保存回显/返回；J06中文→English恢复并登录保持；其他字段prior | pass；默认设备未修改 |
| S25 公司准入与停用 | prior公司管理scope；J06两个实际角色身份 | pass retained；B批准是APIfixture准备，不算原生审批 |
| S26 策略与附件容量 | prior全策略/容量/权限scope | pass retained；未策略写入或改变容量 |

### R11 前台消息反馈与系统后台限制清楚 — 组内结论 pass（原有效范围）

| Scenario | Evidence / verification | Result / boundary |
|---|---|---|
| S27 前台提醒与返回App | J04后台恢复/history/draft；原banner点击/未读scope | pass retained；本轮没有后台新消息/锁屏/真实banner新证 |
| S28 不承诺免费后台推送 | J02手机实际帮助和前台提示初值，明确不保证background/lock/terminate | pass；没有伪承诺已开系统push |

### R12 免费安装、续签与过期恢复可实际完成 — 组内结论 fail

| Scenario | Evidence / verification | Result / boundary |
|---|---|---|
| S29 首次安装 | R1signed原地安装/实际图标launch；J02实际到期帮助；J01–06登录/聊天/Files/管理代表功能可用 | inconclusive于“已验收完整功能”全部物理面；安装/启动/本轮正常功能/到期意识子分支pass，未使用付费能力 |
| S30 同网续签与失败恢复 | 无reviewer实际AltStore刷新/真实Mini同网/自然到期恢复 | inconclusive；caller负责，不把R1安装/帮助/新包代替续签与自然到期 |

## 上层文档同步与后续

- [x] `SPEC.md`：无需更新，本轮不改变跨包架构。
- [x] `docs/specs/im/`：最终行为增量归并仍由 orchestrator 按最终版本完成；reviewer不改canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

仅写/提交本报告，不push；caller同期progress/readiness及output状态保留。reviewer未启动任何服务，无自行清理进程。`highest_required_action = fix-implementation`（DEV2-01权限体验的owner核对/窄复验）；`issues_count = 1 minor`；`gh_issues_filed = 0`；`needs_re_review = true`。保存照片后从仅含授权合成物的系统路径重新选取/发送/再次预览需在新包完成；若必须扩大读取私人相册则仍停止并交回caller，不用授予全库来冲掉缺口。真实中文IME/软件键盘、实体操作/大字体/完整VoiceOver及S30需要可观察的本地物理证据，继续保持Full标准。
