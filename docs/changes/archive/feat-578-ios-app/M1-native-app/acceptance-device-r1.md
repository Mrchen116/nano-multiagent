# feat-578 — 新版物理 iPhone 验收 R1

> Mode targeted；独立 `change-reviewer`。`executed_base = validated_at = d4d8be38c7789ec3334063c257f79a14c9285159`，原生源码版本 `383a5a9b15694af404ecb0ca0ddab8ff45bb62fd`，本轮独立确认两者 `src/IM/ios/` diff empty。2026-10-08 +08。本文为本轮实际观察的持续记录；后续观察追加，不改写早先事实。

## Verdict

**Full verdict: fail；本轮targeted结果 inconclusive，新增产品问题0，环境阻塞1。** 沿用 [Simulator R5](acceptance-simulator-r5.md) 全矩阵和 [R6](acceptance-simulator-r6.md) S21闭环：S1、S3–S28共27项现行可达范围 retained pass；S2中文/多行/AX部分 retained，完整 VoiceOver、S29新版物理功能和 S30同网/自然到期仍有缺口。此次不能以镜像启动或安装success替代完整物理功能接受。

## 验收环境与证据边界

- 设备：caller交接 iPhone 15 Pro Max / iOS26.4（设备标识仅保存在本机私有回执），配对、Developer Mode enabled、无线 localNetwork。reviewer独占 `com.apple.ScreenContinuity` 时段；只用该App操作手机。其AX只暴露Mac镜像容器，无手机产品控件，因此本轮坐标从fresh截图推导，动作后观察AX/实图。
- 私有包receipt独立只读：47项源/资源manifest SHA256 `4539caaede19a8d71c36a1c81250fe8e895a01cb15af0fd11218abf95d002b47`；发送的Release executable SHA256 `f408d045a30deba2c70447f320563a39d873bf9a5d8b58aaf52ad4f11612da74`；bundle `win.nanoim.ios`、免费profile到期 `2026-10-13T11:31:19Z`，原profile UUID保持。`device-install-r1.json`实际 outcome success，安装URL指向新的bundle目录（原始路径只保留私有回执）。这是发送包与安装回执证据，**不是手机二进制读回哈希**。
- caller集中准备持久隔离runtime `runtime-phone-r1`、IM loopback54184、可信 tailnet HTTPS19443、本轮owner `u_fsqbhkuc`、online专用节点及 `e2e`/`e2e-peer` Agents。reviewer实际确认App连接设置为交接精确origin，未忽略TLS证书或改ATS。私有token、密码、数据库和截图缓存不入repo。
- 只操作已授权合成账号及本轮资源；未打开未知旧 `c_81nb7o3h`、私人聊天、照片/联系人/个人文件，未外发真人平台。旧恢复会话TLS提示发生于先前Tailscale disconnected背景，不作为本轮新版业务bug证据。
- Mirror可证明物理设备正在运行的原生UI与通过镜像输入后的结果；不能证明实体触屏/实体键盘流程、屏幕阅读器发声或完整VoiceOver。S30由caller推进，reviewer不操作AltServer、Mini或签名安装。

## 实际用户旅程

### J-DEV1-01 图标启动及旧会话安全退出（00:17–00:18）

实际 `⌘3` 打开手机Spotlight，fresh实图Siri Suggestions中Nano IM图标清楚；点击中心后实际进入Nano品牌/“欢迎回来”/用户名/密码/登录/创建账号/连接设置原生页面。完成动画后的实图为696×1532镜像窗口，产品上下安全区可见，没有Safari或Web地址栏。旧恢复状态仍显示英文TLS错误及“重试恢复登录”“清除本机登录”。点击一次“清除本机登录”，随后展开连接设置；实际红色反馈变为“已退出本机；服务器登录撤销尚未确认。”，账号及密码框空白，地址与本轮精确19443 origin一致。没有把服务器撤销未知显示为成功。

S29图标/本期已签名包启动子分支 **pass**，S4本地退出及远端未知反馈子分支 **pass**；免费功能可用及新版全部物理旅程未完成，因此两项完整Scenario不由这一子分支重标pass。

### J-DEV1-02 合成登录输入与安全输入操作器断点（00:18–00:19）

用户名坐标聚焦后，镜像 `paste` 实际只插入 `v`，不是预期内容；随后逐 `pressKey` 重填，实图完整 `nano` 可见。因此host clipboard不能当作phone粘贴能力证据。密码框先收到最初两字符；随后镜像批量逐键、带120ms按键、选中后单键及 `typeText` 均未得到后续字符变化。实际截图只见选中两掩码字符。**未点击登录、没有失败密码请求，没有判断产品验证失败。** 这是本轮操作器/安全输入前置未完成，S3本轮登录 **inconclusive**。

00:19向caller具体attention并停止全部GUI；00:19正式交还唯一GUI给caller集中解决合成密码输入/媒体fixture。断点是登录页、连接设置展开、用户名正确、密码选中两字符、旧本机session已清除，无未知聊天/附件操作。等待caller明确恢复后才继续，不自行争用镜像或设备。

### 前置交还后的caller辅助状态（非reviewer新旅程）

