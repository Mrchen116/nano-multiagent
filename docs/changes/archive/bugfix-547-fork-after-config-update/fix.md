# bugfix-547: Agent 配置更新后旧会话无法直接 fork

## Relations

- Related: feat-445, refactor-463, bugfix-471
- Closes: #288

## 原始报告

> 这是为啥
>
> 见 `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-d6ebed2d-9a06-455e-a610-3d6f37541a25.png`

> 是改了配置，改了配置就无法fork了吗

> 按现有配置切换机制，在原会话先发一条新消息、让它完整采用 v2 后，再 fork 应该能恢复。确实，为啥啊，这合理吗

关联报告：https://github.com/Mrchen116/nano-multiagent/issues/288

## 澄清记录

- Q1: 从旧配置 v1 产生的回复 fork 后，分支第一次继续聊天应该使用哪版配置？
  A(原话): v2
  Agent 解读: fork 复制截至目标回复的对话历史，但新分支第一次继续聊天采用 Agent 当前已保存的完整配置 v2，不冻结旧配置 v1。
- Q2: 如果 Agent 配置确实在 fork 执行途中再次变化，用户应该得到什么结果？
  A(原话): ok
  Agent 解读: 用户同意推荐语义：本次 fork 原子失败且不留下分支，明确提示 Agent 配置刚刚更新、请重试；重试时采用最新配置。
- Q3: 这个修复应覆盖哪些 Agent 配置变化？
  A(原话): ok，当然
  Agent 解读: 覆盖所有影响后续运行的完整配置，包括模型、推理强度、Custom Instructions、skills、tools 和 features，不只处理本次截图涉及的某一个字段。

## 现象 / 复现

### 观察到的故障

Web IM 用户在单聊中已有 Agent 使用配置 v1 生成的完成回复。用户将该 Agent 任一运行配置保存为 v2 后，如果没有先在原会话开始并完成一轮新交流，直接从已有 Agent 回复 fork，会看到发送失败：

```text
forkConversation failed: 502 {"detail":"agent config changed while session fork was running"}
```

fork 不会留下孤儿分支，原会话也没有数据损坏；但用户无法执行本应合法的分支操作。只有先发送一条可能没有业务意义的新消息、等待 Agent 用 v2 完成回复后，fork 才恢复成功。

本次在 `codex/feat-546` 的 `d7429f4fd` 隔离运行环境中观察到：IM 的 Agent profile 已是 v2，源会话仍记录已应用 v1；同一 fork 请求返回 502。用户随后确认，先让原会话完成一轮新回复后再 fork 确实成功。

### 稳定复现

1. 在 Web IM 与某个在线 Agent 的单聊中，用配置 v1 完成至少一轮对话。
2. 修改并成功保存该 Agent 任一影响后续运行的配置，使当前完整配置成为 v2。
3. 不在原会话发送新消息。
4. 对原会话里任一支持 fork 的已完成 Agent 回复执行 fork。
5. 操作返回上述 502，页面不进入新分支，会话列表不新增分支单聊。
6. 在原会话发送一条消息并等待 Agent 完成回复，再执行同一 fork；操作恢复成功。

受影响的是所有共享同一完整运行配置版本语义的修改：模型、推理强度、Custom Instructions、skills、tools 与 features。纯展示信息不改变后续运行配置，不在本单范围内。

### 目标状态

- 配置 v2 已在 fork 开始前稳定保存时，用户可直接从 v1 历史回复创建分支，无需先发送占位消息；分支保留截至 fork 点的历史，第一次继续聊天采用当前完整配置 v2。
- 若配置确实在 fork 执行期间再次变化，本次操作原子失败、不留下分支，并明确提示配置刚刚更新、请重试；重试采用最新稳定配置。
- fork 的既有可用范围不扩大：仍只处理单聊中支持 fork 的已完成 Agent 回复，Agent 离线等既有失败边界保持不变。

## 根因

### 直接原因

Gateway 同时维护 Agent 当前配置快照和每个会话绑定对应的配置来源快照。源会话在 v1 下形成后，配置同步把 Agent 当前快照发布为 v2，但按现行配置连续性设计保留原 Kernel Session 与 durable binding，等待该会话下一轮新交流时再整体采用 v2。因此，在下一轮发生前，会话绑定的内存来源快照仍可能是 v1。

