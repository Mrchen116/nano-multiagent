# feat-623 — 独立产品验收

> 对齐 [spec.md](spec.md) / [design.md](design.md)；Round 1，2026-10-20，Asia/Shanghai。
> 实际真栈受审版本：`f036aedd5e7bc972a413989474f166a8d49db752`。运行期间不重启、不更换实现。

## Verdict

**pass**。全部 16 个 Scenario 按真实旅程与 design 指定控制证据完成；无新增 blocking / major / minor。真实模型只覆盖本轮明确记录的输入与配置；恢复、长文本 fragment、idle 补发及 guard 竞态保留其控制证据边界。

## 用户旅程体验

本 unit 无客户端变化，按 runbook 使用 Web 同一登录、建群、发消息、查询聊天和 Work API。隔离 IM `http://127.0.0.1:61157`，node `wt-nano-multiagent-44706`，PA `pa_5d508a7ee324`，主 session `1f0b9e1b-93db-4352-b643-f87844460171`。独立检查 checkout、HEAD、进程路径及实际持久状态。模型实际事件为 `codexOAuth:gpt-6.1-sol`，真实 DSH；没有注入模型返回或缩短产品十分钟周期。

主人能在原 Web 私聊读到完整报价核对版，群里仅收到群内公开报价。观察主人与小王聊天时，PA 读到双方原文但没有接管承诺或插话。飞书使用首次真实来信绑定，在实际平台单聊读到回复与一次性提醒。功能结果来自原聊天 API 回读、平台 API 和持久 tool/result；不宣称已观察 Web/飞书原生排版、动画或设备视觉。

## Reference Artifacts Reviewed

N/A：design 无客户端原型、viewport 或 must-match 条目，允许同一产品 API 驱动。采用共同体验标准评价交办、阅读结果、识别受众和交付完整性。

## 独立真实证据

所有下列临时原始证据位于 `/tmp/pa623-review-evidence/`，不提交凭据、数据库或运行态。

- **A：真实首批十分钟**：首条 `3f56f8bbe90e450bbc326131a7b55572` 于 11:47:19.909 发出，节点接收后截止为 11:57:19.955；11:47、11:49、11:54 分三组双向追加，最后一条 11:54:45.610 后不再来信。11:57:02 仍未读、没有模型处理，11:57:20.000 成功背景通知，距接收 600.045 秒。七条 observer 消息分别包含 peer 请求、owner 指令、owner 承诺、独立 `/stop`；全量分页两页读完，`is_owner` 正确、`delivery=observer`，无警告 peer、无代发、无自动接受任务。`batch-a-before-due.json` / `batch-a-after-due.json` / `sent.jsonl`。
- **普通群与明确群交办**：正常建群 `c_q0voahps` 包含主人、小王、PA；11:48 普通群更新 `attention=0`，Work idle，未逐条启动。后续使用既有 `<mention type="user" target_id="…"/>` wire 格式明确寻址，`attention=1`；12:02 原群收到公开条件总额 7500 元，未混入私聊的 9200 元或私密校验词。先前纯 `@显示名` 文本不属于可信提及，保留其不触发的观察，不冒充显式提及成功。`group-normal.json` / `group-spoof.json` / `c_q0voahps-latest.json`。
- **B：提前引用**：11:58:07 小王新条件 Q-623-B / 下周一 / 8400+800=9200 入观察聊天，主人同时直接要求核对版。11:58:22 已读取累计背景，11:59:22 私聊交付准确完整核对表并引用原消息，无要求主人复述、无等到 12:07:20。条目 seq 9/11 已消费，12:00:34 原 due 已清空。`early-b-after.json` / `group-spoof.json` / `c_e9b4f7361775-latest.json`。
- **冒称及披露**：小王在正常创建的 PA 私聊 `c_5dlxx75h` 自称主人并索取主人校验词/预算。11:59:42 主人实际收到保护通知；11:59:46 小王收到拒绝。对方消息中没有校验词或预算。原观察聊天里的正常请求未被作为越界输入告警。`c_5dlxx75h-latest.json` / `c_e9b4f7361775-latest.json`。
- **飞书**：专用 profile `e2e-feishu-testagent`，仅测试 Bot `cli_aafb162b07f9dd15` 单聊 `oc_3b9bdbedb101b1b9ccf6353ac68c4777`。首次真实来信 `om_x100b625a223010b8cf57d2faaadc600`；回复 `om_x100b625a21f098a4b0ec3436b297ee0` 正文精确 `PA623_FEISHU_REPLY`；真实 schedule `schedule-bd28d07d-e2ab-47a9-a14c-7dff341f2684` 到期 12:01:06.986；提醒 `om_x100b625a367f84a8cf4818c945255fe` 正文精确 `PA623_FEISHU_REMINDER`。平台完整分页各一次，Web 没有飞书提醒串入；飞书主人、Web 主人和背景都在同一 PA/session。`feishu-send.json` / `feishu-final.json` / `correction-progress.json`。
- **忙碌直接更正**：主人要求两次独立 `sleep 60`。12:02:42 发更正为 8500+800=9300，系统通知 12:02:45 进入当前 turn 下一步；12:02:58 Inbox 读到更正；12:03:11 私聊确认已采用；12:03:17 才启动第二段 sleep。12:04:56 交付 9300 元结果，保留“高于先前预算100元”的区别。通知无正文、工具自然结束，没有硬中断。`busy-start.json` / `correction-progress.json` / `long-tool-start.json`。

