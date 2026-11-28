# bugfix-818-auth-session-lock-recovery: Review

## 范围与版本

- 本次问题与需求/设计位置：[fix.md](fix.md)（跨标签页 Web Locks 无超时阻塞、非 `SecureContext` / 受限存储与广播兼容、认证与身份核验半开请求超时、`hydrate()` 异常收敛与 `revision` 并发保护）及 [docs/specs/im/auth-tenancy.md](../../../specs/im/auth-tenancy.md)
- 实际 `executed_base` / `validated_at`：`890d74f70d1444f2fd961a7e60d02b858821abaa` (`origin/develop`) .. `98655817ada33a5e60980afac80a5329e4398e30`
- 最终 `effective_base` / `effective_through` 与保留依据：`890d74f70d1444f2fd961a7e60d02b858821abaa` .. 本归档提交；`98655817a` 之后仅新增本报告、补充 `fix.md` 链接并执行 `docs/changes/archive/` 目录归档，产品实现、测试与 canonical spec 零变更，原审查与测试证据完整保留（`retained`）。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| R1：跨标签页 Web Locks 超时降级与获锁异常不重放 | `change-code-review`（独立 subagent `043648ba-6d2f-42d0-99b8-1cd59aff90c7`，`full`） | pass | 核实 `auth-session.ts:104-152` 在 8s 锁等待超时后 `abort` 排队请求并降级至 `enqueueInTab` 执行一次；获锁回调在执行 `operation` 前置 `state = "granted"` 并清定时器，业务/网络异常原样抛出不重放；`auth-session.test.ts` 红绿单测验证通过 |
| R1：非 `SecureContext`（明文 HTTP）与受限 `BroadcastChannel`/`localStorage` 兼容及 `hydrate()` 收敛 | `change-code-review` + `frontend-experience-review`（独立 subagent `043648ba-6d2f-42d0-99b8-1cd59aff90c7`，`full`） | pass | 核实 `navigator.locks === undefined`、`BroadcastChannel` 缺失/抛错、`localStorage` 受限均安全降级；`auth-store.ts:81-99` 与 `auth-session.ts:200-213` 确保无 `{ hydrated: false, hydrationError: false }` 悬停死态，`LoginPage` / `RequireAuth` / `MembershipPage` 收敛至登录表单或可重试提示并保留受保护深链 |
| R1：半开连接请求超时与 `revision` 并发栅栏 | `change-code-review`（独立 subagent `043648ba-6d2f-42d0-99b8-1cd59aff90c7`，`full`） | pass | 核实 `auth-api.ts:38-58` `withAuthRequestTimeout`（10s）覆盖请求与响应体读取并在 `finally` 清理定时器，无未捕获 rejection；`require-auth.tsx:32` 透传超时 `signal`；`startRefresh`、`restoreSession`、`establishSession`、`logout` 全链路双检 `revision`，延迟响应不覆盖或误登出新会话 |
| R1：`docs/specs/im/auth-tenancy.md` 最终契约校对 | `change-code-review`（独立 subagent `043648ba-6d2f-42d0-99b8-1cd59aff90c7`，`corrected-delta`） | pass (`aligned`) | 新增两条 `AND` 子句准确表达跨标签协调受阻、非安全上下文及请求无响应时的有界恢复与防覆盖保证，与实现、单测及服务端明文 HTTP Cookie 策略一致，未固化内部超时常数 |

## Findings 与关闭

无存活 `CONFIRMED` 或 `PLAUSIBLE` findings（`[]`）。

## 流程收口

- 重要目标和关键设计覆盖：用户反馈的 Web Locks 永久卡死及三条关联根因（锁无超时、非安全上下文 `navigator.locks` 缺失与存储/广播受限、认证请求无超时及 `hydrate()` 异常未收敛）均已闭环修复并由回归单测覆盖，严格遵守文件所有权边界。
- 开放问题 / pending / inconclusive：无。
- 最终 delta 校对：`docs/specs/im/auth-tenancy.md` 已归并，独立审查结论 `aligned`。
- 版本变化后保留 / 补验的判断与依据：归档提交仅移动 unit 目录并写入审查记录，代码与规格未变，沿用 `98655817a` 验证结果。
- 测试资源回收结果：未启动常驻后台服务或浏览器进程；`src/IM/frontend/dist/` 本地构建产物已清除；按规定保留当前开发 worktree 供 PR 审查。
- 交付范围与剩余事项：归档后推送分支并向 `develop` 创建 PR，跟进远端必需 CI 检查，不自动合并、不触碰生产环境。
