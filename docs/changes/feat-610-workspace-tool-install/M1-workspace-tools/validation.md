# M1 validation

- implementation tree: `33ef0d76d342a10c411ccbc0828f82d0d564e810`
- executed_base: `9182699fca58d42fbf166f3de7445c635dcb3527`

## 回归保护与处置

既有 `packages/dsh-integration/tests/capabilities.test.ts` 保留：静态两层扩展、显式空集、配置热变更与 PTC 执行限制仍适用。新增 `workspace-tools.test.ts` 归属 workspace 安装生命周期，使用真实锁定 DSH 子进程和确定性模型，经原生工具调用验证先加载失败→修正重装→同一轮实际调用、同 workspace 第二聊天、跨 workspace 实际拒绝、禁用静态工具/空集、另一个坏 bundle 不破坏好工具、重启恢复与持久停用、重新启用/移除。该风险此前没有安装链路保护，没有重复测试框架或私有方法。

开发过程先确认新测试在未实现版本失败：Agent 工具列表缺少 `plugin_manager`。安装核心复用原生服务；未复制 package-manager、patch parser、Agent Loop 或模块缓存处理。

## 检查结果

| 命令 | 结果 | 证据边界 |
|---|---|---|
| `pnpm build`、`pnpm typecheck` | passed | 本地构建和类型检查；不代表生产部署 |
| `pnpm test` | 84 files / 313 tests passed | 包括原生子进程生命周期；模型 fixture 不能替代真实 LLM 产品验收 |
| `python -m pytest -m 'not e2e' -q` | 56 passed / 31 deselected | standalone tooling / architecture |
| `ruff check .`、`ruff format --check .` | passed / 82 files formatted | Python gates |
| 前端 `npm ci`、`npm audit --audit-level=critical`、`npm test` | 0 vulnerabilities；94 files / 881 tests passed | 未改变客户端；常规前端回归 |
| `PYTHON=<main>/.venv/bin/python ./scripts/docs-check` | 239 Markdown / 64 routes passed | 修正 delta 中复制的相对链接后通过，无契约语义变化 |
| `git diff --check` | passed | diff 格式 |

独立静态审查、corrected-delta 和真实 IM+Node+DSH/LLM 产品验收结论分别见 unit 的 code-review、verification 与 acceptance 报告。隔离真栈使用 worktree 专用身份、workspace、运行数据和随机端口；不触碰生产配置或服务。
