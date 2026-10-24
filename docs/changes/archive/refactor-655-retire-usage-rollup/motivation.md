# refactor-655: 工作记录增量恢复与累计用量汇总退役

## Relations

- Related: refactor-460
- Related: refactor-581
- Related: perf-650

## 原始诉求

> 那你把这条累计用量汇总链的所有使用方查清楚，确认没有用就删掉，别影响 Work 页的统计。当初设计的时候，你能不能找到当初的设计文档？

## 澄清记录

用户授权以完整消费者核查为前提删除累计汇总，并明确要求保留 Work 页统计；本次没有授权生产部署或删除已有数据。累计汇总与 Work 统计是两条不同的数据链，调查依据和保留边界如下。实现细节按已有授权自主决定。

## 原始设计和演进证据

1. M99 首次建立 owner / conversation / agent 维度的 Token/Turn 汇总 API，目的是运维可见性。原始任务设计：`docs/archive/legacy-development-records/TASKS/M99-IM-节点管理与统计.md` 的 R3；引入提交 `7cfa68b11cb975ac592ec5e51334c87d41a1b7a7`（2026-03-11）。
2. M137 增加 Web 聊天页使用量展示，M143 修正真实 completion 计数并提供 This chat、Workspace total 和群聊按 Agent tabs。原始设计分别位于 `docs/archive/legacy-development-records/TASKS/M137-Web-IM-token-turn与附件统一路径交付.md`、`M143-usage指标正确性与群聊按Agent可视化.md`；`docs/archive/legacy-development-records/ACCEPTANCE/M143-acceptance.md` 记录了当时的浏览器/API 验收。它并非从未有用途。
3. refactor-460 将 canonical Chat 提升为唯一实现，删除 legacy cluster。提交 `86b07fee77236c8921935b57ea09525890995869`（2026-07-13）实际删除 usage API client、This chat / Workspace total 组件及 Agent usage panel。需求背景在 `docs/changes/archive/refactor-460-web-im-client-runtime/motivation.md`。
4. refactor-581 迁移到 DSH / TypeScript 时延续后台用量链，`9336eb393` 加入原生用量接线；perf-650 改为进程内增量，仍保留冷启动重建。API 回归证明其可工作，不等于仍有产品页面消费。

## 当前消费者核查

基线：`d2cad8d59bb7025cacdd546d7fc9e0949fe13916`。对 git tracked 源码、Web/iOS、脚本、测试、current specs、内置 skills 和历史提交搜索 `metrics/usage`、`usage_metrics`、`usage_receipts`、`usage_reports`、`node.report`、`usage.read` 及其类型/方法引用，随后沿实际调用核对。

| 项目 | 实际依赖 | 处置 |
|---|---|---|
| Web/iOS 累计统计 UI、生产脚本、内置 Skill、预算/配额控制 | 无当前读取方；旧 Web UI 已在上述提交删除 | 允许退役累计汇总 |
| Node `UsageReports` → `usage.read` → native descendant scan | 生产者；启动、重连、turn/end 扫描及上报 | 删除 |
| PA usage outbox → `node.report` → IM `usage_metrics` / receipts | 持久汇总和去重；唯一查询为 `/im/v1/metrics/usage` | 删除运行链、查询和新库建表 |
| Work 页主/子轮次、最近主上下文 | `projectWorkEvent` → WorkSync → `agent_work_turns` → Work API；Web WorkUsage / iOS AgentWorkView | 保留并验证，不使用累计表 |
| 普通聊天 Token 气泡 | PA presentation / streaming → 消息 token_usage | 保留并验证 |
| Workflow budget / run spent | 原生消息使用量和 workflow 独立计量 | 保留；workflow-native 测试只移除累计 RPC 的断言 |
| session.event 的 rootSessionId | `usageRoot` 在 live 父会话卸载后提供归属，GlobalAgent 用于触发 Work 更新 | 保留关系解析能力，移出累计计量；不能粗删 |
| `reporting_enabled` 设置字段 | 节点设置读写字段，当前不参与累计上报判断 | 不在本次扩大清理范围 |
| tests/e2e 的累计 metrics probe | 为累计 API 自身提供验收，非产品消费者 | 改为保护聊天/Work 的实际统计 |
| Channels 重连测试和生命周期 spec 中的 node.report | 通用请求语义示例 | 换成仍存在的请求，不减弱覆盖 |

未发现仓库可识别的第三方客户端依赖；无法由源码证明任意外部手写调用不存在。本次退役按已删除产品入口和当前完整调用图判断，现有受保护 API 本身不视为继续保留后台扫描的充分理由。

## 现状痛点

本机真实历史副本上，33 个 binding 的冷用量恢复约 99.4 秒，取得完整日志 1,796 次，约 1,800 万条事件中 99.1% 为继承前缀。这是指定恢复路径的隔离测量，不是完整生产启动或物理 I/O 计数。调查报告位于本机 `/Users/czj/.codex/reports/nano-air-cold-start-20261024/recovery-plan.md`。为了无人消费的累计汇总重读原生日志，还延迟 Node 上线；仅优化扫描算法会继续维护失去产品入口的链路。

