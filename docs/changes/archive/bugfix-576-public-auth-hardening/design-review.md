# bugfix-576 Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_review_576`，独立于 design author `/root`
- review_mode: full
- mode_reason: 首轮 Gate 2；覆盖完整 incident、design、canonical delta 与 M1-hardening。
- started_at: 2026-10-04T01:13:58+08:00（首个记录的现场时间；前置读取已开始）
- completed_at: 2026-10-04T01:15:43+08:00
- duration: 约 3 分钟；非性能测量。
- validated_at: `8e8e60b1c91a19d0dffff5395c33002aa963d6de` 的 unit tree；受审 incident/design/specs delta 均无本地修改。
- executed_base: `main@8e8e60b1c91a19d0dffff5395c33002aa963d6de`
- 工作区：main 有其他 dirty/untracked 文档与技能；未修改它们，未创建分支、未提交、未运行产品或改动设计/实现。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。Gate 2 暂不通过。**

唯一阻断项是撤销后 fork 异常清理是否仍允许写入的决定未闭合。没有把假想平台扩展、分布式部署或视觉偏好列为问题。

### Coverage 与证据

1. **现状与实际装配入口。** 核对 `src/IM/app.py` lifespan、middleware 装配和单 worker 约束，`api/public_boundary.py` 当前来源限流位置及 company_gate 生命周期；核对 `api/routes/auth.py` 同步密码路由、`application/auth_service.py` 签发及持久轮换、`infra/auth_limits.py` 固定窗口与连接提交。设计关于 bcrypt 位于公司锁内、跨来源账号失败桶和 localStorage token pair 的描述与实际代码一致。incident 中的历史性能数字作为历史观察，本轮未重新跑性能实验。
2. **并发、共享 SQLite 与撤销。** 独立限流连接避免 gate 外提交同一共享连接事务；bcrypt 线程只拿不可变输入/快照、回 gate 后重读用户及 epoch，计算名额直到线程退出才释放，均是必要边界。默认持 gate、只在显式等待处让出，比逐路由改事务更小；同 Agent 局部锁等待也让出 gate，覆盖真实 AB/BA 关系。已核对 `application/agent_config_operations.py:94-209`、`ws/gateway/control.py` 的 Future 等待与 finally 清理、`ws/gateway/work.py:95-135` 的 permission 等待和 `api/deps.py:364` 的数据身份入口。身份复核涵盖会话、成员、机器；异常链上的 fork 清理见 R1-W1。
3. **限流与范围。** source、source+account、1 秒目标窗口以及 2 个计算名额覆盖来源切换账号与分散目标猜测，且明确不宣称消除 DDoS；正确密码不绕过来源限流是明确取舍。复用现有表和 Retry-After，无外部基础设施，符合用户低维护复杂性要求。
4. **Cookie、CSRF 与程序兼容。** 明确 browser 标记 + 精确 Origin + SameSite，Bearer 数据面不隐式读 Cookie；程序模式只读显式 refresh 且不改 Cookie，避免同一端点混用凭据。Secure 基于可信 public URL、host-only、HttpOnly、no-store 和不导出 refresh 给 JS 的方案闭合。已核对前端 `auth-api.ts`、`auth-store.ts`、`auth-session.ts` 当前接线；迁移清旧 localStorage、升级一次重新登录属于明确行为。Web Locks 覆盖所有 Cookie 写操作、single-flight + version 覆盖标签内迟到响应，BroadcastChannel 只传登录/退出事件；这些机制各有直接用途，没有另造会话后端或重放宽限。
5. **浏览器策略与前端边界。** CSP/HSTS 策略集中、HTTPS public origin 与 Tunnel 内部 scheme 分离、Swagger 与 Vite 分开处理，未要求部署或修改边缘服务。本次没有新布局、控件或用户操作决策；允许不制作新 prototype。没有本轮视觉验收结论；M1 必须真实浏览器验证桌面/窄屏、加载/恢复/错误/多标签/pending/深链、附件及 WS。RequireAuth 当前验证与重试路径已核对，实施须接入空内存的 Cookie hydration，不能仅删持久化。
6. **delta 与 milestone。** `specs/im/auth-tenancy.md` 锚定正确 canonical 文件；修改 JWT requirement 时保留全部既有 Scenario，新增浏览器模式限定，未覆写 unrelated policies/对象权限。限流原 Scenario 保留并改变维度。M1 同时包含后端 worker 验证与真实浏览器 reviewer 验证；隔离临时库、WS 协议节点和本地 TLS 前置明确，无需真实 LLM/生产账号。请求取消、撤销期间 RPC、同 Agent 竞争、程序 API、轮换持久化均列入退出标准。R1-W1 修正须投影至同一验证矩阵。
7. **架构判断。** CompanyBoundary/infra lease 负责统一锁生命周期与授权重验；AuthService 负责密码/会话业务；HTTP 层负责 Cookie/Origin；前端 auth 层负责浏览器协调。这些职责没有越过 IM→Agent 红线。对既有会话 CAS、epoch 与 operation recovery 的复用合理；增加 lease 而不散落锁管理有明确运行收益。只有异常清理是否允许的职责边界尚未定案。