fork handler 从源 binding 捕获这份 v1 来源快照，按指定消息完成 Kernel 历史复制；随后用同一 v1 快照为目标分支提交 semantic binding。`bind_conversation()` 要求写回时的快照仍是 Agent catalog 当前版本，而当前版本已经是 v2，于是把这一笔“配置早已稳定更新、旧会话尚未开始下一轮”的正常操作判成 stale，返回 `agent config changed while session fork was running`。IM 再按既有原子性契约回滚已创建的空分支并向浏览器返回 502。

用户先在原会话发送一条消息之所以能绕过问题，是因为新一轮准入会读取当前 v2、在同一个 Kernel Session 上整体替换运行配置，并把会话来源快照更新为 v2。之后 fork 捕获到 v2，恰好满足现有写回守卫；这条占位消息并不是 fork 产品语义的一部分。

### 原始设计意图与回归引入点

- `feat-445` 建立 message fork：分支复制源会话截至消息 M 的上下文快照并立即成为可继续聊天的独立单聊；源会话不受影响，任一步失败都回滚，不能留下只有展示历史而没有 Agent 记忆的空壳。历史快照语义不等于冻结 Agent 此后的运行配置。
- `refactor-463` 在提交 `1d090718d` 中为 session fork 增加跨 `kernel.fork_session()` await 的 revision/generation guard。其原意是：如果配置真的在 fork 运行期间发布，旧快照不能落成新的 durable target binding，失败进入 IM 原子回滚。这个真正的竞态保护必须保留。
- `bugfix-471` 要求配置变化后不重建或删除既有会话，而是在下一轮准入时对同一 Session 采用最新完整配置并保留 transcript。实现提交 `190ba1dab` 因此从 `_republish_agent()` 移除了 `session_binder.invalidate_stale()`，改为只发布新 catalog snapshot。该变更正确保住了会话连续性，却没有同步调整 fork 对“源历史快照”和“目标分支当前配置”的处理，遂使旧来源快照持续到下一轮，并触发 `refactor-463` 的 stale 守卫。

### 为什么现有门禁没有拦住

现有 fork 测试覆盖了“配置在 `kernel.fork_session()` await 期间发布”并期望 stale 失败，也覆盖了 fork 捕获来源与 revision 的原子性；配置同步测试则覆盖“profile refresh 后保留旧 session binding”。两组测试分别守住了竞态安全和会话连续性，但没有组合覆盖：**v1 已绑定会话 → 配置在 fork 前稳定发布为 v2 → 不开始新一轮 → 直接 fork 历史回复**。因此，两个单独正确的行为组合成用户不可用路径后仍能通过门禁。

修复必须同时保住三项不变量：fork 历史精确到目标回复且原会话不变；分支下一轮采用当前完整配置而不混用新旧字段；真正发生在 fork 期间的配置竞态仍不得提交 stale binding 或留下孤儿分支。

## 修复

- `GatewaySessionBinder.capture_binding_provenance()` 在 fork 操作开始时先捕获 Agent catalog 的当前快照，再读取源 binding。源 Kernel Session 仍只提供截至 fork 点的历史；目标分支则使用 fork 开始时已经稳定发布的当前配置建立 provenance 和写回 guard。
- 若配置在这次捕获之后、目标 binding 提交之前再次发布，现有 revision guard 继续拒绝写回；错误增加 `please retry`，IM 沿既有事务路径回滚临时分支。
- current IM spec 补充“配置已更新但源会话尚未开始新一轮时可直接 fork”和“fork 途中再次更新则原子失败”的场景。

## 验证

- Red：新增 `test_fork_uses_config_published_before_operation_without_source_turn`，修复前稳定得到 `ok=False`。
- Green：`tests/unit/personal_assistant/test_session_fork_handler.py`，7 passed。
- 并发回归：session fork、binder 与 binder concurrency 聚焦集，18 passed；既有两类真实 mid-fork publication 均继续失败且不落目标 binding。
- 黑盒产品旅程：真实隔离 IM + Gateway 进程、recording LLM stub 下执行“旧配置回复 → 保存新配置 → 不发源会话占位消息 → fork → 分支首条消息”，1 passed；上游请求同时包含 fork 前历史和分支新消息，并使用新 Custom Instructions 与新 tool allowlist。
- 完整 Python CI 分片：Agent + PA 1772 passed；其余 1814 passed。
- 前端 CI：`npm ci`、`npm audit --audit-level=critical` 通过（无 critical）；Vitest 71 files / 689 tests passed。
- 静态门禁：`scripts/docs_check.py`、`ruff check .`、`ruff format --check .`、`git diff --check` 均通过。
- `change-code-review`：full finder 与独立 verifier 均无存活 finding；verifier 另外确认 fork 后首次准入会在 submit 前把继承的 v1 runtime 整体重配为当前配置。
