# Design 评审:feat-445-message-fork-branch

**评审者**:change-design-reviewer(独立视角,只读不改)
**对象**:`design.md` v2.5 + `spec.md` v1 + 三份 delta-spec(kernel/im/gateway)
**轮次**:第二轮(复审 v2.5)。第一轮对 v2.2 报 1 CRITICAL + 2 WARNING。

**结论**:Approved(第一轮三处 Issue 全部化解;新方向架构更优。遗留 1 条架构进攻 WARNING + 1 条内部一致性 Recommendation,均不阻断门禁,作者自行取舍)

---

## 第一轮 Issue 化解核对

| 上轮 Issue | 化解动作(v2.5) | 核实 |
|---|---|---|
| **[CRITICAL] manager.load 非无损、无 raw-materialize 路径,整套「无损权威」前提站不住** | **彻底改方向**:不再追求「无损全量」。v2.4 据用户「分支与源体验一模一样」翻转为「复制源在 M 的 as-of-M 视图(含源当时压缩态)」。design.md:24 显式纠正旧错称——「manager.load 的『raw』指『未经 typed Session 包装』、非『压缩前全量』,本 unit **不需要**取回 compact 前全量」;:45 既有约束新增「store.load 的 boundary-aware materialize 给出的就是源运行所用视图,fork 要的正是这个」 | ✓ 化解。新前提与我追到的 store.load:224-229 行为**完全一致**(boundary-skip 视图),不再依赖任何不存在的能力。且新方向有真需求驱动(用户:分支≡源零差异),架构更正 |
| **[WARNING] 决策1风险句「IM 消息携带 run_id(feat-340-M2)」与决策4 矛盾** | v2.3 changelog 注明「删决策1/3 的 run_id 残留」 | ✓ 化解。决策1风险(:117)现为「映射回源日志中那条 assistant 消息,靠决策4 的逐气泡 message_id」,run_id 残留已清 |
| **[WARNING] kernel delta 写 MODIFIED 但无可锚既有条目,应 ADDED** | v2.3 changelog 注明「kernel delta MODIFIED→ADDED」 | ✓ 化解。kernel delta 现为 `## ADDED Requirements`,且顶部加「归并提示」明示 canonical 仅声明方法存在、无行为契约,本条为首次建立 → ADDED |

---

## 核实台账(本轮新方向的承重原子;旧轮已核且未变的原子标注「沿用上轮 ✓」)

### 现状断言(与新方向相关的重新核实)

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| store.load 的 boundary-aware materialize = 源运行所用视图(有 compact 时 = summary + boundary 后 turn) | 复核 jsonl_store.py:198-231 | ✓ 成立。:224-229「Only keep turns after latest compact_boundary」;:231 无 boundary 时取全部 turn。新 design 把它当「源在 M 的视图来源」正确 |
| compact_boundary / summary turn 的内部引用结构 | 读 manager.py append_compaction:240-270 | ✓ 核到:`compact_boundary` 带 `summary_uuid`;summary turn `uuid=summary_uuid`、`parent_uuid=first_kept_event_id`、`is_compact_summary=True`。**这些内部引用是 CC-式 raw-clone 必须一致 re-stamp 的对象**(见架构进攻) |
| `_fork_locked` 操作的是 materialized `Message`,**不含** compact_boundary 标记 | 复核 store.load:223-231(turns 只收 type==turn)+ runtime.py:1340-1366 | ✓ 成立。store.load materialize 出的 Message 含 summary turn 但**不含 compact_boundary 条目**;`_fork_locked` 遍历的是 Message 列表 → 它**看不到也无法 re-stamp boundary 标记**。这决定了 CC-式(需克隆+重写 boundary)无法直接复用 `_fork_locked`(见进攻发现) |
| realtime_stream.py:54 逐气泡 message_id / Message 模型无 kernel id / _ensure_binding 复用 / RPC dispatch / 前端气泡落点 | 沿用上轮第一手核对 | ✓ 沿用上轮 ✓(本轮未变) |
| runtime.fork_session 热路径优先读内存 `_session_histories`(compact 后被重置为摘要) | 复核 runtime.py:2048 + 决策1拒绝项/风险:241 | ✓ 成立。design 对策「fork 不复用过期缓存、从当前 JSONL 重 materialize」正确 |