### 历史问题闭环

首次审查，无历史问题。

### Issues

#### R1-W1 — 撤销后 fork 清理写库与“不得继续受保护副作用”仍冲突

- 位置：`design.md:53-57`；`incident.md` 的“Gateway 等待与成员撤销” Scenario；delta 的“等待结果期间撤销” Scenario。
- 证据：`src/IM/application/web_im_service.py:444-449` 在 RPC 外层捕获 **BaseException**，无论是取消、普通失败还是未来的撤销错误，都会调用 `_rollback_fork`；`:594-604` 明确执行 `delete_conversation` 写库。只在 helper 中重新取得 gate 并抛出身份失效异常，并不能阻止此 handler 的写入。设计已经识别这个 cleanup，却同时承诺撤销失败“不进入受保护提交”，未指定 cleanup 在撤销时的处理。
- 具体后果：按现有描述直接接入 helper，用户在 fork RPC 等待中被停用或登出后，旧请求仍可删除 IM 分支，违反 incident 与 delta 的绝对承诺；若实现者为避免写入任意跳过 cleanup，则会改变失败/取消的半成品清理语义，也没有确定的退出预期。
- 要求：在设计中选择并收口一种最小处理方式：撤销错误明确跳过原 cleanup，并定义预建空分支的保留/后续处理；或明确把受 gate 保护、仅限本请求预建半成品的服务内部 cleanup 列为撤销后的有限例外，同时同步 incident/delta。无需引入通用补偿框架。明确区分正常授权下的失败/取消清理与身份已撤销，并增加确定性测试：发出 fork、挂起结果、撤销、恢复成功/错误或取消，断言最终 DB 状态及拒绝响应。

### Recommendations

- R1-R1（可选）：实施中的 Cookie 恢复测试区分“请求未到服务端的网络失败”与“CAS 已完成但响应丢失”。严格一次性 refresh 不保证后者无感恢复；如最终需要重新登录，准确报告该边界，不用模拟请求前失败代替所有网络失败。
- R1-R2（可选）：在现有取消/并发回归里直接断言退出时共享连接没有遗留事务、gate 不泄漏、计算名额直到真实线程结束才归还。可用受控 Future/Event，避免用固定 sleep 和绝对毫秒阈值作为主要正确性证据。

### Author Resolutions

- R1-W1 — accepted。选择有限内部清理例外：仅在 company gate 内清除本请求预建、尚未绑定且仍无消息的 fork 半成品，非空则保留。同步 design 关键决策 1 / 风险与回退、incident Gateway 撤销场景与 delta 等待撤销场景；补充成功、错误、取消三种确定性回归。保持原失败清理意图，无通用补偿框架。
- R1-R1 — accepted as evidence boundary。严格 CAS 已完成而响应丢失可能要求重新登录；验收报告须明确，不引入重放宽限。
- R1-R2 — accepted。取消回归断言 gate 与真实计算名额生命周期，不依赖固定延迟作为正确性依据。

## Round 2

### Metadata

- reviewer target: `/root/design_review_576`（同一独立 reviewer）
- review_mode: closure
- mode_reason: 仅 R1-W1 的有限清理决定及对应 incident/delta/验证发生局部修订；完整 diff 未含产品代码或其他设计变更。
- started_at: 2026-10-04T01:16:52+08:00
- completed_at: 2026-10-04T01:17:49+08:00
- duration: 约 1 分钟。
- validated_at: `34e9a6598bb2db38bfeb1497bc7adf0cfae7b246` 的 unit tree，受审文件无本地修改。
- executed_base: `main@34e9a6598bb2db38bfeb1497bc7adf0cfae7b246`
- retained_from: Round 1；限流、Cookie/CSRF、前端、SQLite/锁方案和 M1 范围均未改变，沿用其覆盖证据。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。** R1-W1 的清理例外已明确，但新增的“尚未绑定”条件与真实 Gateway 顺序及成功分支验收仍冲突，尚未完全闭环。

### 历史问题闭环与本轮证据

