# bugfix-706: Web 聊天历史日期与 iOS 对齐

## 原始报告

> 我发现现在一个问题，就是现在iOS版本在聊天框里面是能看到一些历史消息它的日期的，但是我在网页版好像看不到日期。你确认一下现在是不是有这个问题？

> 那帮我把网页版也补上日期展示，和 iOS 保持一致。

## 现象 / 复现

Web 打开包含多日历史消息的聊天，只能看到消息下方的时分，不能直接判断消息日期。iOS 在首条、相邻普通消息间隔至少五分钟或跨本地日期时显示独立时间分隔，当天仅时分，其他日期显示年月日和时分。

范围：Web 聊天记录增加相同规则的独立日期/时间分隔，覆盖历史分页与实时消息；保留现有气泡时分、状态、配置边界和系统通知，不改服务数据或 iOS。

## 根因

Web `message-pane.tsx` 的 `formatHM` 从 `86b07fee77` 起仅输出时分；时间线直接渲染消息，没有日期分组。iOS 在 feat-636 追加消息元信息精简时独立实现首条/五分钟/跨日分隔（`ChatTimelinePresentation` 与 `ConversationView`），Web 没有同步该能力，属于能力差异，不是日期数据丢失。已有 Web 测试只核对气泡下方时分，没有覆盖多日历史日期。

参考意图：feat-636 的 spec 与 design 要求减少元信息冗余且保留完整日期/时间语义；本修复采用其时间分隔规则，系统通知不参与普通消息分组，配置边界仍锚定对应消息。

## 修复

- `ea359b4fd`: 时间线新增轻量居中日期/时间分隔，按浏览器本地日期及界面语言格式化；已加载消息每次变化时重新分组，保留原消息组件和气泡时分。
- `5c22d341a`: 补齐测试消息 fixture 的必填权限字段；`a398b7d67`: 同步 IM current spec 索引。
- 纯 Web 展示调整，不改变存储、服务协议、模型上下文或 iOS；无部署迁移。

## 验证

- 测试策略：在 MessagePane 渲染层保护用户实际可见的日期分隔，覆盖本地午夜、相邻不足/恰好五分钟、系统通知与配置边界、历史前插与 live 追加。新建独立短文件，既有超长 message-pane 测试保持不变；既有气泡时间与 memo/系统通知回归保留。
- 修前新增三项用例全部因缺少日期分隔失败（`/tmp/bugfix706-red.log`）；修后相关四个文件 120 tests passed（`/tmp/bugfix706-green.log`）。全部前端 112 files / 1059 tests passed（`/tmp/bugfix706-web-tests.log`）。
- `pnpm build`、`pnpm typecheck`、Web production build、`pnpm check:ios-runtime`、Python non-E2E 129 tests、ruff check/format、docs-check、npm critical audit 均通过；日志位于 `/tmp/bugfix706-*`。构建保留既有 chunk size / bundler 注解告警，audit 存在低于 critical 阈值的依赖告警，未升级依赖。
- 实际浏览器：使用专属 worktree 内 IM，独立测试账号 nano，SQLite 中加入四条隔离展示消息（无模型调用）；从登录页进入真实 `/chat/chat-dates-706`。中文页面实际显示 `2026/11/2 23:58`、`00:00`、`00:09` 三个分隔；00:04 不重复。原气泡时分与输入框可见。快照 `.playwright-cli/page-2026-11-03T14-51-54-388Z.yml`，本地图片 `output/playwright/bugfix706-chat-dates.png`，不提交缓存；图片截取前服务已停止，顶部断线提示不作为实时链路验收。只证明日期展示，不冒充模型、Gateway 能力或 iOS 实测。
- 隔离 daily 起栈的 Agent capability 同步返回 504，故未宣称 daily 模板 ready；IM 聊天读取与浏览器日期展示已实际验证。临时 IM/Gateway 与浏览器均已关闭，`/tmp/bugfix706-e2e-down.log` 为 `STOPPED`。
- 独立 code review 及闭环见 `code-review.md`，无存活 finding。
- 初次额外 root `pnpm test`：210 files 中 192 passed / 18 failed，1125 tests 中 1096 passed / 29 failed，另有 EPIPE。失败集中在未修改的 DSH/Node 原生运行时测试，包含 capability deadline 和测试超时；这不是全绿结果，不能仅凭改动范围断言根因。保留 `/tmp/bugfix706-runtime-tests.log`，仅对该批失败文件以 `--maxWorkers=2` 复跑，不修改后端或增加测试超时。
