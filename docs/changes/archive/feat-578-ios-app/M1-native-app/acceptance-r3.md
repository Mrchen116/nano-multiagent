# feat-578 — 原生产品功能续验 R3

> 2026-10-05，11:44–11:52 Asia/Shanghai；full 续验的一段，保留 R1/R2 与 acceptance-visual-r3 有效证据。
> 实际 native binary：`051abdcf8` / visual-build-r5，caller 安装390 Simulator并启动PID67332。相比P6受审5ab仅新增Tasks清空query主动reload。本轮不重做36幅视觉矩阵。

## 当前结论

**fail / 未收口**。新增1项major（心跳配置保存确认后读回丢失），修复尚未产品复验；其余未完项保持inconclusive。末段Mac锁定导致CUA明确失败，立即停止UI，没有重试解锁或争用手机。

P6-M1搜索清除问题已窄复验关闭；Cron删除实际完成；配置节点pending分支已补齐。不能由这些结果宣布整个App通过。

## 环境与约束

沿用390专用iPhone14 / iOS26.4 Simulator，IM62008、主测试Gateway45904，账号nano。UI只用CUA，输入为click/typeText/Tab，不用paste/setValue。未打开旧私密e2e聊天，未操作生产、手机或Mini。caller控制服务暂停恢复和后端辅助证据；reviewer不读实现、不修源码。

截图目录 `output/feat578/reviewer-r3/`，JPEG本地产物不提交。报告未commit。

## 本段实际旅程

### J12 P6-M1窄复验

Tasks中输入999999，按Return后实际显示暂无任务；点击右侧“清除搜索”，一次click+getAXState约0.998秒后立即返回两条真实任务“原生探索验收”和“原生验收计划”。**没有再次按Return**。截图 `search-clear-fixed.jpg`。P6-M1关闭，P6其它有效证据不重跑。

### J13 删除明确授权的测试Cron

e2e-peer→配置→现有定时任务，展开iOS-delete-check，核对ID `e27e2969d9b34a809b55c857b0f8f627`、一次性at `2099-01-01T12:00:00+08:00`、指令输出测试。点击“删除此任务”后出现“确认删除所选定时任务？”及明确任务名；确认后列表为空，仍说明节点读取超时也可能为空，未把空状态单独作为删除成功证据。

caller随后辅助核实同隔离IM真实GET cron/jobs为200 []，约0.17秒，非超时。结合真实原生确认操作和列表结果，**本任务删除分支pass**。未创建其他任务，没有触发2099任务。截图 `cron-deleted.jpg`。

### J14 心跳字段保存与节点待确认

在e2e-peer配置中真实键盘输入24h、03:00、03:01；每项click/typeText/Tab。随后开启心跳。11:47实际截图及提交后AX均显示三个完整字段，选择活跃时段避开当时11:47，未安排即时执行。

caller SIGSTOP45904后点击保存。App显示“已提交，等待节点确认。请重读状态，勿重复保存”，保存和字段均禁用；三个草稿值仍保留。截图 `config-pending.jpg`。caller收到截图通知后立即SIGCONT，点击“重读确认状态”显示“配置已由节点确认；聊天在下一轮采用新配置”。**S18节点未确认与已确认的区分pass**，结合R1冲突恢复、R2非owner边界，S18本轮可标pass。

但此时开关仍true，三个文本值全部变回placeholder。截图 `config-confirmed-fields-missing.jpg`。立即关闭心跳并保存，UI实际off；caller核实profile_version4、features.heartbeat=false，确保已恢复。截图 `heartbeat-off-restored.jpg`。HEARTBEAT.md原生预览显示真实默认文件及注释，与R1证据一致。

caller后端诊断（辅助、不是本reviewer读源码）：持久化candidate和Gateway确认result都含24h/03:00/03:01，证明输入和提交正确；live GET合并漏heartbeat_json导致返回null。caller已准备服务端窄修复及测试，**本报告尚未把修复写为产品通过**。需重启隔离IM后重新填写保存/重开核对，无需重复pending暂停。

