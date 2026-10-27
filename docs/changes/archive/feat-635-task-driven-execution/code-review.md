# Code Review: feat-635

- review_round: 1
- review_mode: full
- executed_base: `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a`
- validated_at: `e1e187e0e9c4c488aba2f0ec61e8c1c48f827ab0`
- diff_range: `executed_base...validated_at`
- 对受审 63 个文件的完整 diff、直接调用方、current Task/能力契约及本 unit design/delta 进行了独立静态审查。没有修改实现、测试、设计、delta 或配置。

## Findings

```json
[
  {
    "file": "packages/dsh-integration/src/task-execution.ts",
    "line": 123,
    "summary": "[P2] 配置恢复后应重新接续相同 revision 的未完成责任",
    "failure_scenario": "自动 Task 轮次发生模型故障后，agent/error 设置 interrupted。用户将模型配置切换到可用模型，main.ts 在 configuration.apply 完成后调用 task.execution.changed；Task 快照没有变化时此处继续 return，既不清屏障也不提交下一轮。真实锁定 DSH 子进程复现：第一次 llm/stream 抛错，切换健康 fixture 及模型配置并发送 changed 后，模型请求数仍为 1，Agent idle，Task 仍 doing。新输入或修改 Task 才能恢复，违反条件恢复后接续承诺。应区分配置/运行恢复信号与重复 Task 失效提示，保留同因权限拒绝的防热循环。",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "apps/node/src/main.ts",
    "line": 361,
    "summary": "[P2] 开启 Task 能力时需发现尚未绑定会话的现有责任",
    "failure_scenario": "Agent 尚无聊天 binding，Task 能力关闭时，用户可在 Tasks UI 为它建立 doing。recover 因关闭跳过；之后配置页开启能力，此处仅调用 changed，而 Driver.changed 只遍历现有 bindings，无法发现 scope 或建立 session。因此已开始的任务不自动运行，必须再聊天或重连。用真实 TaskExecution/NodeStore 复现：关闭时 recover，开启后按 main.ts 调 changed，唯一请求为 task.execution.changed，bindings 仍为空。应在有效配置启用/恢复后执行现有 recover 以发现责任，再由原生驱动幂等接续。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## 直接证据

1. F1：`node /tmp/feat635-review-config-recovery.mjs`，真实锁定 DSH 子进程、普通公开 RuntimeClient，fixture 只替换 LLM stream；根 binding 与 Task RPC 为真实协议接线。第一次模型调用抛错，到 idle 后将 fixture 改为成功，调用 `configuration.apply` 切换模型，再 `task.execution.changed`。输出：`{"failedCalls":1,"callsAfterConfigurationRecovery":1,"status":"idle"}`（`/tmp/feat635-review-config-recovery.log`）。该 fixture 不证明真实 provider 可用性；它直接证明已恢复运行条件时插件仍不重新入场。
2. F2：`node /tmp/feat635-review-enable-recovery.mjs`，导入受审构建的 PA `TaskExecution` 和实际内存 NodeStore；先 feature=false 调 recover，再改 true 调 changed，记录跨边界请求。输出：`{"calls":["task.execution.changed"],"bindings":[]}`（`/tmp/feat635-review-enable-recovery.log`）。结合 driver 只迭代现有 bindings 的 `task-execution.ts:133` 可确定不会启动。此复现不声称进行了真实 UI 点击。

受审构建日志 `/tmp/feat635-frozen-build.log` 包含对应 SHA；运行脚本均在 /tmp，临时 DSH home 在 finally 中清理，未启动 Web/iOS 或生产服务。没有存活的 PLAUSIBLE 候选被当作缺陷。其他覆盖不足见 verification.md，独立于代码缺陷。


## Round 2 — closure + patch review

- review_round: 2
- validated_at: `567785b58bef199399bc005082e383bde6e3b2ed`
- executed_base: `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a`
- finding_origin_head / pre_fix_head: `e1e187e0e9c4c488aba2f0ec61e8c1c48f827ab0`
- review_mode: closure（F1/F2）+ patch（全部修复及新增行为）
- diff_range: `e1e187e0e9c4c488aba2f0ec61e8c1c48f827ab0..567785b58bef199399bc005082e383bde6e3b2ed`
- 固定差异 30 文件均已读；继续保留 R1 对未变部分的有效静态结论。不是重新审查完整分支，也不扩大到假想兼容场景。

### Focus closure

| Finding | Outcome | Evidence |
|---|---|---|
| F1 模型配置恢复不接续 | closed | Driver 区分 error/cancelled/denied，configured 只释放无 deniedTools 的 error；有效非 metadata 配置完成后接线。真实 native failed model → healthy config、同一 Task revision 续跑通过；duplicate changed 仍不重试失败；原有两类权限拒绝保护仍在。 |
| F2 首次开启不发现 scope | closed | main 配置完成及 agents 更新后调用 recover；PA 测试从 feature=false 无 binding 开始，启用后发现 scope 并建立当前 session。 |

### New boundary review

- Task runtime API 先以认证用户执行已有 graph get 读 ACL，再查图内真实 node/assignee；调用方传 agent_id 无效。Gateway 只请求该 assignee 当前节点；回应须匹配认证连接、request_id、response type。Runtime 只遍历已有 binding/native Agent，不创建、加载或唤醒会话；仅返回 running/idle，断线 offline，错误 unknown。两端使用相同 Task route，错误不沿用缓存 running。没有暴露 session ID、私有消息或工具内容。
- resume_request 只能由认证真人 paused→doing 写入，patch 白名单不允许模型构造；stop/后续暂停和责任改派会清除。PA 透传服务端事实；Driver 仅在首次/变化时生成 nano-system/task-human-control；审批投影 human-task-control 明确限定该 Task 的恢复，不授额外工具权限。未进入 nano-human、人类 Goal 资格或 humanInputs 快捷许可路径。普通自动提醒与 peer 自称恢复不升级为真人来源。
- controlText 只剥除 host roster 里 input.agent_id 对应 user_id 的前导 mention；其他成员 mention 不剥除，sender_type/PA owner admission/attention 等既有控制资格继续生效。
- 原生 A/B、stop restart 与旧 Schedule、消费后有效替换的新增 fixture 直接经过公开 RuntimeClient 与原生生命周期；没有修改上游包或新增执行 loop。

### Findings JSON

```json
[]
```

未发现本轮 patch 中存活的 CONFIRMED/PLAUSIBLE 缺陷。复用 build、89 tests、最后 native+Global 51 tests、Web 6 tests、typecheck、ios-runtime 与最新 iOS BUILD SUCCEEDED 日志。它们不替代进行中的产品 R2/must-match 验收，也不把 R1 全量 552 tests 冒充 R2 已重新全量运行。


## Round 3 — retained-input recovery and main integration

- review_round: 3
- validated_at: `30cd2e0a1272ec0a157337ebe644ad11e642809c`
- executed_base: `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a`（保留原验证基线）
- effective_base: `0904bc49c`（已合入最新 origin/main）
- pre_fix_head: `567785b58bef199399bc005082e383bde6e3b2ed`
- review_mode: patch + retained finding closure
- diff_range: `567785b58bef199399bc005082e383bde6e3b2ed..30cd2e0a1272ec0a157337ebe644ad11e642809c`

### Reviewed scope and retained conclusions

审查本方 `1e5169cd0` 恢复修复、相应 native fixture、merge conflict resolutions 和其直接来源/审批/PA/iOS/Goal 集成；使用两个 merge parent 对照以区分上游已交付功能与本次改动。没有重审 feat-636 全部独立产品功能，也没有将上游完整 diff 自动计为本 unit 新功能。R1/R2 的 Task 事务、ACL、scope、stop、Schedule、Goal gate 和相同源码的静态结论保留；运行恢复与冲突文件由本轮新证据覆盖。旧客户端截图不作为新布局通过证明。

- 排队输入恢复：configured 仅在 interrupted=error 且无 deniedTools 时解除错误；存在 idle、未 blocked、Task enabled、原生 Inbox 非空时用 task-change followup 唤醒已保存输入，之后仍走正常 changed/pre-step。没有清除拒绝/取消屏障、没有重新提交通知、没有另起 Task loop。新增 throw/error-finish/error-finish-with-inbox 三分支；最后分支在修复前不能完成，修复后完成，assignment-notice 原生 user/message 仅一次。额外模型 step 为原有责任撤回 delta，不是重复消费通知。
- 真人来源合并：isHumanSource 保留原生 user 的 host identity 字段要求及旧 nano-human 读取；child 的普通 user 提示不自动成为真人。人工审批路由保留 isHumanSource 与 Task 自动 turn 可审批两个入口，同时仍先执行 subagent/Global/Schedule/Heartbeat 分流。task-human-control 在专用分支投影，不进 isHumanSource/humanInputs 或原生 Goal 资格。两个 native-human Goal fixture 只显式 opt-in，未改测试权限结论。
- iOS 合并：以最新 TaskCompactCard/TaskStatusSummary 为基础，根/负责人/子层卡片都传递 wait/health，waiting 快捷定位 doing group；详情保留真实 runtime 与恢复/暂停动作。上游 PA 配置入口、chat polish 相对最新 main 无本方差异；Goal 开关/tool 联动仍完整。
- 四份 canonical 合并逐 Requirement 对比通过；保留上游真人来源要求，Gateway 能力索引为 38；bugfix-633 设计链接已指向 archive。

### Findings JSON

```json
[]
```

Focus status：R1 F1/F2 closed、R1 W3 回归缺口保持 closed；R3 retained-inbox recovery gap closed。没有本轮存活的 CONFIRMED/PLAUSIBLE 问题，需要的范围未扩大为 full。

### Validation provenance

复用 `/tmp/feat635-main-integration-tests.log`（9 files / 86 pass）、build/typecheck/ios-runtime/iOS simulator build/docs-check。同组 build 的 installer stamp 是 `0e5405c79`，不能声称日志 stamp 是 30cd：caller 已确认产品冲突解决后的源码与最终 30cd 相同，build 后只改两项 native-human fixture opt-in 和文档；86 tests 及最终 docs-check 执行树与 30cd 相同。按已核 caller 的 source-tree 等效声明复用，保留此版本边界。提交后的最终 Web/Swift tests/archive/contract 与真实产品迁移复验仍由 caller/reviewer 完成；本报告不预先宣称通过。


## Round 4 — CI cold-session recovery fix

- review_round: 4
- review_mode: patch
- validated_at: `1bd82f9ebbec17b85868640eb1c5e78733c0c709`
- pre_fix_head: `42aa1f9afb0faeb59cd55574626fb67040d911fc`（仅归档报告，产品等同30cd）
- diff_range: `42aa1f9afb0faeb59cd55574626fb67040d911fc..1bd82f9ebbec17b85868640eb1c5e78733c0c709`
- executed_base: 保留原 `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a`；effective_base: `0904bc49c`。

完整审查该5文件增量（1实现/2测试/2文档）及锁定DSH公开controller声明和实际恢复/创建契约。只追加报告，未修改产品或测试，未新增其他角色。

1. ensure已有binding时先经公开resolveAgent加入原生resume Promise，再调用原create。公开resolveAgent按session去重恢复，create仍检查cwd/preset；仅session/not-found继续创建未落盘binding，writer-held、subagent ownership或其他恢复错误均继续失败。真实owner/binding/config校验仍在该调用之前；taskStops在initialize安装，先于本次resolve，未绕过stop准入屏障。没有私有import、上游patch或本地恢复loop。
2. native stop/restart测试同时发出session.observe和session.ensure，直接触发冷恢复/创建冲突。修复前日志明确writer-held，修复后既能共享恢复，又维持旧Schedule/真人输入在stop确认前不调用模型、确认后输入保留。冷绑定/cron/profile/supervisor/native-human相邻边界15项也通过，覆盖未落盘binding首次创建的适用风险。
3. Goal fixture用最后role=user消息的hold ID决定挂起，修正已迁为user而旧过滤只认nano-human的测试前提。未改产品来源、Goal opt-in、工具权限或下一轮配置语义。fixture ID为本测试显式提交，识别条件不是授权判断。

### Findings JSON

```json
[]
```

没有新的CONFIRMED/PLAUSIBLE缺陷。R1 F1/F2、W3与R3 retained-input gap保持closed；本轮CI暴露的cold-recovery竞争和fixture失配已closed。

复用 `/tmp/feat635-cold-race-red.log` 的确定性失败、`/tmp/feat635-ci-race-green.log`（2 files/10 native tests）、`/tmp/feat635-ci-cold-bindings.log`（5 files/15 tests）。最终 `/tmp/feat635-ci-fixed-full-backend.log` 已完成：121 files / 575 tests PASS，93.05s；不是以前573/575的失败结果。已复用caller本轮build/typecheck通过声明，不重复产品全量。


## Round 5 — ordinary Goal tool selection and image removal

- review_round: 5
- review_mode: patch（用户反馈修订）
- validated_at: `30a53c2047ea391adba6399a35234883d6c1e8fd`
- pre_fix_head: `89a4beeb80ce102e9a0a39acb162bc0f2a34342f`（R4后仅报告/主干文档同步，既有产品结论保留）
- effective_base: `866877a83`；executed_base保留各历史轮次，不改写原记录。
- diff_range: `89a4beeb8..30a53c2047ea391adba6399a35234883d6c1e8fd`。

审查完整代码/测试增量、Gate2 design-review R4及新spec/design/delta/canonical，图片删除与引用处理。未变Task逻辑、PA路由、来源审批、冷会话恢复不重审全量。该轮以前Goal Feature/专门driver/disarm的旧结论已被用户新要求取代，不继续宣称这些旧行为应该存在。

- 能力目录已删除dsh_goal Feature，三个普通工具default_on=false；缺省allowlist排除三者，显式allowlist逐项决定，选get不暗选create/update。根/child沿同一有效工具选择；无Goal工具时隐藏tool:goal prompt。
- 移除Goal plugin、disarm与goal来源过滤和直接dsh-goal依赖；未新建wrapper或权限路径。工具调用继续走原生授权与既有审批，已创建Goal生命周期不因工具选择被额外修改，Task驱动代码未变。
- 显式UI列表的取消选择立即通过原有限制层收缩，新增等待idle完整配置；restrictSelection从当前有效selection求候选交集。缺省无Goal的运行中会话改选get时不会提前暴露get；忙时get/read→update会先撤掉get/read，update在idle后出现。native回归覆盖两种分支，既有model/prompt/skill整体配置路径保持。
- Web/iOS删除总开关与三工具联动，复用普通工具选择组件；Web真实组件回归只保存get_goal且另两项保持未选。iOS没有新增私有状态或独立Goal选择逻辑。
- 53张图片从当前树删除；git ls-files核对unit没有图片，旧图片Markdown链接已改为本地标识。仓外备份由caller持有；历史提交仍含原图，最终squash/PR历史清理由caller后续完成，不能把当前树无图写成历史已清。

### Findings JSON

```json
[]
```

无本轮存活的CONFIRMED/PLAUSIBLE缺陷。R1–R4未变Task/恢复/来源边界结论保留；旧Goal Feature及其生命周期撤销/总开关联动验收superseded。

验证：窄范围4 files/12 native/Node/approval/native-human通过；Web2 files/28通过；typecheck、contract13通过（caller声明）。本轮全量后端573/575（personal-security30s、workspace-tools90s timeout），Web962/963（chat-workspace Reply draft缺失）；无代码变更的低并发窄复验已通过：后端2 files/7 tests、Web chat-workspace59 tests；未重跑全套，因此不写全量一次全绿，也不将初轮失败直接归因并发。iOS TEST SUCCEEDED。用户最新明确收缩本轮验证为Web真入口/运行时，iOS仅源码+编译测试回归，不再要求新增原生UI实测，也不宣称新逐工具原生UI已独立验收；旧Feature截图不能代替新要求。