- **R1-W1 — still-open（范围缩小）。** Author Resolution 接受有限内部清理例外，并同步 incident/design/delta，消除了原本“所有写入均禁止”的矛盾；已补挂起 RPC 后撤销、成功/错误/取消的确定性要求。
- 进一步核对实际绑定入口 `src/personal_assistant/gateway/session_binder.py:1062-1081`：Gateway 在返回 `{ok: True, new_session_id, id_map}` **之前**完成 `bind_conversation`。IM 的 `ws/gateway/control.py:420-434` 仅把结果交给 waiter；`application/web_im_service.py:444-476` 则在收到结果后才复制显示历史。它并没有一个独立的“IM 尚未绑定”阶段状态可用来满足新增条件。
- 因此撤销与成功结果交错时，空 IM 分支可能已经在 Gateway 绑定；取消/超时时更无法从 IM 判断远端是否已绑定。设计一方面只允许删除“尚未绑定”的空分支，另一方面要求成功结果恢复后空半成品被清除，无法同时落实。
- 最小闭环方式：把例外按 IM 可观测状态限定为本请求预建、仍无消息且未完成历史复制的半成品，并明确删除 IM 半成品不撤回远端 fork/binding；不新增查询或补偿。也可保留未绑定条件，但明确远端状态未知/成功时保留空分支并调整测试预期。选定一种即可，无需扩大平台能力。
- **R1-R1 / R1-R2：accepted。** 作者在 resolutions 接受响应丢失边界及受控并发证据约束，无需增加会话宽限或测试基础设施。

### Issues

无独立新问题编号；唯一 WARNING 为上述 R1-W1 剩余的绑定条件消歧。

### Recommendations

无新增建议。没有实施、运行验收或视觉验收结论；未修改产品、设计或其他 dirty 文件。

### Author Resolutions

- R1-W1 (R2) — accepted。移除 IM 不可观察的“尚未绑定”条件，design/incident/delta 统一使用“本请求预建、仍无消息且尚未完成历史复制”的 IM 条件；design 明确远端 fork/binding 可能已完成，不查询或自动补偿。成功结果、错误与取消的退出断言仍适用，已有用户内容不删除。

## Round 3

### Metadata

- reviewer target: `/root/design_review_576`（同一独立 reviewer）
- review_mode: closure
- mode_reason: 仅消除 R1-W1 在 R2 指出的远端绑定条件歧义；完整 diff 只含相应 design/incident/delta 和审查记录，未改其他设计或产品代码。
- started_at: 2026-10-04T01:18:23+08:00
- completed_at: 2026-10-04T01:18:49+08:00
- duration: 不足 1 分钟。
- validated_at: `4533d50842a89c720606911abfa7091d291de175` 的 unit tree，受审文件无本地修改。
- executed_base: `main@4533d50842a89c720606911abfa7091d291de175`
- retained_from: Round 1 完整覆盖与 Round 2 真实绑定路径证据；未受影响范围和运行代码未变，无须重做 full review。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。Gate 2 设计审查通过。**

### 历史问题闭环

- **R1-W1 — closed。** Author Resolution 已被实际修订支持：`design.md:53`、incident 的 Gateway 撤销 Scenario 和 delta 的等待撤销 Scenario 统一为“本请求预建、仍无消息且尚未完成历史复制”的 IM 空半成品。design 明确非空保留、只能持 gate 清理、不复制历史、不删已有内容、不发新远端命令，且远端 fork/binding 可能已经完成、不查询或自动补偿。此条件可由 IM 当前请求与数据库状态判断，不再依赖 R2 核实的不可观察远端状态。
- **验证闭合。** `design.md:118` 保留成功、错误、取消三种撤销交错，断言拒绝旧请求、有限清理、已有用户内容不变与 gate 不泄漏；成功结果时远端绑定已经完成不再与本地空分支清理矛盾。非空保留要求明确，不允许直接沿用无条件 cascade delete 作为修复结果。
- **R1-R1 / R1-R2 — accepted，保留。** CAS 响应丢失的重新登录边界和受控取消证据由此前 Author Resolutions 明确承接；没有增加重放宽限、远端状态协议或补偿机制。

### Coverage 与架构判断

本轮只核对上述闭环和三个受审文件一致性；沿用 Round 1 的来源/目标限流、共享 SQLite、lease/局部锁、Cookie/CSRF、多标签、响应头、原生接口兼容、canonical delta 和 M1/runbook 证据。有限清理归属现有 IM fork 服务，统一 gate 仍负责提交串行及身份复核，不扩展到 Gateway 业务补偿，符合低复杂性约束。

设计批准不代表实现、测试、浏览器或部署验收通过。实施须兑现上述条件及原 M1 退出标准；本轮仅追加本报告，保留此前历史和其他 dirty 状态。

### Issues

无。

### Recommendations

无新增。
