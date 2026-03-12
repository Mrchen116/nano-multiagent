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
- 测试门禁：`cd src/IM/frontend && npm run test && npm run build`
- 允许改动：`src/IM/frontend/**`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`、`data/dev-tasks.json(only via script)`
- 禁止改动：`src/personal_assistant/**`、`docs/**`、`README.md`、无关产品/包
- Prevention rules:
  - 真实用户入口必须先能打开，不能再让 discoverable URL 返回 `404`
  - 不通过“改文档绕路”解决问题
  - 只修入口 reachability / routing / shell loading，不扩散到更大聊天 UX 重做
  - 遵守 `LOGBOOK` 中真实入口与 Playwright/UI 回归规则

## 第一轮测试基线
- 命令：`cd src/IM/frontend && npm run test && npm run build`
- 结果：失败，未进入代码断言阶段
- 失败点：`npm run test` 直接报 `sh: vitest: command not found`
- 当前判断：这是 worktree 内尚未安装前端依赖的环境前置问题，不是 `M122` 功能回归本身；补齐依赖后需要重新建立 Red 基线
- 已确认现状：
  - `src/app/router.tsx` 已声明 `/ -> /chat` 重定向，路由设计目标本身存在
  - `src/IM/frontend/README.md` 仍宣称默认入口为 `http://127.0.0.1:4173/chat`
  - `ACCEPTANCE/M120-acceptance.md` 记录 2026-03-12 在运行环境中 `http://127.0.0.1:4173/`、`/index.html`、`/chat`、`/settings/agents` 均返回 `404`
  - 共享环境中的 `4173` 实际被残留旧 worktree 的 Vite 进程占用并持续返回 `404`
  - 当前源码一旦带上 `src/IM/frontend/dist`，IM-hosted 入口即可在隔离端口上返回 HTML 壳

## Roadpoints

### R1 入口 reachability 契约固化
- Acceptance:
  - 至少一个 discoverable URL（优先 `/`，次选 `/chat`）能加载前端壳或稳定重定向到可用聊天入口
  - 当前源码生成的前端产物可被 IM-hosted 入口消费，而不是继续依赖残留 `4173` dev server
  - 前端入口契约明确覆盖 SPA shell / redirect，而不是仅靠内存路由单测
  - 不修改文档路径承诺，不把入口改到隐藏地址
- Tests Plan:
  - unit: 仅保留已有组件/路由单测，不新增纯函数级测试；本问题是入口可达性，不是局部逻辑
  - contract: 新增前端分发契约测试，断言 `dist` 不再被前端自身忽略
  - integration: 补 discoverable 路由回归，覆盖 `/` 的默认重定向声明与 `/settings/agents` 入口渲染
  - e2e: 在真实浏览器中打开 IM-hosted 默认入口，确认页面进入聊天应用
- Expected Tests:
  - `src/IM/frontend/src/app/distribution-contract.test.ts`
  - `src/IM/frontend/src/app/router.test.tsx`
  - `cd src/IM/frontend && npm run test && npm run build`
  - IM-hosted 入口验证：`http://127.0.0.1:8121/`、`/chat`、`/settings/agents`
- DoD:
  - 分发契约测试先红后绿
  - `cd src/IM/frontend && npm run test && npm run build` 全绿
  - PROGRESS 记录入口行为、证据与回滚点
  - 完成 C1/C2/C3
- 状态: DONE

### R2 真实入口复验与回归收口
- Acceptance:
  - 浏览器真实打开默认入口时，可进入聊天应用或被稳定带到可用聊天入口
  - 复验浏览器打开 URL 的行为，而不只看 HTTP 文本响应
  - 若入口依赖重定向，行为应稳定且可复现
  - 构建产物与运行入口在真实浏览器下无入口级报错阻断
- Tests Plan:
  - unit: 不新增；用户入口行为不适合拆成局部函数测试
  - contract: 复用 R1 入口契约，避免重复定义
  - integration: 复用前端 build/test 与隔离 IM-hosted 入口 HTTP 验证作为发布前门禁
  - e2e: 用真实浏览器打开入口 URL，核验聊天壳/关键文案/路由落点
- Expected Tests:
  - `cd src/IM/frontend && npm run test && npm run build`
  - 真实浏览器复验记录（Playwright 操作 `http://127.0.0.1:8121/`）
- DoD:
  - 浏览器复验通过并记录在 PROGRESS
  - 入口级回归不再出现 `404`
  - 完成 C1/C2/C3
- 状态: DONE

## 产出清单
- `TASKS/M122-Web-IM-默认入口恢复可达.md`
- `PROGRESS/M122-Web-IM-默认入口恢复可达.md`
- `src/IM/frontend/.gitignore`
- `src/IM/frontend/dist/**`
- `src/IM/frontend/src/app/distribution-contract.test.ts`
- `src/IM/frontend/src/app/router.test.tsx`
