# refactor-682: Agent 能力目录生命周期隔离 — 技术方案

> 对齐: motivation.md，用户明确只改后端。

## Changelog

## 现状分析

### 涉及范围

- IM `control-routes.ts` 在 `ops.serialized` 中同步恢复配置并调用目录 RPC；`agent-settings.ts` 保存有限配置展示快照，权限/绑定/版本 fencing 已存在。
- `node-rpc.ts` 固定 10 秒 pending timeout，不通知 Node；`channels` 的 `serverRequests` 在 handler 失败/不返回时可能滞留。
- Node `main.ts` 组装可信 runtime configuration；`RuntimePartitions` 将执行隔离到普通/个人运行时。目录和 prompt preview 共用这些长期执行进程。
- DSH `index.ts` 的 preview 被 UI catalog、prompt preview、配置 prepare 共用。每次挂载全能力临时 preset、创建 Session、枚举原生 tools/skills/workflows，并释放 Agent/preset/cron；持久化 Session 未删除。
- 已检查锁定 DSH 0.2.1-alpha.1 公开 `CreateAgentOptions`、`AgentHandle`、`SessionPersistence`：创建必须带 SessionId；支持创建期 AbortSignal，但没有无 Agent 的同等完整目录 API，也没有持久 Session delete。workspace plugins 的挂载可执行第三方生命周期，单靠 Promise.race 不会终止它。

### 既有约束

DSH 只从 integration 的公开依赖接入，Node 只使用 `@nano/dsh-integration/client`。不 fork/patch/private import，不增加第二套 Agent loop 或 HTTP runtime。保护主仓 dirty patch 和生产数据。UI/API 既有字段、权限、离线只读、配置版本及保存校验保持不变。

### 可复用能力

复用 `RuntimeClient`/`prepareProfile` 启动官方 CLI、同一 preset/skill/workflow 投影、现有 settings 展示快照与连接 fencing、NodeRpc request correlation 和既有 metrics/logging 入口。不新建持久全量目录表，不把缓存当作配置授权；不复用聊天进程承载不可可靠取消的临时挂载。

### 相关历史

bugfix-644 离线 settings、feat-652 设置页重构、refactor-672 typed configuration/RPC 是现有行为来源。工作树由 `4cea0166d` 创建；首文档基于最新 main 发布，实施前合入最新 main 的已提交内容，明确保留此基线来源，不带入原仓日志 patch。报告是现场证据；内部锁名和 RSS 长时泄漏仍未经证明。

## 架构总览

```text
settings GET / capabilities GET
  -> IM CatalogReads (版本、连接 fencing；TTL cache；single-flight)
  -> Node capability handler (deadline、cancel、投影)
  -> integration ConfigurationInspector (最多 2 个临时官方 DSH worker)
  -> 独立临时 home + 原生 preview
  -> 完成/异常/取消：退出 worker -> 删除其整个临时 home

配置 prepare / prompt preview
  -> 同一个 ConfigurationInspector，使用本次真实候选，不复用陈旧校验结果

聊天运行时：保持原有 RuntimePartitions，不承载临时 preview
```

## 关键决策

1. **保持客户端协议，用后端缓存消除重复构建。** IM 每个 Agent/节点槽只保留一个 current entry，key 包含 owner、agent/node、binding epoch、connection identity、workspace、profile_version、schema revision；缓存 5 分钟。完整候选只存内存，SQLite 仍只存已有展示投影。GET 命中直接返回；冷读/过期读加入同一有界刷新，成功保持原 `ready=true`，失败仍用原 `last_known` / `ready=false`。刷新逻辑独立于 HTTP 和配置锁，等待者不能占有配置写锁。已有展示不能作为授权或过期的 live_capabilities。

   报告的“冷读立即返回 + 前端后台轮询”和新增交互不采用：用户明确不改交互；沿用首次打开同步取候选体验，但有严格 deadline。读与刷新在后端职责分离，并非新增用户 API。缓存未命中可以创建隔离临时资源，普通连续 GET 不创建真实 home 的 Session。

