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

Air/Mini 已安装的固定 Node 可通过 `PATH="$HOME/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH"` 使用；Python 辅助命令将当前开发主仓 `.venv/bin` 放到 PATH 前部。先用下面的 check 核对实际版本，不以全局默认 Node/Python 代替。

## 本机开发配置

Air 与 Mini 共用仓库、Skill 和开发流程；机器路径、模型入口与可用能力由本机私有配置提供。换机器后重新执行 `python3 scripts/dev_host.py check`，不沿用上一台机器的路径或连接结论。开发与生产使用独立 checkout、数据和运行依赖；部署入口和生产位置以 [生产舰队](../operations/prod-fleet.md) 为准，完成开发或合并不触发部署。

配置默认位于 `${XDG_CONFIG_HOME:-~/.config}/nano-multiagent/dev-host.json`，也可用 `NANO_DEV_HOST_CONFIG` 指定。所有路径支持 `~` 展开，展开后须为绝对路径。文件可选：默认位置不存在时，社区/CI 继续使用仓库原有默认行为；显式指定的文件缺失或配置格式错误则失败。无密钥示例见 [`config/dev-host.example.json`](../../config/dev-host.example.json)；真实文件、测试 YAML 和凭据不提交。

| 字段 | 用途 |
|---|---|
| `host` | 展示用机器标签，不据此推断权限或网络能力 |
| `e2e_config` | 可选的完整本机 E2E 源 YAML；从仓库测试模板复制，只调整本机模型入口等测试设置，不复制生产身份或凭据 |
| `protected_paths` | 生产 checkout、持久数据等禁止作为 E2E 源或运行目录的绝对路径数组 |
| `feishu_e2e` | 可选布尔；Air 为 `true`，Mini 为 `false`，显式 `false` 会在读取飞书凭据和取得锁之前拒绝飞书起栈 |
| `llm_logs` | 可选的本机 LLM 日志根目录；不存在或未配置时如实报告不可用，不能据此假定模型不可用或已有请求证据 |
| `reference_root` | 可选参考仓根目录；[AGENTS 调研入口](../../AGENTS.md#调研参考项目)中的相对路径从这里解析；未配置时可查 `~/Repos/opensource-hub`，仍需确认仓库实际存在 |

`e2e_config` 用于 default、daily 和专用飞书配置转换。未配置时使用仓库 [`config/e2e/gateway.yaml`](../../config/e2e/gateway.yaml)；default 的显式 `--main-config` 优先于本机设置。daily 不接受 `--main-config`，也不与飞书混用。仓库模型目录升级后，本机副本需要同步相应模型声明，保留本机 endpoint。Air 使用现有测试 Bot；Mini 不复制其凭据，需要飞书验收时交接明确代码 SHA 和场景到 Air，普通隔离 E2E 仍可在 Mini 执行。

```bash
python3 scripts/dev_host.py check
python3 scripts/dev_host.py e2e-config --repo "$(git rev-parse --show-toplevel)"
python3 scripts/dev_host.py guard --repo "$(git rev-parse --show-toplevel)" \
  --runtime /absolute/isolated/runtime --profile daily
```

`check` 只报告命令路径/版本、声明路径是否存在和本机能力，不安装依赖、不发模型请求、不操作服务，也不证明 endpoint 可达或真实 E2E 通过。`e2e-config` 只返回选定的源 YAML 路径；真实模型验收与日志定位见 [LLM 联调](llm-integration.md)。

`e2e-up.sh` / `e2e-down.sh` 在修改文件或停止进程前自动调用 `guard`，检查源码 checkout 和运行目录的真实路径（包括符号链接）：拒绝保护目录内的路径，也拒绝包含保护目录的祖先路径。生产 checkout/数据目录另放 `.nano-production` 标记，向上查找标记，即使没有本机配置也拒绝误用；标记属于本机文件，不提交。保护机制用于防止误操作，不是安全权限边界。完整起停和清理要求见 [worktree runtime](worktree-runtime.md)。

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