### J15 外部通道前置与锁屏中断

caller明确交接专用测试Bot身份验证、listener锁和节点0600私钥均准备好，只允许e2e Agent，禁止外部真人消息或生产Bot。reviewer从Agent列表进入e2e详情→外部通道→添加通道，实际看到provider说明、App ID、启用开关、SecureField、空字段保存禁用、已保存密钥不可读/修改App ID须替换提示。

按授权仅把测试env中的指定App ID/Secret读入CUA内存，不打印、不截图密钥、不使用paste。随后click/typeText调用返回：`The Mac is locked and automatic unlock could not unlock it.`。立即停止，未重试解锁。该调用中的部分输入动作是否已送入guest无法证明；**尚未点击保存，没有创建/连接通道的证据**。解锁后必须fresh AX，安全清理/补完字段，不能沿用旧索引或声称已填好。

已告知caller当前无在途提交，可在此安全断点重启IM加载心跳读回修复；Gateway由caller保持管理。

## 新问题及闭环

| ID | Severity | 状态与证据 | Required Action |
|---|---|---|---|
| R3-01 | major | J14心跳字段保存且节点确认后读回全空；UI输入、pending草稿、确认后placeholder截图齐全。caller已定位服务端读回漏字段，但尚无新服务UI复验。 | fix-implementation + targeted reacceptance；真实保存/重开保持24h与时段，再恢复off |
| R3-02 | blocking/environment | J15 CUA明确Mac locked，按授权立即停止。不是产品缺陷。 | 用户解锁后继续既有授权旅程，不绕过锁屏 |
| P6-M1 | minor/closed | J12清除搜索无需Return立即恢复 | 无需重跑视觉矩阵 |

## 与前轮逐场景状态的增量

| Scenario | 本轮增量状态 | 仍缺范围 |
|---|---|---|
| S14 | inconclusive | 搜索清除已关闭；R1/R2 DAG/探索/子层级/回聊证据保留，分页/失效关联仍未全验 |
| S18 | pass | R1真实冲突恢复、R2非owner边界、本轮pending/重读确认覆盖；不代表本轮心跳内容回显正确 |
| S19 | fail | Skills真实用量沿用R2，Cron删除和HEARTBEAT.md完成；心跳字段持久化回显R3-01待复验，离线状态仍未全部验 |
| S20 | inconclusive | 已进真实表单，锁屏中断；尚未保存、保留/替换密钥旅程 |
| S21 | inconclusive | 未创建通道，连接/停用/删除实际回执待续 |
| 其余S1–S30 | 保留R2结果 | 没有新增证据的项目不扩大为pass；S29/S30及真机IME/VoiceOver等后置 |

## 续验断点

- 当前binary051abdcf8；390 booted/large，App在e2e→添加通道表单。430仍shutdown且未更新r5，不用它冒充051ab复验。
- UI恢复先检查是否有部分凭据输入；不要输出密钥，不截图含明文密钥的画面。不启动第二Bot listener。
- 首先确认caller隔离IM重启完成，然后窄复验心跳字段保存读回并关回off。
- 后续已准备可执行项：S20/21专用通道；History65分页/草稿/真人对话；iOS Access Check群的合成图片撤权；多节点创建/路径；其余R2未完分支按实际资源推进。
- 没有发送外部消息、没有新增服务进程；清理归caller。

### 停止后caller环境交接

caller已安全重启隔离IM至服务端源`c4794acef`，PID69765；Gateway45904未动。辅助GET mirror/live均返回heartbeat_json={}、enabled=false、version4。此为修复载入与off状态的环境证明，24h/时段新原生回显仍待用户解锁后窄复验；native binary仍051abdcf8。没有启动飞书连接，listener锁由caller保留。reviewer已在CUA内存把测试App ID/Secret、原env文本及解析函数清为undefined，未打印内容、未调用UI。UI停止并交还caller。
