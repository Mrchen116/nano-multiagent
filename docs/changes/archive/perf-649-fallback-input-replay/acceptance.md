# perf-649 — 验收报告

> 对齐：motivation.md 用户侧验收标准；design.md Runbook for Reviewer。
> Validation snapshot: `52b9a1ac831cc7f92709d12764cdd1a9410dea0f → 986cb0a237831795a2964e598112a501cd007d66`
> Round 1；mode=full；revalidation_mode=full；2026-10-23 23:24:55–23:26:08 Asia/Shanghai。

## Verdict

**pass**。Highest Required Action: pass。blocking / major / minor = 0 / 0 / 0；无需复验。

## 版本与入口

独立确认 checkout 为 `.worktrees/unit-perf-649`、branch 为 `unit/perf-649`、HEAD 等于 validated_at，开始时工作树 clean。运行 PID 84039 的命令指向该 worktree 的 `apps/node/lib/cli.js`、Node 24.22.1 和本次 `/tmp/perf649-environment/runtime/.gateway-config.yaml`。复用 caller 提供的 e5a381 构建；独立核对 `git diff e5a381 HEAD -- apps packages src scripts` 为空，构建日志 apps/node build Done。验收中只按 runbook 重启本次 Gateway，并通过新 generation 验证，未重建、修改受审实现或接触生产。

真实入口为 `http://127.0.0.1:54179`，隔离测试账号 nano，节点 `wt-runtime-83892`。用 IMClient 调用 Web 客户端同一登录、配置 PATCH、发送消息、读取消息 API；最终结果以 `/im/v1/conversations/{id}/messages` 为准。HTTP fixture 只替换上游模型返回，IM、Gateway、DSH 与持久恢复链真实运行。未操作 Web/iOS 画面，本轮不声称视觉、布局或端特有体验通过。

## 用户旅程体验

本轮会话 `c_twfee4ij` 已有 caller 的一条自检历史；该条不计入独立验收结果。创建直聊接口对同一身份与 Agent 返回既有会话，所以实际旅程在同一历史会话中执行；各段通过正常配置保存重置模型/粘性。此与 runbook 的“新 conversation”步骤不同，但不影响本 unit 输入归属与状态恢复判据，且覆盖了历史累积下的连续行为。没有以旧 ACK 作为新请求成功证据：首次辅助轮询可能命中已有 ACK，随后独立补验严格逐条等待新增回复的普通成功旅程（证据 24–26）。

普通请求各收到一条新正文；主模型无备用失败时看到带 `fail` 名称的 401 提示，未收到本轮 ACK。配置备用后，同一请求依次出现 `fail` 失败提示、独立说明「已改用 backup，因为主模型不可用。」、普通正文 `PERF649-ACK-backup`；用户无需重发。后续与重启后的请求各仅新增 backup 正文，切换说明不重复，使用户能够理解当前回复来源而不被重复提示打断。

取消旅程在 slow 请求已进入且尚无正文时发送 `/stop`，看到「已停止当前操作。」；释放旧请求后继续观察 5 秒无旧正文，随后新请求正常得到一条 slow 正文，再观察 3 秒仍无额外旧回复。整体用户目标在本次隔离入口可完成，未发现阻塞或退化。

## 证据

本机原始独立证据（不提交运行数据）：

- `/tmp/perf649-environment/reviewer-evidence.jsonl`：带 UTC 时间的配置响应、节点 generation、真实消息列表；下表数字为该文件行号。
- `/tmp/perf649-environment/reviewer.py` 与 `reviewer-normal.py`：本次驱动步骤；对应 stdout 在同目录。
- `/tmp/perf649-environment/requests.jsonl`：模型请求顺序，只用于确认 fail/slow 条件与模型选择，不代替用户结果。
- `/tmp/perf649-environment/build.log`、`up.log`：caller 构建与环境来源；reviewer 未以其成功叙述替代场景观察。

关键证据摘要保留如下，避免结论仅依赖临时文件：