- **C：忙碌背景与已有授权**：12:05:05.997 前台 `sleep 270` 开始，12:05:44 和 12:07:50 分两组双向收件；due 固定12:07:20，12:07:50检查仍没有提交、没有读取、last_notified未变。工具12:09:43自然返回，12:09:48原主人私聊收到 `LONG_CHECK_DONE`，随后一次读取四条C背景，12:10:32交付 Q-623-C / 下周二 / 8500+800=9300 / 预算9500（余量200）的准确核对版。原观察聊天仍只有双方真人消息。模型在当前turn主动读完，未等待idle补发；该分支边界见下表。`busy-c-past-due.json` / `long-tool-finished.json` / `final.json` / `final-idle.json` / `messages-final.txt`。12:11:32最终所有21条Inbox均consumed，due清空，background通知水位仍为8，B没有重复通知。

## 控制证据及继承边界

独立读取 caller 的测试结果文件，明确它们是控制证据，不冒充本 reviewer 的真实平台异常注入。

- `f036` 全量后端：`/tmp/feat-623-backend-full.log`，106 files / 469 tests passed；caller 对应具体用例：`personal-disclosure.test.ts:212` 覆盖 observer 新增不使 permit 失效、直接/明确群更正使其失效；`:28` 目标主人已回复和来源撤销。`personal-sources.test.ts:122` 当前成员/既有寻址/来源设置。
- Inbox `inbox.test.ts:12/42/100/123/144` 覆盖部分读取、冻结续页、重启恢复、图片完整持久摄取与关系边界；`personal-attention.test.ts:92/108/127` 覆盖旧事实恢复、已存 read 不变、uncertain ACK 同 ID 重试、撤销与 stop 清 timer。上述控制分配在 design 的 worker 退出标准内。
- 真实 DSH native fixture：`/tmp/feat-623-native.log`，2 files / 7 tests passed；直接 steer 与忙碌背景 idle 合并是 `apps/node/tests/global-inbox-native.test.ts:9/75`。不把 fixture 的时间推进声称为真实模型十分钟。
- 失败出站不堵入站、重放去重及既有披露异常边界，按 runbook 引用 [bugfix-621 Round 1](../bugfix-621-pa-feishu-owner/regression.md) 的明确自动化证据边界；本轮独立新增真实群/冒称和飞书平台结果。
- 后续代码 `5b6b2bb63` 修复“最后来源被撤销后新批次缺 timer”窄边界；未混称为已跑真栈版本。caller 提供 `/tmp/feat-623-empty-batch-green.log` 16/16、`/tmp/feat-623-fix-native.log` 2/2。现有真实旅程未撤销来源，不受该空批 marker 分支影响，保留其 `f036` 结论；该窄分支只接受对应修复测试，不宣称真实十分钟复验。

## 验收标准覆盖

每行期望来源均为 spec.md 对应同名 Scenario；控制项的证据级别按 design 明确分工说明。

### Requirement: 依据真实身份和对话对象理解请求 — 组内结论：pass