### 决策

| 决策 | 四问 | 结论 + 证据 |
|---|---|---|
| 决策1 复制源 as-of-M 视图、分支≡源逐字一致、绝不还原压缩前全量 | 拍死/spec驱动/自洽 | ✓ 方向拍死且第一原则清晰(分支≡源零差异)。spec/Q2=A 上下文连续 + 用户「体验一模一样」驱动。三种压缩态分支(:116)逻辑自洽。**实现要点选了 CC-式 raw-clone**(:106)——正确但偏重,见进攻 |
| 决策2 IM 同步编排 + 一次 WS RPC | — | ✓ 沿用上轮 ✓ |
| 决策3 两份表示(IM 展示副本 + gateway as-of-M 视图) | 自洽 | ✓ 强化后更自洽::131「分支照搬源本就有的展示/记忆两层关系,差异与源一致」——正面回应了「压缩态下展示≠记忆」 |
| 决策4 relay 落逐气泡 message_id 对齐 | — | ✓ 沿用上轮 ✓(全 unit 最扎实) |
| 决策5 在线校验 + 原子回滚 | — | ✓ 沿用上轮 ✓ |
| 决策6 普通 direct-agent 单聊 | — | ✓ 沿用上轮 ✓ |

### spec 约束 / delta-spec / milestone

| 维度 | 核实 | 结论 |
|---|---|---|
| spec 全 Requirement 覆盖 | 逐条比对 | ✓ 沿用上轮(全覆盖);新方向对「完整气泡形态」仍由 IM 展示副本承担(决策3),agent 记忆侧 as-of-M 视图与源一致,不削弱任何 Scenario |
| kernel delta(as-of-M 视图、ADDED、THEN 可观察) | 复读 specs/kernel/spec.md | ✓ 与新方向同步翻转;Scenario「fork 复刻源在 M 的上下文(含压缩态)逐字一致」用消费者可观察语言(模型记忆表现),无内部符号断言 |
| im / gateway delta | 复读 | ✓ 未受方向翻转影响,仍成立(gateway delta 主语为 gateway 代码消费者) |
| 单 M1 垂直切片 + 两轨退出标准 | 复核 :269 | ✓ 仍单 M1;退出标准随新方向更新为「分支≡源在 M 三组守护测试」(① boundary 后 ② boundary 前 ③ 未压缩),可验、引 spec |

---

## 架构进攻(四角度逐个走)

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | relay 落 kernel message_id 到 IM 行 / fork 编排分层 | ✓ 走完无存活发现。message_id 作不透明 token,无 IM→kernel 反向依赖;跨机纪律保持(沿用上轮结论) |
| **该不该存在 / 深还是浅** | **决策1 选 CC-式「复制源 JSONL 完整 transcript(含 boundary/summary 标记、re-stamp 内部引用)到 M」,而非自己已识别的「更轻等价做法」(复制 as-of-M 视图交 `_fork_locked`)** | **⚠ WARNING(见下)**。两法模型行为相同(design 自承),CC-式 多出 boundary/summary 内部引用 re-stamp(design 自己的「头号易错点①」),换来的 kernel-side scrollback 在 nano **无任何消费者** |
| 治本还是补丁 | 「fork 从源 as-of-M 视图复制」整体 | ✓ 走完无存活发现。方向治本(分支≡源,对多 channel 一视同仁);「旧气泡无 message_id 禁用不回填」是显式合理降级 |

---

## Issues(WARNING,不阻断)

