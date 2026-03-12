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
  - 共享环境中的 `4173` 同时被残留旧 worktree Vite 进程占用并返回 `404`，因此不能继续把产品入口绑死在这条 dev-server 地址上
- 已确认事实：
  - `src/app/router.tsx` 已声明 `/` 首页重定向到 `/chat`
  - `src/IM/frontend/README.md` 把 `http://127.0.0.1:4173/chat` 当作默认用户入口
  - `ACCEPTANCE/M120-acceptance.md` 记录 2026-03-12 运行环境里 `/`、`/index.html`、`/chat`、`/settings/agents` 都曾返回 `404`

## 2. 当前发现
- 路由声明与实际可达性存在错位：代码层已存在 `/` 与 `/chat` 路由定义，但真实用户入口仍可能在“壳文件未被服务器返回”这一层失败。
- 当前优先排查方向是“如何把前端产物稳定交付给真实入口”，而不是聊天页面内部数据流或交互 UX。
- `LOGBOOK` 对本里程碑最相关的规则：
  - 入口验证必须经过真实入口，不接受只靠局部单测宣布修复
  - UI 抽检需要同时看浏览器 console，避免静态资源/入口级噪音掩盖真实错误
  - 2026-03-12 对照验证显示：当前源码新起一份 Vite 实例时，`GET /` 与 `GET /chat` 均为 `200`；坏掉的是旧环境里的残留 `4173` 进程。与此同时，当前源码在带有 `src/IM/frontend/dist` 时，IM-hosted 入口可稳定返回前端壳

## 3. Roadpoint 记录

### R1 入口 reachability 契约固化
- Context:
  - 文档宣称默认入口存在，但真实环境中 discoverable URL 返回 `404`
  - 代码内存路由已存在，说明问题更可能在入口壳加载与构建产物交付层，而不是路由定义缺失
- Decision:
  - 新增前端分发契约测试，显式禁止前端自身继续忽略 `dist/`
  - 将 `src/IM/frontend/dist` 纳入源码树，作为 IM-hosted 默认入口的可交付壳文件
- Rationale:
  - 共享环境中的 `4173` 是残留进程，不可靠；把默认入口落到可交付的静态壳文件，才能摆脱“正确源码 + 错误残留端口”这种失真环境
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test && npm run build` => `15 files passed, 36 tests passed, vite build succeeded`
  - Entry: 在隔离 IM-hosted 实例 `http://127.0.0.1:8121` 上，`GET /`、`GET /chat`、`GET /settings/agents` 均返回 `200 text/html`
- Rollback:
  - 若需重做实现，可回退到 `ea90216`，保留 Red 测试但移除已交付产物
- Commits: C1=ea90216, C2=65c3dc2, C3=
- Next:
  - 做真实浏览器复验，确认浏览器实际从 `/` 落到聊天壳而不是只返回 HTML 文本

### R2 真实入口复验与回归收口
- Context:
  - `M122` 的退出标准要求真实浏览器打开默认入口即可进入聊天应用或稳定跳转
  - 仅做 HTTP 文本检查不足以证明真实用户入口恢复
- Decision:
  - 用 Playwright 直接打开隔离 IM-hosted 入口 `http://127.0.0.1:8121/`，以浏览器真实跳转结果作为验收证据
- Rationale:
  - 入口级问题最容易在“HTTP 看起来正常、浏览器仍打不开”时漏检，必须保留浏览器级证据
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test && npm run build` 仍全绿
  - Entry: Playwright 打开 `http://127.0.0.1:8121/` 后，浏览器最终 URL 为 `http://127.0.0.1:8121/chat`
  - Entry: 浏览器 snapshot 显示页面标题 `IM Frontend`，页面内可见 `Conversations` 和 `Open Agent · OpsBot`
- Rollback:
  - 若浏览器复验需要重做，可回退到 `65c3dc2`，保留已交付产物并重跑验证
- Commits: C1=ea90216, C2=65c3dc2, C3=
- Next:
  - 更新 TASKS/PROGRESS、完成文档提交并准备集成 main