## 目标状态

删除累计扫描、上报、outbox 和服务端累计查询链；启动和重连不为累计统计读取历史。保留 DSH 原生计数、聊天气泡、Work 主/子任务统计、Workflow budget。现有数据库的历史累计表和行原样保留，不加启动清理/迁移，也不伪造已部署或已释放历史磁盘空间。

## 用户侧验收标准（不变性）

### Requirement: Work 页保留真实主子执行统计

#### Scenario: 查看主任务和子任务完成轮次
- **WHEN** 用户完成 Global 主任务及子任务，在 Work 页查看最近主上下文和各轮统计
- **THEN** 与变更前一致，显示 provider 提供的上下文、输出及缓存计数；主子执行不串账，未知值仍表示未知

#### Scenario: 节点重启后继续查看及执行
- **WHEN** 节点重启后用户读取已有 Work 记录，再执行新任务
- **THEN** 历史轮次统计保持可读，新完成轮次仍更新；父执行卸载不使已知子执行的 Work 更新丢失

### Requirement: 聊天与 Workflow 的原生用量语义保持

#### Scenario: 查看聊天 Token 气泡和 Workflow 消耗
- **WHEN** 用户查看已完成聊天或执行有用量预算的 Workflow
- **THEN** 与变更前一致，聊天气泡显示真实 provider 计数，Workflow 的 spent / budget 使用自身计量，不依赖累计汇总 API

## 影响范围

`apps/node`、`packages/dsh-integration`、`packages/personal-assistant`、`packages/product-contracts`、`apps/im-server` 的累计链与相关测试/契约。Web/iOS 既有内容和操作保持，仅补充记录同步状态提示；原始设计档案保持冻结。需要同步退役的公开接口为 `usage.read`、`node.report` 累计上报、`GET /im/v1/metrics/usage`。

## 迁移与回滚策略

成套升级 Node 和 IM，避免旧节点继续上报退役协议。旧数据库表不删除、不重写；新库不再创建累计表。回滚到旧版本可读取原表并由原生日志重建缺失汇总。生产执行另行授权，本次只交付代码、验证和部署说明。

## 同一 unit 的追加确认：工作记录持久增量恢复

2026-10-25，用户在聊天 `01a16edc-c480-7c42-aa3a-29e3d2f2e63c` 明确要求将下列已讨论设计发给本聊天，在同一个 feature 上完成；已读取该聊天原始用户消息核实。它扩充本 unit，不另建 feature，也不增加生产部署授权。

> 工作记录持久保存，用户请求时分页读取；原始执行细节按需查询。正常启动不重建历史，正常打开页面也不重算历史。

Work 现有工具开始/完成/失败、参数结果、主子关系、历史轮次、最新已报告的 Token/缓存和实时更新必须保持。正在查看时继续收到变化；新模型用量未报告时沿用当前“最近已报告”语义。已经完成并同步的旧执行不进入普通启动的全量正文重建；重启应核对在途执行、审批和交付，只补处理或传输缺口。保存必要的小型父子关系和处理位置，不能重复存全部模型上下文，也不能仅把全量重建移到后台。

### Requirement: 已保存工作记录可以立即读取，恢复只处理缺口

#### Scenario: 完成的历史增长后重启
- **GIVEN** 主、子执行的工作记录已持久化且中心已确认
- **WHEN** 节点普通重启，用户打开 Work 并翻阅分页
- **THEN** 页面直接读取中心保存记录，旧执行不为展示恢复全量读取正文；工具、关系、轮次和已报告统计一致
- **AND** 历史展示补齐不阻塞新输入与必要控制；确需继续运行的主会话由原生运行时恢复，成本与展示恢复分别计量

#### Scenario: 崩溃发生在原生持久化与产品记录提交之间
- **WHEN** 节点恢复
- **THEN** 未处理原生事实被补入工作记录，稳定事件身份保证无丢失、无重复；处理进度不能被传输确认进度替代

#### Scenario: 断线补传时继续工作
- **WHEN** 中心已有记录，节点还有未处理或未同步记录
- **THEN** 页面仍可分页回看，明确展示正在补齐或最新进度尚未确认；完成同步后持续更新，聊天和必要控制可用

#### Scenario: 检查具体执行原始详情
- **WHEN** 用户进入原生轨迹并查询历史范围
- **THEN** 现有详情、分页和继承历史仍可检查，不触发执行或全树恢复
- **AND** 实际底层读取放大必须如实报告；不能用较短返回数组或全量内存缓存声称消除了 JSONL 全文读取

验证须通过真实隔离 DSH，记录正文读取次数、处理事件数及保留限制，不只报告服务在线或总耗时。
