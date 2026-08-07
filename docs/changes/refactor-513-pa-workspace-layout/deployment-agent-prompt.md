# refactor-513 首次生产部署 Agent Prompt

> 使用时机：refactor-513 已合入 `main`、所有实现测试与 E2E 已通过后，由部署 Agent 在现有两台机器上执行一次。
> 目标：把 PA 的 global home / default workspaces 与 workspace-managed 目录收敛到终态；**不**在产品运行时代码中添加迁移、fallback 或同步逻辑。

将以下内容完整交给有生产部署权限的 Agent：

---

你正在部署 `nano-multiagent` 的 `refactor-513-pa-workspace-layout`。执行一次、可中断、无覆盖的数据迁移，再按现有 fleet 流程启动服务。

## 生产拓扑与终态

- Mac mini（`ssh mini`）运行唯一 IM `:8011`、`mac-mini` Gateway、LLM_Bridge。
- 本机运行 `macbook-air` Gateway、LLM_PROXY；本机绝不能启动 IM `:8011`。
- PA global home：`~/.nanoassistant/`。
- PA 默认 Agent workspace：`~/.nanoassistant/workspaces/<agent-id>/`。
- PA workspace-managed 文件：`<workspace>/.nanoassistant/`。
- CLI workspace-managed 文件：`<workspace>/.nanocode/`。
- mini IM signing key：`~/.nanoassistant/im-jwt-secret`，内容不变、mode 必须 `0600`。

## 非协商约束

1. 不把 secret 输出、写入仓库、shell history、聊天回复或临时文件。
2. 不添加或依赖运行时旧路径 fallback、首次启动迁移或持续同步。
3. 同相对路径目标已经存在且内容不同：立即停止该项；两侧均不覆盖、不删除、不合并。记录冲突清单，等人处理。
4. 任何显式外部代码仓 workspace 不整体移动；只对确认归属 PA/CLI 的 workspace 做下面的 extension fork。
5. 旧 root `chat_history/` 与 `<workspace>/.nano/background-tasks/` 只随**整个默认 workspace**移动而保留相对位置；外部 workspace 的这些历史文件不移动。
6. 旧 `.nano` extension 只做一次“目标缺失才复制”，不覆盖、不删 source、之后不再同步。
7. Gateway config 必须遵守“先 stop，再编辑，再 start/restart”；运行中的 Gateway 会回写 config。
8. 除已确认监听 `:8011` 的 mini IM 外，不 kill PID；本机不允许存在 `:8011` listener。

## 执行步骤

### 0. 部署前盘点，先不写任何文件

1. 两机分别确认 `~/Repos/nano-multiagent` 的 checkout、branch、dirty files 与最终 refactor-513 commit；保留所有非本次 dirty/untracked 文件。
2. 读取两台 Gateway config，列出：
   - `node.workspace_base`（若显式）；
   - 每个 `agents[].workspace_root`；
   - 哪些是旧默认 root `~/nano-assistant/workspace/<agent-id>/`，哪些是外部 workspace。
3. 在 mini 识别 IM SQLite DB 的实际路径（通常为 repo 的 `data/im_service.sqlite3`），并在修改前建立可恢复备份；不要猜测或替换其他 DB。
4. 建立 migration manifest，逐项列出 source、target、产品归属（PA / CLI）、处理方式（move / copy-if-missing / retain）。不能确定某 workspace 的产品归属时停止并询问，不自行猜测。
5. 对所有将写入的 source/target 路径做内容冲突检查。目录合并必须逐文件比较；目标仅存在目录本身不构成冲突，**同名文件内容不同**才构成冲突。
6. 先报告 manifest、冲突结果、DB backup 路径与计划停机窗口。只有所有项目都“缺失或相同”时才继续写入。

### 1. mini secret 的 fail-closed 预检（IM 仍在运行）

在 mini 上检查 source `~/.nano-assistant/im-jwt-secret`：必须非空、mode `0600`。随后在**写入前**分类 target `~/.nanoassistant/im-jwt-secret`：

- target 缺失：可在以后复制 source；
- target 已存在且 byte-identical：保留 target，不覆盖；
- target 已存在且内容不同：立即停止整个迁移；两份文件均不修改。

成功分支才准备 target（缺失则私有方式复制），并再次验证 source 与 target byte-identical、target mode 为 `0600`。source 是恢复点，必须保留到新 IM 与两个 Gateway 都验证 online 后才可删除。不得生成或轮换密钥。

### 2. 停止服务

1. 先停止 mini Gateway 和本机 Gateway（使用各自的 Gateway `stop` 命令，不手杀 Gateway PID）。
2. 再在 mini 停止唯一 `:8011` listener；停止前已经完成 Step 1，且只杀 `lsof -tiTCP:8011 -sTCP:LISTEN` 识别出的 listener PID。
3. 记录停机前状态；如果无法确认 listener 或服务未真正停止，停止并报告，不继续迁移。

