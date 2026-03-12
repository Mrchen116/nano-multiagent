# M122 — Web IM 默认入口恢复可达

## 0. 前置说明
- 本里程碑只处理 `M122`，不接其他任务。
- 工作目录固定为：`/Users/czj/Repos/nano-multiagent/.worktrees/M122`。
- 已阅读并遵守：`tdd-execution-worker/SKILL.md`、`LOGBOOK.md`、`COMMENTING_GUIDE.md`。
- 入口验收以“真实用户可打开 discoverable URL”为第一优先级，不通过改文档绕路。

## 1. 当前基线
- 基线命令：
  - `cd src/IM/frontend && npm run test && npm run build`
- 基线结果：
  - 失败，停在 `npm run test`
  - 错误：`sh: vitest: command not found`
- 当前判断：
  - worktree 内前端依赖尚未安装，导致门禁未能进入代码层
  - 该失败是环境前置，不足以推翻 `M120` 已记录的入口 `404` 事实
  - 当前问题不是纯前端路由缺失；IM 服务默认入口未提供前端装配，运行中的 `4173` 也来自残留旧 worktree 进程
- 已确认事实：
  - `src/app/router.tsx` 已声明 `/` 首页重定向到 `/chat`
  - `src/IM/frontend/README.md` 把 `http://127.0.0.1:4173/chat` 当作默认用户入口
  - `ACCEPTANCE/M120-acceptance.md` 记录 2026-03-12 运行环境里 `/`、`/index.html`、`/chat`、`/settings/agents` 都曾返回 `404`

## 2. 当前发现
- 路由声明与实际可达性存在错位：代码层已存在 `/` 与 `/chat` 路由定义，但真实用户入口仍可能在“壳文件未被服务器返回”这一层失败。
- 当前优先排查方向是 IM 服务入口装配 + 前端入口 reachability，而不是聊天页面内部数据流或交互 UX。
- `LOGBOOK` 对本里程碑最相关的规则：
  - 入口验证必须经过真实入口，不接受只靠局部单测宣布修复
  - UI 抽检需要同时看浏览器 console，避免静态资源/入口级噪音掩盖真实错误
  - 2026-03-12 对照验证显示：当前源码新起一份 Vite 实例时，`GET /` 与 `GET /chat` 均为 `200`；坏掉的是旧环境里的残留 `4173` 进程，而 `8011` 当前只暴露 API/docs，尚无产品级前端入口

## 3. Roadpoint 记录

### R1 入口 reachability 契约固化
- Context:
  - 文档宣称默认入口存在，但真实环境中 discoverable URL 返回 `404`
  - 代码内存路由已存在，说明问题更可能在入口壳加载、构建产物暴露或 IM 服务服务器 fallback
- Decision:
  - 先补 IM 服务入口契约与 HTTP 验证测试，再做最小实现修复；默认入口收敛到 `8011`，必要时回退到 dev server redirect
- Rationale:
  - 只有先把“浏览器打开 URL 时应该看到什么”固化，后续实现才不会退化为再次修文档、只修内存路由，或继续依赖残留 worktree 进程
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service/unit/test_app_factory.py tests/im_service/unit/test_repositories.py tests/im_service/integration/test_account_binding_api.py` => `12 passed`
  - Tests: `cd src/IM/frontend && npm test && npm run build` => `33 passed` + `vite build` 成功
  - Entry: 临时验证端口 `8111` 上，`GET /`、`GET /chat`、`GET /bind/confirm?token=test-token` 均返回 `200 text/html`
  - Entry: live 端口切换后，`GET http://127.0.0.1:8011/`、`/chat` 与 `GET http://127.0.0.1:4173/chat` 均返回 `200`
- Rollback:
  - 当前未提交；若需整体回退，可回到 `b954088` 作为本里程碑起点
- Commits: C1=, C2=, C3=
- Next:
  - 继续做浏览器级复验与 M120 复验，确认聊天 UI 在真实入口下可继续进入而不只是返回 HTML 壳

### R2 真实入口复验与回归收口
- Context:
  - `M122` 的退出标准要求真实浏览器打开默认入口即可进入聊天应用或稳定跳转
  - 仅做 HTTP 文本检查不足以证明真实用户入口恢复
- Decision:
  - 在实现完成后，用真实浏览器复验 `/` 与 `/chat` 的打开行为，并把结果写回 PROGRESS
- Rationale:
  - 入口级问题最容易在“HTTP 看起来正常、浏览器仍打不开”时漏检，必须保留浏览器级证据
- Evidence:
  - Tests: live smoke 期间未新增失败；当前门禁仍为 `12 passed` + `33 passed` + frontend build 成功
  - Entry: 已完成真实 HTTP 复验与 live 进程切换，但尚未完成浏览器级 UI 复验
- Rollback:
  - 可回退到 `b954088`，并恢复旧 `8011/4173` 进程配置
- Commits: C1=, C2=, C3=
- Next:
  - 用真实浏览器打开 `http://127.0.0.1:8011/`、`/chat`，确认 UI 已进入聊天壳并视情况重跑 M120
