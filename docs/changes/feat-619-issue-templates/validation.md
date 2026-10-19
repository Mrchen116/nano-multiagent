# feat-619 delivery validation

## Baseline and gate validity

- executed_base: `dfdbf6bf300f7af899f13d67957586ee517f3c0b`；effective_base: `9b110168359b9c9ae5937d07a77b697e03a61d65`。最终 main 仅新增 bugfix-618 的隔离设计/原型/证据文档，不修改本 unit、运行时代码、CI、依赖或开发规范；设计、静态和产品门禁 retained，合并后重跑文档检查。
- 初次全量构建/类型/前端/Python 检查在 `8213bc6f1` 的运行时代码上执行；之后只有 GitHub 配置、同步脚本和文档变化，运行时代码/依赖/测试不变，结果 retained。
- 最终实现版本：`7e4873084`；最终 corrected workflow schema 通过。8 个部署文件（四表单、config、清单、workflow、同步脚本）与私有验收仓 `fb613e6` 逐字节一致。
- 门禁实际版本分别记录在 design-review、code-review、verification、acceptance。后续只归档 unit、追加验证记录和 PR 元数据，不改变配置或执行代码；有效性保留至 PR head。
- no spec delta：长期 GitHub 协作规则归 `docs/development/issues.md`，Nano 包行为未变化。

## Local checks

| 检查 | 结果 |
|---|---|
| 四个 Issue Forms JSON schema、默认标签引用、字段 ID、26 标签唯一性 | PASS |
| GitHub workflow JSON schema（修正后的版本） | PASS |
| node --check scripts/sync-issue-labels.mjs / git diff --check | PASS |
| pnpm build / pnpm typecheck | PASS |
| pnpm exec vitest run --maxWorkers=2 | 93 files / 346 tests PASS，323.69s |
| npm ci / npm audit --audit-level=critical / npm test（Web） | 0 vulnerabilities；96 files / 887 tests PASS |
| .venv/bin/python3.12 -m pytest -m 'not e2e' -q | 62 passed / 31 deselected |
| .venv/bin/ruff check . / .venv/bin/ruff format --check . | PASS，83 files formatted |
| PYTHON="$PWD/.venv/bin/python3.12" ./scripts/docs-check | PASS；归档后再执行 |

首次默认并发 pnpm test 为 345 passed / 1 workspace-tools 90s timeout；该文件独立复跑 41.31s 通过，再以 maxWorkers=2 全量通过。首次超时根因未确认，未修改运行时代码或放宽测试超时。

## External results

- 主仓清单中的 26 个标签均已同步；原有 13 个标签名称/颜色/说明全部保留；读取全部 115 个历史 Issue 的标签归属，before/after 完全一致。没有历史 Issue 批量编辑。
- 私有验收仓：[nano-issue-intake-validation-619](https://github.com/Mrchen116/nano-issue-intake-validation-619)。详细真实网页、同步与 Actions 结果见 acceptance.md。
- 真实验收先发现 `context.issue.number` 与 REST `issue_number` 不匹配导致 404，修复后：[#7](https://github.com/Mrchen116/nano-issue-intake-validation-619/issues/7) 仅补 needs-triage，[run](https://github.com/Mrchen116/nano-issue-intake-validation-619/actions/runs/39262949061) success；[#8](https://github.com/Mrchen116/nano-issue-intake-validation-619/issues/8) 保留自定义 status 和 area，[run](https://github.com/Mrchen116/nano-issue-intake-validation-619/actions/runs/39262957877) success，均无评论。
- 表单与主仓 opened workflow 需 PR 合并到默认分支后生效。远端 CI 结果以 PR 检查为准，不把标签已同步等同于 PR 已合并。
- Read/Triage 视角没有独立账号实测；普通贡献者空白入口关闭依据 GitHub 官方契约，ADMIN 实测看到原生 Maintainers only 例外。

## Retained scope

文档入口修复已独立 closure；平台例外文案已独立 delta 核对；REST 编号修复有独立 targeted 静态复验与真实 Actions 复验。表单、标签清单和同步 CLI 自 `34eee81ff` 后未变化。归档路径和本记录不新增行为，因此不重复跑已经有效的运行时/前端全量套件。

## Cleanup

独立 reviewer 创建的测试 Issue #1–#8 已全部关闭、0 评论，私有测试仓随后由主 Agent 归档。未启动 Nano 真服务；本次构建和测试由命令自身结束。