2. **临时检查使用可销毁进程，不修改上游 Session 存储。** `ConfigurationInspector` 位于 integration，通过 client export 给 Node 使用。每次实际构建创建功能专属随机临时 home、启动官方 RuntimeClient，以 agents/bindings 空列表初始化，再执行同一 preview 代码。providers 来自 Node 当前配置；不发送 LLM 请求。必要的 provider metadata 继续走现有配置，不复制聊天/session 数据。受信 workspace 路径和插件加载行为保持一致。Node 不 import DSH，也不实现工具注册逻辑。

   Node 启动时创建 inspector root，只有本节点实例拥有它（位于已受 Gateway 单实例保护的运行目录下）。构建目录使用随机 ID，目录内所有数据均可删除。worker 以受控 env 标识检查模式；仅该模式允许本进程执行 preview，普通 runtime 将 preview 请求经既有双向 RPC 转交 Node inspector。这样配置 prepare 的隐藏 preview 也不会继续泄漏。RuntimeClient 默认安装反向检查 handler；生产 Node 向所有 partition 传入同一个 inspector，直接 native fixture 可使用独立 inspector。worker 显式禁用转交、无用户 bindings，不会递归创建 worker。测试自定义 prepareProfile patch 按显式可信参数传给 inspector，生产仍使用 Node 生成的标准 patch 与 config 内的共享/workspace 扩展，不复制整个持久 home。

3. **deadline 覆盖准备、启动、构建和退出，不只覆盖等待。** IM catalog RPC 默认 9 秒；Node 默认 8 秒；worker 构建预算默认 7 秒（参数允许测试覆盖，生产仅专属配置入口限制为正数）。deadline_at 向下传播并取本地上限；不增加现有 10 秒上限。AbortSignal 传给原生创建；worker 超时先尝试取消，再终止其进程组，短暂宽限后 SIGKILL，确认退出后删 home。共享聊天进程不被重启。清理失败单独记录并保留路径，下次 Node 启动处理本功能的孤儿目录。

   **异常父进程死亡接管：** 每个 worker 使用随机 inspection_id，同时放入独立目录名、lease（pid、process group、创建时间）和官方 CLI 透传的专属参数 `--nano-inspection-id=<UUID>`。在发送 initialize 之前写入 lease。Node 单实例锁内的新 inspector 逐项处理本节点专属 root：无活进程可删；仍活且 OS 命令行中的完整随机标识与 lease/目录一致，才接管并终止该进程组，确认退出再删；PID 被复用、身份无法确认或 lease 不完整且可能存活时保留并记录 cleanup_error，不扩大扫描到其他 runtime。本期运行平台为仓库受支持的 macOS/Linux；当前启动的 ChildProcess 直接由 handle 保证身份。worker 自身也在父 stdio EOF 时退出，覆盖正常异步代码；对事件循环卡死仍靠重启后的身份接管。新运行不得把尚未清理的存活旧 worker 当作已释放预算：明确拒绝新构建并报告 cleanup_error，避免反复崩溃绕过并发上限。

4. **single-flight 与资源预算都有明确 owner。** IM key 的刷新 Promise 完成或失败后无条件释放；过期结果通过身份/版本/连接 fence 丢弃。Node inspector 按本地 catalog generation、候选配置、cwd、providers 与方法的稳定指纹合并同时发生的相同检查，不缓存保存校验。多个调用者各持 waiter，取消一个 waiter 不终止其他 waiter；最后一个退出才取消 worker。最多 2 个实际 worker，不维护无界队列；满额返回明确暂时不可用，现有 UI 走失败降级，后续重试可恢复。失败短退避（1 秒），不让 30 个并发失败立刻再次开 30 个进程；成功不设退避。

5. **缓存失效不扩大权限。** Profile、binding epoch、connection、workspace 变化强制失效；节点/Agent 删除或重绑不使用旧 entry。模型服务成功变更和插件安装/开关/移除成功后清除该节点的候选缓存并推进节点 catalog generation，外部文件改变最迟 TTL 后可见。配置 prepare 始终以真实候选重新检查。缓存最多 256 个槽，LRU 淘汰已完成槽；in-flight 另受实际 worker 预算和 RPC deadline 限制。

6. **pending 配置恢复与 settings 读取解耦。** GET 直接读 committed profile/active operation，必要时后台启动已有 `ops.recover`，每个 agent 合并一次；返回 pending operation 让已有客户端轮询继续工作，不持有读锁等待。恢复仍在 ConfigOperations 的现有串行/持久 owner 中，不实现第二个写协调器。catalog 等待后重新 authenticate HTTP identity，fence profile 和连接再写 snapshot；旧结果不能解锁。

