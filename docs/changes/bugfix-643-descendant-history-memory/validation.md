# bugfix-643: 验证记录

日期：2026-10-23。Base 为 `520d5432e7b614af4624cf10678697f48bc56fcb`，受审代码指纹见 `code-review.md`；Node 24.22.1、锁定 DSH 0.2.1-alpha.1。

## 冷历史压力与输出一致性

Claim：大量冷后代的完整继承历史不再同时保留，投影内容不丢失。

Method：复制 Air 三个根执行的 645 份后代持久日志到隔离目录；基线从 base 源码转译，修复版直接读取本 worktree 编译产物，分别提取实际 `session.descendants` 注册函数执行。历史读取使用真实 DSH 公开 SessionStore / SessionQueryEngine / JSONL persistence；根执行、后代目录、workflow/model 信息为固定 fixture，工具展示通过一次 `setImmediate` 模拟跨 I/O 等待并保留输入事件。不连接生产、不启动 Agent 或模型、不改源日志。

| 版本 | V8 堆上限 | 完成后代 | 自有事件 | 采样峰值 heapUsed | 输出 SHA-256 |
|---|---:|---:|---:|---:|---|
| 基线全量并发 | 8192 MiB | 645 | 33,583 | 4568 MiB | 相同 |
| 修复顺序读取、提前释放 | 1024 MiB | 645 | 33,583 | 386 MiB | 相同 |

两个正常退出的复跑输出哈希均为 `49f4da9f8981a972c97b7bf20b929a101e8ad3666281b8f127348b6899788a4c`。最初两次探测也完成并得到同一哈希，但随后使用了不存在的 `ctx.dispose()` 清理接口；已改为 persistence 插件 fiber.dispose 并重跑，表中仅采用退出码 0 的结果。

Locator：本机 `/tmp/nano-air-oom-20261023/handler-probe.mjs`、`handler-baseline-verified.log`、`handler-fixed-verified.log`。验证后删除隔离目录内复制的全部会话正文，仅保留脚本、统计和诊断定位；生产文件未变。

Limit：这是实际处理函数的隔离压力验证，不是完整服务/E2E。堆上限不同会影响 GC，采样点不等于精确最大值；不把表中比例或耗时作为严格性能指标。它直接证明修复版在 1 GiB 上限内完成同一批投影且结果一致。单日志及完整自有事件响应的成本仍存在；生产恢复和消息送达尚未验证。

## 自动化检查

| 检查 | 结果 / 定位 |
|---|---|
| `pnpm -r --if-present build` | 通过；`/tmp/bugfix643-build.log` |
| `pnpm typecheck` | 通过；`/tmp/bugfix643-typecheck.log` |
| `node scripts/build-node-release.mjs` | 通过；本地构建，不代表发布或部署 |
| `pnpm check:ios-runtime` | 通过；`/tmp/bugfix643-ios-runtime.log` |
| `tool-presentation` / `trajectory-runs` / `global-agent` | 3 文件、48 项通过；`/tmp/bugfix643-focused.log` |
| runtime dependency contract | 13 项通过；`/tmp/bugfix643-contract.log` |
| `./scripts/docs-check` / `git diff --check` | 通过 |
| 全量 `pnpm test` | 122 文件、596 项：595 通过、1 失败；详见下段 |

全量失败是 `knowledge-review.test.ts` 的 F4 自动整理测试：第 131 行等待 `f4-held` 超时；其余 121 文件通过。该文件隔离运行仍为 3 通过、1 同样失败，不能归因为已经证实的并行负载。日志：`/tmp/bugfix643-all-tests.log`、`/tmp/bugfix643-knowledge-isolated.log`。该测试没有调用本次更改的 `session.descendants`。随后基线源码转译版单项及整文件均通过，修复版单项通过，最终修复版整文件也 4/4 通过（`/tmp/bugfix643-knowledge-fixed-final.log`）。这是间歇失败；具体原因尚未确认，不把一次复跑通过写成全量 gate 全绿。对照只临时替换本 worktree 的 ignored 编译产物，并在 finally 中恢复修复版，未修改受审源码。

## 交付边界

独立代码审查通过。用户尚未实际验收；unit 保持 active，未归档，未推送 PR、合并或部署。没有改动原工作区或生产配置，没有补发真实消息。未运行无关前端/iOS 原生 gate，不宣称完整本地 CI 全绿。