- **[WARNING] [决策1 实现要点 / 可复用能力段 / M1 范围 / 风险头号验证点]:CC-式「克隆完整 transcript+标记」比所需更重,建议改用 design 自己识别的「复制 as-of-M 视图」轻法。**

  **事实**:决策1 选的 CC-式(:106)= 复制源 JSONL 原始条目(`turn` + `compact_boundary` + `is_compact_summary` summary turn),re-stamp UUID **及其内部引用**(`compact_boundary.summary_uuid`、summary turn 的 `uuid`/`parent_uuid=first_kept_event_id`,已第一手核到 manager.py:248-264),到 M 截断,新 session 再 boundary-aware load 派生视图。design 自己在 :110 括注了「更轻的等价做法:直接复制『boundary-skip 后的视图截断到 M』交 `_fork_locked`,**模型行为相同**」,并说「CC 选了保留完整克隆,nano 取齐」。

  **为何「取齐 CC」的理由不成立**:CC 保留完整 transcript 是因为**它的 transcript 就是它的展示面**(CLI 直接 scrollback/rewind 这份记录)。nano 不是——kernel session JSONL **不是展示面**:展示由 IM 展示副本承担(决策3),且既有约束(:44)明令「IM 绝不直读 gateway kernel JSONL」。更关键:**compact 之后 nano 永不再读 boundary 前的 turn**(store.load:224 永久跳过),它们已是 write-only 死重。CC-式把这些死重连同 boundary 标记克隆进分支,在 nano 端**无任何消费者**。

  **长远代价**:① CC-式 必须正确一致 re-stamp boundary/summary 的内部引用——这正是 design 标的「头号验证点·易错点①」,re-stamp 漏一处(如 `summary_uuid` 与 summary turn `uuid` 不同步)→ 分支 boundary-aware load 找不到 summary、视图错乱、且是 compact 后才暴露的隐蔽 bug;② 与 compact 条目 schema 形成**长期耦合**——未来任何对 `summary_uuid`/`first_kept_event_id`/`is_compact_summary` 的改动都要同步维护 fork 的 raw-clone re-stamp,否则 forked-compacted session 静默损坏;③ 经核对,CC-式 **无法复用 `_fork_locked`**(它操作 materialized Message、看不到 boundary 标记),是一条**新的 raw-entry 克隆路径**,与「可复用能力段(:49-50)宣称『整体复用 `_fork_locked`/store.load materialize,只加截断』」**自相矛盾**。

  轻法(b)则:对源 raw 前缀 [0..M] 做 boundary-aware materialize 得 as-of-M 的 Message 列表 → 交现成且已测的 `_fork_locked` re-stamp 写新 session。**两法都需要新增「源 as-of-M materialize(截断到 M)」这一步**(M 在某 boundary 之前的老消息场景下不可避免,二者共担此成本);差别只在最后一步——(b) 复用 `_fork_locked` 的 Message 复制、**完全避开 boundary/summary 标记 re-stamp**,(a) 另起 raw-clone 并承担该 re-stamp。

  **不改的下游坏事**:worker 会把 M1 最难的力气花在可避免的 boundary/summary 内部引用 re-stamp 上(本 unit 头号易错点),并背上与 compact schema 的长期耦合;且会困惑于「可复用能力说复用 `_fork_locked`,实际 CC-式 要另写 raw 路径」。**建议**:除非能指名一个 nano 端真消费 kernel-side scrollback 的现在或近期特性,否则改用轻法(b),并相应更正可复用能力段措辞。

---

## Recommendations(不阻断)

- 若坚持 CC-式(a):请把「可复用能力段(:49-50)」措辞从「整体复用 `_fork_locked`,只加截断」改为如实——CC-式 是新增 raw-entry 克隆路径(`_fork_locked` 仅作 Message 侧 re-stamp 参照,不直接承载 boundary 标记复制),免得 worker 起手按「小改 `_fork_locked`」估而低估真实工作量。
- 风险段「头号验证点」三组守护测试(分支≡源在 M)写得到位;若采纳轻法(b),其中「易错点① re-stamp 内部引用」可整条删去,守护面收敛到「as-of-M materialize 截断点正确」,M1 风险显著下降。

---

> 复核范围:第二轮第一手复核了 store.load:198-231、manager.append_compaction:240-264、runtime `_fork_locked`/`_session_histories`、kernel delta 全文,确认方向翻转后旧 CRITICAL 的事实基础已不复存在(新前提与真实 store.load 行为一致)。台账无存活 ✗;架构进攻一条 WARNING 属「绕路/偏重」而非「站不住」,不构成让 worker 走偏的硬缺陷 → Approved。
