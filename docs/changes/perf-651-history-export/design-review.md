# perf-651 History Export — Design Review

## Round 1

### Metadata

- reviewer target: independent Codex agent `/root/design_review`; 未参与本 unit 设计或实现。
- review_mode: `full`
- mode_reason: 首轮 Gate 2，覆盖首文档、所有设计决定、实际组装与消费者、delta 和单 milestone。
- reviewed HEAD: `af01637e41f5e6cadade25dd2760a1e0a2980022`
- base: `55376c1112ff870837a6ee65febf52e1f3686a9b`
- checkout: `/Users/czj/.codex/worktrees/history-export/nano-multiagent`
- branch: `codex/perf-651-history-export`
- started_at: `2026-10-24T00:56:36+08:00`
- completed_at: `2026-10-24T00:57:18+08:00`
- duration: `PT42S`；上述时间记录报告汇总阶段，前置只读取证已先完成但未记录起始时钟，不作为全程耗时指标。
- 初始工作区仅有未跟踪的 `packages/dsh-integration/tests/export-benchmark.tmp.test.ts`；按派发视作临时基线测量脚本，未修改、未运行、未当作产品实现。
- 受审文档 SHA-256：
  - motivation.md: `7269ced76b6e617e643fe3f1f8e9599bedd2fd1680334ba0daffd6682bf1a398`
  - design.md: `c177f32befb3a92d027da13952c7b3cd1f4e6af5d253483fbc9c24c675619eba`
  - specs/gateway/routing-delivery.md: `79c634cb3e355abd2aef6b740f8171ca2e74c1c2086bf5eeb4f8f1ff13a6e97b`

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING.** Gate 2 尚未通过。增量导出本身的职责和恢复方案合理，但原始文件真实消费者的延迟读取边界未闭合；仅在返回路径前等待队列不能兑现实际提炼时的完整可读性。

### Coverage 与证据

1. **现状与真实接线。** `packages/dsh-integration/src/index.ts:121` 创建 NativeHistory，`:271` 在 accepting=true 前调用 recoverExports，`:355-358` 在 session.export 校验 binding 后调用 path，`:587-601` 停机先等待运行结束再等待导出。`history.ts:96-105,320-337` 在 nano turn/end 为每次请求串行全量 flush、snapshot、重写；`:268-318` 原始与可读文件各自临时写入再 rename。基线重复序列化/写盘原因成立。没有以仅测试调用的实现代替产品入口。
2. **消费者。** `packages/personal-assistant/src/history.ts:145-175` 对每个来源请求 session.export 后，只将路径写入 source_jsonl_paths；`docs/specs/im/web-chat-ux.md:375-393` 明确生成 prompt 后预填普通聊天，由用户随后发送；`packages/personal-assistant/assets/skills/conversation-skill-distiller/SKILL.md:12-18` 随后要求读取所有 JSONL，无法解析时不得部分创建 Skill。workspace 副本仍是直接文件消费面。设计已披露 workspace 热更新尾行边界，但把原始提炼消费者归为“经过 session.export 即完整”并不充分，见 R1-W1。
3. **持久上界、增量和 fork。** 锁定依赖 `@deepseek-ai/dsh-session` 的公开 README 与安装实现确认 `seq` 是包含继承前缀的日志长度，snapshotEvents 接受半开区间、事件只追加，flush 等待所有 durability listeners 并传播失败。设计复用既有同步读取调用而不扩张调用面；先捕获 to 再 flush，尾段读取受 to 限制，可避免 flush 等待期间的新事件越过持久边界。成功水位在两份文件均完成后推进；首次与 fork 从零保留全部继承前缀。未引入 DSH private import 或第二份事实源。
4. **恢复与队列。** `history.ts:338-355` 既有恢复通过 sessionQuery observation 重建；锁定 `dsh-session-query/README.md:110` 说明 observation 固定事件切面。设计在初始化阶段重建并建立内存水位，长度不符/缺失/写失败清除水位后完整重建，权限等错误传播，不以空文件替代。每会话一个任务加 dirty 标志比逐请求 Promise 链简单且适合当前范围；明确失败期间新请求仍须处理，跨会话可并行、失败不伪报成功，没有无界自动重试。实现时按既定测试矩阵检验，无需另增复杂调度层。
5. **架构判断与用户约束。** `SPEC.md:29-50` 把持久历史产品投影归于 dsh-integration，PA 依赖 RuntimePort；把优化放在 NativeHistory 内合理。复用 DSH 日志、flush、query 和现有文件重建能力优于永久索引或缓存正文。保留自动更新可满足 workspace 直接读取，顺序轮次收益也不能仅靠合并队列取得；主要选择有依据。独立 worktree、不合并/部署、不删除历史、不改运行时和不扩大到任务/ACK/UI 的约束均被设计保留。
6. **delta。** `specs/gateway/routing-delivery.md` 的 canonical target 正确，ADDED 未覆盖或删除原有 Scenario；版本头、来源、envelope 过滤、图片占位、fork 与恢复语义有明确消费者描述。设计指出既有 conversation-id 与当前 session-id 命名漂移并避免命名迁移，本轮不要求借此扩大优化。新增完成边界本身须随 R1-W1 修正，不能只增加“读取时可能遇到尾行”便宣称提炼兼容。
7. **milestone、验收与性能口径。** M1-export 单切片无并行冲突；95% 指标针对应用传给文件 API 的 payload 和原始事件序列化量，未冒充设备 I/O 或生产时延。临时 benchmark 的真实 NativeHistory、临时文件与计数方式匹配该口径，但本轮只核方法，未重复运行或背书数值。现有 `tests/history.test.ts` 有真实 RuntimeClient 的 fork、compaction、来源过滤和 restart 证据入口；runbook 用确定性 LLM 避免无关模型变量合理。该测试在请求导出后立即读取（`:188-200`），尚不能代替 R1-W1 的延迟并发读取验收。无前端视觉变更，不要求原型或启动 UI。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 返回可变追加文件路径不能保证提炼 Agent 稍后读取完整 JSONL

