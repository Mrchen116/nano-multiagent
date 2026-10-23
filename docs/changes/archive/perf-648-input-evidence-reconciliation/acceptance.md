# perf-648 — 验收报告

> 对齐：motivation.md；Round 1，mode=full，revalidation_mode=full。
> Validation snapshot: `1ef49808ffd2618c275b6e38683f93f74ff8455d → 2c4b06abcad6ab4af35d2fffdf0daeb6ba7788a1`

## Verdict

**pass** — 两个产品 Scenario 的用户可观察不变性通过。Highest Required Action: pass。blocking/major/minor：0/0/0。

范围为真实 IM API → Node/PA → DSH → 真实 LLM → IM 历史。无客户端变更，按 design 的 Runbook for Reviewer 使用客户端同一 HTTP API，不提供未观察的视觉、iOS 或生产性能结论。精确 lookup 数量和取消未消费属于实现层验证，本报告不以此旅程冒充其协议测试。回执恢复指 Node→IM 的交付/确认通路。

## 版本与环境

- 独立核实 checkout `.worktrees/unit-perf-648`、branch `unit/perf-648`、HEAD 为 validated_at；`git diff 95a8c00ea HEAD -- apps packages src config` 为空，复用 caller 交付的构建。
- 初始 Node PID 86297 的 executable、CLI 与 cwd 均属于本 worktree。IM 为 `http://127.0.0.1:54793`，PID 85833；专用 nano 测试身份、node `wt-unit-perf-648-85799`、agent e2e/e2e-peer。不使用生产实例或其他 worktree。
- 临时故障只改未跟踪 `.gateway-config.yaml` 与专用测试 Agent 的产品设置。隔离 HTTP transport 对 p648-fault 注入认证 401，其他请求转发既有本地 proxy，备用正文来自真实 deepseek:deepseek-v4-flash。没有模拟模型成功输出。
- 结束恢复 config（与备份 cmp 相同）、e2e-peer 主模型及空备用列表，停止故障 transport；Node PID 95745 已 online。共享测试栈按交接交 caller 清理。

## 用户旅程体验

### 连续回复与重启

在 `c_wh4o4jrj` 连续发送 P648_FIRST、P648_SECOND，再重启同一 Node、同一持久数据，在原聊天发送 P648_RESTART。最终三个用户输入和三个回复全部 completed。用户不用重发；原聊天中的旧回复 ID 保持稳定，没有多出旧正文。

| 正文 | 最终消息 ID | 最终状态 / 数量 |
|---|---|---|
| P648_FIRST | ed964c2fa99f44b0adcb9b0c360c0271 | completed / 1 |
| P648_SECOND | af1970365d2c44559cf12aa603374498 | completed / 1 |
| P648_RESTART | 2ade804062074b7cb7469209fc7ea502 | completed / 1 |

第一条在重启前已 completed；第二条初读为 running，重启后收口 completed。新 Node 首次约 58 秒才 ready，超过 helper 默认 40 秒；后续按 120 秒窗口确认真实 online，没有把超时误报为产品恢复失败。caller 同时报告主机重负载；本报告不推断延迟根因或生产表现。

### 备用模型与交付确认通路恢复

在 `c_wpz0i33m` 配置主模型 p648-fault 与真实备用 deepseek。第一次独立请求得到主模型失败提示、独立“已改用 deepseek:deepseek-v4-flash，因为主模型不可用。”、P648_FALLBACK 正文；正文 completed 且 token usage 可见，用户未补发。

决定性故障恢复探针使用全新标识 P648_FALLBACK3、P648_OUTAGE3：先观察前者 completed，再接受后者。测试 transport 对含后者的请求延迟 12 秒，输入接受 2 秒后 SIGSTOP 本栈 IM 40 秒。日志顺序为 `IM_PAUSED 85833 → REAL_PROXY 200 → IM_RESUMED`，证明模型响应发生在 IM 无法处理投递/确认的窗口内。随后原聊天得到唯一 completed 正文；8 秒后及恢复原配置再重启后的独立查询，正文与旧消息 ID 均不变，没有要求用户重发。

