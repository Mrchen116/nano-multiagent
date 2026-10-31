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
