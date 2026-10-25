# M1 实施记录

基线：`a54d11aed`；开发 worktree：`unit/feat-657`。2026-10-25 开始实施，未部署生产、未发布安装包。以下为中间验证记录，最终门禁在独立审查与最终汇总中收口。

## 已有证据

- 普通 Agent 共享进程隔离红测：新增第二普通 Agent 断言首先失败；改为 `agent:<id>` 与 control 后通过。Node controller/partition/layout 相关 13 tests 通过。
- IM 生命周期真实 WebSocket、DB 重开、CAS、Task 跨 await 写入竞态、Work ACK/旧审批、冻结 Schedule 共 7 tests 通过；首轮 IM 非 E2E 全套 202 tests 通过。
- PA 首轮全套 25 文件、197 tests 通过；取消后的最终增量 Work/history 回归补充通过，禁用态不执行 Runtime/relay 副作用。
- 迁移副本 4 tests 通过：普通/PA/子会话/fork、附件、10 个 Nano domains、Schedule 历史、SQLite/WAL 保真、提升中断/继续/拒绝混入归属；CLI 临时目录 plan/apply/verify/重复 verify 成功。
- Web 首轮 58 tests、build 通过；1440/390/320 受控 API 实际组件检查存于本地 output/playwright/feat-657-client/。
- iOS build、build-for-testing 与 iPhone 17 iOS 26.4 test-without-building 通过；包括 lifecycle enable-confirmation 回归。证据 `/tmp/nano-ios-feat-657-tests.log`，25 tests/5 suites。原生视觉走查尚未完成，不能以编译替代。
- 首次后端全套 138 文件：730 tests 通过、2 失败。日志 `/tmp/nano-feat-657-backend-tests.log`。一项 PTY 顶层持续创建子进程使 DSH 报存活进程，结果正确保持未确认；正常交互 PTY+前台任务的独立成功不证明该模式被修复。另一项 task-execution-limits 高负载下超时，隔离重跑通过（47.91s 整个用例），未修改其产品逻辑或上调测试阈值。
- docs-check 通过，ruff check/format 通过。Python 首轮 69 passed/1 failed：前端 import 需要明确 browser-safe contract subpath；改成 `@nano/product-contracts/agent-lifecycle` 并仅开放该类型边界后 dependency contract 13 tests 通过。

## 真实环境

首轮 daily：`/tmp/nano-feat-657-acceptance/.e2e-daily.json`，IM `http://127.0.0.1:53116`。P/E/Q/PA 真实生命周期报告均 enabled/revision1，各自不同 processInstanceId。客户端编辑未保存名称后直接停用，配置草稿未提交。该进程加载了中间构建，清理时暴露 ToolSelection 卸载注册竞态，界面显示“停止未确认”且只有重试，证据 `/tmp/nano-feat-657-acceptance/web-stop-unconfirmed.png`；修复版本需要重新起栈核验，不把这次当正常停止成功。

模拟器：本任务独立 `Nano feat657` / `C268926E-861B-450F-8F1B-477ADD9C0B34`。CUA 初次连接现有 Simulator AX 接口两次超时；正在启动独立设备，不干预其他任务的模拟器。
