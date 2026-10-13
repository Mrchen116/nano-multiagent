# bugfix-585 — 回归验证

**最新结论：Round 3 PASS**，受审版本 `8e453ab963fb93469a2a8933f0f320d13935349d`。以下保留各轮原始失败及修复复验记录。

> 对齐: incident.md；Round 1，Full，2026-10-12
> Validation snapshot: `649e80311 → 48287332f5979e0c7aa5fa736aa67d0a2b0fcd4e`

## Verdict

**fail**。R1/R2已通过；R4 SIGTERM 远端关闭未记录设计约定的关闭原因。R3 正在完成。未修改源码、测试或设计；仅通过产品 UI 切换隔离测试 Agent 模型，产出报告及脱敏证据。

## 环境与 Reference Artifacts Reviewed

读取 incident.md、design.md、change-reviewer skill/template/handoff、worktree-runtime.md 及 IM current auth/node 契约。未读取实现定位原因。

HEAD 精确匹配受审版本，branch `codex/bugfix-585`，起始 git status clean。前端 dist 构建时间 18:24:06，Node lib 18:24:05；Node PID 27259 启动于18:25:05，cwd 为本worktree，DSH PID27322。IM PID27148 cwd 为 `.runtime-585`。仅访问隔离 `http://127.0.0.1:49936`，health ok；owner `u_2sajrkra`、node `wt-.runtime-585-27082`。初始真实模型 deepseek:deepseek-v4-flash；后经caller授权通过UI改本次隔离Agent为codexOAuth:gpt-5.6-sol，无假Agent。浏览器 IAB，截图viewport 1280×720。

## 复现验证与回归测试

| 来源 | 操作与实际证据 | 结果 |
|---|---|---|
| R1 | 18:28:42 SIGSTOP PID27259；18:30:53 SIGCONT。同PID 18:30:54.060重新注册ready，无重启/重新绑定/重新登录。18:31:05聊天入口新发算术问题无正常回复；18:33再发新问题，真实Agent最终显示 `Anthropic stream ended without a stop reason`。经caller独立确认上游压缩SSE环境问题，UI切换备用真实模型并保存profile v2，18:35新发17+26，真实回复43（3.4秒）。 | pass |
| R2 | 三个已打开标签 Nodes、Chat、Agent detail 由online自动变offline，再恢复online；API offline/last_error=heartbeat_timeout，恢复后online/last_error=null。Agent detail未保存显示名 `Unsaved recovery draft 585` 在两次状态变化后保留。离线发送明确显示 `Send failed` 与503 target_node_id is not connected。 | pass |
| R3 | 待补充。 | inconclusive |
| R4 | heartbeat日志1012/heartbeat_timeout，阶段heartbeat；retry 1000ms，registering/ready且outage_ms=1010。SIGTERM IM后实际1005/空原因（非设计1001/server_shutdown）；随后ECONNREFUSED、1006、退避1/2/4/8/16/30秒；同Node18:32:55重新注册ready，outage_ms=61054。 | fail |

旧连接延迟关闭的人工竞态不由本次UI操作单独证明；R2恢复后持续观察无错误离线。worker契约测试不能代替这里的产品证据。

离线失败消息被保留为delivery_status=failed；恢复注册后、下一条新消息发送前出现Agent响应占位并最终模型失败。按caller范围澄清，既有PA reconciliation不等于本unit新增离线队列；此处只记实际行为，不单独据此判新增范围外功能。

## Issues

1. **major / direct / fix-implementation** — R4服务关闭诊断缺乏约定原因。期望实际服务正常SIGTERM能辨认server_shutdown，实际持久日志仅1005/空原因。节点/时间/阶段/退避/重新注册均具备，关闭触发原因仍无法仅凭日志恢复。证据：[relay日志](evidence/round-1-relay.jsonl)，10:31:54.030Z。

## 环境限制与既有行为

初始deepseek请求在真实产品中两次报流结束缺stop reason。caller独立直连代理验证：HTTP200 SSE body为未声明Content-Encoding的Zstandard二进制，解压后才可见完整SSE。该诊断为caller提供，reviewer未改代理，也未将模型失败归为本unit实现；按授权改本次隔离Agent模型后得到正常回复。截图 `review-chat-failed.png` / `review-chat-success.png` 均在gitignored runtime，不提交截图缓存。

## 自动化测试增量

本reviewer不读取或运行实现测试作为验收替代。caller交接已build/typecheck；这里仅记录真实进程、浏览器、HTTP及持久日志结果。实际gateway.log未发现本次JWT/access/refresh token或三条测试消息正文；正常心跳无逐条生命周期输出。未注入恶意远端字符串，因此白名单覆盖仅是本次实际日志检查，不宣称穷举脱敏测试。

## 上层文档同步

- [x] SPEC.md：无需更新（当前设计未改跨包边界）。
- [x] docs/specs/：gateway relay-protocol及IM agents-nodes需按最终通过行为归并，不能以本轮fail认定完成。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

## 环境交接

IM故障注入后重启PID31845，Node仍27259；IM重启第一次缺IM_PUBLIC_URL启动失败，已补齐隔离URL后正常启动，故服务中断总时长包含该环境准备时间。原数据/JWT/dist均复用；未操作生产。SIGSTOP有180秒自动SIGCONT保护且已手动恢复。服务最终由caller e2e-down清理。


## Round 2 — SIGTERM 诊断复验与相邻状态回归

> Validation snapshot: `48287332f5979e0c7aa5fa736aa67d0a2b0fcd4e → 684122882e410c870e37595b5b3d00e76bb8da62`

