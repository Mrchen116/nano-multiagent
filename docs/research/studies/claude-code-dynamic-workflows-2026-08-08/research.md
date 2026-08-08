---
status: research-snapshot
recorded-at: 2026-08-08
nano-baseline: b95e19f152cf498ea05601df4f76a67c924dbfd5
upstream: claude-code-local-reconstruction
upstream-baseline: 0991eac5ccd518d6bd0486752f61a42f9ad68fa8
source-baseline: claude-code-local-reconstruction@0991eac5ccd518d6bd0486752f61a42f9ad68fa8; claude-code-cli@2.1.226
installed-claude-code: 2.1.226
binary-baseline: claude.exe@013a1cf17df5ff1dcc189d5d6fd3fdd5f097ddc3cd41aa9992e99805574febbe
current-landing: pending-review
current-owner: pending-adoption
---

# Claude Code Dynamic Workflows 证据记录

## 研究问题

本轮研究要回答的不是“Workflow 看起来能做什么”，而是：

1. 什么输入真正激活它，哪一层做选择？
2. 主模型、`Workflow` 工具、JavaScript runtime 和子 agent 如何分工？
3. 提示词分别位于哪里，哪些是固定指令，哪些是模型动态生成？
4. 并发、返回值、持久化、通知和 resume 的外部契约是什么？
5. 在本地开源代码缺少实现时，哪些部分仍能从 landing seam 和相邻组件中复用？
6. 要做到兼容复刻，哪些是已观察事实，哪些仍然只能推论？

## 证据边界

| 标签 | 含义 | 本轮用途 |
|---|---|---|
| 官方事实 | 2026-08-08 读取的一手产品文档 | public contract 与版本边界 |
| 源码观察 | 固定 commit 的本地开源重建仓 | 注册点、stub 与可复用相邻 primitive |
| 运行观察 | 可定位的 CLI transcript、proxy request、run state、journal | installed 2.1.226 实际输入输出 |
| 二进制观察 | 哈希固定的本机 installed package/binary | shipped 2.1.226 的内嵌实现调用链 |
| 推论 | 主证据与必要的二进制 escalation 共同约束下的实现解释 | 复刻蓝图；不冒充 vendor 内部实现 |

原始 LLM 请求、完整 system prompt 和本机日志不进入 Git；本文只记录 locator、必要短摘录和脱敏摘要。

## 官方来源

### O1. Dynamic Workflows

