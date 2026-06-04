# feat-394 复盘：一个小特性为何拖了 6 轮验收 / ~3 天

> 作者：orchestrator（自我复盘，记录的是**编排流程的问题**，不是把锅甩给特性难度）。
> 触发：unit 经历 6 轮 verifier+reviewer 验收仍未 pass，用户质疑"一轮又一轮、三天了、这么小的特性"。

## 一句话结论

特性本身不小（heartbeat + cron 是跨 agent 内核 / Gateway / IM / 前端四包的调度+投递子系统），但**真正拖时间的是我的编排方式**，不是实现难度。cron 的"执行→投递"是**一条紧耦合链上串着约 6 个具体 bug**，我用"冷启动新 worker 改一个 + 两个验收 agent 跑全旅程"的重型轮次去撞，一轮只揭一层；本该是一个人坐在跑起来的系统前 crash 一个修一个、一两小时扫平的活。

## 我的四个编排错误（按影响排序）

### 1. 每轮新派 worker，不复用 —— 大量重复探索

8 个全新 worker（m1 / m1-2 / m2 / fix-r1 / fix-r2 / fix-r3 / fix-r4 / fix-r5），每个**冷启动重读** spec + design + 历轮报告 + 爬代码。每个 fix worker 干完即关停、下轮再开新的，**连"刚把 cron 跑起来的那个 worker 的热环境 / 上下文"都丢弃重建**。

违反了项目既有记忆 `feedback-reuse-worker-for-followup-fix`（"修后续问题优先 SendMessage 复用原 worker 保上下文"）。这条我反复违反，直接造成每轮的冷启动重复探索成本。

### 2. 用重型轮次撞"单路径串行 bug" —— 一轮只揭一层

cron 执行链的 bug 是**逐层串行**的，前一个不修就到不了下一个：

| 轮 | cron 崩点 | 性质 |
|---|---|---|
| r1 | 没接进 gateway 运行循环 | 漏接线 |
| r2 | `PersistentSessionBindingStore` 缺 `find_by_kernel_session_id` | 两 store 契约分裂 |
| r3 | 被 `auto_mode_gate` 拦（无 `check_permissions`） | 没接权限门 |
| r4 | `create_session(session_id=)` —— shim 无此参 | 对不存在的 API 编码 |
| r5 | `submit_message` 用不存在的 `_RunOrigin.SYSTEM` | 对不存在的 API 编码 |
| r5(深) | cron **可见投递链整段从未实现**（fire-and-forget） | 缺核心实现 |
| r6 | `_IntervalSchedule` 用 `ceil` → 只触发一次不 recurring | 运行时 rounding bug |

每个"轮"= 冷启动 worker（改一层）+ verifier + reviewer 跑全旅程 + 等待。对一条只需连续调试的链，这是极重的开销。正确做法是**一个会话连续 crash-fix-rerun 直到跑通**。

### 3. 接受"单测绿 / 结构验证"，没早早坚持"recurring 的 live 证据"

多轮 worker 用 **进程内 tick / stub / 只验首次（last_due=None）** 充当"验证通过"，于是每个 DONE 都掩盖了下一层运行时 bug：
- r2 的 store 分裂被内存 stub 掩盖；
- r6 的 ceil bug 只在**第二拍**暴露，而所有"live 验证"都只验了首次触发。

我作为 orchestrator 在 §3.3 退出标准核对时，多次接受了"代码结构对 + 单测绿"，没有从早期就把验收门槛钉死在 **"连续触发≥2 次 + 真消息进直聊"** 的 live 证据上。

### 4. 环境阻塞 + 升级后又"甩问题"

- round-3 的 worker 因 **LLM proxy(:4000) 没起** 没法跑完整 live，退而机械验证，于是漏了 round-4 的 create_session bug。我没有早点确保 live 环境（proxy + owner 绑定）就绪。
- 触发 §0.7 同-issue 5 轮硬停后，我**升级并问用户"要 A/B/C 哪个"**，被用户正确指出"任务没完成却甩问题"。应当继续把它做完，而不是把决策推回去。

## 证据链：根因是"从未端到端跑通过"

cron 子系统（M2）在实现时**从头到尾没有在真环境端到端跑过一次**——每个层间边界独立坏，且出现两处"对着不存在的内核 API 编码"（r4 `create_session(session_id=)`、r5 `_RunOrigin.SYSTEM`）。这类 bug 单测（尤其用 stub 的）抓不到，只有真跑才暴露。这也是为什么"逐轮远程 fix + stub 验证"始终在追下一层。

## 纠正措施（已执行 / 形成约束）

1. **改为单个保活 worker、一口气跑到 recurring**：派 `cron-finisher` 并**全程不关停**，crash 一个修一个、我贴身喂精确诊断，直到 cron/heartbeat **连续触发≥2 次 + awareness 追问通** 才算完。
2. **orchestrator 亲自前置 trace 全链路**：M7 起我自己把 cron 执行→投递链读通、一次找全接缝（含"可见投递从未实现"），不再等 reviewer 一轮挖一个。
3. **验收门槛改为 recurring live 证据**：不接受"只验首次 / 单测 stub"，必须连续触发 + 真消息 + 端到端集成测试走真 `_KernelClientShim`。
4. **先保证 live 环境就绪**：proxy(:4000) + owner 绑定 是 cron/heartbeat 投递的前置，验证前先确认。

## 给未来 unit 的教训（沉淀）

- **单路径串行 bug 不要用重型验收轮次撞**——优先一个保活 worker 在 live 环境连续调试；reviewer 全旅程留到"功能自认为跑通"之后做确认，而非每个微 fix 都跑。
- **复用 worker 是默认**（保上下文 + 热环境），新派是兜底——尤其 fix 落在原 worker 做过的模块时。
- **新子系统在 worker 收口前必须有一次真环境端到端运行**，否则"对不存在的 API 编码 / 层间契约分裂"会被 stub 掩盖，留到验收阶段逐层引爆。
- **周期性功能的验收必须验"第二拍"**——首次触发（last_due=None）走的是不同分支，会掩盖 recurring 的 rounding/状态 bug。
- **触发轮次 cap 时，继续把活做完是默认**；只有在真的需要人决策（产品取舍 / design 改动）时才升级，不要把"继续不继续"甩回用户。

> 状态：本复盘写于 round-6 之后、`cron-finisher` 保活会话推进中。cron 已能首次投递（M7 实证 "Current time" 消息进直聊），剩 ceil(recurring) / awareness / 合约白名单三个尾部 bug 收口中。
