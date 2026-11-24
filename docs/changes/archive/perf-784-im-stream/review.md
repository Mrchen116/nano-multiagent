# perf-784 交付审查

集成基线 e03670b77，性能基线 6e387616f，两者仅有 unit 设计文档差异。M1 与 M2 的测量方法及限制分别见 [流式消息](milestones/M1-stream/evidence.md) 和 [Web 目录](milestones/M2-directory/evidence.md)。

## 独立判断

独立 reviewer code_review 按 change-code-review 与 performance-review 审查 e03670b77..be89da822。M1 pass，实时授权、逐 session 撤权、事务回滚、已提交历史、重放和终态键均符合设计。M1 no spec delta。M2 联系人字段、可见范围及各状态 aligned。独立本机复跑后端 37 项、Web 45 项通过。

| Finding | 修复与独立关闭 |
|---|---|
| P2，连续生命周期上报重复读取多页目录 | b73dd07fb 更新已授权目录中的现有徽标。独立复核 50 次重复上报零次目录读取、重连恢复一次，closed。 |
| P2，WS 暂断时本机启用后侧栏滞后 | b73dd07fb 同步用成功回执更新当前用户目录。独立复核无 WS 用例通过，closed。 |
| P2，节点先确认停用、迟到的同代 HTTP stopping 可能覆盖徽标 | b0a08cae2 只从启用或已确认停用回执更新摘要；独立复跑生命周期 8 项，closed。 |

最后受审产品提交 b0a08cae2，先前两个修复的独立 Web 复验为 47 项。归档与证据补充保留上述判断。

## 交付验证

- SQLite 注入事件写入失败后，正文与 key 回滚，同 key 重试、重复、迟到、运行中 HTTP 历史与最终文本通过真实 gateway WS/IM 进程验证。双 session 测试覆盖相同用户的一个 session 被撤销，另一个仍可读取。
- 历史清理已在隔离库验证，已有生产历史键留到获授权的部署窗口。Web 的真实浏览器验证和一次性服务均已回收。
- Node 24.22.1 的后端 build、typecheck、打包 iOS 交互运行时检查通过；IM 单独运行 74 个文件、494 项全部通过。Web 构建与全量 1249 项通过，最后追加的迟到回执回归另在 8 项定向复验中通过。Python 136 passed，29 deselected；ruff check 与 format check 通过。npm audit critical 门槛通过。
- 本机第一次并发运行完整 pnpm test 为 1449 passed、24 failed，涉及 DSH、Node 与一项 IM RPC 超时。该 IM 用例在 IM 单独整包运行时通过。独立从 e03670b77 解出干净源代码，对照重现 Dreaming valid extraction 的 travel.md 缺失；其余失败未逐一判定根因。远端 Linux CI 结果以 PR 对应 head 的检查记录为准。
