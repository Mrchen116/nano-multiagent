# M1 progress

2026-10-25 — 实施中，未合并/部署。

## 已验证

- 累计 API 退役先复现 200，再验证 404；node.report unsupported，仍保留 reporting_enabled 与旧库数据。没有 DROP。
- 新 GlobalAgent 重新构造后的 child cursor 从空丢失（RED），改为 InboxStore 持久 checkpoint 后通过。处理位置不使用 journal ACK。
- InboxStore 文件库 close/reopen、stable ID 去重、事务失败回滚通过；root 接收先于产品提交的崩溃窗口补齐、开放轮次 tool 配对和跨轮 model/context carry-forward 通过。
- WorkSync 同 epoch 换 Connection、过期连接在途声明、仅 pending 清零无新 event 等 19 项通过。Web panel 22 项 + TypeScript、IM typecheck、iOS AgentContracts 8 项通过。
- 真实锁定 DSH 0.2.1-alpha.1 Workflow 用例：四子执行完成后冷重启，Work 检查和 descendant 读取的 persistence body reads 均为 0；公开 write handle 给一个子执行追加后，仅该子执行正文读取 1 次；历史增加到八个子执行后再冷重启仍为 0。原 Workflow spent=15 保持。测量包装仅在测试 fixture 的公开 persistence.open/handle.read seam，不改运行时或原生日志格式。
- 范围限制：变化分支的 JSONL 正文仍由上游完整解码；事件范围与产品处理 checkpoint 不等于文件范围 I/O。
- 真 Node + DSH + IM + fake provider token critical path 通过：bubble 与 Global Work 都为 context_used=31001/output=1/cache_read=1000，累计查询 404。

本机运行证据：/tmp/refactor655-native.log、/tmp/refactor655-token-e2e.log、/tmp/refactor655-build.log、/tmp/nano-refactor655-ios-test.log（不提交日志/截图/运行数据）。完整 build 已通过；后续定向代码修改已单包 build。
