# bugfix-348: session JSONL 未按 workspace_root 存储

## Relations

- Related: feat-330

## 原始报告

> 等下，commit了？那现在个人助手的聊天记录放在哪里？哪里的jsonl，我没看到

> 比如，我在 http://127.0.0.1:8011/chat/50e80bda7ac145219d46a4a4f6e2ed27 和"架构"Agent的沟通存在哪里

> 实现了就不用改这两个文档了。但是落进了仓库目录里的 .nano/ 和需求不一致吧

> 在main分支的worktree上开个bugfix吧，其实就是一个很小的改动，对吧？

> 照 design 改版

## 澄清记录

- Q1: 修复目标是"小修版"（让 session 落到产品固定 home，session 仍平铺在一个目录），还是"照 design 改版"（按 feat-330 design.md 的 `{workspace_root}/.nano/sessions/` 分目录存）？
  A: 照 design 改版 —— 按 design.md 的 `{workspace_root}/.nano/sessions/{session_id}.jsonl` 存。
- Q2: 影响范围只算个人助手，还是 Coding CLI 也算、修复一并覆盖？
  A: 一并覆盖。两个产品都受同一根因影响，修复同时覆盖个人助手和 Coding CLI。
- Q3: 已经落在旧位置（启动进程 cwd 的 `.nano/sessions/`）的 session 文件要不要迁移到新位置？
  A: 不迁移。修复只改"今后新建/写入的落点"，旧文件留在原地（feat-330 已定调"开发态不兼容旧数据"；IM 侧 SQLite 仍有完整聊天副本，丢的只是内核侧 resume 上下文）。

## 现象 / 复现

feat-330 给 agent 内核引入了 JSONL 会话存储，design.md 要求会话落在
`{workspace_root}/.nano/sessions/{session_id}.jsonl` —— 即每个会话的 JSONL 跟着它自己的
workspace 走。实际落地的行为不是这样：

- 会话 JSONL 落在**启动内核进程时的当前工作目录（cwd）下的 `.nano/sessions/`**，与
  会话自己的 `workspace_root` 无关。
- 复现（100% 必现）：在仓库目录下启动个人助手 Gateway → 和某个 agent（如"架构"）对话
  → 该会话的内核 JSONL 出现在 `<仓库目录>/.nano/sessions/sess_xxx.jsonl`（git 未跟踪的
  脏文件），而不是该 agent 的 workspace `~/nano-assistant/workspace/架构/.nano/sessions/` 下。
  Coding CLI 同理：会话落在"启动 CLI 时的 cwd"，而非 design 要求的 workspace 下。

后果：

1. 所有 agent、两个产品的会话平铺进同一个 cwd 相关目录，**无 workspace 隔离**。
2. 换个目录启动内核 → 之前的会话"找不到"（resume 不到，因为还在旧 cwd 的 `.nano/` 里）。
3. 污染代码仓库 —— 会话文件以未跟踪状态堆在仓库目录里。

不涉及数据损坏：写入的 JSONL 内容本身正确，只是落点错；IM 侧 SQLite 仍有完整聊天副本，
前端 `/chat` 页面读的是 IM 存储而非内核 JSONL。

## 根因

- 直接原因：`src/agent/platform/bootstrap.py` 构造内核 session store 时，把存储根目录写死成
  「内核进程 cwd」下的 `.nano/` —— 用的是 bootstrap 的 `repo_root` 入参，和会话的
  `workspace_root` 完全无关。`src/agent/platform/persistence/session/service.py` 的
  `_resolve_data_dir()` 同样只返回 cwd 相对的 `.nano/`：它的 docstring 甚至声明了"优先级 2：
  按 Profile 的 global_config_home 解析"，但代码体里根本没实现这一分支 —— 实现连自己
  docstring 声明的意图都没写完。
- 为什么这种错能进来：feat-330 design.md 写的是按 `workspace_root` 分目录存，但 session store
  的存储根目录是**进程启动时一次性定死的单一目录**，而 `workspace_root` 是**每个会话各自不同**
  的。存储层的接口形态（构造时定死一个根目录）和 design 意图（按每个会话的 workspace 解析路径）
  从一开始就不对齐。feat-330 落地时没人拿 design 的存储路径做对照验证；PR review 也没卡住 ——
  因为 feat-330 的验收标准里没有把"会话存储位置"列成可验项（当时被当成实现细节），这条偏差
  就直接溜过了。

## 修复

<!-- 改了什么 + commits。 -->

## 验证

<!-- 修前能复现 → 修后不能；相关功能回归正常。 -->