caller集中再次确认手机Tailscale Online、当前专用IM授权节点可读且owned online；这些健康/API结果没有替代手机登录。caller复验同一secure字段选中两字符后标准键入/粘贴不改变，镜像Edit命令disabled，标准粘贴曾触发系统Save Password提示，已选择Not Now；未保存密码、未提交错误登录。caller已请求用户在当前合成密码框本地填入指定测试密码并点击登录，这一用户动作仍pending。当前最终安全断点由caller交接为Nano登录页、连接设置折叠、username完整、password两dots、未submit；reviewer没有在交还后继续GUI。

caller另已集中准备合成媒体前置，私有 `device-private/media-fixture-receipt.json`：user-only专用群 `c_j58iaual` / `578 Phone Media R1 Files`，API-seed marker与PNG/text；此前 `c_mlk4cab7` 空群同属callerowned fixture。reviewer本轮没有打开这两群、没有查看/发送这些附件。API-seed不是原生send，也不能关闭S10物理上传/预览/分享缺口。下轮仅在登录已完成、caller明确交还GUI后，从这两个已授权fixture继续，不访问私人相册/文件或未知旧聊天。

## Reference Artifacts Reviewed

期望来源为spec S2/S4/S7/S10/S29及design P1/P4/P5/P6、2026-10-06直接提及与头像修正契约；[R5](acceptance-simulator-r5.md)/[R6](acceptance-simulator-r6.md)保留原精确scope，不用worker成功叙述代替UI。

| Reference / required contract | Actual product evidence | Viewport / state | Conclusion |
|---|---|---|---|
| design P1/P6：原生登录、持续字段标签、清楚主操作/次级连接设置 | J01 fresh CUA图，品牌、用户名/密码、实心登录、创建账号、展开连接origin；Mirror AX仅容器 | 696×1532窗口；iPhone15ProMax；中文普通字体；错误/退出状态 | 当前观察match；键盘与大字体未新证 |
| design P4/S4：退出清本地并区分服务器撤销未知 | J01实际中文“已退出本机；服务器登录撤销尚未确认。”，空账号字段 | 旧恢复错误→本地退出 | 子分支match；迟到回复/换账号范围retained |
| design P5/S29：图标入口与免费安装 | J01手机Spotlight实际Nano图标→原生App；私有签名/安装receipt辅助包身份 | Release原地无线安装；主屏搜索入口 | 启动子分支match；帮助/功能未完成 |
| design P1/P6/S2/S7：中文组合、多行、直接@候选、名称缩写/稳定配色 | 尚未进入本轮聊天 | 新版物理聊天 | inconclusive，不能由旧Simulator代填物理证据 |

## 问题与安全断点

| ID / Severity / Relation | Expected / actual | Required action / rationale |
|---|---|---|
| ENV-DEV1-01 / blocker to this execution / not product-classified | 已授权合成登录必须可输入完整密码；Mirror secure输入只收到最初两键后不再变化，未提交 | caller集中解决输入前置后继续；不改源码，不以操作器失败定产品bug |

商业UX观察：当前登录视觉层级、深色正文与青绿主操作清楚，旧连接失败/退出说明在字段旁可读。TLS英文提示在中文页是旧恢复状态，未重新触发本轮稳定网络请求，暂不列本轮回归；不以它作为网络仍失败的证明。

## 当前覆盖与retained范围

| Scenario | Result | 本轮新证 / retained限制 |
|---|---|---|
| S1 四入口/返回 | pass retained；本轮未全部复验 | J01只新证物理原生登录入口，原R5/R6四入口有效证据保留 |
| S2 键盘/辅助 | inconclusive | 原模拟器中文/多行/长表单/大字体/AX有效部分保留；物理中文软件键盘/完整VO待验 |
| S3 登录/恢复 | pass retained；本轮物理登录inconclusive | J02无登录提交，操作器前置缺失；不虚报新会话 |
| S4 退出/切换 | pass retained | J01新增本地退出/远端撤销未知子分支；物理B切换待验 |
| S5–S28 | pass retained当前可达范围 | 逐项沿用R5完整矩阵及R6 S21新闭环；本轮新聊天、中文软件键盘、多行、安全区、@直接候选/不同头像、正文/代码Copy、前后台恢复、代表管理页及媒体均未证，不虚写物理pass。S13global Work人工pending范围裁决retained |
| S29 真机安装/功能 | inconclusive | 新版签名/安装receipt+图标启动已证；登录与新版物理功能尚未完成 |
| S30 同网/自然到期 | inconclusive | caller负责真实Mini/AltStore/同网及自然到期；不由本轮安装替代 |

## 上层文档同步

- [x] `SPEC.md`：无需更新，本轮验收不改跨包架构。
- [x] `docs/specs/im/`：待orchestrator按最终验收/实现归并；reviewer不写canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

仅本报告写入；caller `output/` untracked保持。reviewer未启动服务，无需要自行停止的进程。Full仍fail，不降低未完成物理/VoiceOver/S30门槛。

需本地完成事项：用户在当前Nano登录页将合成密码完整输入并点击登录；caller观察结果后明确交还镜像，后续独立轮次继续新版物理交互。完整VoiceOver需要可验证的物理操作/发声证据；Mirror空AX和截图均不能代替。S30同网真实刷新、Mini维护与自然到期恢复由caller继续推进，不以提前安装/手动刷新冒充自然到期。`highest_required_action = out-of-unit`（本轮环境前置）；`needs_re_review = true`；没有归因于源码的 `fix-implementation` finding。