### 3. 迁移 global home 与默认 workspaces

在无冲突 manifest 的约束下：

1. 将旧 `~/.nano-assistant/` 的非-secret 内容合并至 `~/.nanoassistant/`。只写 target 缺失项或已确认 byte-identical 项；旧 source 先保留。
2. 将每个旧默认 workspace `~/nano-assistant/workspace/<agent-id>/` 整体迁至 `~/.nanoassistant/workspaces/<agent-id>/`。这样旧 root `chat_history/` 和 `.nano/background-tasks/` 保持相对 workspace root 的位置；不专门搬它们。
3. 不整体移动外部代码仓 workspace，也不移动其中旧 root `chat_history/` 或 `.nano/background-tasks/`。
4. 对 Gateway config 中的旧默认绝对路径更新为新默认绝对路径；显式外部 workspace 路径不改。若 `node.workspace_base` 指向旧默认 base，也一并更新。
5. 对 IM SQLite `agent_profiles.workspace_root` 只更新**恰好等于**旧默认 workspace 路径的记录；不要按宽泛前缀改写外部 workspace。完成后核对新旧行数、备份可恢复、外部路径未变。

### 4. 对每个已确认产品 workspace 做一次 extension fork

逐项处理 manifest 中每个 workspace：

| 产品 | 旧 source | target | 规则 |
|---|---|---|---|
| PA | `<workspace>/.nano/{tools,hooks,policy.toml}` | `<workspace>/.nanoassistant/` | target 缺失才复制；source 保留；不覆盖、不 merge、不再同步。 |
| CLI | `<workspace>/.nano/{tools,hooks,policy.toml}` | `<workspace>/.nanocode/` | target 缺失才复制；source 保留；不覆盖、不 merge、不再同步。 |
| PA | `<workspace>/HEARTBEAT.md` | `<workspace>/.nanoassistant/HEARTBEAT.md` | target 缺失才复制；source 保留。 |

不要为 CLI 创建 `chat_history` 或 `HEARTBEAT.md`。不要把 PA 的 extension 写到 `.nanocode`，也不要把 CLI 的 extension 写到 `.nanoassistant`。

### 5. 更新代码与从新路径启动

1. 在两机按正常受控流程更新到含 refactor-513 的目标 `main` commit；不要用 reset/clean 覆盖用户修改。若 frontend 改动需要构建，只在 mini 按既有流程构建。
2. 确认两台 Gateway 已使用新的 `~/.nanoassistant/config.yaml`，且各自的 `node_id`、`node.user_id`、IM URL、LLM/SearXNG 配置保持原有正确值。
3. 从 mini 的**新** secret path 读取 `IM_JWT_SECRET` 并启动唯一 IM `:8011`；不允许使用旧 path 或生成新值。
4. 等 IM HTTP 可用后，先启动 mini `mac-mini` Gateway，再启动本机 `macbook-air` Gateway；保持现有 `SEARXNG_URL` 与各机 LLM proxy 约束。

### 6. 必须通过的验证

1. 新 secret 非空、`0600`，且在删除旧 source 前仍与旧 secret byte-identical。
2. mini IM HTTP 正常；`GET /im/v1/nodes` 显示 `mac-mini` 和 `macbook-air` 均为 `online`。
3. 本机 `lsof -ti:8011` 为空。
4. 两边 Gateway 的 `node.user_id` 均等于 `GET /im/v1/me` 返回的真实 IM owner UUID；日志没有持续 `configured node owner differs`。
5. 新建未显式 workspace 的 PA Agent 落在 `~/.nanoassistant/workspaces/<agent-id>/`；IM 返回的 `workspace_is_default` 与此一致。
6. 用一个外部代码仓 PA workspace 完成真实聊天/RPC journey，确认新的 chat history、heartbeat、cron、background output 在 `.nanoassistant/`；再用 CLI 在代码仓确认 extensions、policy、background output 在 `.nanocode/`，且 CLI 没有 PA chat history/heartbeat。
7. 确认无新写入落到 root `chat_history/`、root `HEARTBEAT.md` 或旧产品目录；历史保留文件不应被误删。

### 7. 收尾与报告

只有 Step 6 全部通过后，才删除已成功迁入的旧 global/default roots 与旧 secret source。对于 external workspace 的 `.nano` extension source 和 root `HEARTBEAT.md`，按 Step 4 规则保留。任何冲突、验证失败或不确定路径均不删除 source。

最终报告必须包含：实际目标 commit、迁移 manifest 摘要、保留的冲突/历史文件、DB backup 路径、服务启动结果、两个节点 online 证据、验证结果与未做事项；绝不包含 secret 内容或 token。

---

维护者注：此 prompt 是本次两机的一次性部署操作书，不替代最终实现随 M2 更新的长期 production operations 文档与 `prod-fleet-deploy` skill；以终态代码与这份严格的无覆盖规则为准。