| UTC 时间 | 独立观察 |
|---|---|
| 15:24:59.717 | `review649-no-backup` 后仅新增 fail 401 失败提示；该段仅一次 fail 请求，未调用 backup |
| 15:25:01.322 | `review649-fallback-one` 后失败提示 → 切换说明 → backup ACK |
| 15:25:01.876 | `review649-fallback-two` 后新增第二条 backup ACK，无新失败/说明；模型请求直接 backup |
| 15:25:03.200975 | Gateway replacement generation floor |
| 15:25:23.056 | 同 node 新 heartbeat 严格晚于 generation floor，节点 online |
| 15:25:24.256 | `review649-after-restart` 后新增第三条 backup ACK，无旧输入重复回复 |
| 15:25:26.911748 | fixture 已收到 slow 请求；15:25:27.114 消息列表尚无 slow 正文 |
| 15:25:29.394 | `/stop` 后出现「已停止当前操作。」；随后 release |
| 15:25:34.475 | release 后无 slow ACK；旧取消请求未恢复回复 |
| 15:25:41.532 | `review649-new-after-cancel` 后仅一条 slow ACK；先有 fail 提示和独立 slow 切换说明 |
| 15:26:05.544、15:26:06.139 | 严格顺序发送 `review649-sequential-one/two`，各新增一条 ok ACK；15:26:08.167 无额外回复 |

## Reference Artifacts Reviewed

N/A：内部性能变更，无前端原型、reference 或 must-match 视觉契约。已读取共同判断标准与验证平台/深度，采用 runbook 允许的客户端同一真实 HTTP 接口。

## 问题清单

无产品验收问题；未创建外部 issue。配置、重启与取消均使用本次明确授权的隔离资源。

## 验收标准覆盖

### Requirement: 普通回复与未配置备用的行为不变 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 普通成功 | motivation.md；current agent-capabilities.md | 走既有行为，与变更前 current 契约比对；已有历史会话，ok/无备用，两条顺序消息，各等待新增正文 | 23–26；请求记录最后两次均 ok | pass | 无历史重复回复；未另跑旧二进制 A/B |
| 无备用失败 | motivation.md；current 备用链契约 | fail/空备用保存后发送；观察本轮新增失败与模型调用 | 7–8；15:24:57.387 仅 fail 请求 | pass | 失败提示带模型名，未借其它模型，本轮无 ACK |

### Requirement: 备用继续原请求并保留恢复与取消边界 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 备用成功 | motivation.md；current 备用链与粘性契约 | fail+[backup]，发一次后自动续成；同会话再发消息检查粘性 | 9–11；请求 fail→backup→backup | pass | 独立说明只出现一次，每个输入一条正文，正文带 token_usage |
| 恢复或取消 | motivation.md；design runbook | 备用成功后重启 Gateway，generation 确认再续聊；fail+[slow]在途 `/stop`，release 后观察，再发新请求 | 12–21；重连时间与取消摘要见上表 | pass | 重启后仍 backup；取消旧正文未出现，新请求完成 |

## 覆盖边界与环境交回

本次没有强制中断 model.check 中间状态；该更细恢复/claim/消费边界属于 design 的 runtime gate，不冒称真栈观察。没有运行性能基准或以产品旅程代替事件访问数/耗时门禁；合成 ACK 不证明真实模型质量、上游延迟或生产性能占比。取消后的无迟到回复为上述有限观察窗口，并结合完成新请求后的消息列表确认。

既有服务 owner 为 caller；reviewer 仅调用既有 restart helper，替换 PID 已写回 runtime/.gateway.pid，服务交回 caller 集中停止。未启动额外常驻服务。release 文件已 touch，最后测试 Agent 配置恢复为 ok/无备用，审核与工具未变。临时证据由 caller 按本地产物规则处理。

## 上层文档同步

- [x] `SPEC.md`：无需更新；跨包架构无变化。
- [x] `docs/specs/gateway/agent-capabilities.md`：无需更新；本次观察保持既有失败、备用、粘性行为，design 为 no spec delta。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## Round 2 — 同步 main 后有界产品 delta

> Validation snapshot: `4bb02455b1d072a899a54bf62cdf2927c4069a99 → 9b95fea3b7a577674ffbdd2c9882ab6ee3e97fa2`
> mode=targeted；2026-10-24 00:07:41–00:07:47 Asia/Shanghai。

**Verdict: pass（产品 delta）**。Highest Required Action: pass；问题 0；无产品复验阻塞。此结论不代表本机全量测试 green，亦不替代远端 CI。

### 版本与独立观察

