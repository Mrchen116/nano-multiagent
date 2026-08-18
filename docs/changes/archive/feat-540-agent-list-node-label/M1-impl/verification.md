# feat-540-M1 真栈验证记录

> 日期: 2026-08-18。验证人: 实施上下文(orchestrator-simple)。验收闸(change-reviewer)独立复验前的实施自证。

## Claim

design.md Milestone 表退出标准 1-7、9 的用户可观察行为,在真实 IM + 双 Gateway 栈 + 真实浏览器(vite dev + Playwright)上成立。

## 环境

- worktree: `.worktrees/unit-feat-540`,`./scripts/e2e-up.sh` 起 IM(:62686,隔离端口)+ Gateway 1(`wt-unit-feat-540-38743`,agents: e2e、e2e-peer)。
- Gateway 2 手工起于隔离 runtime 目录 `.gateway-air/`(gateway runtime_dir = config 所在目录,同目录会与 GW1 撞 channel-manifest):node `wt-feat540-air`,agents: air-planner、air-researcher、migration-verification-20260816。
- 别名: `PATCH /im/v1/nodes/wt-feat540-air/config {alias:"工作室"}`(真实 API)。
- 前端: `npm run dev -- --port 5410`,`VITE_IM_PROXY_TARGET=http://127.0.0.1:62686`。
- 浏览器: playwright-cli,desktop 1280x720 / mobile 390x844(viewport resize)。

- 2026-08-18 19:00 UTC: 应用 code-review 关闭项后,在 worktree 内重跑 `cd src/IM/frontend && npm test`: 69 files / 677 tests passed;`npx tsc -b` exit 0。额外改动:shared `initialsOf` 抽到 avatar.tsx、hover 改为 Tailwind 类、focus-visible 恢复、nodes queryKey 合并、`nodesPending` 防闪、nodes-page alias 编辑后失效 agents 缓存。

## 结果(逐退出标准)

| # | 标准 | 结果 | 证据 |
|---|---|---|---|
| 1 | 多设备逐条标注,与 Account 页一致,含别名 | pass。e2e/e2e-peer 标 `wt-unit-feat-540-38743`,air 三个 agent 标 `工作室`(alias 优先);Account 页同设备亦显示「工作室」 | screenshots/desktop-index.png |
| 2 | 设备离线仍显示归属 | pass。停 Gateway 2 后 `/im/v1/nodes` 显示 offline,air 三条目角标转灰、`工作室` 保留 | screenshots/desktop-offline-node.png |
| 3 | 无归属留空 | **产品内不可达,降级为单测锁定**(见下「边界说明」) | agent-row.test.tsx |
| 4 | 移动端同样标注,› 保持 | pass。390px viewport:每条右上是设备名、› 在其下,第二行为 description | screenshots/mobile-index.png |
| 5 | 名字两行与行高不被挤压;状态由头像角标;右缘无圆点 | pass。三处列表行高 52px 不变;在线/离线仅从头像角标辨认;DOM 快照右缘无独立圆点 | screenshots/desktop-index.png |
| 6 | 原型 must-match 一致(含超长 ID、别名) | pass。超长 ID 行(migration-verification-20260816)名字截断、`工作室` 完整;超长设备名(wt-unit-feat-540-38743)设备名自身截断 | screenshots/desktop-index.png |
| 7 | 桌面首页未选中条目浅色可读,三处观感一致 | pass。首页侧栏 0.86/0.64 浅字(before 为 0.18 深字,修复点),首页/详情/新建三处一致 | screenshots/desktop-index.png(before 对照见 prototype.html) |
| 9 | 真实浏览器截图对照 prototype.html | pass。console 无错误(仅 vite hmr 噪声) | 本目录 screenshots/ 全量 |

## 边界说明(spec 偏差,已按用户裁决收口)

Scenario「无归属信息的条目右缘留空」在真实产品内**不可达**:`GET /im/v1/agents` 的 SQL 强制 `JOIN nodes` + `WHERE ap.node_id IS NOT NULL AND ap.node_id != ''`(`src/IM/infra/repositories/agents.py:72-100`),无归属 agent 根本不进列表。曾直接向 DB 插入 `node_id=NULL` 的 profile 验证,列表确实不返回它(已删除该临时行)。

**裁决(2026-08-18,用户原话):「这种压根不会出现的场景就不应该写,改干净」**——该 Scenario 已从 spec.md / delta-spec / M1 退出标准 / prototype.html 删除(spec Q8,design Changelog 第二条)。组件层防御性渲染(无 `node_id` → 不渲染设备名;节点表缺失 → 回退显示设备 ID)保留,由 `agent-row.test.tsx` 锁定,M1 退出标准 3 转为 [worker] 轨单测覆盖。本表退出标准 3 一行据此同步。

## 进程与现场

- 运行中(供 change-reviewer 复验):IM(.im.pid)、Gateway 1(.gateway.pid)、Gateway 2(.gateway-air.pid)、vite(:5410,.vite.pid)。token 缓存 `.e2e-token`(过期需重新 login,见本文件上方命令)。
- 验证结束后由 orchestrator 收尾统一清理(`e2e-down.sh` + 杀 vite/GW2)。
