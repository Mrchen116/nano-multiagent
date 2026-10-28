# Verification Report: refactor-675-dual-host-development

> Validation snapshot: `f6175e871 → df21cb2efef77c833682d9d631002dac0dca41c6`

> 最终现场补证：`5b5dffee6019d0c58f1fde00b3beff400667d75a`，相对受审快照仅增加 M1 实施记录 9 行；没有代码、配置或契约变化，保留同一验证快照。

## Summary

- 日期：2026-10-28；review_round=1；verification_mode=full，合并核对 no spec delta。
- 独立 verifier，未参与实现；复用已完成的 Mode B / code-review Round 2，通过读取最终实现及可信运行证据核对，不再执行完整 Context Review、重复全量或操作生产。
- 当前结论：**PASS — Ready for PR**。0 CRITICAL / 0 WARNING；全部实施与本地验收条件成立，最终 600 秒 Tunnel gate 和旧 data 收尾证据已核对完成。

| 维度 | 结果 |
|---|---|
| Completeness | M1 实施/本地退出标准齐全；远端 CI 待 PR 后门禁 |
| Correctness | 3/3 Requirement / Scenario covered |
| Coherence | Followed，无实现/设计偏离 |

远端 CI 属于创建 PR 后的交付门禁，本地 verifier 不能替代；截至本报告未提供远端 run，不声称 M1 的远端 CI 标准已完成。通过本地验证也不授权合并、发布安装包或升级生产代码。

## Completeness

- M1-development 为唯一 milestone。退出标准中的 CLI 防误操作、两机 check/daily/模型回包/down、隔离数据副本演练、同 SHA 生产路径/身份/健康证据、独立代码及 Context 审查、本地 CI、最终 Tunnel 600 秒 gate、原主仓 data 保护收尾均有实现与直接证据。远端 CI 仍由 caller 在 PR 后完成，不将整个交付里程碑提前标为所有门禁完成。
- Prototype / Reference：N/A。没有产品 UI、业务协议或运行时行为改动；`design.md:64–70` 明确零产品用户面，由 verifier 核开发工具与迁移结果，无需产品 reviewer。
- 测试策略满足 `docs/development/testing.md`：13 项新测试通过真实 CLI 子进程和磁盘不变量保护新的前置策略，处于 integration 最低有效 seam。原生命周期 E2E、飞书身份配置测试 keep；一次性数据迁移与模型回包是本机验收证据，没有变为永久测试或额外平台。

## Correctness

| Requirement / Scenario | 实现位置 | 测试 / 真实证据 | 状态 |
|---|---|---|---|
| 开发不会替换生产现场 / 两机分别开发 | `scripts/dev_host.py:61–79`；`scripts/e2e-up.sh:148–151`；`scripts/e2e-down.sh:14`；部署固定目录与独立 IM 数据/Tunnel Python | 13 条 CLI 保护测试；两机同 `20887f251` daily 真栈与各自回包并 down；`M1-development/implementation.md` 的迁移数据、live 路径和旧 data 移入受保护备份记录 | covered |
| 飞书测试身份不被两机争用 / Mini 需飞书验收 | `scripts/dev_host.py:76–79`；up 前置 guard；`docs/development/local-development.md:29–33` | 禁用飞书子进程测试；Mini `/tmp/nano-675-feishu-refusal.log` 实际提前拒绝，未复制 Air 凭据 | covered |
| 手动部署与既有业务行为保持 / 开发或合并不自动部署 | `.claude/skills/prod-fleet-deploy/SKILL.md`、`references/runbook.md:51–78`；`docs/operations/prod-fleet.md` | 无自动部署代码/触发器变动；Mini 迁移保持 `4cea0166d70a604da6a7dcea9246d81e37b1e1bb`；保留身份/签名密钥、已发布 1.0.0 清单、现有两机节点与通道；600 秒 Tunnel gate 成功 | covered |

### 可复查运行证据

