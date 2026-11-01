# bugfix-693: Validation

- Base: `39a1d78ed25b4c19878dc98b63d96d4810cb2523`。
- 环境：隔离 worktree；Node 24.22.1、pnpm 11.7.0；测试用临时 home、动态本地端口与真实锁定 DSH；测试进程及临时文件均由 finally 清理。
- Red：新增 native 模型请求回归在原实现失败，提醒总数实际 4、期望 2。
- Green：首次窄回归 4 files / 60 tests 全部通过，覆盖 native Inbox、global-agent、runtime-profile、input-evidence。随后加强既有工具执行中消息批次覆盖；最终验证结果见下方补充。
- 用户亲自验收：待用户确认，不能以自动化验证替代。
- 真实模型 / 生产 / Feishu：未执行，本次验证对象为确定性提醒机制。