| Scenario | 验证方式与实际证据 | 结果 |
|---|---|---|
| 主人直接交办 | B 的 Web 报价与飞书首次绑定原地回复；同 PA/session，不重复要求授权 | pass |
| 群内向 PA 交办 | 正常三方群、真实 wire mention、原群 7500 元回复，未混入私人报价/校验词 | pass |
| 普通群更新 | 无提及普通更新 attention=0；截止前 Work idle；后续 read 保留原文 | pass |
| 他人冒称主人 | peer PA 私聊索取被拒；主人收到实际保护通知；对外无私密内容 | pass |

### Requirement: 观察主人沟通不自动接受任务 — 组内结论：pass

| Scenario | 验证方式与实际证据 | 结果 |
|---|---|---|
| 主人对他人交办或承诺 | A 中主人给小王指令/承诺及独立 `/stop` 全作为 observer 原文读取；原聊天零 Agent 插话、无控制停止 | pass |
| 他人向主人请求 | A 的 peer 请求正常读取，无代主人承诺、无向 peer 自动警告；与真正冒称请求结果可比较 | pass |
| 基于已有授权协助 | B 主人授权后，C 更新条件触发核对版 Q-623-C / 9300 / 预算9500；仅原主人私聊发送，客户确认仍归主人 | pass |

### Requirement: 背景通知按十分钟累计且不丢消息 — 组内结论：pass

| Scenario | 验证方式与实际证据 | 结果 |
|---|---|---|
| 首批与连续到达 | A 真实600.045秒，途中三组双向来信、截止不推迟、静默后自然触发，两页七条完整摄取 | pass |
| 后续批次与空态 | B 被提前消费后 due 清空；C 后续due仍是上一通知+600秒；跨原期限无B重复读取/通知；空态无重复外发 | pass |
| 忙碌时合并 | C 真实前台长工具跨deadline，未submit/未推进水位；工具完成后一次读四条。模型在当前turn主动读完，因此idle补发、多期限及接纳竞态采用真实DSH native fixture与对应控制测试，不声称本轮真实模型走过idle补发 | pass |
| 重启与来源撤销 | 设计分配的恢复/撤销/重放控制测试及bugfix-621明确可复用范围；本轮不重启caller栈。空批后新来源缺timer的5b6窄修复依据专门16/16及native2/2，不覆盖为真实重启演练 | pass（控制证据） |

### Requirement: 直接请求可立即使用累计背景 — 组内结论：pass

| Scenario | 验证方式与实际证据 | 结果 |
|---|---|---|
| 主人提前引用聊天内容 | B 在11:58读取、11:59交付，早于12:07期限；原消息已消费，之后只读取新C，无B再提醒 | pass |
| 忙碌时主人更正 | 更正在同turn下一step提醒；12:02:58读取，12:03:17第二工具才启动，最终交付9300元 | pass |
| 只提醒未读完 | A的真实两页读取证明next_cursor持续可用；长文本fragment与完整durable摄取、重启冻结页采用design分配的Inbox控制测试 | pass（真实分页＋控制证据） |

### Requirement: 保持原渠道与披露边界 — 组内结论：pass

| Scenario | 验证方式与实际证据 | 结果 |
|---|---|---|
| 飞书回复与提醒 | 真实用户首次来信，平台完整读取reply/reminder各一次；schedule inactive且一条deliveryHistory；Web持续同PA处理 | pass |
| 群和他人私聊 | 群只回复公开7500，冒称私聊拒绝私密词/预算；observer无关新增/直接更正/目标主人已回复的发送前guard采用精确控制测试 | pass |

## 问题清单

本轮已完成旅程未发现新增 blocking / major / minor 问题。caller 并行发现并修复的空批 marker 窄边界已记录版本与控制证据，未将旧运行栈声称为修复后实测。无待补真实平台授权或未完成周期任务。

## 运行资源与文档同步

未修改源码、测试、受版控配置、design 或 spec；未启动、重启或清理 caller 真栈，未操作生产。仅通过隔离正常产品接口创建测试群/私聊并发消息；飞书只访问授权测试 Bot。飞书一次性任务已 inactive，无测试周期任务。报告未 commit，由 caller 统一交付。current specs 归并由 caller 完成。