- 独立复用本 reviewer 的 code-review Round 1：两机以文档推荐 PATH 实际 check，Node 均 24.22.1，Air/Mini 能力不同，Mini 缺失可选参考根被准确报告；13 passed/0.62s。Round 2 固定 `9de55b2df..7d4052c4b` 关闭唯一部署顺序冲突，0 CRITICAL / 0 WARNING。
- 本轮直接读取 Air `/tmp/nano-refactor675-air-20261028/model-smoke-result.json` 与 Mini 同类摘要：各 `reply_count=1`、`matched=true`，nonce 为 `dual-host-air-675` / `dual-host-mini-675`；conversation 分别 `c_i9u55alf` / `c_q0te1p1l`。Mini 飞书实际拒绝日志直接核对成功。这些是隔离模型兼容性事实，不外推成所有模型任务可靠。
- 本轮读取 `output/refactor-675/data-copy.py`，其 SQLite backup、表计数/integrity、附件哈希、拒绝覆盖、切换后新写入恢复机制与记录一致。演练成功和生产实际执行结果复用 caller 的实施记录，未在生产重跑演练。
- 收尾 locator：上述一次性模型探针脚本已清理，模型结果 JSON/日志仍留各自 E2E 运行目录；数据复制脚本作为生产恢复材料移入 Mini 受保护迁移备份，开发临时副本已删除。此前读取的脚本内容与执行结论仍有效；实施记录随后只更正这一保留位置，不改变实现或测试结论，无需重验。
- 实施记录给出停写后 69 表计数/integrity 一致、5 个附件路径/哈希一致，现场备份定位为 Mini `~/.nanoassistant/deploy-backups/refactor-675-path-migration-20261028/`；秘密和原始数据不进入仓库。新 IM/Gateway live cwd/CLI、DB 打开路径、两类 DSH 子进程固定 Node/profile 链接已离开开发主仓，原 workspace/state 保留。
- 生产核对复用 caller：本人两节点同 owner、online，Mini 3/Air 1 现有通道 connected；HTTPS 首页/health/HTML 引用 JS+CSS 成功、HTTP 308 保持，Air 无 IM :8011；Release 清单继续 1.0.0，无安装包发布。未做生产测试消息或故障注入。
- 最终核对 `5b5dffee6` 的 M1「最终迁移与保留范围」：2026-10-28 12:11:33–12:21:33 +0800 的 600 秒 gate 全样本 PID 84441、IPv6 QUIC HA=4、en0、closed_connections=0、HTTPS=200；日志位于 Mini 迁移备份根 `tunnel-gate.log`。首次尚未建立四连接的失败另保留于 `tunnel-gate-startup.log`；后续采样没有额外重启或更换网络路径。
- 同一最终记录确认旧 DB 无打开引用后，整个原主仓 `data/` 移到受保护迁移备份 `original-data/`，原件/历史文件与元数据保留，`migration.json` phase=completed。Mini 最终保护根为 `~/.nanoassistant`，Air 另含 `.codex` 生产根；Mini check 成功、开发主仓 guard 放行、生产 checkout guard 拒绝、源站 health 成功。两机 E2E PID 已清理，Mini 无飞书 env；主仓原有两提交保持，开放 PR 期间开发 worktree 保留。复用 caller 的受限生产记录，不额外操作生产。
- 本轮直接读取本地日志：`pnpm-test-bounded.log` 为完整 `pnpm exec vitest run --maxWorkers=2`，144 files/782 tests passed，285.15s；`frontend-test.log` 为108 files/1029 tests passed；`pytest.log` 为113 passed/28 e2e deselected；build/typecheck、iOS runtime、ruff check/format、docs-check通过。critical audit通过，保留既有11项非critical漏洞（4 low/2 moderate/5 high）；本 unit 没有锁文件或依赖改动。
- 两轮默认并发均有2项失败，失败集合不同；首次两文件窄复跑9/9通过。低并发完整套件通过可用于本次回归验证，不能据此宣称已定位默认并发失败内部根因或修复其稳定性。没有改测试/业务代码隐藏这些失败。

## Coherence

| Design 决策 | 遵守 | 实现 / 证据 |
|---|---|---|
| 私有单 JSON，缺省兼容、显式配置错误失败 | 是 | `scripts/dev_host.py:22–58`；本机说明与 example；缺失/错误配置测试 |
| 完整本机 E2E 模板，无第二套产品合并器 | 是 | `scripts/dev_host.py:82–90`；up:133–151 及既有 daily/feishu 转换；两机真实 daily |
| 源 checkout / runtime 真路径与祖先标记在副作用前保护 | 是 | `_guard:61–75`；up:148、down:14；CLI 参数化测试；example保护 `~/.nanoassistant`，Air另配 `.codex` 生产根 |
| 飞书机器能力显式区分，Mini 不取得 Air Bot | 是 | `_guard:76–79`；先于 feishu config/lock；实际拒绝证据 |
| Mini 生产固定 detached、数据/Tunnel依赖分离且同SHA | 是 | 实施记录的 live 路径、69表/5附件、固定Node、原身份密钥；最终600秒gate及旧data受保护迁移记录 |
| 轻量编号，首次推送占号、已发布沿用、不force-push | 是 | `docs/changes/README.md:49–63` 与 spec/design author Skill 一致；未改编号算法或新增跨机锁 |
| 开发 Agent 按本机来源发现参数，不沿用 Air 历史路径 | 是 | AGENTS → local-development → check/llm-integration，code-review Mode B实际两机消费；无产品 prompt/schema/Memory变化 |

`SPEC.md` 的包职责、依赖方向、DSH公开接入与stdio边界保持。完整 diff 没有 `apps/`、`packages/`、`src/`、锁文件或 CI workflow 代码变化；Python仍只做运维辅助，不新增产品执行运行时。

### Prototype / Reference Contract

N/A：没有前端原型或 must-match reference。

## Issues

- CRITICAL：0。
- WARNING：0。
- SUGGESTION：0。不因可选参考根缺失或默认并发已有不稳定性扩大本 unit。
- issues=[]；validated_issues=[]；requires_full_verification=false。允许提交 PR；远端 CI 待其正常运行，尚不构成可合并或发布结论。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| no spec delta（design:52–54） | 工具及文档仅改变开发/运维流程；IM/Gateway产品实现和公开协议无diff | 两机隔离模型与既有全量机制回归；同SHA生产身份/数据不变核对 | aligned |

### Uncovered Observable Behavior

None：开发 CLI 的配置选择、前置保护与部署流程变化已由 development/operations current 文档覆盖；无需在产品 `docs/specs/` 重复建立契约。没有遗漏应进入 delta-spec 的产品可观察行为。

Outcome: aligned。

## 现场与结论保留边界

仅写本报告，不提交、切分支或操作生产；沿用 caller 的工作目录，没有自建常驻进程/现场。`validated_at` 保持上述固定代码快照，后续纯证据报告提交不改变受审实现。

若后续只是整个 unit 由 active 移至 archive，可保留代码审查与本轮 verifier 结论：核对实现/测试无变化、unit各文件内容相同、修正目录移动所需链接/索引且没有契约语义变化，并通过 docs-check。归档位置变化本身不要求重跑真实模型、数据迁移或完整套件。若有实现/契约实质变化，则按真实 delta 另行核验。
