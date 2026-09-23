# M1 implementation

- PA 增量：原生 task_graph 使用默认能力目录，保持显式 allowlist；Gateway 复用真实 binder guard 与现有 WS pending/ACK lane；输入来源与 graph home 独立。
- 原生工具缺失先得到 ModuleNotFoundError；实现后，工具/真实 loopback/binder/领域/API 共 29 项通过；WS correlation 与释放 lane 的窄测试另 1 项通过。原有 Gateway listener/IM connection 加工具检查 37 项通过。
- 最近 change_note 保存到受改节点并在 Web 详情展示（无历史表）；这是已批准返工原因的持久化落点。列表 total 属同一权限过滤，delta 已按实现补齐这两项可观察细节。
- 最新前端 build + task graph 6 项窄测试通过；上一前端增量全量 776 项通过，最终 CI 还将核对集成树。

- Baseline: `499774a56`; branch `codex/feat-569-task-graphs`, managed worktree `/Users/czj/.codex/worktrees/unit-feat-569/nano-multiagent`.
- Gate 2: Round 3 Approved; only status metadata changed afterward.
- Work split: primary owns IM persistence/authorization/protocol and PA tool integration; bounded frontend implementation delegated independently under the same fixed API. Primary integrates and owns final validation/PR.
- Existing tests searched: IM Work API/repository tests (keep: separate Work semantics), Gateway internal listener/IM connection tests (extend where transport changes), frontend current chat/navigation tests (frontend owner).
- New permanent coverage: task-graph domain invariants and atomic persistence/ACL through HTTP/WS. This new business resource has no prior regression owner. Tests stay at the lowest seam exposing each risk; model/browser evidence is separate.
- Consumer clarification: list results include `total` under the same member/query/conversation filter, so Chat can display its count without loading every page. No change to the approved user behavior or write interface.
# IM 持久化增量

- 真实 HTTP/WS 测试先取得缺失端点 404，再实现 IM 单一存储、原子批量、revision 冲突、请求去重、当前成员授权与只读浏览 API。
- `PYTHONPATH=src .venv/bin/python -m pytest tests/im_service/unit/test_task_graph_rules.py tests/im_service/integration/test_task_graph_api.py -q`（使用主仓 .venv）：20 passed。覆盖 global/single_thread 同权、并发只成功一次、重启后数据保持、撤权后不能重放历史成功回执。
- 对本增量全部 Python 文件执行 Ruff check：通过。

## P5 修复：从 Agent 正文和 Work 返回时保留草稿

- 独立真实浏览器验收复现：聊天/Work 的任务 Markdown 链接触发完整页面导航，清空内存中的聊天 composer；顶部 Tasks 的 SPA 跳转正常。根因在跳转边界。
- 同源任务链接统一走现有 Router，在聊天正文、Work 和任务详情的 Markdown 中复用；原有外链分类与普通链接行为保持。
- 先补真实 MessagePane 链接路径和 Work 路由断言得到红测，再修复：140 项相关测试通过，TypeScript/Vite build 通过。任务往返断言包含正文、mentions、待发附件及不自动发送。
- 产品 Round 1 的其余场景和原型对照保留；I1 交给独立 reviewer 做针对性复验。

## 用户实测反馈：DAG 分层与连线

