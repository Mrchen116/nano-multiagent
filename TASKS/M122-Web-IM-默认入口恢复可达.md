# M122 — Web IM 默认入口恢复可达

## 前置阅读
- [x] 已先阅读 `/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/LOGBOOK.md`
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M120-acceptance.md`
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/src/IM/frontend/README.md`

## 当前约束
- Milestone: `M122 / Web IM 默认入口恢复可达`
- Execution: `parallel`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M122`
- Branch: `milestone/M122`
- 测试门禁：`PYTHONPATH=src pytest -q tests/im_service/unit/test_app_factory.py tests/im_service/unit/test_repositories.py tests/im_service/integration/test_account_binding_api.py && cd src/IM/frontend && npm run test && npm run build`
- 允许改动：`src/IM/app.py`、`src/IM/api/**`、`tests/im_service/**`、`src/IM/frontend/**`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`、`data/dev-tasks.json(only via script)`
- 禁止改动：`src/personal_assistant/**`、`docs/**`、`README.md`、无关产品/包
- Prevention rules:
  - 真实用户入口必须先能打开，不能再让 discoverable URL 返回 `404`
  - 不通过“改文档绕路”解决问题
  - 只修入口 reachability / IM 服务装配 / shell loading，不扩散到更大聊天 UX 重做
  - 遵守 `LOGBOOK` 中真实入口与 Playwright/UI 回归规则

## 第一轮测试基线
- 命令：`PYTHONPATH=src pytest -q tests/im_service/unit/test_app_factory.py tests/im_service/unit/test_repositories.py tests/im_service/integration/test_account_binding_api.py && cd src/IM/frontend && npm run test && npm run build`
- 结果：失败，未进入代码断言阶段
- 失败点：`npm run test` 直接报 `sh: vitest: command not found`
- 当前判断：这是 worktree 内尚未安装前端依赖的环境前置问题；同时，IM 服务默认入口未挂载前端也是本里程碑需要一起收口的代码缺口
- 已确认现状：
  - `src/app/router.tsx` 已声明 `/ -> /chat` 重定向，路由设计目标本身存在
  - `src/IM/frontend/README.md` 仍宣称默认入口为 `http://127.0.0.1:4173/chat`
  - `ACCEPTANCE/M120-acceptance.md` 记录 2026-03-12 在运行环境中 `http://127.0.0.1:4173/`、`/index.html`、`/chat`、`/settings/agents` 均返回 `404`
  - 当前源码在独立对照端口上可返回 `GET /` 与 `GET /chat = 200`，说明路由本身不是唯一缺口
  - 运行中的 `8011` IM 服务当前只暴露 API 与 `/docs`，并未提供 Web IM 前端入口

## Roadpoints

### R1 入口 reachability 契约固化
- Acceptance:
  - 至少一个 discoverable URL（优先 IM 服务 `/`，次选 `/chat`）能加载前端壳或稳定重定向到可用聊天入口
  - `GET /`、`GET /chat`、`GET /settings/agents` 在 IM 服务入口上不再返回入口级 `404`
  - 前端入口契约明确覆盖 SPA shell / redirect，而不是仅靠内存路由单测
  - 不修改文档路径承诺，不把入口改到隐藏地址
- Tests Plan:
  - unit: 仅保留已有组件/路由单测，不新增纯函数级测试；本问题是入口可达性，不是局部逻辑
  - contract: 新增 IM 服务入口契约测试，断言 discoverable URL 返回 HTML 壳或可接受的重定向
  - integration: 新增基于 `TestClient` 的 HTTP 入口验证，覆盖 `/`、`/chat`、`/settings/agents`、`/bind/confirm`
  - e2e: 在真实浏览器中打开默认入口，确认页面进入聊天应用或自动跳转到可用聊天入口
- Expected Tests:
  - `tests/im_service/unit/test_app_factory.py`
  - `tests/im_service/unit/test_repositories.py`
  - `tests/im_service/integration/test_account_binding_api.py`
  - 真实浏览器验证：打开 `http://127.0.0.1:8011/`、`/chat`，必要时对照 `http://127.0.0.1:4173/`
- DoD:
  - 入口契约测试先红后绿
  - `PYTHONPATH=src pytest -q tests/im_service/unit/test_app_factory.py tests/im_service/unit/test_repositories.py tests/im_service/integration/test_account_binding_api.py && cd src/IM/frontend && npm run test && npm run build` 全绿
  - PROGRESS 记录入口行为、证据与回滚点
  - 完成 C1/C2/C3
- 状态: DONE

### R2 真实入口复验与回归收口
- Acceptance:
  - 浏览器真实打开 IM 服务默认入口时，可进入聊天应用或被稳定带到可用聊天入口
  - 复验 `8011` 与文档中 `4173` 的用户行为，不只做 HTTP 文本检查
  - 若入口依赖重定向，行为应稳定且可复现
  - 构建产物与运行入口在真实浏览器下无入口级报错阻断
- Tests Plan:
  - unit: 不新增；用户入口行为不适合拆成局部函数测试
  - contract: 复用 R1 入口契约，避免重复定义
  - integration: 复用 IM 服务入口 HTTP 验证与前端 build/test 作为发布前门禁
  - e2e: 用真实浏览器打开入口 URL，核验聊天壳/关键文案/路由落点
- Expected Tests:
  - `PYTHONPATH=src pytest -q tests/im_service/unit/test_app_factory.py tests/im_service/unit/test_repositories.py tests/im_service/integration/test_account_binding_api.py`
  - `cd src/IM/frontend && npm run test && npm run build`
  - 真实浏览器复验记录（Playwright 操作 `http://127.0.0.1:8011/`、`/chat`，必要时对照 `4173`）
- DoD:
  - 浏览器复验通过并记录在 PROGRESS
  - 入口级回归不再出现 `404`
  - 完成 C1/C2/C3
- 状态: DOING

## 产出清单
- `TASKS/M122-Web-IM-默认入口恢复可达.md`
- `PROGRESS/M122-Web-IM-默认入口恢复可达.md`
- `src/IM/app.py`、`src/IM/api/**`、`tests/im_service/**`、`src/IM/frontend/**` 中与入口可达性相关的测试与实现
