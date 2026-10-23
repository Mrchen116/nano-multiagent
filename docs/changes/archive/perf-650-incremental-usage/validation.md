# perf-650 收尾验证

## 版本与门禁

- actual `validated_at`: `cc091e4b9a396e87a659fedadb296c5a924d80e4`。
- actual `executed_base`: `40deea7f19794b73614e56c339fd02a88dd1ae7c`。
- final-sync `effective_base`: `b78b263abc8249617906117f8f19eeb1e825fab3`。
- final-sync `effective_through`: `53ddb04e2cea2645101c9cce70ce3890ca31f5cb`；此后只新增本收尾记录及整个 unit 路径归档。
- Gate 2 Round 2 Approved、Code Review `[]`、Verification PASS/aligned/no spec delta、产品 Round 1 pass。各独立报告保留其实际验证版本，不改写历史 SHA。

## Final sync 影响判断

`40deea7..b78b263` 合入 bugfix-647：新增 DescendantReader，修改独立 `session.descendants` RPC 和 GlobalAgent 子轨迹 drain，增加公开 sessionPersistence 依赖；无锁定 DSH 版本变更。逐项核对后，usage reader、PA usage/store、UsageReadResult 与本 unit 测试内容均与受审版本完全一致；index.ts 自动合并仅保留两个独立 RPC 的各自接线。DescendantReader 不修改 Session 原始事件和用量事实，也不接管 UsageCollector。

因此三项实施门禁和 Gate 2 均 retained：原有代码/契约证据仍支持计量行为、ACK 持久幂等及冷/热性能结论；产品已验证的普通/Workflow、ACK 丢失和重启场景仍有效。同步后补跑本 unit usage 两文件与真实 workflow-native 接线作为集成确认：3 files / 11 tests passed（36.05 秒），见 `final-sync-usage.log`；不以无冲突 rebase 代替影响判断。no spec delta，无 canonical 合并项。

## 已执行本地检查

Node 24.22.1、pnpm 11.7.0；受审版本 build、typecheck、check:ios-runtime 全部通过；docs-check 通过；pytest 非 e2e 65 passed / 31 deselected；ruff check/format 通过；frontend npm ci 和 critical audit 通过（未声明所有等级零漏洞）。用量两文件 10 passed、真实锁定 DSH workflow-native 1 passed。

本地全量不标绿：frontend 全套 955 passed / 8 failed；失败五文件串行复验 107 passed / 5 failed，仍为两文件。单独 private reply 测试也未找到 Reply draft。整个 frontend Git tree 在基线与本候选均为 `0432845539bbcf3bc413b54e081c5f866c033271`，本 unit 未改前端或其依赖。后端全量多个无关 native/identity 等测试超时，宿主同时运行其他 worktree 全量与模拟器，实测 load average 748.78；为避免继续增加共享负担，终止了本任务全量及属于本 worktree 的测试子进程。高负载是环境观察，不能据此断言每项失败根因。未改无关测试、timeout 或实现来掩盖失败；远端 required CI 必须另行全绿才算交付。

本地原始记录在 `/tmp/nano-perf650-evidence/`：final-build、typecheck、pytest、frontend-audit、frontend-tests、frontend-recheck、frontend-isolated、backend-tests 等日志；性能及真实产品数值分别见 M1 progress 和 acceptance。

## 环境收尾

产品验收后由 owner 执行 e2e-down，专用 Node/IM 已停止；透明 ACK relay 的专有 PID 经命令身份核对后停止。端口 57982/58479 均无监听。没有触碰生产、其他 worktree 或其进程；没有 merge/deploy。临时原始日志和本机凭据不提交。