- 用户指出连线凌乱，要求依赖从左到右、同列可并行，并明确允许采用开源画图库。原布局虽然已有拓扑列，但列内固定按输入顺序，跨列边统一绕图顶，简单独立支路也会交叉。
- 新增独立双支路交叉回归先失败（1 failed / 7 passed），再使用 `@dagrejs/dagre@3.1.1` 替换手工布线。仅在布局输入中反转边并使用 RL + longest-path，将任务保持在最早满足前置的列；实际边、箭头、详情和数据不反转。保留每条跨列直接依赖，使用库计算的走线通道，圆角仅应用于局部转折。
- 同列任务加“可并行”，依赖列加标签；探索继续显示虚线衍生关系，两种模式嵌套保持。8 项任务图测试和 TypeScript/Vite build 通过。最终 JS gzip 从 307.45 kB 到 324.03 kB，增加约16.6 kB；没有引入图编辑器。
- 原 P2 must-match 的边语义和所有直接依赖保留，节点间距/线弯曲属于既有 may-adapt；这是同一开放 PR 的用户体验修复，不新增 milestone 或重开生命周期。用户确认的分层含义同步 canonical 与 delta，交独立静态和产品 reviewer 做一次针对性复验。
- 布局接口依据 [Dagre 官方文档](https://github.com/dagrejs/dagre/wiki) 与安装包公开类型核对。真实隔离页面已观察到四列、开发/文档同列和跨层边经过节点间的空白通道，停止统一绕顶。

## 用户实测反馈：减少节点 ID token 开销

- 用户授权自主选择简单设计，并明确开发态不做后向兼容。比较短随机 ID、图内序号与 alias 映射后选择直接持久化 `n1…n500`；复用现有图作用域、只增不删节点操作与 IM 写事务，不加计数器或转换层。
- 修改服务根 ID 和领域新增 ID 两个生成点，工具说明明确复用图内返回 ID；前端和关系读写消费原字符串字段，无额外适配。隔离旧测试图统一重编号的操作只留本地，不提交迁移路径。
- 测试处置：扩展既有 `test_task_graph_rules.py` 的稳定引用行为和 `test_task_graph_api.py` 的真实 HTTP/WS 接线、跨图和回执链。首次红测为5 failed/16 passed（原实现仍生成 UUID）；随后验证短编号跨批更新、关系保持和不随排序重编号。保留其余原子性/权限/重启与 PA 工具桥接测试，不增平行测试文件。

- 同轮用户补充 graph_id 同样过长：直接从35字符缩为 `tg_`+8位随机码（11字符）。沿用既有写事务查询全局重名并重试，避免save upsert覆盖已有图；无新依赖/表/字段。扩展既有HTTP/WS文件，用实际UUID前缀碰撞保护短图ID、旧图不覆盖与回执重放；原长ID实现先取得2failed，再实现。独立产品Round4的节点两轮证据保留，追加图ID创建/入口验证。

## Open-PR follow-up: Agent task-graph feature

- User requested a task feature alongside memory/skill/cron/heartbeat. Gate2 Round4 found catalog freshness prematurely revoked in-flight tool calls; author resolution and independent Round5 approve session-applied configuration ownership.
- Implementation `9892cd39c`: dynamic capability plus zh/en text, one effective-tool resolver for runtime/preview/Bridge, task-only prompt hint removal when disabled, global address lookup preserves the running snapshot and SDK-accepted runtime updates it. Default on still requires explicit tool allowlist; closing preserves graph data and current membership.
- Existing bridge test was rewritten from immediate catalog revocation to next-runtime behavior; added mode/feature/allowlist matrix and real binder/global-store/adapter busy boundary. Existing payload goldens extended. Generic frontend linkage tests retained. No new test files or migration layer.
- Red: 8 failed,10 passed; focused green40passed. Full local shards1995+2068passed, frontend779passed, build/Ruff pass. Logs and limits in integration evidence. Independent static/product delta reviews cover only the new configuration behavior; previous graph/DAG/short-ID evidence retained.

## Open-PR follow-up: account goals and per-node update chats

- User confirmed human-account ownership and shared access for its enabled Agents; explicitly excluded node assignment. User then required each return-to-chat action to follow the selected node's last update. Gate2 Round9 approves the final design using the existing run-delivery context, avoiding ambiguous reverse session bindings.
- Implementation `b383419bc` replaces graph conversation ownership with trusted owner_id, removes list chat filters, keeps per-node soft chat references with independent read-time chat permission checks, and adds copy-reference actions. Writes without a source clear affected nodes' previous source; idempotent retries never move it.
- PA passes the native run ID internally. Bound single-thread writes derive their actual Web or external-shadow chat from RunDeliveryContextStore after Agent/session checks. Global writes accept explicit sources and otherwise record none.
- Added HTTP/WS account and per-node behavior in `test_task_graph_ownership.py`; shared real-stack fixture extracted to `task_graph_support.py` to keep new files under400lines. Existing API atomicity/restart coverage is retained. Initial backend/tool red12failed20passed; final narrow Python33passed; frontend11passed and build passed.
- Independent static review caught a source-backed root creation default overwrite. Regression reproduced2failures; `99a22fb80` preserves the supplied source and API/ownership/domain27passed. Review closure and live acceptance are recorded separately.
- Full checks: remaining Python2072passed, frontend782passed; Agent/PA1998passed on recheck after an unrelated40ms heartbeat test failed under simultaneous full-suite load. That test file independently passed11tests. No timing code or unrelated tests changed.
- The retained stack was backed up and its6existing development graphs converted once without changing IDs, revisions, content or dependencies. Unknown old per-node source history is null. This is local setup, not a shipped migration; services remain available for user testing.
- Live Agent acceptance exposed an extra synthetic-user owner equality check that rejected actual registrations. ConfigService provisions a chat user whose own identity differs from the profile's human owner. `c4266e886` removes that incorrect equality while retaining registered profile/node ownership and stale checks. The integration fixture now uses ConfigService.create_profile; it reproduces4failures before the fix and API/ownership/domain27pass afterward. No runtime user records were rewritten to make the check pass.

## Open-PR follow-up: remove duplicate chat goal button

- User observed that the chat header's “目标 N” and the app's “任务” tab open the same account goal list. Removed the header button and its extra list/count request, associated CSS, and the now-unused MessagePane header action slot in `2a4b88423` and `f86b898b0`.
- Retired the two obsolete CTA assertions/test paths. Existing AppShell tests retain desktop/mobile Tasks navigation; existing task graph journey retains the Agent message link, node return and draft preservation.
- Targeted task graph + shell tests15passed; frontend full84files/781passed; TypeScript/Vite build, docs integrity, Ruff and diff check passed. No backend, goal ownership or per-node update behavior changed. The isolated service continues serving this worktree's rebuilt frontend.