| 观察 | 消息 ID | 结果 |
|---|---|---|
| 最终探针主模型失败提示 | d15347aac47d4294ac17f7cbd366cfa3 | 失败模型名可见 |
| 最终探针切换说明 | 3a573a98588e40ed9cab5526c4ca085c | 独立 completed 说明 |
| P648_FALLBACK3 | 0d442d2d29d14f69915ffd5975e976cb | completed / 1 |
| P648_OUTAGE3 | 81cc1d8df301419ea220218c9e5acad2 | completed / 1；恢复及再重启后 ID 不变 |

这验证 IM 投递/确认通路停顿后的用户结果，不声称 TCP socket 必然关闭；暂停期间 IM 无法消费 WebSocket 请求或返回确认，恢复后观察最终交付与幂等性。首次暂停探针因真实模型 1.8 秒即完成、早于暂停，不计为恢复证据；中间补探针复用旧 sentinel 导致等待提前命中并在未终结时重启，同样弃作决定性证据。最终唯一 sentinel 探针消除了这两个观测缺口。历史中该中间探针的失败提示不被计为最终探针重复。

## 独立证据

临时原始证据保留本机，未提交日志或运行数据：

- `/tmp/perf648-review.log`：首次连续消息及重启前快照。
- `/tmp/perf648-resume.log`：重启后三个回复最终状态。
- `/tmp/perf648-fault.log`：首次真实 fallback、失败/切换/最终正文。
- `/tmp/perf648-fault-final.log`：最终唯一标识的 fallback、暂停窗口与恢复历史。
- `/tmp/perf648-final-check.log`：恢复配置并重启后的两聊天独立历史及 online 节点。

报告上表内嵌决定性消息身份和结果，临时文件不是长期文档依赖。没有读取产品实现寻找根因，没有以 worker 的成功叙述替代独立观察。

## Reference Artifacts Reviewed

N/A：本 unit 无前端原型、参考图或 must-match 视觉契约；viewport 不适用。读取 motivation、design 内 Runbook、gateway routing-delivery 与 agent-capabilities 当前契约，按现有行为不变性比对；未启动变更前二进制作性能或 UI 对照。

## 问题清单

无阻塞产品问题。环境启动等待与无效探针已在上文单列，不作未经归因的实现缺陷。

## 验收标准覆盖

### Requirement: 同一聊天持续回复且历史结果不重复 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 |
|---|---|---|---|---|
| 长聊天继续发送和恢复 | motivation.md 同名 Scenario；routing-delivery.md 会话持久化契约 | 既有聊天连续回复、同数据重启、原聊天再发，对照既有行为 | c_wh4o4jrj 三个 completed 且唯一的消息 ID；最终独立历史查询 | pass |

### Requirement: 运行和投递的中间状态不冒充完成 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 |
|---|---|---|---|---|
| 备用模型和交付恢复 | motivation.md 同名 Scenario；agent-capabilities.md 备用模型契约；design Runbook | 主候选真实401失败，真实备用成功；模型返回时暂停IM，恢复及再重启，对照既有行为 | c_wpz0i33m 独立失败/切换提示、P648_FALLBACK3 和 P648_OUTAGE3 各唯一 completed | pass |

## 上层文档同步

- [x] `SPEC.md`：无需更新，跨包架构无变化。
- [x] `docs/specs/gateway/`：无需更新，本次观察符合既有路由/备用模型契约，design 明确 no spec delta。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

本报告按 caller 明确交接仅写 acceptance.md、不 commit；report_commit 由 caller 收口。

---

## Round 2 — final sync targeted 产品复验

> Validation snapshot: `b78b263abc8249617906117f8f19eeb1e825fab3 → 817f92040be5916e5abb42196948c1147009c399`
> mode=targeted，revalidation_mode=targeted；保留以上 Round 1 原文。

### Verdict

**pass**。Highest Required Action: pass；blocking/major/minor：0/0/0；needs_re_review=false。

### 范围裁决与继承依据

