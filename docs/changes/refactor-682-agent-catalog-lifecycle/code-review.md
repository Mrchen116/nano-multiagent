# Code Review: refactor-682-agent-catalog-lifecycle

## Round 1 — full

- reviewer: `/root/catalog_static_review`，未参与实现。
- scope: `99354a6a1 → 0812c67efe12174c429c372103fb8842891eed64`，完整 unit diff 和受影响调用链；现场 HEAD 与固定受审 head 一致。
- date: 2026-10-31；读取本 worktree AGENTS、code-review/verifier/context-review skills、current IM/Gateway specs、SPEC、design/Gate 2/delta、测试规范和实施证据。
- constraints: 仅后端；无 UI/reference must-match，未部署、未操作生产、未触碰 caller 隔离栈。审查者仅写本报告和 verification.md。
- verdict: **Issues Found — 2 CONFIRMED P1**。

## Findings

```json
[
  {
    "file": "apps/node/src/main.ts",
    "line": 50,
    "summary": "[P1] 将 inspector 清理失败限制在临时检查，避免阻断整个 Node 启动",
    "failure_scenario": "重启时 inspector root 含身份不符、lease 缺失或无法回收的 inspection，recover() 设置 catalog_cleanup_failed 并 reject initialize()；这里顶层 await 没有处理，Node 在创建 store、运行时与 relay 前退出。设计要求保留未知身份资源并拒绝新检查，但正常聊天应恢复；当前一次临时资源故障使所有 Agent 离线。现有 configuration-inspector.test.ts 最后一项已确认 identity mismatch 会 reject initialize。应记录/保留 cleanup_error，让 Node 其余服务启动，由 inspect 拒绝新临时检查，并增加 Node 启动 seam 的回归保护。",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "packages/dsh-integration/src/configuration-inspector.ts",
    "line": 243,
    "summary": "[P1] 回收进程组时确认子进程退出，不能只等待 worker leader",
    "failure_scenario": "可信 workspace/profile 插件启动同进程组子进程，子进程注册 SIGTERM handler；临时检查成功后发送组 SIGTERM，worker leader 立即退出，本行立即 return，因此不会执行后续 SIGKILL。真实 native 探针返回 inspection success / preview_active=0，但插件 child 仍存活，home 已被删除。worker 在初始化中提前退出也走 240 行的同一漏清理路径；recover 只 ps lease.pid 同样不能识别 leader 已退出但组成员仍活的情况。应持有并确认整个已拥有进程组的释放，在宽限后回收仍活成员，再删除 home/释放容量；恢复路径也应覆盖这一状态并保持身份保护。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## 直接核验证据

- F1：`main.ts:49-50` 为顶层创建/await；`configuration-inspector.ts:214-229` 的任意恢复失败向外抛出。已有 `configuration-inspector.test.ts` 的 `retains an orphan with mismatched process identity and refuses new work` 明确断言 initialize rejects；未另跑整个 Node 或触碰运行栈。
- F2：在固定 head 的已构建 `lib/client.js` 上以 `node --input-type=module` 运行一次真实 ConfigurationInspector；仅创建 `/tmp/refactor682-review-*`。profilePatch 挂载临时插件，插件 `spawn(process.execPath, ['-e', "process.on('SIGTERM',()=>{});process.stdout.write('ready');setInterval(()=>{},1000)"], {stdio:['ignore','pipe','ignore']})`，等待 child ready 后完成 apply，再做普通 catalog。实际输出：`{"inspection_result":"success","preview_active":0,"plugin_child_alive":true,"child_pid":86447}`。探针 finally 对自己创建的 child 发 SIGKILL、关闭 inspector 并删除整个探针目录。未留下长期测试或运行服务；该输出只证明此确定性进程组分支，不宣称生产已有该 child。

## Coverage

- IM：检查 bounded 256-slot LRU、5 分钟 TTL、capture time 保真、失败退避、同 key single-flight、invalidation abort、scope/connection/profile fence；settings 读移出串行写锁、后台恢复合并、等待后的重新鉴权和 snapshot/live fence；node/agent/settings 全入口以及 setup/plugin 失效入口。
- RPC/Channels/Node：检查 9/8/7 秒预算、取消只影响 transient inspections、断连/替换连接、late ACK、serverRequests TTL/settle 清理、Node request controllers、真实配置/provider 投影、shutdown/update 接线。
- Integration：检查 2-worker 限额、generation 指纹和 completion fence、独立 waiter、失败退避、专属 home、lease/随机 CLI identity、startup reclaim、deadline 与 disposer；已发现 F1/F2。
- 全调用者：`configuration.catalog`、`configuration.preview`、`configuration.prepare`、apply 隐式 prepare，以及 initialize 的 pendingConfigurations，均经过 preview 原语反向 `configuration.inspect`；Node 直接 catalog/preview 经过同一个 inspector。保存未使用 IM TTL 缓存，reservation/usage/apply 仍留原执行 runtime。
- 依赖边界：Node 通过 integration/client 接入；无 DSH private import/fork、新 Agent loop 或额外 HTTP runtime。新实现未触及 UI。
- 复用实施记录的窄验证，并读取对应日志结尾：IM 5 files/78 tests，inspector 1 file/5 tests，native-presets 2 files/6 tests，model-regression 2 files/5 tests 均通过。没有重跑 caller 正在执行的全量 CI、100 次、soak 或迁移副本。

## Agent Context — Implementation Review

- mode: `agent-context-review` Mode B，同一固定 head；触发原因是能力目录、配置校验和 prompt preview 的来源/时序改为独立临时 runtime。
- surface/consumer：用户配置选择产生的后续 tools/Skills/native assembled prompt；检查 config 的显式 Skill roots/共享和 workspace extensions、personal trust、Feature、fixed tools 与同名覆盖，未发现可确认的 Context 内容缺陷。
- 实际装配 seam：读取 `capabilities.test.ts` 中真实 `configuration.preview` 的工具/Skill结果及 `session.capabilities` 的 assembled prompt；读取 `personal-security.test.ts:62-116` 的 Global/PA native catalog、Skill 正文、真实工具 dispatch 和 session prompt；读取 `workspace-tools.test.ts` 的 workspace catalog/actual session tools/prompt。新代码在临时 projection 前等待 Nano composition readiness，并沿用原 catalog/assemble 和参数来源；未新增模型必填参数。
- 证据限制：现有已通过 fixture 证明若干确定性装配及白名单/Skill 选择；没有用一次成功外推全部保真。Global/PA/workspace prompt preview 与真实 assembly 的对应对照、prepare 对真实变更的完整同源证据，以及 design 指定的两层 generation 交错，尚待 caller 补验。它们记录为 verification 证据缺口，不推断模型必然误解，也不新增真实模型任务要求。
- 无模型自由选择/理解行为变更，本轮未调用真实 provider；静态 review 不冒充 provider 输入捕获或真实模型行为。

## Round 2 — targeted closure / patch（最终）

- finding_origin_head: `0812c67efe12174c429c372103fb8842891eed64`。
- executed_base / effective_base: `01c8e0b80`（本轮已同步的 main）；finding_origin_head 只描述旧 finding 来源，不充当 main base。
- validated_at / effective_through: `8e0f327c81a3e0e6543f8ef3f22cd2ab7768c00c`；后端源码固定于 `bf0cdfdc32df872c9c40a0461c8284652d142d2f`，修复提交 `372654f60`。
- fix_delta_range: `0812c67ef..bf0cdfdc3`；`bf0cdfdc3..8e0f327c8` 只有证据、产品报告及 lease 字段精确化，没有源码变化。最新 main 仍 `01c8e0b80`。
- verdict: **Approved — 0 存活 finding**；不代表远端 CI 已执行。
- scope: F1/F2、对应进程 owner 修复、新增 preview 保真断言、workspace mutation notification delta，以及 final main sync 对本 unit 的影响。
- retained_from: Round 1 的 IM cache/scope/鉴权/snapshot fence、Node/RPC/Channels 取消语义、所有 preview/prepare 调用者与公开依赖边界。`0812c67ef..bf0cdfdc3` 未更改 IM/Channels/PA 产品代码；main 新增仅 bugfix-681 当前计划前端与文档，不与本 unit 后端交叉，未把 main 自带 UI diff 归为本 unit 越界。
- design lease 字段澄清只把现有 pid/随机 inspection_id 与 `pgid=pid` 写准确，不引入新机制；本 reviewer 未修改该文档。最终证据及独立产品报告已在上述 effective_through 可达。

### Findings

```json
[]
```

### Focus findings

- **F1 — closed。** `apps/node/src/main.ts:51` 捕获并记录 inspector 初始化错误，随后继续 durable Node 装配；inspector 的 cleanup_error 仍令 inspect 拒绝。实际 daily Node 的 `/tmp/refactor-682-startup.json` 与对应脚本证明：identity mismatch 时 node online、settings ready=false/read_failed、cron section current、未知进程/目录保留；不是仅以 catch 源码宣称聊天层已启动。未发送模型消息，不能外推模型回复行为。
- **F2 — closed。** `configuration-inspector.ts:243-271` 不再以 leader exit 提前返回；对当前拥有的进程组 TERM→宽限→KILL，等待 leader 与无活组成员后才删 home/释放名额。recover 在有标记 leader 时清整个组；leader 已死但 group 仍活且身份无法确认时保留并报 cleanup_error。新增真实 native `reclaims a plugin child that ignores SIGTERM even after its worker leader exits` 保护原探针失败原因。进程组 zombie 排除反映无活执行资源，不掩盖活 child。

### Context / 关联 delta

- ordinary selected tools/Skills preview 对实际 assembly；Global/PA preview tools/Skills、主人指导及 PA section 正文对照；workspace 插件 prompt contribution 和工具集对实际 session assembly，均已加入原 native fixture。未新增模型输入参数、Prompt 指令或权限旁路。
- workspace watch/初次 mount 仍重建本地 selection，但只在实际 native plugin mutation 完成时推进 generation，避免重复 watch 自行取消新检查。外部文件变化继续受既定五分钟 TTL 约束。
- `/tmp/refactor-682-race.mjs` 与结果证明 real reverse prepare + shared inspector + native plugin mutation + real IM CatalogReads 的两层交错：旧 prepare/read 拒绝、新 worker ID、禁用工具不出现、只接受新 snapshot fence、active=0/目录空。该探针没有 HTTP/relay，未把组合 seam 证据描述为真实 HTTP 验收；既有鉴权/relay 测试与独立产品验收承担这些边界。
- `/tmp/refactor-682-fidelity-r3.log` 实际为 workspace 主旅程筛选的 1 file / 1 test passed；最终后端 153-file suite 包含全部新增保真断言，失败只在未修改的 agent-disable-native / task-execution-limits 两项。更早 `/tmp/refactor-682-fix-tests.log` 为 2 failed / 18 passed 的局部通过，未当作整轮通过。
- 本轮没有重复运行全量/性能负载。最终 100 次实际重建全成功、每轮 home 空、active=0；1800.065 秒 / 1001 HTTP 全成功，6 cold / 995 cache，p95 2324.085 / 12.951 ms，32 资源采样目录与持久 preview 全 0，FD 固定 Node39/IM20。读取 JSON 统计和 soak 脚本，正常每 600 秒 refresh token、按真实 captured_at 分类；未采用早期无效/短 preflight。
- 最终独立产品验收 pass：真实 inspection 同步阻塞后只读降级/其他分区与 Agent 可用/移除故障后恢复；断连、重连、正式 logout 后拒绝已撤销身份；配置保存/版本冲突和并发目录均通过。证据 `M1-catalog-lifecycle/acceptance.md` Round 2 与 `evidence/product-acceptance.json`。
- 最终后端全量为 838/840 passed（151/153 files），两个既有测试失败在源码不变时以两文件串行复验 8/8 passed。保留 PTY cleanup 与 45 秒等待原始失败，不宣称一次全量绿，也不把负载归因视作已证实。其他本地门禁及风险限制见 verification.md；归并/归档/Ready PR/远端 CI 仍由 caller 按工作流完成。