7. **只对临时检查增加取消，不改变持久 mutation 的不确定性契约。** NodeRpc 给 catalog/preview 帧附 deadline_at，timeout/close 时向同一连接发送 `node.request.cancel` 通知（target_request_id）；Node 的请求 controller 取消 waiter。Node 返回稳定 error_code，IM 以现有 timeout/read_failed 降级。已认证连接上已过期的已知 RPC response 被识别为晚到并丢弃/ACK，避免 unsupported_message_type 风暴；未知类型仍按旧规则拒绝。Channels 在 callback settle/断连/有限 request TTL 时释放 correlation，不让 callback 失败永久留 ID；过期的服务器响应禁止重新包装为新的业务请求。

## 接口与数据流

### IM CatalogReads

`read(key, connection, load)` 返回有限候选 Promise，`invalidateNode(nodeId)` 清理，`close()` 取消正在刷新。load 只负责 RPC/安全投影；settings 路由负责鉴权、profile fencing 与展示快照写入，不能持有 HTTP req 作为后台凭据。每个读结果携带仅服务端可见的 entry/generation 身份；`invalidateNode` 递增代次、abort 旧刷新并使旧 waiter 失效。新读不能加入旧代次，load 完成和路由最后写 snapshot/返回 live 前都核对 entry/generation；若过时则按既有失败语义降级，不复活缓存，不标 current。模型 setup 的异步状态：IM 对开始 save/remove/login 时即失效，status 观察到 revision/operation 完成变化再失效；插件 mutation 成功时失效，Node 在返回实际变化结果时发送既有可扩展节点事件使 Agent 自己的 plugin_manager 操作也失效，后端按 owner/connection 鉴别该事件。Node inspector 同步维护独立 generation：实际模型配置提交、runtime workspace/plugin catalog change 通知到达时先 inspector.invalidate()，作废并 abort 本代所有在途检查，再通知 IM 失效；Node 显式插件 mutation 返回路径也执行此边界。所有检查（包括反向 prepare waiter）完成前核对该代次，过时结果不能返回成功；新请求绝不加入旧 worker，即便旧 worker 还有 prepare waiter 或仍在 cleanup。providers 指纹另隔离模型配置差异。跨层测试固定旧 worker 不返回，让插件变更推进两层代次，再发新 settings 请求并释放旧结果，断言新请求不加入旧 worker、旧结果不成为 live/snapshot。外部文件变化仍以 TTL 有界。缓存 captured_at 保留实际构建时间，命中不伪造新确认时间。live_capabilities 仅对未过期且同 key 的结果存在。节点 capabilities、Agent capabilities 和 settings 使用同一协调器/投影来源，禁止绕回旧 preview 分支。

### Node / integration

`ConfigurationInspector.inspect({method, config, cwd, providers, packageManager?, requestId?, deadlineAt?}, {signal?})` 返回现有 catalog 或 prompt preview 值。它隐藏 worker 创建、相同请求合并、容量、deadline、终止、临时目录和日志；Node 只提供可信配置及当前 provider 描述。`close()` 中止所有 worker并等回收，Node shutdown/update 必须调用；`initialize()` 清理已确认无活 worker 的本功能 orphan，不能删除其他节点 root。普通 DSH runtime 的 reverse RPC `configuration.inspect` 使用同一入口，不复制产品鉴权逻辑。

worker 内 preview 注册/Agent 创建纳入 try/finally，失败也逐项尝试 dispose Agent、unregister preset、删除配置映射及 dispose cron，某一步失败不能跳过其余项。原生 signal 为协作取消；进程退出是对未知 plugin hang 的最终资源边界。目录删除在进程退出之后，避免删后重建。

### 可观测

沿用 stderr JSON 结构化日志，不新建监控服务：component、event、request_id、agent_id、refresh_id、elapsed_ms、result、counts。以 bounded labels 记录 `active_catalog_refreshes`、`catalog_refresh_total{result}`、`catalog_refresh_duration_ms`、`preview_active`、`preview_orphan_total`、`settings_read_stale_age_seconds`；实现可复用进程内统计快照并输出到诊断日志，不能把 request_id 或路径用作 metric label。无凭据、完整配置/Prompt 或用户数据。各实际 waiter ID 与 shared refresh_id 关联，冷读失败和 cleanup_error 可分辨。

