# 默认 E2E 配置修复

2026-10-19，用户在 617 的旁支讨论中明确要求：“本需求内顺便修了配置问题吧，而且不应该都是单thread的，应该包含global的agent”。修改位于同一 `unit/feat-617` worktree，纳入该需求交付。

## 原因与范围

默认 `config/e2e/gateway.yaml` 原先省略工具名单与 work mode。Node 原始配置运行时将未定义名单视为不限制，但 `canonicalAgentConfiguration` 将其投影成空数组；Skills 迁移等配置写回经过 canonical 配置后，就会持久化为空工具集。新增回归在旧模板上实际得到 `[]` 并失败。

修复限定为仓库默认 E2E 预设：显式写出文件、命令、搜索、Skill 和消息工具，Skills 使用空 `explicit_denylist`。保留 `e2e`、`e2e-peer` 为普通模式，新增 `e2e-global`；既有双普通 Agent 审批测试继续适用，默认环境同时覆盖 Global。没有更改产品里显式空工具集表示禁用的权限语义，也没有改写所有历史本机配置。

相关文件：默认配置、`apps/node/tests/configuration.test.ts`、既有 worktree 启停 E2E 的预设身份断言、`docs/development/worktree-runtime.md`。

## 验证

- `pnpm exec vitest run apps/node/tests/configuration.test.ts -t 'keeps E2E preset'`：修改模板前失败，实际同步后工具名单为 `[]`。
- `pnpm exec vitest run apps/node/tests/configuration.test.ts`：修复后 9 tests passed，覆盖真实模板读取、canonical 配置持久化、重载工具名单不变及两种工作模式。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/e2e/test_worktree_stack_lifecycle_e2e.py::test_worktree_stack_isolates_runtime_and_releases_owned_resources -q`：1 passed in 36.70s。使用独立 pytest 临时目录，经过真实 IM/Node 启动、注册、动态 Agent 创建和清理。
- 本次四个修改文件 `git diff --check` 通过。

未重启、修改或清空主线程已运行的 617 环境；未触碰 616。自定义 `--main-config` 仍使用调用者自己的预设。已有 Agent 的 work mode 不可原地修改；在已启动环境补 Global 应新增 Agent 身份，不能把已注册的 `e2e-peer` 改成 Global。真实模型的交互 UI 验收由 617 主线程继续完成。
