# M3 — Work 完整事件链

共享 `WorkFact` 闭合当前生产事件的 type/payload 关系，`WorkDraft` 强制本地事件身份；GlobalAgent、KnowledgeUpdates 调用者、InboxStore 原子 checkpoint 与 WorkSync 使用该契约。历史日志和 HTTP/WS 输入经共享 decoder 检查，返回原对象，不修改原 JSON 字段顺序或扩展内容。

中心 `WorkRecords` 仅持有 SQLite：注册身份、去重/顺序、事务日志与投影、水位、固定记录和公开页归其所有。`Work` 保留鉴权入口、连接状态与提交后广播，HTTP 批量/分段与旧 WS append 进入同一契约。聊天查询/命令/权限决定业务未迁移；动态工具与未知事件保留原值。

验证（Node 24.22.1，maxWorkers=2/no-file-parallelism）：

- 迁移前 baseline：5 文件/41 项通过。
- PA 首轮交接：typecheck、9 文件/114 项通过。
- 中心边界：3 文件/27 项通过，含 tenancy、批量/分段原子拒绝与字节兼容。
- 最终首轮集成：10 文件/110 项通过；日志 `.e2e-refactor-672/m3-integration.log`。
- 新生产链在独立 IM 子进程上执行 GlobalAgent→InboxStore→WorkSync→HTTP→SQLite→公开 Work/子执行 API；覆盖大工具参数与结果、主子统计、WS 拒绝、刷新、中心重启及重复上传。原生执行由 RuntimePort fixture 提供，不声称模型语义验收。
- PA 与 IM 编译负例均进入常规 typecheck；禁止错误配对、未知生产类型、缺身份、持久行冒充公开视图。Knowledge link/review 两个生产者被覆盖。

后续独立门禁与完整 CI 在 unit 报告和 delivery 中记录。

独立静态与产品审查均在 `badc559a1` 确认权限选项缺口：flat `options:[null]` 或 nested 非数组可提交。修复 `197da048e` 增加具名 option/id 契约与两种表示的共享校验；红测 2 failed / 1 passed，修复后 3 文件 / 23 项通过，PA/IM 编译负例通过。独立复验只覆盖该实际失效范围，其他结论保留。
