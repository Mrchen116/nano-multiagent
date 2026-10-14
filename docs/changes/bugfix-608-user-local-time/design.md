# bugfix-608: As-built Design

> 本文在快速开发实现完成后根据实际代码、diff 与已确认决定整理。

## 实现范围

- Base: `20400dffb6b5877169d444377f573188e217485e`
- Implementation: `e8adc2784e6c3fd4cfbd07cd438f988584447dab`
- Review fix: `d0a224ced807d885aadadcc02690f8d7821e0bb5`
- Worktree: `/Users/czj/.codex/worktrees/user-local-time/nano-multiagent`
- 原 checkout 的其他 dirty/untracked 内容未纳入本次提交。

## 最终结构

1. Web 使用 Intl 系统 timezone，iOS 使用 TimeZone.autoupdatingCurrent。打开/回前台 PATCH 当前账号 timezone，发送消息也携带新读取值。后台不轮询。前台报告不能因客户端缓存相等而跳过；Web 仅去重相同时区的在途请求。
2. IM 校验 timezone，写入 users.timezone；值变化才写库并向所属节点发送 user.timezone。节点注册 ACK 返回 owner_timezone；NodeStore 持久缓存，因此客户端关闭后仍可使用。
3. IM 原子保存 messages.created_at 和 timezone。幂等重试返回原消息快照。外部渠道把飞书原始毫秒时间固定为 created_at；有可信 ownerOpenId 映射的 owner 使用缓存时区，未知外部发送者不冒用 owner 时区。
4. SingleThread 给模型追加独立时间/入口块，global Inbox 和历史读取返回本地时间。共享 formatLocalTime 生成带 UTC offset 的 ISO；用户可见正文不变，NativeHistory 简化副本去掉精确匹配的 envelope，原生完整轨迹保留模型输入。
5. Heartbeat 使用同一缓存时区解释 active hours 和 HEARTBEAT.md 内 cron，并在系统唤醒里提供当前本地时间。相对 every 节律不变，DSH 原生定时工具不变。

## 状态与失败边界

- users/messages nullable timezone 通过幂等迁移添加；旧消息不补造当前时区。已有 active_hours.timezone 在未收到用户时区时作为旧配置来源，收到后以用户值优先。
- 未知用户时区的消息保留明确 UTC 原值，不伪装成本地时间；无已知时区的时钟窗口/文件 cron 不按 Gateway 系统时区猜测。无时段限制的相对 Heartbeat 仍可运行，并标明 user timezone unknown。
- 同步失败下次前台或发送重试；已有缓存继续供外部渠道和 Heartbeat 使用。
- 回滚代码不删除已存数据；新列/独立缓存表可以保留，不需要破坏性数据库回滚。

## 关键决策

| 决策 | 原因 | 代码定位 |
|---|---|---|
| 客户端采集，IM 保存，Gateway 缓存 | Gateway 所在地不能代表用户所在地；离线机制仍需可用 | user-timezone.ts、IMClient.swift、identity-routes.ts、apps/node/src/main.ts |
| 每条消息冻结 timezone | 切换设备/时区后历史语义仍准确 | messaging.ts、external-channels.ts、inbox.ts |
| 前台每次报告，服务端抑制相同值写入 | 多设备会改变共享账号的权威时区 | useUserTimezone、syncTimeZone、updateUserTimezone |
| 无手动 timezone 表单 | 用户明确要求按系统所在地时间 | AgentConfigView.swift |

## 验证定位

- 全量后端：`pnpm test`，82 files / 309 tests passed；`pnpm build`、`pnpm typecheck` 通过。
- 全量 Web：`npm test`，94 files / 873 tests passed；生产构建通过。
- 审查修复后：IM timezone 跨进程 HTTP/WS 测试通过；Web timezone/chat-api/i18n 3 files / 18 tests passed。
- iOS：模拟器 build 通过；完整测试 29 XCTest + 17 Swift Testing 通过；审查修复后 SessionTests 7 tests 通过。Release archive 通过，未签名 arm64 IPA 位于本机临时构建目录。
- 架构依赖契约：13 passed；完整非 E2E Python tooling：56 passed / 31 deselected；docs-check 与 diff-check 通过。
- 浏览器：隔离 IM `127.0.0.1:61534` + 独立 Gateway；真实 Chromium 自动读到 Asia/Shanghai，登录后 IM users.timezone 与 Gateway owner_timezone 均为 Asia/Shanghai；第二标签通过 Chromium CDP 模拟 Asia/Tokyo，刷新后两处都变成 Asia/Tokyo。原标签加载最终 bundle index-DnIvtXX0.js 后，保持其上海系统时区，手动派发 focus 事件，两处都恢复为 Asia/Shanghai（PATCH 200）。这里验证了真实浏览器事件处理、HTTP 和 Gateway 接线，focus 事件由自动化模拟，不宣称完成两台实体设备验收。
- 本机运行定位：`/tmp/nano-user-local-time-ios-test.log`、`/tmp/nano-user-local-time-ios-test-final.log`、`/tmp/nano-user-local-time-ios-archive.log`、`/tmp/nano-user-local-time-web-build-final.log`、`/tmp/nano-user-local-time-python-tests.log`；浏览器网络记录位于隔离 worktree 的 .playwright-cli，均不提交到仓库。
- 长期覆盖归属：IM 新 timezone e2e 保护账号持久化/WS 同步/幂等快照；Web 新生命周期测试保护前台与后台边界；其余 inbox、external-channels、single-thread、heartbeat、native history 和 iOS Session/ChatState 扩展既有覆盖，未创建里程碑专用测试。
- 自动化渠道 fixture 使用真实 provider 时间字段，但未向生产飞书账号发送；模拟器与 API 测试不替代 iPhone 真机验收。
- 用户亲自验收：尚无确认，unit 保留 active。

## Canonical 文档影响

本目录 specs/ 保存最窄 delta：IM 账号时区、Gateway 真人消息时间、global Inbox 时间和 Heartbeat 本地时间。用户实际验收后再归并对应 current 文档。
