# Local Development

本文负责本地开发环境、常用测试命令、产品开发入口、测试身份和提交约定。IM、Gateway 与 Web IM 的启动和排障见 [`../operations/`](../operations/README.md)；worktree 内真实服务的隔离规则见 [`worktree-runtime.md`](worktree-runtime.md)。

## Python 环境

项目要求 Python 3.11+。首次安装：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

仓库已有 `.venv` 时优先使用它。无需激活也可以显式执行：

```bash
.venv/bin/python -m pytest
```

## 常用测试

```bash
# 全部测试
.venv/bin/python -m pytest

# 单个测试文件
.venv/bin/python -m pytest -xvs tests/unit/test_xxx.py

# 跳过需要真实运行时的 e2e
.venv/bin/python -m pytest -m "not e2e"
```

先跑最窄相关测试，再按改动风险扩大到 integration、contract 或完整套件。测试应该放在哪一层、何时使用 e2e marker、哪些临时证据不应固化为回归测试，以 [`testing.md`](testing.md) 为准。

## 产品开发入口

### Coding CLI

```bash
PYTHONPATH=src .venv/bin/python -m coding_cli.main
PYTHONPATH=src .venv/bin/python -m coding_cli.main \
  --model volcanoArk:doubao-seed-2-0-code-preview-260215
```

CLI 的交互命令、`--text` 模式和排障见 [`../../README.md`](../../README.md#cli)，当前行为契约见 [`../specs/cli/spec.md`](../specs/cli/spec.md)。

### IM 前端

```bash
cd src/IM/frontend
npm install
npm run dev
npm run test
npm run build
```

`src/IM/frontend/dist/` 是本地构建产物，不提交。前端开发模式、Mock/真实 IM 边界见 [`../../src/IM/frontend/README.md`](../../src/IM/frontend/README.md)。

## 本地测试身份

手工调试可以使用：

```yaml
username: nano
password: nano1234
display_name: Test User
im_url: http://127.0.0.1:8011
```

注册示例：

```bash
curl -X POST "http://127.0.0.1:8011/im/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"nano","password":"nano1234","display_name":"Test User"}'
```

手工反复重启同一 IM 数据库时，使用稳定的开发 JWT secret，避免已有 token 因重启失效：

```bash
IM_JWT_SECRET="demo-jwt-secret-for-feat340-testing" \
  PYTHONPATH=src .venv/bin/python -m uvicorn IM.app:app \
  --host 0.0.0.0 --port 8011
```

Gateway 的 `im_service.username` / `password` 可以使用这组测试身份，以便启动和重连时自动登录。完整配置见 [`../operations/gateway.md`](../operations/gateway.md)，启动顺序见 [`../operations/local-stack.md`](../operations/local-stack.md)。

`scripts/e2e-up.sh` 会为隔离运行生成随机 secret，并在临时 IM 中注册测试身份；不要为它手工复用主实例的数据库或 token。

## 开发约定

- 注释与 TODO/FIXME：以 [`commenting.md`](commenting.md) 为准。
- TODO/FIXME 格式：`TODO(<issue-id>): <改进> — <删除条件>` / `FIXME(<issue-id>): <缺陷> — <影响/风险>`。
- 模块边界：以 [`../../SPEC.md`](../../SPEC.md) 为准；产品包不得绕过 `agent.sdk`。
- 测试分层：以 [`testing.md`](testing.md) 为准。
- 前端产物：`src/IM/frontend/dist/` 不提交。

Commit message：

```text
<type>(<unit>/<milestone>/<roadpoint>): <desc>
```

- scope 使用 unit 实际目录中的 id，例如 `bugfix-355/M5/R1`；
- milestone 级 commit 可以省略 roadpoint，unit 级 commit 可以省略 milestone；
- phase 通过 type 表达：C1 红测用 `test`，C2 实现用 `feat` / `fix` / `refactor`，C3 文档用 `docs`。

具体 change unit 内的提交节奏由当前 `change-*` skill 决定；本文只保存命名格式。