## Agent Context 影响与验证

Consumer 仍是用户设置页与配置校验；模型工具/Skill/prompt 的生产组装内容不作改写。preview 使用同一 native preset 及可信候选，生命周期从聊天进程移到临时检查进程；其输出用于选择和预览，因此属于间接 Context 影响。保持原有 source precedence、同名覆盖、Feature 固定工具、PA trust 配置和工作区插件内容。保存校验不能用 TTL 缓存。验证比较 representative ordinary/global/PA 的 catalog 经过该配置白名单/固定工具投影后的集合和实际 session.capabilities（不把候选全集误当可调用集），并对 prompt preview 与真实 native assembled prompt 的工具、Skill 和 workspace 贡献做保真断言；不需要新增真实模型自由发挥来证明确定性机制。现有真实 native fixtures 提供公开 API 证据。

## 契约层增量 (delta-spec)

- IM：`specs/im/agents-nodes.md` 修改 runtime 候选按需解析契约，允许有界内存缓存，保留所有既有候选字段/权限 scenarios；新增 timeout/recovery 场景。
- Gateway：`specs/gateway/agent-capabilities.md` 增加临时检查资源隔离与不可阻塞正常运行的契约。
- 顶层 SPEC：实施后补充临时官方 DSH 子进程职责一句说明，依赖方向不变。

## 风险与回退

冷进程启动比单次 warm preview 更慢，以缓存降低频率；实测冷 catalog p95 目标 <5 秒，若超过不得简单延长 deadline。可信插件可能含启动副作用，这与现有 preview 相同；临时 worker 不拥有实际会话/排程。两个 worker 预算满时暂时降级，不影响聊天。缓存 TTL 内外部 Skill 文件变化存在最多五分钟可见延迟；保存始终重新验证。回滚代码保留原配置/快照，临时数据无需迁回。

## 一次性部署迁移

见 [deployment-prompt.md](deployment-prompt.md)。历史生产 preview 只在停止其旧写进程并备份核验后移动到归档；新 root 的未来 orphan cleanup 是本功能正常生命周期。当前任务不授权部署、不操作生产。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM/Node/DSH | `./scripts/e2e-down.sh` | `PATH="$HOME/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH" ./scripts/e2e-up.sh --profile daily` | `.e2e-env` 中 IM URL `/health`，对应节点在线 |

**Review 驱动方式**：后端变化，不改客户端；独立 reviewer 用 Web 实际调用的 settings/capabilities/config/section HTTP 接口驱动同一真栈，不绕过 Node/DSH。使用 daily P/E/Q + PA，冷读/缓存/故障后恢复/配置保存/独立分区/断连重连为必验。无需重新设计或验收前端画面。

**验收前置**：本机 dev_host 已确认 Air、隔离 E2E YAML 存在；依赖已安装，使用固定 Node 24.22.1，daily 模板自建身份。故障只注入临时 worker 的测试 workspace 插件，不动生产和真实聊天 runtime。真实 provider 连通性仅在确需模型任务时单独验证；本 unit 的核心机制不依赖真实模型响应。

## Milestones

报告的 M1–M4 是建议的实施顺序；本次不改 UI，缓存、进程边界和取消须一起交付才能解决同一故障，采用一个 M1，不按层机械拆分。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-catalog-lifecycle | 后端目录与临时检查生命周期 | 无 | 无 | IM、Node、Channels、integration、相关测试/spec | [reviewer] motivation 全部用户场景通过，保持既有 UI/API 语义；[worker] 30+ 并发读只有一次构建；冷/过期/版本/绑定/cache failure 保护；卡住后的重试成功且聊天进程不重启；取消与迟到响应不泄漏；worker 挂起时强杀其 Node 宿主，再启动接管回收并成功构建，PID 身份不符时保留且报错；模型/插件变更与在途结果交错不返回旧 current；100 次真实刷新临时 home 无净增长、活动 worker 回零；至少 30 分钟/1000 请求 soak 记录 cold/cache 样本数、p95/RSS/FD/目录；preview/prepare 全调用者保真；历史目录迁移在副本上验证幂等/中断恢复；最窄测试、类型/构建、本地与远端 CI 通过 |
