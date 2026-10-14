# M1-fix 实施与运行证据

## 实施

独立 managed worktree：`/Users/czj/.codex/worktrees/task-graph-descriptions/nano-multiagent`；base `290652ada2bf5fafbd4ac9f27a1514680ff78ca9`。编号通过共享 Git common dir 的编号脚本分配为 602，与并行审批 unit 601 分离。

仅落地七处描述；第一版真实 fresh case 全部通过，没有后续文案迭代，也没有人工修正 Agent 参数。

## 真实 Agent 验证

调用 `scripts/e2e-up.sh --wt <本 worktree>` 启动真实隔离 IM + Node + DSH；IM 使用临时端口 55571。模型 `deepseek:deepseek-v4-flash`、High。每例创建独立 global Agent、主 Session、会话和 workspace；skills 显式空 allowlist，关闭 memory/skill 自维护，隔离 owner 的 self_evolution.enabled=false。不复用旧实玩的知识或失败记忆。

已知 classifier 故障通过本次 owner 配置的 `auto_mode.always_allow_tools: [task_graph, inbox, conversations]` 显式隔离，仅影响这次临时栈；没有改产品默认或 IM 真实权限/持久校验。send_message 继续走产品对绑定本人单聊的既有许可。此证据证明工具理解和持久化，不证明 classifier 已恢复。

用户提示只有自然目标和先后关系，没有 create/apply/change_note/@ 或工具参数教学：

| 用例 | Session | 图 ID | 实际结果 |
|---|---|---|---|
| 聚会：方案→人数→采购 | `429bae8c-b4ec-47c3-b703-dee46183a769` | `tg_bb6acdc3` | 28.36 秒；create+apply，0 错误；确定聚会方案→确认参加人数→采购物资。 |
| 读书会：主题→名单→材料 | `51719949-d691-442a-b1db-643d1510f074` | `tg_a8edf109` | 19.18 秒；create+apply，0 错误；定主题→确定到场名单→准备材料。 |
| 发布：审查→验证→发布 | `6219e8b8-5639-44c3-a542-2fbf95ba01f3` | `tg_39691068` | 14.12 秒；create+apply，0 错误；代码审查→发布包验证→发布。 |

每例 create 均未带 operations；apply 均传 change_note，并使用此前定义的 @client_ref 连边。直接读取隔离 SQLite 核实：各一张 revision 2 的图，根+三直属子节点、两条正确方向依赖。未仅依赖 Agent 自称成功。

本地原始证据在 `output/task-graph-descriptions/`：`live-agent-summary.json`、三份 `*-work.json`、三份 `*-graph.json`。实际 LLM_PROXY 日志按上述 session IDs 定位；提取后的 `*-wire-tool.json` 与 `wire-contract-summary.json` 核实三例实发请求均包含七处新文案，task system prompt 与原实玩原文一致。原始日志及 runtime 数据不提交。

## 聚焦验证

- `pnpm install --frozen-lockfile`、`pnpm build`：通过。
- Web 是独立 npm 项目；`pnpm --dir ... install` 未安装该非 workspace 的依赖，改用其正常入口 `npm ci --prefix src/IM/frontend` 与 `npm run build --prefix src/IM/frontend`：通过。没有因此改代码或锁文件。
- `pnpm exec vitest run packages/dsh-integration/tests/task-graph-permission.test.ts packages/dsh-integration/tests/capabilities.test.ts apps/im-server/tests/task-collaboration.test.ts`：3 文件、13 测试通过。
- `git diff --cached --check`、`PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check`：通过（247 个维护 Markdown source、64 条 required routes）。

## 原图增量与清理

同一聚会 Agent 收到自然更新：“聚会计划里，确认人数一步改成‘确认人数与饮食偏好’，保留原依赖关系；方案这一步已确定，标成完成。请更新已有记录，不要另建计划。”实际一次 apply 后 get 核对，0 错误，14.13 秒；仍是 `tg_bb6acdc3`、四节点、原依赖，revision 2→3，节点改名与方案 done 均已持久。证据：`live-update-summary.json`、`party-update-work.json`、`party-updated-graph.json`。

`scripts/e2e-down.sh` 成功停止自启栈；随后核对拥有的 IM/Node/DSH PID 均不存活、55571 无监听。删除脚本保留的临时 config/JWT/key/token/identity、owner/workspace/runtime/data 目录；保留 output 的已提取轨迹、工具请求和任务文档。清理记录：`output/task-graph-descriptions/cleanup.json`。

## 待收口

独立 full code review 已通过，findings `[]`；审查者核对了三例共 29 份实际模型请求、自然输入与图数据，详见 [code-review.md](../code-review.md)。2026-10-14 用户明确要求“把 #351 和 #352 转正式合并”，据此记录结果确认、归并 canonical 并归档；PR/CI 与合并由主会话完成，不补记真人亲手测试。