已核对 HEAD 等于新 validated_at。`latest-build.log` 最终 installer metadata 为该完整 SHA；运行 PID 22364 指向本 worktree 的 cli.js、Node 24.22.1 与 `/private/tmp/perf649-environment/final-runtime/.gateway-config.yaml`。真实 IM 为 `http://127.0.0.1:51967`，独立登录隔离账号 nano 后确认节点 `wt-final-runtime-22158` online。未重启、未启动重型测试，未读取 caller final-smoke 成功结果作为验收证据。

以客户端同一 HTTP 接口独立发送三条新消息，每次先记录现有消息 ID 集合，仅断言集合外的新消息；等待预期正文后再读一次列表确认恰好一条正文。会话为 `c_zgy3i41v`。原始证据 `/tmp/perf649-environment/reviewer-final.jsonl`，驱动 `/tmp/perf649-environment/reviewer-final.py`，进程退出码 0，记录末项 `pass=true`。

| 场景 / UTC 观察时间 | 新用户消息 ID | 实际 IM 返回与裁决 |
|---|---|---|
| 普通成功 / 16:07:43.629 | `54c46c1803c5473abf06a5d42b7dd1f2` | 保存 ok/空备用后，一条新 `PERF649-ACK-ok`，ID `870381975afb41d1ac6d538e8334ae3b`；无额外 Agent 消息。pass |
| 备用成功 / 16:07:45.840 | `f106e15955bb46749ee221c2f7ffa938` | 保存 fail+[backup] 后按序新增 fail 401 提示 `474ca01068e742ccbec6d29420040871`、独立切换说明 `7fdd9a3e5d1149d19e93497e2b9ef016`、backup 正文 `d8d3552d928f498198c8ef5c0fb38ded`；无需重发。pass |
| 粘性续聊 / 16:07:47.445 | `ac2d9715f9764224bb9e812aaeaa31b3` | 仅新增一条 `PERF649-ACK-backup`，ID `b0dace28d0b44f4ba364383ef0607213`；无重复失败或切换说明。pass |

备用与粘性正文均有 `token_usage`：context_used=10、output=4、total=14，未观察到 usage 接缝妨碍正文交付。该字段检查不代表本轮覆盖 usage 全部计费或并发语义。用户可以正常接续请求，并通过一次切换说明辨认备用来源。无前端变化，视觉 / viewport 仍未验；Reference Artifacts Reviewed 继续 N/A。

### 前轮保留范围

独立核对前轮 validated_at 到本轮 HEAD 的文件增量：涉及 descendants 装配、usage 和相应 PA 接缝；本 unit `input-evidence.ts`、`model-fallback.ts` 无 diff。新真栈普通/备用/粘性已覆盖重新装配后的实际回复链。本轮不扩展到 descendants 子任务或 usage 并发场景，也不将静态审查当作真实恢复证据。

- **普通成功、备用成功：pass**，以上新消息证据刷新该范围；Round 1 严格连续两条普通消息的历史不重复结论保留。
- **无备用失败：pass，retained**，仍引用 Round 1 证据 7–8 的实际 401 且无备用调用；本轮未重跑。备用选择/输入归属源码未变，新装配下 fail→backup 正常，没有发现失效信号。
- **恢复或取消：pass，retained**，仅保留 Round 1 证据 12–21 已实测的“备用成功后 Gateway 重启续聊”和“slow 在途取消、release 后有限窗口无旧正文、新请求继续”。本轮没有重启或重新取消，不声称新 SHA 下重新观察了这两段。此次增量没有修改该 input/fallback、重启入口或取消路径；有界 delta 未出现需要扩大复验的副作用。
- 中间 model.check 强制中断恢复仍属于 runtime gate，不新增真栈覆盖。旧有限观察窗口与合成模型限制继续有效。

### 交回与总门禁边界

仅追加本报告，未修改源码、测试或设计，未提交。最后隔离 e2e 配置为 fail+[backup]，服务仍运行，交由 caller 集中停止。上层文档无需更新的判断保留。

Caller 明确交接：本机全量验证两次因过载失败，不算 green；用户允许先 Draft PR 并依靠远端 CI 补齐。产品 delta 通过不能抹平该缺口，最终工程门禁以 caller 的验证记录及远端 CI 为准。