**verdict: fail**；R1保留Round1真实43回复，R4已修复通过；R2新增服务恢复后Nodes状态不收敛，R3暂未执行，避免提前停用影响修复复验。

- 先停止旧IM31845以载入新build，IM33276在当前HEAD运行；Node27259始终未重启。
- 10:37:20.971Z 对IM33276 SIGTERM，实际Node持久日志 **1001 / server_shutdown**、phase receive。随后的连接拒绝ECONNREFUSED、retry 1000/2000/4000ms可辨认；IM33673恢复后10:37:28.015Z ready，outage_ms=7044。原R4 issue closed。证据：[Round2 relay](evidence/round-2-relay.jsonl)。
- API `/im/v1/nodes` 已 online / last_error=null / heartbeat10:37:28；Chat已online；但同一轮已打开Nodes标签仍offline、server_shutdown，heartbeat停在10:37:09。至18:37:40后观察依然如此，没有手动刷新。证据：[Nodes stale DOM](evidence/round-2-nodes-stale-dom.txt)，runtime `review-nodes-stale.png`。

### Round 2 Issue

**major / suspected-regression / fix-implementation**：R2要求节点重新注册后已打开页面自动恢复online。实际服务关闭/恢复后Nodes保留offline，即使API/Chat已online；需修复页面收敛并以同样真实服务关闭恢复再验。因果由owner定位，不以API正确替代页面验收。


## Round 3 — 最终复验

> Validation snapshot: `684122882e410c870e37595b5b3d00e76bb8da62 → 8e453ab963fb93469a2a8933f0f320d13935349d`
> mode: targeted，覆盖Round2 R2问题及R4相邻回归，补齐R3；R1/R2心跳与草稿证据引用Round1，并追加新消息真实回复。

**verdict: pass**。Highest Required Action: pass。未解决blocking/major/minor：0。前两轮2个major均已关闭；无需再验。未创建GitHub issue；报告不commit，按caller要求交回统一处理。

| 来源 | 最终实际证据 | 结果 |
|---|---|---|
| R1 | Node PID27259自18:25:05连续存活，未重新绑定/登录/重启；再次IM停启后，18:43真实聊天发送8+9，codexOAuth:gpt-5.6-sol经真实Agent返回17，4.6秒。 | pass |
| R2 | 原Nodes标签3一直保留，无reload/编辑，载入修复IM35543后自动从此前stale offline收敛online。再次SIGTERM35543时自动offline/server_shutdown；IM35709恢复、Node10:42:39重新注册后同页自动online，1 Online / 0 Offline，last_error提示清除。API同时online/last_error=null。Chat online。心跳三页面/未保存显示名仍引用Round1。 | pass |
| R3 | 专用管理员fixture修正active/admin后通过同客户端suspend接口停用owner，18:43:38返回suspended；两已开页面立即到/login不可收发。旧token读取nodes与POST消息均401 session revoked or expired。Node日志1008/authority_revoked/revoked=true；截至18:44:56（78秒，超过30秒最大退避窗口）无任何connecting/retry/ready事件，Node仍原PID；持久DB node=offline,last_error=authority_revoked。 | pass |
| R4 | 10:42:32.473 SIGTERM服务产生1001/server_shutdown，phase receive；连接拒绝ECONNREFUSED，1/2/4秒退避；10:42:39.511 ready/outage_ms7039。日志包含ISO时间、node_id、generation、阶段与恢复时长，撤权原因同样可辨认。无正常逐条heartbeat输出；实际日志抽查脱敏结果沿用Round1且新增事件仍为固定安全字段。 | pass |

证据：[最终Nodes](evidence/round-3-nodes-online-dom.txt)、[真实回复](evidence/round-3-chat-dom.txt)、[撤权页面](evidence/round-3-suspended-dom.txt)、[持久生命周期日志](evidence/round-3-relay.jsonl)。真实截图保留在gitignored `.runtime-585/review-final-reply.png` / `review-suspended.png`，不作为受版控截图缓存提交。

### 归因与范围

Round2已见Nodes漏更新属于R2必验范围，修复后以原页面与相同故障注入通过，不靠刷新掩盖。两次修复仅IM模块，Node/前端受审构建未变，故保留对应Round1成功证据合法；本轮HEAD及新IM build由caller交接并核对。模型切换仅本次隔离Agent配置，无生产代理修改。停用通过真实产品管理API完成；管理员资格准备为caller修改临时fixture，不能代替停用结果证据。

### 最终环境交接

IM PID35709、Node PID27259、DSH PID27322；Node没有暂停残留。owner nano 已suspended，Node撤权终止连接但进程仍存活。三个reviewer创建IAB标签全部已关闭；无额外常驻reviewer进程。临时restart脚本和认证文件均位于gitignored runtime；caller负责e2e-down及本次数据清理。保留的raw日志/截图不暂存。上层spec待caller按最终通过行为归并。

## Final integration retention

- validated_at: `8e453ab963fb93469a2a8933f0f320d13935349d` (latest executed scope; earlier unaffected evidence retained as documented above).
- executed_base / effective_base: `6bb37a06925c20bb5714f6986f94e92f2d3f78d5`. Final fetch found no main increment.
- effective_through: final PR head, whose product source/test tree is unchanged from validated_at. Only reviewed delta-to-canonical merge, report completion and whole-unit archive follow; the PR records the exact final SHA.
- No gate invalidation from those documentation-only operations; code, product and corrected-delta conclusions retained.
