# Code Review: bugfix-646-task-continuation

## Round 1 — full

- 独立 reviewer：`/root/static_review_646`，未参与实现；使用 `change-code-review`。
- 固定范围：`e7f8249d26287dbaccde298365323c70e3cd5fc8..6223412809e5bdb98a741402d913e33589d686bc`，完整 20 文件 diff；开始时工作树干净。
- 完成时间：2026-10-23 23:28 +08。完整读取 Task driver、IM 事务/receipt、PA snapshot/调用包装、工具 schema、提示生成源与产物、Codex 审核及相关测试；核对 incident、design、两份 delta 和架构/测试契约。
- 复用 `implementation.md:9-11` 的红绿测试与构建/typecheck 证据；未重复全量 CI，真实产品旅程由独立 reviewer 执行。未把尚未提供的 CI/产品结果当作代码缺陷。

## Findings

```json
[
  {
    "file": "packages/dsh-integration/src/task-execution.ts",
    "line": 121,
    "summary": "[P2] 依赖操作拒绝时应只阻挡可定位的关联责任",
    "failure_scenario": "同图有本人 doing A、B、C，A/B 的 add_dependency 或 remove_dependency 被拒。真实 task_graph schema 和 IM applyOperations 使用 from/to，但此处只读 node_id/container_id/scope_id，得到空 ids 后把该图所有 doing 任务都记入 denied，包括独立 C。runnable 因所有任务 held 返回 false，C 也失去下一轮自动推进，直到责任变化或新输入；违背 design.md:46 的其余 doing 继续。应识别依赖端点并保留与该操作无关的责任可执行性，增加同图独立 C 的拒绝回归。最小驱动 seam 复现输出 held=[g/A,g/B,g/C], automaticAdmitted=0。",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "packages/dsh-integration/src/task-execution.ts",
    "line": 122,
    "summary": "[P2] 子树操作无法匹配直接责任时仍需保留拒绝屏障",
    "failure_scenario": "本人只负责父节点 P 下的 doing 子任务 C，P 本身未进入责任快照。task_graph delete(node_id=P) 被拒后，这里只按 P 与直接责任 node_id 相等筛选，tasks 变空，因此不保存任何拒绝。下一次 idle poke 立即再次 admission 未变化的 C，而该轮可能再提出相同被拒的子树删除，重现本 unit 要停止的无效自动重复。IM delete 的真实语义会递归删除 P 的全部子树，不能把未命中直接责任解释成无关操作。应对能定位到图却无法在最小投影核实子树影响的情况保留适当作用范围的屏障，不凭空推断无影响；增加父节点不在责任清单的回归。最小驱动 seam 复现输出 held=[], automaticAdmitted=1。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## 独立复核证据与边界

2026-10-23 在固定实现上执行：

```sh
PATH=/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH pnpm exec tsx /tmp/nano-646-review-scope.mts
```

临时脚本直接 import 受审 `src/task-execution.ts`，以最小 Context 捕获构造器注册的 `tools/result` listener，设置完整 shown responsibility，再经该 listener 注入真实错误形状 `isError:true,error.info.name=NanoApprovalDenied`，随后调用真实 `poke`；不替换 `denied`、`heldTasks` 或 `runnable`。两例的 snapshot 和责任版本保持不变。输出：

```json
{"case":"dependency","held":["g/A","g/B","g/C"],"automaticAdmitted":0}
{"case":"delete-subtree","held":[],"automaticAdmitted":1}
```

依赖入参来自 `features/task-graph-schema.ts:97` 和 IM `task-graphs.ts:285-294`；删除子树语义来自 IM `task-graphs.ts:718-738`。复现确认 admission 计算缺陷，不声称模型在生产中已经重复删除或造成副作用；被拒动作仍需原审批，未发现由此绕审。

`policy/codex.ts:105` 的 effort 修订只在所选模型的声明能力内选择 low/default/首档，没有更换 provider/model、删证据、改变 verdict parser、失败分流或只读 reviewer 约束；生命周期参数回归有对应证据。此结论限于 CodexApproval。固定版本的默认 Nano `policy/classifier.ts:28` 仍硬编码 low（未在本次 diff 内），caller 已确认另补兼容性修订；本报告不把 Codex 测试外推为整条默认 Nano 产品链路通过。

上述两项条件均已直接复核，无待证实高风险候选。未启动服务、未改源码/测试/配置；仅新增本报告与 verification.md。
