# feat-764 实施审查

## 范围与版本

- 目标见 [spec.md](spec.md)、[design.md](design.md)。
- executed_base / effective_base 为 `a7895ff03855cb44d325be98cba67a4ad978dc58`。独立实现闭环实际核对 `4b9e02773`。最终行为和本地构建核对 `45785c91435c532a09eea3e45d21d0913afa9a8a`。
- `45785c914` 补真实浏览器发现的投递摘要与粘性工具栏。新增差异用真实浏览器和工具呈现回归重验，原授权、预览、独立用量与校正 delta 证据仍有效。此后 canonical 归并和归档只更新文档。

## 审查结果

| 问题 | 能力和执行者 | 判断及限制 |
| --- | --- | --- |
| Work 查询、权限、跨进程投影和规范 | change-code-review，独立 reviewer `implementation_review`，full 与 closure | 最终校正 delta aligned。中心使用现有 Work 授权；原生/iOS 读取入口继续走已有契约。 |
| 群聊入口、定位、两层派工、记录区 | frontend-experience-review / product-journey-review，实施者实际操作，独立 reviewer 读取关键宽屏画面和连续快照 | [隔离旅程](M1-web-work/evidence/journey.md)。最终宽窄记录区由实施者复验。 |
| 长历史、头像和密集派工 | performance-review，中心实现者验证，实施者复测 | [HTTP 和索引证据](M1-web-work/evidence/performance.md)。浏览器使用真实小样本；大型夹具未做端到端浏览器前后对照。 |
| Dreaming 真实运行指标和恢复 | DSH/PA 受控 provider 和 Work 中心测试 | 各阶段指标只读取本次执行，覆盖未发起模型请求、供应方未报告、失败、结束投影和旧记录。真实 Chromium 未另行触发维护。 |

## Findings 与关闭

- 独立审查指出头像缺最新工具状态和名单入口、旧知识链接污染活跃确认、同名派工不可区分、后台读取失败时丢掉已保存内容。按 `72e0f0f36` 与 `4b9e02773` 关闭。服务端明确拒绝或删除时隐藏缓存。
- 独立审查指出图来源混入另一父级栈、展开过的大工具离开视区仍刷新完整正文、旧大工具首次打开后仍折叠，以及回复定位应等首次预览。按 `4b9e02773` 关闭。
- 浏览器实际观察到阅读区收窄和已发送结果重复的截断投递摘要。明确阅读区宽度，已发送状态从结构化结果取值，原消息从真实投递事实打开。最终构建复验桌面、窄屏和回归。

## 本地检查

- 仓库构建与类型检查、共享 iOS Runtime 检查及 Python 135 项通过。
- Web 全量 1,194 项通过。最终小修后 Work、工具呈现和聊天消息共 153 项通过，Web 生产构建通过。
- 中心实际 Fastify/SQLite/WebSocket 的四项核心测试通过。实际 DSH 维护与 PA 投影、增量恢复共 25 项通过。
- 根 TypeScript 套件首次高并发执行 1,343 项通过，15 项在 DSH 测试失效。将受影响文件限制为两个 worker 后，仍有 4 项超时或能力检查截止。再以一个 worker 精确复跑这四项全部通过。远端整轮结果独立核对。
