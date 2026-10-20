# bugfix-621 — 回归验证

> 对齐: [incident.md](incident.md)；Round 1，2026-10-20 10:04–10:10 Asia/Shanghai。
>
> Validation snapshot: `0fa706a67 → fad8b8355716a73165bf0d688644dfbf0cc84dde`。

## Verdict

**pass**。无 blocking / major / minor 问题。真实飞书主人来信、原单聊回复、两次一次性提醒实际平台收件、Web 主人私聊均通过。失败隔离及非主人/群聊边界按 design 的 worker 退出标准复用自动化结果；未声称在真实平台制造这些异常。

隔离 IM 为 `http://127.0.0.1:62652`，node `wt-nano-multiagent-19058`，正式 PA `pa_52a910e43b0f`。独立检查 HEAD、进程启动路径和产物时间：服务运行本 worktree 的 lib，产物 10:00:34–36、服务 10:00:54–58 启动，晚于 caller 交接的构建；客户端无改动，沿用既有 dist。本轮未改实现、测试或配置，未操作生产。唯一真实平台目标为专用测试 Bot 的单聊 `oc_3b9bdbedb101b1b9ccf6353ac68c4777`。

## 复现验证

使用 lark-im skill 的 `lark-cli --profile e2e-feishu-testagent im +messages-send --as user` 从真实用户入口发消息；用 `+chat-messages-list --as user --no-reactions` 独立读取飞书实际收件，返回 `ok:true`、完整分页。没有直接注入 runtime。

| incident Scenario | 实际观察 | 结果 |
| --- | --- | --- |
| 飞书主人来信 | reviewer 于 10:06:22 发出请求 `PA621_REVIEW_REPLY_1006` 并安排一个两分钟提醒，来信 `om_x100b6258872e15a4ceb797856428a8b`；平台收到回复 `om_x100b6258857898b0b059e455faf506f`，正文包含准确回复标记。创建确认另有消息，属于同次交办的阶段反馈。 | pass |
| 到时主动提醒 | 独立提醒 `schedule-3228ba03-4c07-4911-a7f9-31f2c9be0b52` 到期 10:09:14.705，10:09:14.718 投递至原主会话；飞书实读 `om_x100b62589bc854bcce5c0699ce4956e`，正文精确为 `PA621_REVIEW_REMINDER_1006`。ExternalStore 为 confirmed，同一 platform_id。 | pass |
| 旧输出失败后的新来信 | 复用 `/tmp/bugfix-621-focused.log` 的 7 files / 100 tests passed（10:00:38），caller 交接范围为输入与旧输出隔离、恢复及重放去重。真实平台本轮未制造旧输出失败；按 design 的 worker 退出标准接受该层证据。 | pass（自动化） |
| 非主人或群聊 | 同一 focused 运行覆盖身份、原始授权、非主人与群聊边界。本轮仅获专用主人单聊授权，没有向其他目标发送私密信息；未声称真实群聊实玩。 | pass（自动化） |

独立读取 caller 先前 10:04 来信 `om_x100b62588cfe34b0cd0f935e822bad1`，也实际收到回复 `om_x100b62588d28d880ce8a5f7c4d99e67` 和提醒 `om_x100b6258819514b0cd3a54305c30390`（正文 `PA621_REMINDER_1005`）。因此原复现中的“不回应”和“提醒无法送达”在本测试样本均未再现；不推断生产每日任务已经恢复。

## 回归测试

- **Web 主人私聊 pass**：通过前端 `chat-api.ts` 使用的实际 REST 入口，于 10:06:32 向 canonical DM `c_35fde076c312` 发送请求，消息 `d3fb74b27c7445f78324e4f499f48c5a`；GET messages 读取 PA 回复 `9f5dcfaa0537456e86999f8eb8a4ff0c`，正文精确为 `PA621_WEB_REVIEW_1006`。飞书完整读取中没有这个 Web 回复，原渠道区分正确。
- **同一个 PA / 单次接入 pass**：只读 global.sqlite3 的 inbox 恰有三条输入，两个飞书中心消息 ID `65b49ee28db842588e88b2ea5292e47a`、`ab2ee87af12b44e8b1cd5d9322d5a521` 与上述 Web ID 各一条且 consumed=1；ingestions 均指向 `35d34236-f4c7-4817-a8cd-08378e63f25a`。两个 schedule 也属于该 session，各有一次 deliveryHistory，结束后均 inactive。每个提醒平台正文各出现一次。
- **体验范围**：本 unit 无客户端 UI 变化，按 runbook 使用客户端同一 API，无 viewport / 原型 must-match 项。用户交办后能在原飞书单聊阅读确认与实际提醒，在 Web 私聊阅读 Web 回复；本轮未宣称观察飞书原生排版、THINKING 动画或 Web 视觉布局。
- **证据链**：`/tmp/pa621-review-evidence/feishu-final.json`（真实平台完整消息列表）、`web-latest.json`（Web 回读）、`persistence.json`（只读 inbox/ingestions/source events 快照）、`outputs-final.json`（平台 confirmed 回执）、`schedules-final.json`（同会话调度及一次性结束状态）。这些为本机临时证据，不提交日志/数据库/凭证。

## 自动化测试增量

本 reviewer 不修改或重新设计测试；引用 caller 的 focused 100 pass 作为设计明确分配给 worker 的权限与异常回归证据。真实飞书发送、平台读取、Web API 和只读持久状态由 reviewer 独立执行核实，未以 worker 成功叙述代替。构建、全量 CI、静态代码审查由 caller 另行汇总，本报告只作产品回归裁决。

## 上层文档同步

- [x] `SPEC.md`：无需更新，保持原 DSH 与跨包职责边界。
- [x] `docs/specs/<包>/`：需要由 orchestrator 归并本 unit 的 gateway global-agent / external-channels delta；本 reviewer 不修改。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

保留 caller 正在使用的隔离服务；本 reviewer 未启动额外服务。两个一次性提醒已 inactive，无后续周期发送。