来源：[Claude Code Dynamic Workflows](https://code.claude.com/docs/en/workflows)，访问日期 2026-08-08。

支持的关键声明：

- Dynamic Workflows 从 Claude Code 2.1.154 起提供。Claude 先生成 JavaScript 编排程序，runtime 在后台执行；中间结果存在脚本变量中，而非依赖主会话逐轮记忆。
- 人工输入可以通过 `ultracode`、明确要求 workflow 或自然语言复杂任务触发。2.1.160 之前的关键词是 `workflow`。
- 自 2.1.210 起，关键词只对 typed human input 生效；`-p`、SDK 非人工 origin、schedule 和 webhook 不因关键词自动触发。
- 可保存的 workflow 位于项目 `.claude/workflows/` 或用户目录；脚本可接收 `args`。
- runtime 暴露 `agent`、`pipeline`、`parallel`、`phase`、`log`、`workflow`、`args`、`budget`，但脚本不能直接访问文件系统、shell、Node API 或 import。
- 默认最多并行 16 个 agent，总计最多 1000 个；文档建议从较小规模开始。
- `resumeFromRunId` 复用未变化的 agent 调用前缀；prompt 或 options 变化后从差异处继续执行。
- permission bypass/non-interactive 模式不在 workflow 中追加人工确认；子 agent 接受 edits 并继承允许列表。

### O2. Subagents

来源：[Claude Code subagents](https://code.claude.com/docs/en/sub-agents)，访问日期 2026-08-08。

支持的关键声明：普通 subagent 有独立 context、system prompt、tool access 和 permission scope，不继承主会话历史；其定义正文进入 system prompt。Workflow 子 agent 的具体 workflow addendum 则由本轮 trace 直接观察。

## 本地源码基线

路径：`/Users/czj/Repos/opensource-hub/claude-code`

```text
commit: 0991eac5ccd518d6bd0486752f61a42f9ad68fa8
commit date: 2026-05-29
working tree: dirty; all baseline claims read with git show HEAD:<path>
```

### 已存在的 landing seam

| 文件 | 观察 |
|---|---|
| `src/tools.ts` | `feature('WORKFLOW_SCRIPTS')` 为真时初始化 bundled workflows 并加载 Workflow tool；随后把它加入工具池。 |
| `src/constants/tools.ts` | 引入 workflow tool name，并把它列入 subagent 不允许递归调用的工具集合。 |
| `src/commands.ts` | 预留 workflow command 注册入口。 |
| `src/components/permissions/PermissionRequest.tsx` | 预留 workflow permission request UI。 |
| `src/tools/WorkflowTool/WorkflowTool.ts` | committed baseline 是生成 stub，`WorkflowTool = {}`。 |
| `src/tools/WorkflowTool/WorkflowPermissionRequest.ts` | committed baseline 是生成 stub。 |
| `src/tools/WorkflowTool/createWorkflowCommand.ts` | committed baseline 是生成 stub。 |
| `src/tools/WorkflowTool/constants.ts` | committed baseline 是空 tool-name stub。 |

这只能证明重建仓知道功能的接入位置，不能提供 JavaScript runtime、journal、cache 或工具契约的真实实现。

### 可复用的相邻 primitive

| 文件 | 可复用能力 |
|---|---|
| `src/tools/AgentTool/AgentTool.tsx` | agent 输入 schema、异步 agent task、普通/分叉 system prompt 选择与工具限制。 |
| `src/tools/AgentTool/runAgent.ts` | 使用同一个 `query()` 核心运行隔离子 agent，并装配子 prompt、messages 和 context。 |
| `src/query.ts` | 模型流式循环、tool use 捕获、结果回灌。 |
| `src/services/tools/StreamingToolExecutor.ts` | 可并发工具和 exclusive 工具的调度、顺序结果提交。 |

因此，兼容实现不必重新发明 agent loop；缺口主要是 workflow 专属的“脚本编译/执行 + durable state + task integration”。

## Installed package / 二进制静态取证

本节是后三条主证据仍留下“AST 解释还是直接执行 JS”这一实现歧义后追加的只读 escalation。没有修改、调试注入或重新签名二进制，也没有运行新的模型实验。

```text
installed_version: 2.1.226
package: @anthropic-ai/claude-code@2.1.226
binary_path: /opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe
file_format_arch: Mach-O 64-bit executable arm64
size: 279661952 bytes
sha256: 013a1cf17df5ff1dcc189d5d6fd3fdd5f097ddc3cd41aa9992e99805574febbe
signer: Developer ID Application: Anthropic PBC (Q6L2SF6YDW)
embedded_runtime: Bun 1.4.0 / JavaScriptCore
```

### 调用链观察

二进制包含 Bun 的通用 VM 能力，单凭 `node:vm` 字符串不能证明 Workflow 使用它。本轮进一步沿 Workflow 专属错误、schema 与 minified identifiers 恢复了完整调用链：

1. `pP(script)` 调用内嵌 Acorn 8.15.0，以 `sourceType: "module"`、允许 top-level await/return 的模式解析脚本；要求首条语句为 `export const meta`，并从 AST 只接受 pure-literal metadata。
2. `jBb(scriptBody)` 再次用 Acorn 解析包裹在 async IIFE 中的 body，拒绝 `with`、dynamic `import()` 和保留 identifier，并对 `await`、async return/yield、`for await` 的表达式位置做源码插桩。
3. `Fwt(scriptBody)` 先用 `Function("async function _check() {...}")` 做语法编译检查，再构造 `new vm.Script(transformedSource, { filename: "workflow.js", importModuleDynamically: throw })`。
4. `s$p(...)` 调用 `vm.createContext(..., { codeGeneration: { strings: false, wasm: false } })`，只把桥接后的 `agent`、`parallel`、`pipeline`、`workflow`、`phase`、`log`、`budget`、timer 与 JSON-cloned `args` 注入 context；同时替换 `Date.now`、`Math.random` 和无参 `new Date`。
5. `l$p(...)` 最终调用 `vmScript.runInContext(vmContext, { timeout: 30000 })`，再 await VM 返回的 Promise。Task schema 也把 local workflow 描述为 `in-process runs`。

所以准确结论是：**Claude Code 会使用 AST 做 metadata 提取、静态限制和异步边界插桩，但不会把整个 workflow 当作自定义 AST 逐节点解释；改写后的 JavaScript 由 Bun/JavaScriptCore 的 Node-compatible `vm.Script` 在隔离 context 中直接执行。**

### Resume key 的实现观察

二进制还恢复出 journal key：以版本前缀 `v2`，对“前一个 key + NUL + 当前 prompt + NUL + canonical options”做 SHA-256。Options 只选择影响行为的 `schema`、`model`、`effort`、`isolation`、`agentType`，对象 key 排序后 JSON 序列化。每次调用把当前 key 作为下一次的 previous key，因此天然形成最长相同调用前缀；`label` 和 `phase` 不进入该 options 集合。

这解释了官方 resume 语义，但 append-only journal 的 fsync/crash consistency 和跨版本迁移仍未从本轮静态阅读中建立。

## 运行实验

### E0. 成本校准后终止的并行实验

```text
claim: 主模型会生成含 parallel/agent/phase 的编排脚本，Workflow 调用异步返回
claude_version: 2.1.226
session_id: 25793ab4-824c-4287-979b-998ec53fe984
proxy_locator: /Users/czj/Repos/LLM_PROXY/logs/session/2026-08-08_17-56-17_226_25793ab4-824c-4287-979b-998ec53fe984/
transcript_locator: /Users/czj/.claude/projects/-Users-czj-Repos-nano-multiagent/25793ab4-824c-4287-979b-998ec53fe984.jsonl
status: deliberately stopped after launch to control cost
```

主请求使用 Sol，3 个 worker 使用 Terra。主模型生成两个 phase、三个 `parallel` worker 和一个 synthesis worker 的脚本；`Workflow` 立即返回 task/run/script/transcript locator。用户随后要求全部用 Luna，因此实验被主动停止。它只作为脚本形状与异步 launch 的辅助观察，不作为完整生命周期证据，也不再复跑。

### E1. Luna 最小完整生命周期

```text
claim: typed ultracode 请求会生成并异步执行单 agent workflow，完成后用 task notification 回到主会话
claude_version: 2.1.226
nano_commit: b95e19f152cf498ea05601df4f76a67c924dbfd5
working_tree: dirty; prompt explicitly prohibited file reads/writes
main_model: codexOAuth:gpt-5.6-luna
child_model: codexOAuth:gpt-5.6-luna
effort: low
session_id: 896b1c37-dec8-402f-9116-238c55377086
proxy_locator: /Users/czj/Repos/LLM_PROXY/logs/session/2026-08-08_17-59-46_353_896b1c37-dec8-402f-9116-238c55377086/
transcript_locator: /Users/czj/.claude/projects/-Users-czj-Repos-nano-multiagent/896b1c37-dec8-402f-9116-238c55377086.jsonl
run_state: /Users/czj/.claude/projects/-Users-czj-Repos-nano-multiagent/896b1c37-dec8-402f-9116-238c55377086/workflows/wf_be7ccbcb-d39.json
journal: /Users/czj/.claude/projects/-Users-czj-Repos-nano-multiagent/896b1c37-dec8-402f-9116-238c55377086/subagents/workflows/wf_be7ccbcb-d39/journal.jsonl
status: completed
```

人工终端输入：

```text
ultracode: 做一个最小成本的 workflow 生命周期实验。只启动 1 个 agent，不调用任何工具，只让它原样返回字符串 WORKFLOW_LIFECYCLE_OK；workflow 直接返回该字符串。不要读取或修改任何文件。
```

Transcript 把该消息记录为 `origin.kind = human`、`promptSource = typed`，随后追加 `workflow_keyword_request` attachment。主模型生成并调用：

```js
export const meta = {
  name: 'workflow-lifecycle-minimal',
  description: '验证最小 workflow 生命周期',
  phases: [{ title: 'Lifecycle', detail: '启动单个 agent 并返回固定字符串' }],
}

phase('Lifecycle')
const result = await agent(
  '不要调用任何工具。只原样返回字符串 WORKFLOW_LIFECYCLE_OK。',
  { model: 'sonnet', phase: 'Lifecycle', label: 'single-agent' },
)
return result
```

关键观察：

- `Workflow` 的 tool result 是 `async_launched`，包含 task ID `wtcw4djow`、run ID `wf_be7ccbcb-d39`、script path 与 transcript dir；主模型没有同步等待 worker。
- environment override 优先于脚本里的 `{ model: 'sonnet' }`：实际子请求与 run state 都是 `codexOAuth:gpt-5.6-luna`。
- journal 顺序为一个 `started` 和一个 `result`；最终值为 `WORKFLOW_LIFECYCLE_OK`。
- 完成后进入主会话的是 origin 为 `task-notification` 的合成 user message，携带 result、diagnostics、usage 和重新执行方式；主模型再输出最终结果。
- worker 请求带 `cc_is_subagent=true`，独立 system prompt，24 个可用工具。任务虽然没有调用工具，工具 schema 仍进入 context。
- worker 固定 addendum 的关键短句是：`Your final text response is returned verbatim as a string to the calling script`。这使子 agent 的 final text 成为脚本值，而不是直接对用户说的话。

成本和时延：

| 指标 | 结果 |
|---|---:|
| 主模型首次 Workflow 调用输入 | 30,712 tokens |
| workflow 子 agent | 20,304 tokens |
| 子 agent tool calls | 0 |
| workflow runtime duration | 2,888 ms |
| agent count | 1 |

即使“一个 agent、不调用工具”，固定 system、tool schemas、skill/repository attachments 仍然产生约 20K 子 agent 输入。因此后续实验默认 Luna、low effort、单变量，并把扩容视为需证明必要性的成本。

实验中既有仓库 hook 在 worker 启动时报告一次非阻塞 JSON 解析错误，但 workflow 仍完成；它不影响本轮生命周期结论，也不能用来推断 Workflow 自身错误处理。

## 逐项证据矩阵

| 声明 | 官方 | 源码 | 运行 | 二进制 | 结论 |
|---|---:|---:|---:|---:|---|
| typed `ultracode` 产生 workflow opt-in | 是 | gate seam | E1 | input/tool call site | 高置信事实 |
| 主模型负责把自然语言编译为 JS | 是 | 未实现 | E0/E1 | tool schema/compiler | 高置信事实 |
| tool launch 与 workflow execution 分离 | 文档称后台 | Task/Agent primitive | E0/E1 | local task launch | 高置信事实 |
| 子 agent final text 是脚本返回值 | 间接 | Agent primitive | E1 system + journal | child runner | 高置信事实 |
| 中间数据在脚本变量中组合 | 是 | 未实现 | E0/E1 script | VM context | 高置信事实 |
| runtime 以 durable run/journal 支持通知与 resume | 是 | 未实现 | E1 | task/journal code | 高置信事实 |
| cache key 是 chained SHA-256 调用前缀 | 仅前缀语义 | 未实现 | 未测试 | call site recovered | 高置信实现观察 |
| runtime 使用 AST 辅助的直接 JS VM 执行 | 未披露 | 未实现 | trace 不可判定 | Acorn → vm.Script → runInContext | 高置信实现观察 |
| permission UI 内部状态机 | 部分公开 | 只有 seam | bypass 模式未覆盖 | 仅 permission dialog seam | 仍不完整 |

## 已排除的错误理解

1. **不是“主模型多轮手工调 Agent tool”**：主模型只生成脚本并发起一次 `Workflow`，调度循环发生在独立 runtime。
2. **不是“把完整子结果都塞回主会话再继续规划”**：脚本变量承接结果，主会话收到 launch 和最终 notification；这正是它能扩展到大量 agent 的关键。
3. **不是“纯确定性 DAG”**：图结构由主模型动态生成，节点本身仍是非确定性的 LLM agent；确定性主要属于脚本控制流、journal 和相同调用的 resume cache。
4. **不是“开源重建仓已经有完整实现”**：固定 commit 只有 gate、注册点和 stubs。
5. **不是“写了 ultracode 就一定在任何入口触发”**：当前官方契约限制为 typed human origin；E1 也观察到了 origin/attachment 区分。
6. **不是“用 AST 自己解释整个 JavaScript”**：AST 负责 metadata、限制和插桩；真正执行发生在 `vm.Script.runInContext()`。

## 仍需实验的未知项

只有在实现决策真正依赖时才继续：

| 未知 | 最小后续实验 |
|---|---|
| `parallel` 的结果顺序与单节点错误转 `null` | Luna/Luna 两节点，一快一慢，其中一个按指令失败 |
| `pipeline` 是否逐 item 流水而非全局 stage barrier | Luna/Luna 两 item 两 stage，用 journal 时间戳区分 |
| resume 的精确前缀边界 | 完成两个 trivial agents，修改第二个 prompt 后用同 run ID 恢复 |
| normal permission 下首次 agent edit 的 approval 归属 | 临时仓、一个受控文件、用户明确授权后实验 |
| 取消与重启后的 durable 行为 | 一个受控等待任务，启动后取消并检查 state/journal |

这些实验都不需要更高模型档位；默认仍是 Luna。
