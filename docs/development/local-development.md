# Local Development

## 环境和安装

前后端统一推荐 Node.js 24.22.1 LTS（最低安全版本范围见 package.json）和 pnpm 11.7.0；Python 3.11+ 用于文档、迁移辅助与黑盒测试。使用已有 `.venv`，无需为 worktree 复制环境。后端、前端与安装包 CI 均使用 24.22.1。

```bash
pnpm install --frozen-lockfile
pnpm build
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
npm --prefix src/IM/frontend ci
npm --prefix src/IM/frontend run build
```

## 最窄反馈与完整门禁

```bash
pnpm exec vitest run packages/personal-assistant/tests/single-thread.test.ts
pnpm build
pnpm typecheck
pnpm test
.venv/bin/python -m pytest -m "not e2e" -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
./scripts/docs-check
```

真实模型/平台验收另按 [worktree runtime](worktree-runtime.md) 隔离，不以 fixture provider 的测试代替真模型、浏览器或实体 iPhone。永久测试准入、最低有效层与停止条件见 [testing](testing.md)，证据边界见 [evidence](evidence.md)。

## 产品入口

IM 使用 `pnpm im`，节点使用 `pnpm pa`。配置、首次管理员、设备绑定和真实聊天见 [本地运行](../operations/local-stack.md)。旧 Coding CLI 已退役，不再启动 Python Agent 入口。

```bash
npm --prefix src/IM/frontend run dev
npm --prefix src/IM/frontend test
npm --prefix src/IM/frontend run build
```

Web mock 模式仅用于页面开发；真实模式、代理与路径见 [frontend README](../../src/IM/frontend/README.md)。`dist/` 不提交。原生 App 构建和签名见 [iOS README](../../src/IM/ios/README.md)。

隔离脚本自动建立 `nano` / `nano1234` 测试身份和随机 JWT secret，仅用于本次本地 E2E。已有本地数据库使用自己的固定密钥；不把开发身份或临时凭据搬到生产。

## 提交与边界

依赖以 [SPEC](../../SPEC.md) 为准，只有 integration 导入 DSH。先核对 checkout、branch 和 dirty 状态，只暂存本任务文件；代码规范见 [coding guidelines](coding-guidelines.md)。

Commit message 使用 `<type>(<unit>/<milestone>/<roadpoint>): <desc>`；简单任务可省略不适用层级。具体交付门禁见 [change workflow](change-workflow.md)。

主仓作为已提交内容的同步入口。任务交付前将本任务完成的源码、文档和 Skill 按主题提交；没有完成的工作保存在独立分支/worktree，注明恢复位置与未完成边界，不把草稿长期散落在主仓。已有但不属于本任务的修改先保留并说明归属，只有获得整理授权后才迁移或收口。

本机凭据、Skill 使用记录、机器清单、`.worktrees/` 与 `output/` 使用明确的忽略规则；待提交的源码、spec、设计或 Skill 不得靠忽略规则隐藏。主仓提交完成后检查 `git status --porcelain`，并核对本任务产物已提交或有可恢复的保存位置；正常同步不依赖反复 stash 或覆盖本地修改。
