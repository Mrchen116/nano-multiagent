# M1-fix: tasks

## 目标

修复 session JSONL 落点错误——会话文件落在进程 cwd 的 `.nano/sessions/`，正确位置是
`{workspace_root}/.nano/sessions/{session_id}.jsonl`（见 feat-330 design.md）。

## 退出标准

1. 新建 session 时，JSONL 落在 `{workspace_root}/.nano/sessions/{session_id}.jsonl`，
   workspace_root 取自该 session 创建时传入的值。
2. 不同 workspace_root 的 session 落到各自目录，不混在同一 flat 目录。
3. `load` / resume / append 仍可正常读写——**包括进程重启后**对上一进程写下的 session。
4. 两个产品（个人助手 + Coding CLI）均走同一修复路径。
5. 旧位置文件不迁移（Q3 澄清结论）。
6. 全部相关单测通过，无回归。

## 架构决策（Option C，owner 已拍定）：内核无状态，workspace_root 由调用方每次请求带上

**问题**：`JsonlSessionStore` 构造时定死单一 `data_dir`，bootstrap 把它写成进程 cwd 下的
`.nano`，导致所有 session 落入进程 cwd，与 feat-330 design.md 要求的
`{workspace_root}/.nano/sessions/` 不符。

**鸡蛋问题**：`load(session_id)` 时 workspace_root 写在 JSONL 首行，但读首行先要知道文件
在哪。feat-330 design.md 本身没解决这个窟窿（「文件位置」段写按 workspace_root 分目录，
但 `_resolve_path` 伪代码用扁平 `data_dir`、`load()`/`run()` 只传 session_id）。本 bugfix
补这个窟窿。

**决策**：内核不持有也不持久化 `session_id → workspace_root` 映射。需要定位 session 文件的
请求由调用方带上 `workspace_root`——gateway 和 CLI 本来就知道（PA 在 gateway 配置里有每个
agent 的 workspace_root；CLI 是自己的工作目录）。内核每次从入参拿。

**落地**：

1. `JsonlSessionStore` 的 `create` / `load` / `append` / `update_config` / `resolve_path` /
   `list_session_ids` / `find_session_by_metadata` 接收调用方传入的 `workspace_root`。
   路径仍是 `{workspace_root}/.nano/sessions/{session_id}.jsonl`。
2. 向后兼容：保留 `data_dir` 作为**可选默认 base**——传了 `workspace_root` 用它，否则回退
   `data_dir`。现有用 `data_dir=` 构造 store 的测试不用大改。
3. `SessionManager` 同步把 `workspace_root` 透传给 store；`load`/`append` 等加该参数。
4. `AgentRuntime.run()` 及 resume 路径接收 `workspace_root`，透传给 manager/store。
5. HTTP 请求模型加 `workspace_root` 字段：`SendMessageRequest`、`AppendMessageRequest`，
   以及 fork/compact/interrupt 等会 load session 的路由按需加。
6. `RunsRegistry.submit` 接收并透传 `workspace_root` 给 runtime。
7. 两端发送方带上：PA `kernel_api_client` + gateway、Coding CLI `client` 在 submit/append
   时带 `workspace_root`。
8. `find_session_by_metadata`（agent 工具找 subagent）：subagent JSONL 在父 session 的
   workspace_root 下，agent 工具运行时父 session 已加载，从 runtime 取父 workspace_root，
   作用域化扫描。
9. `list_session_ids`（`GET /v1/sessions` 列表）：探查确认**无产品调用方**（CLI/PA 都只用
   create + get-one + append + stream，不用 list）。内核无状态下无法跨 workspace 列举，
   作用域化为「按传入 workspace_root 列举」，HTTP 路由加 `workspace_root` 查询参数。

## 测试策略

- 纯后端改动，无前端。
- 单元测试：
  - workspace_root 落点正确、多 workspace 隔离
  - 跨进程重启：store A create+写 turn → 丢弃 A → 全新 store B →
    `load(session_id, workspace_root=...)` 读回成功
  - `data_dir` 默认 base 向后兼容
- HTTP 集成测试：`workspace_root` 字段经 submit/append 透传到正确落点。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 调研调用链 + 确认 scanning 操作可作用域化 | DONE |
| R2 | JsonlSessionStore + SessionManager 改「调用方传 workspace_root」 | DONE |
| R3 | AgentRuntime / RunsRegistry / HTTP 路由 / 两端 client 透传 + 文档 + fix.md 回填 | DONE |