caller 交接 final sync 合入 bugfix-647，新增 DSH sessionPersistence 注入及 descendants/Global 子轨迹接线。reviewer 独立以 `git diff --name-only 2c4b06abcad6ab4af35d2fffdf0daeb6ba7788a1 HEAD -- apps packages config pnpm-lock.yaml` 核实，变化限于 dsh-integration 的 index/descendants/package 与测试、PA global-agent 与测试、lockfile；SingleThread、store、Node 启动与 IM 交付源码没有差异。没有读取产品实现定位根因。

运行时组装变化仍可能影响真实初始化和会话恢复，因此本轮不只引用静态结论，而在新构建重验连续聊天及同持久数据重启。Round 1 的主模型失败→备用最终正文、失败与切换提示分别显示、IM 暂停时真实模型完成且恢复后唯一交付等具体结论继续有效；本轮不宣称重复进行了这些故障注入，也不将 Global 子轨迹的其他验收归入本 unit。

### 新版本独立实测

- checkout、branch 仍为本 unit；独立核实 HEAD=`817f92040be5916e5abb42196948c1147009c399`。复用 caller 在 final sync 后重新 install/build/typecheck 的构建。
- 新隔离 IM `http://127.0.0.1:60431`，PID 6100；初始 Node PID 6276 的命令与 cwd 均属于本 worktree。专用 nano 用户、e2e Agent、node `wt-unit-perf-648-6064`。
- 新聊天 `c_jgk8iet9`：先分别等待 P648_R2_FIRST、P648_R2_SECOND completed，再用既有 helper 重启同一 Node/持久数据，依据新于 `2026-10-23T15:47:31.251786Z` 的 heartbeat 确认同 node 新代次 online，再发送 P648_R2_RESTART。
- Node 于 `2026-10-23T15:47:57.309Z` ready；约 26 秒，未把 caller 报告的主机高负载推断为产品缺陷。所有实测等待上限 120 秒，仅在临时驱动脚本设置，不改产品或受控测试配置。
- 三条回复均 completed 且各一条，两个旧回复的 ID 与正文在重启后不变；最后回复完成后再观察 8 秒，未出现旧回复重发。三个对应用户输入也均 completed。

| 正文 | 消息 ID | 结果 |
|---|---|---|
| P648_R2_FIRST | 9823f7e454ad4138941e70b0c71fc502 | completed / 1，重启后不变 |
| P648_R2_SECOND | 0dbc6a36f2774d1aa0d6d7081ffc689c | completed / 1，重启后不变 |
| P648_R2_RESTART | c638490317734ddfa0bbbf701eb8b0e9 | completed / 1 |

原始独立观察为本机 `/tmp/perf648-r2.log`，包括每次发送 ID、completed 回复、重启前后完整历史、新代次节点与最终 PASS。决定性身份与结果已内嵌上表，不提交临时日志。

### Scenario 覆盖与整体可交付性

| Requirement / Scenario | 期望来源 | 本轮处理与证据 | 结论 |
|---|---|---|---|
| 同一聊天持续回复且历史结果不重复 / 长聊天继续发送和恢复 | motivation.md 同名 Scenario | 新构建真实 IM API 连续两次 completed，再重启并收到第三次 completed；以上三消息 ID、旧历史不变与最终观察窗口 | pass（本轮重验） |
| 运行和投递的中间状态不冒充完成 / 备用模型和交付恢复 | motivation.md 同名 Scenario | 继承 R1 的 P648_FALLBACK3、P648_OUTAGE3、独立失败/切换提示和 IM 暂停恢复结论；相关实现无差异，新运行时初始化/持久恢复已由本轮旅程覆盖 | pass（具体结论继承） |

用户仍能在原聊天连续得到回复，重启不用补发，也未看到重复旧结果。无新客户端变化，本轮无 viewport 或视觉评价；Reference Artifacts Reviewed=N/A。R1 无 fail/inconclusive 待继承关闭项。无新增问题；上层文档同步判断沿用 R1，本 unit 仍 no spec delta。

本轮未更改临时 config 或 Agent 设置。重启后的 Node PID 7990、IM PID 6100 留给 caller 按交接清理；只追加本报告、不 commit。
