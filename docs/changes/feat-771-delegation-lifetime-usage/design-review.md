# feat-771 Design Review

## Round 1

- reviewer_target: design_review，基线 `f53579a44`，本轮工作树的 design、spec、delta 和 M1
- review_mode: full
- mode_reason: 首轮，覆盖 IM 累计投影、派工读接口、Web 切窗和首次启用
- started_at: 2026-11-16T10:45:45+09:00
- completed_at: 2026-11-16T10:46:59+09:00
- duration: 74s
- Verdict: Issues Found（0 CRITICAL / 3 WARNING）

### Coverage 与证据

- 从 Web [派工图](../../../src/IM/frontend/src/features/settings/agents/agent-work-delegation.tsx#L55) 经 [授权路由](../../../apps/im-server/src/work.ts#L425) 和 [WorkRecords](../../../apps/im-server/src/work.ts#L122) 走到 [WorkSummaries](../../../apps/im-server/src/work-summaries.ts#L164)。沿用活动候选、父链、分页及授权，使用独立主键读取已返回节点的累计，可避免在读请求中遍历历史轮次。现有范围候选也包含仍在运行或等待权限的执行，集成测试已覆盖一条窗口外但仍运行的会话。
- 核对 [会话注册与历史主会话恢复](../../../apps/im-server/src/work-records.ts#L139)、[中心追加事务](../../../apps/im-server/src/work-records.ts#L182)、[中心删除事务](../../../apps/im-server/src/agent-deletion.ts#L64) 和 [SQLite 启动迁移](../../../apps/im-server/src/db.ts#L32)。会话身份固定，退役与恢复只影响主会话当前身份，适合以已保存会话归属维护跨代累计。中心持有数据及增删边界，Gateway、DSH 和模型 Context 无需参与。
- [delta](specs/im/agent-work.md) 锚定 [Agent Work canonical](../../specs/im/agent-work.md#requirement-web-work-可以从派工关系进入同一工作记录)，保留该场景的节点导航、范围恢复、分页、历史主执行及定时任务入口。M1 单批交付 IM 和 Web 可以避免换口径时接口与界面分开交付。
- 前端设计判断基于 [既有派工旅程记录](../archive/feat-764-web-agent-work/M1-web-work/evidence/journey.md) 和 [当前卡片](../../../src/IM/frontend/src/features/settings/agents/agent-work-delegation.tsx#L108)。复用活动范围控件与卡片结构，文案「轮累计」可表达时间口径，路径说明与缺失覆盖可以并列。历史旅程的截图未随仓检入，本轮未观察运行画面。当前没有需要决策的新导航或布局，设计阶段无需另做原型。覆盖用例应直接核对无 token 报告时累计轮次仍可见、真实零值可见，以及旧祖先同时具有路径说明和缺失覆盖。
- 性能设计验证以汇总键访问路径及活动索引为准，并通过真实中心 HTTP 夹具验证范围与归属。Query plan、真实浏览器切窗、启动迁移耗时均留待实施验证，本轮没有将设计判断计作运行结果。

### Issues

- **R1-W1 | 回填和增量的“结束轮次”缺少共用的持久判据。** [设计](design.md#架构与接口) 以结构化轮次表回填，并仅在结束事件中更新差量。[当前投影](../../../apps/im-server/src/work-records.ts#L319) 的 `finished_at` 来自可省略的 `payload.finished_at` 或 `event.observed_at`，而 [事件解码](../../../packages/product-contracts/src/work-event-codec.ts#L31) 接受二者同时缺省。事件表虽补上接收时间，[轮次投影仍收到原始事件](../../../apps/im-server/src/work-records.ts#L255)。用 `finished_at` 判定会漏掉没有时间的合法结束。用展示 `status` 判定也不能保证批量与在线一致，后续开始或权限事件可以改写状态，中心启动还会重置活动状态。请明确旧记录如何识别已持久化的结束事实，以及增量如何复用同一语义覆盖补报和更正。用隔离夹具验证一个未携带结束时间的已结束轮次在初始化与在线追加中贡献一致。
- **R1-W2 | 两个范围各自缓存累计，切窗可以回退到旧总量。** [Web 派工查询](../../../src/IM/frontend/src/features/settings/agents/agent-work-delegation.tsx#L71) 按窗口缓存完整响应 30 秒，[现有 Work 推送刷新](../../../src/IM/frontend/src/features/settings/agents/agent-work-panel.tsx#L330) 不覆盖派工查询。用户先看三天，随后 Agent 结束一轮，再打开两小时看到新累计，切回仍新鲜的三天缓存便会看到旧数字。单纯改变 API 统计及卡片文案无法满足 [同一节点切窗累计一致](spec.md#验收标准)。请在设计中明确使用最新已保存累计的刷新或复用方式，并覆盖一次真实追加后从新响应切回已缓存范围的 Web 回归。
- **R1-W3 | 回滚后重新升级会跳过已经失效的回填。** [风险与回退](design.md#风险与回退) 已指出旧进程写入后须删迁移标记和汇总，但 [部署段](design.md#一次性部署迁移) 没有交代此条件步骤的执行者或判据。[当前迁移方式](../../../apps/im-server/src/db.ts#L32) 由标记跳过，不会识别其间的旧版本写入。普通重新升级会继续读第一次升级留下的汇总，旧进程还可能已删除该 Agent。请收口一种明确的恢复方式，使中途经过有写入的旧版本后，再升级可安全重建，或按仓库部署提示词约定记录仅在该条件下执行的停写、目标、清除/回填事务、完成判据与隔离验证。常规升级仍可由启动事务自动完成。

### Recommendations

无。

### Author Resolutions

- R1-W1 定义共用的持久结束标记，用已保存的事实补齐旧轮次，以省略时间的轮次验证两条路径。
- R1-W2 复用 Work 刷新，离开活动窗口丢弃缓存，验证切回已读过的窗口。
- R1-W3 在部署提示词明确条件回填的执行者、停写、备份、事务和验证。

## Round 2

- reviewer_target: design_review，基线 `f53579a44`，修订版 design 与新增的条件部署提示词
- review_mode: delta
- mode_reason: 三项原问题的闭环涉及结束判据和刷新路径，并新增回滚恢复操作
- retained_from: Round 1。需求与 delta、会话归属、授权、分页、活动候选及 M1 范围没有实质变化
- started_at: 2026-11-16T10:50:01+09:00
- completed_at: 2026-11-16T10:50:16+09:00
- duration: 15s
- Verdict: Approved（0 CRITICAL / 0 WARNING）

### Coverage 与历史问题闭环

- **R1-W1 closed。** Author Resolution 将结束事实固定为持久的 `finished_at`，用已保存事件补齐旧记录。[修订设计](design.md#架构与接口) 明确新记录沿用中心持久化事件观察时间兜底，旧记录按 turn ID 或现有会话内 run ID 关联补齐，状态变更保留标记，之后回填与在线增量共用该判据。[当前事件接收与投影入口](../../../apps/im-server/src/work-records.ts#L255) 已具备这些信息，启动事务可一并提交修补、汇总与版本。验证安排覆盖省略结束时间的追加和历史回填。
- **R1-W2 closed。** Author Resolution 复用 Work 更新刷新，离开当前窗口时释放该窗口响应。[修订设计](design.md#架构与接口) 将派工纳入 [现有 Work 更新和恢复时的刷新](../../../src/IM/frontend/src/features/settings/agents/agent-work-panel.tsx#L330)，切回活动窗口重新读用途相同的 API。新增的三天、追加轮次、两小时、切回三天序列会覆盖旧缓存导致的累计回退。
- **R1-W3 closed。** Author Resolution 引入 [条件回填操作](deployment-prompt.md)。提示词规定标记已存在且运行过旧中心时才执行清除，先停写和备份，事务同时清除投影和标记，启动目标版重新生成。失败可回滚清除或恢复备份，生产仅核对健康、标记及历史样本。隔离方案覆盖正常升级和重建，常规部署无需这项操作。

### Issues

无。本轮判断为方案审查，实施行为与运行证据留待 M1 验证。