- **位置：** `design.md:31-41,49,59,67`；`specs/gateway/routing-delivery.md:7-11`。
- **证据：** 设计让原始导出在同一路径上 append，并把 session.export 等待队列当作完整读取的解决方案。真实 PA 链路只把路径写入 prompt，IM 允许用户稍后再发送；Skill 此后才读取文件，且明确拒绝不可解析来源。session.export 的队列等待覆盖不到这个后续读取时刻，也没有阻止来源会话重新活动。旧实现通过临时文件 rename 发布完整文件；将发布文件改为原地追加新增了可见半行窗口。
- **具体场景与后果：** 用户取得来源会话的 distill prompt 后，原会话继续一轮；提炼 Agent 读取该路径时，新轮次的大事件正在追加，或追加失败留下部分尾行。即使此前 session.export 成功，输入也可能无法解析，提炼因此失败。多来源逐个取得路径还扩大了先取得路径的等待窗口。此问题是现有异步消费者的正常并发路径，不是假设用户同长度篡改派生文件。
- **要求闭合：** 明确原始导出路径在实际延迟读取期间的完整性保障，例如在显式请求时发布可完整读取的稳定副本，或通过真实消费者可执行的完整切面读取契约闭合；选择简单方案即可，不要求新事实库或广泛文件事务。若选择改变消费者行为，必须同步调整影响范围与契约，不能仅声明调用过 session.export 即安全。
- **复审证据：** 更新设计、delta 和 M1 验收，使“取得路径 → 来源继续产生导出（含部分写入失败）→ 稍后读取此前给出的路径”仍得到合法完整 JSONL，并明确此读取的是哪个切面。无需真实模型或生产服务。

### Recommendations

无额外可选改进；先闭合上述一个消费者边界，不扩大为冷启动、磁盘清理或 UI 改造。

### 本轮执行边界

只读取受审文档、实际组装/消费者/现有测试及锁定 DSH 公开 API 证据，仅新增本报告；未修改设计或代码、未提交，未执行全量 CI、生产服务或额外子任务。本轮是设计可实现性审查，不是实现或产品验收。

### Author Resolutions

- R1-W1 — accepted。PA distill 的 source_jsonl_paths 是延迟读取引用，等待一次队列不能保护后续读取。修订 design 关键决策 1/3/5 与接口数据流：原始导出仅 session.export 显式完整原子发布；正常轮次只增量可读副本，不新增第二份原始缓存。delta 增补延迟读取 Scenario，M1 增补并发读取验证。
- 同次落实恢复共用队列及显式 path 重试，消除对 initialize 回调静默的假设；请求标志在合并及失败重试时保真。
