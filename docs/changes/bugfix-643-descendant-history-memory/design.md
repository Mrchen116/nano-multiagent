# bugfix-643: As-built Design

> 本文在实现后按实际 diff 整理。用户实际验收尚未完成，unit 保持 active。

## 实现范围

- Base: `520d5432e7b614af4624cf10678697f48bc56fcb`
- Branch: `codex/dsh-history-memory`
- 代码：`packages/dsh-integration/src/index.ts` 的 `session.descendants`。
- 回归：`packages/dsh-integration/tests/tool-presentation.test.ts`。

## 最终结构与决定

调用链仍为 PA 的工作投影 → stdio `session.descendants` → DSH 公开 `listDescendants/observeSession` → 工具展示数据 → 返回原有响应结构。

1. 用顺序循环限制单个请求的在途冷历史读取，不引入并发池或新服务。
2. 取得 cursor 并复制自有事件数组后，在内层作用域释放 observation；异步读取模型/工具展示数据时不再持有该租约。
3. 保留原有持久化屏障、workflow 关联、非 child 项、顺序及错误传播。响应仍包含完整自有事件，不启用未经对齐的增量裁剪。

没有持久 schema 或配置迁移；回滚本次代码即可，但会重新引入峰值放大。不同根请求仍可并发，单个日志、缓存和最终响应仍占内存，不能把修复解释为恒定总内存保证。

## 测试策略与验证定位

- `tool-presentation.test.ts`：扩展既有 native profile 回归，在重启后的冷读取及重复查询中核对真实子身份、cursor 和完整自有事件。模型 fallback 的内存列表在重启后可为空，未把它误写成持久化契约。
- `trajectory-runs.test.ts`、`global-agent.test.ts`：keep，保护原生子执行与产品投影语义。三文件共 48 项通过。
- 压力数据仅作一次性隔离证据：真实日志不进入测试仓库；从实际编译产物提取该处理函数，DSH 使用真实公开读取 API，工具展示处以一次事件循环等待模拟 I/O；不启动 Agent、模型或生产 RPC。结果见 `validation.md`。
- 自动化验证不能替代生产恢复、真实消息送达和用户验收。

## Canonical 文档影响

无 spec delta：恢复既有轨迹完整性与可用性，公开接口和用户语义不变。当前 unit 未归档，不声明生产已恢复。
