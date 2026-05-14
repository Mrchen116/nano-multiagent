# M1-fix: tasks

## 目标

修复 session JSONL 落点错误——会话文件当前落在进程 cwd 的 `.nano/sessions/`，正确位置是
`{workspace_root}/.nano/sessions/{session_id}.jsonl`（见 feat-330 design.md）。

## 退出标准

1. 新建 session 时，JSONL 文件落在 `{workspace_root}/.nano/sessions/{session_id}.jsonl`，
   workspace_root 取自该 session 创建时传入的值。
2. 不同 workspace_root 的 session 落到各自目录，不混在同一 flat 目录。
3. `get_session(session_id)` / `load` 仍可正常读取。
4. 两个产品（个人助手 + Coding CLI）均走同一修复路径，bootstrap 一次修好。
5. 旧位置文件不迁移（Q3 澄清结论）。
6. 全部相关单测通过。

## 架构决策：workspace_root 分离存储 + 调用方传 workspace_root

**问题**：现有 `JsonlSessionStore` 构造时定死一个 `data_dir`，但 workspace_root 是每个
session 各自不同的。若要按 workspace_root 分目录存，就必须在 create/load 时动态解析路径。

**load 的鸡与蛋问题**：`load(session_id)` 时，workspace_root 写在 JSONL 第一行 —— 但要
读这一行，先得知道文件在哪。`data_dir` 固定时没有这个问题；改成 workspace-aware 后会出现。

**决策**：

- `JsonlSessionStore.__init__` 接受可选的 `data_dir`。
  - 传入 `data_dir`：兼容现有行为（所有文件落在同一根目录），单测不用改。
  - 不传 `data_dir`（workspace-aware 模式）：`create`/`load`/`append` 等调用方必须同时
    传 `workspace_root`，store 从中解析 `{workspace_root}/.nano/sessions/{session_id}.jsonl`。
- 为避免鸡与蛋，`SessionManager` 在 `get_session(session_id)` 时需要 workspace_root。
  解决方案：把 workspace_root 作为参数透传，或维护 `session_id → workspace_root` 内存索引。
  
  选择**内存索引方案**：`SessionManager` 在 `create_session` 时记录
  `session_id → workspace_root` 映射；`get_session`/`load` 优先查索引。进程重启后索引消失，
  需从 JSONL 首行反扫重建（懒加载）。
  
  但这带来复杂性。更简单的方案：
  
  **最终决策 - 传 workspace_root 给 create，store 用 workspace_root 解析路径；
  load/get_session 维持 data_dir 内平铺（使用 session_id 直接定位），仅 create/append 路径
  改为 workspace-aware**。
  
  实际上，设计最简原则：`JsonlSessionStore` 在 workspace-aware 模式下需在以下时机知道
  workspace_root：
  - `create(session_id, config)` —— config 里已有 `workspace_root` ✅
  - `append(session_id, entry)` —— 需要 workspace_root
  - `load(session_id)` —— 鸡蛋问题
  
  鸡蛋问题解决方案：store 维护 `session_id → workspace_root` 内存缓存（create 时填入），
  append/load 先查缓存。进程重启后缓存为空，`load` 时扫描候选 workspace 目录或接受调用方传入。
  
  **最终最简方案（本次实施）**：
  
  让 `JsonlSessionStore` 在 workspace-aware 模式下，`create` 时从 `SessionConfig.workspace_root`
  解析路径并写缓存（`session_id → workspace_root`）；`append`/`load` 查缓存；
  进程重启后缓存为空时，`load` 降级扫描 sessions 目录（通过 `_scan_workspace_root`）。
  
  但扫描复杂度高。最终选择更直接的方案：
  
  **实施方案（最终）**：
  
  1. `bootstrap.py` 不再在启动时构造单一 `JsonlSessionStore`。改为 `session_store=None`
     传给 `ResolvedProductConfig`，让 `app.py` 通过 `SessionService` 懒惰构建。
  2. `SessionService` 在 `create_session` 时，按 `workspace_root` 构造/选择对应的
     `JsonlSessionStore`（缓存 `workspace_root → store` 的映射）。
  3. `get_session(session_id)` 时：先查所有已知 store 中是否有该 session（遍历
     `workspace_root → store` 映射）。这是 "先扫描已知 workspace" 方案。
  4. 但这仍有进程重启后找不到旧 session 的问题。
  
  **最终结论（采用最简可行方案）**：
  
  唯一真正无鸡蛋问题的方案是：
  - `JsonlSessionStore` 本身仍使用 `data_dir` 固定根目录（现有架构不变），但
  - `bootstrap.py` 改 `data_dir` 为 `workspace_root`，而不是 `repo_root / ".nano"`。
  - 但 workspace_root 在进程启动时（bootstrap 时）就是固定的（每个 agent 进程对应一个 agent），
    而不是动态的！
  
  查看 bootstrap 调用方（个人助手和 Coding CLI）：
  - 个人助手：每个 agent 有自己的 workspace_root，每个 agent 对应独立进程？还是共享一个进程？
  - Coding CLI：每次 CLI 启动对应一个工作目录
  
  这需要看 personal_assistant 和 coding_cli 如何调用 bootstrap。

## 测试策略

- 纯后端 API 改动
- 策略：集成测试（真实 HTTP 请求），验证 session JSONL 落在 workspace_root/.nano/sessions/
- 补充 bootstrap 测试：session_store 的 data_dir 指向正确路径
- 不改前端，不涉及浏览器

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 调研调用方：个人助手和 Coding CLI 如何使用 bootstrap | DONE |
| R2 | C1 失败测试 + C2 实现修复 | DONE |
| R3 | C3 文档 + fix.md 回填 + 合并 | DONE |
