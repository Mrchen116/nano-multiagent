# M1 开发配置与生产隔离证据

## 版本与范围

- 实现基线：`f6175e871`；脚本实现 `20887f251`；开发/部署入口 `9de55b2df`，审查修正 `7d4052c4b`。
- 两机模型验证实际运行 `20887f251`。之后 E2E 唯一脚本变化是成功提示显示所用源配置路径，配置选择/保护/起停机制未变；模型证据保留有效。
- Mini 生产迁移使用 `4cea0166d70a604da6a7dcea9246d81e37b1e1bb`，没有将本次开发版本或后来 main 上的业务提交上线。
- no spec delta，无业务 UI/协议/Agent prompt 改动。开发 Context 由独立 code reviewer 实际从共享入口读取并在两机运行 check，见 code-review.md。

## 测试策略

新风险是 E2E 生命周期命令误写生产目录、Mini 误取 Air 测试 Bot，以及本机配置缺失/错误被忽略。已有 `test_worktree_stack_lifecycle_e2e.py` 保护服务隔离与清理，`test_e2e_feishu_config.py` 保护 Bot 身份，均 keep；它们不覆盖本次命令执行前的路径/机器策略。

新增 `tests/integration/test_dev_host.py` 从 CLI 子进程和磁盘不变量检查保护策略，属于最低可观察的接线层，不起常驻服务。覆盖 up/down、配置保护、symlink、祖先保护、标记、禁用飞书、显式缺失和错误配置；13 项。初始红测中 down 直接删除保护现场的 PID 文件并零退出，up 已进入配置处理；实现后全部通过，独立审查者又确认 13 passed。

一次性数据副本演练与真实模型探针保存在本机 `output/refactor-675/`，不进入永久测试。生产迁移使用相同的 SQLite backup/附件复制函数；演练验证一致复制、拒绝覆盖既有目标和切换后新写入恢复。无生产故障注入或测试消息。

## 两机真实开发验证

| 机器 | 代码与入口 | 结果 | 本地定位 |
|---|---|---|---|
| Air | `20887f251`，daily profile，固定 Node 24.22.1 + 主仓 Python 3.12.9 | IM/Gateway/DSH ready，真实模型返回合成标记 `dual-host-air-675`；随后 down 成功 | `/tmp/nano-refactor675-air-20261028/model-smoke-result.json`，conversation `c_i9u55alf`，IM `127.0.0.1:59804` |
| Mini | 同 SHA，私有源模板只改 LLM 地址为 Mini Bridge 和非秘密占位 key；Python 3.14.5 | daily 栈 ready，真实模型返回 `dual-host-mini-675`；随后 down 成功 | `/tmp/nano-refactor675-mini-20261028/model-smoke-result.json`，conversation `c_q0te1p1l`，IM `127.0.0.1:53247` |
| Mini 飞书 | 本机 `feishu_e2e: false`，直接执行 `--feishu` | 在起服务/读凭据前明确拒绝；没有复制飞书私有文件 | `/tmp/nano-675-feishu-refusal.log` |

两机 `dev_host.py check` 均在推荐 PATH 下报告 Node 24.22.1、各自测试源与日志路径、Air true/Mini false；Mini 可选 reference_root 不存在被如实显示，不影响基本开发。报告只证明路径和版本；模型回包是单独的真实证据。检查未输出 YAML 内容、密钥或 token。

## Mini 迁移核对

- 现场备份：Mini `~/.nanoassistant/deploy-backups/refactor-675-path-migration-20261028/`，0700，含原 config/key/state、launcher/plist、发布清单和迁移记录。原始数据和秘密不入仓。
- 新生产 checkout：`~/.nanoassistant/prod-main/nano-multiagent`；IM 数据 `~/.nanoassistant/im-data/`；Tunnel Python `~/.nanoassistant/runtime/tunnel-venv/bin/python`。Node 保持 24.22.1，设备/签名密钥字节与备份一致，Gateway/DSH workspace/state 留原路径。
- 生产停止写入后 SQLite backup，integrity_check 与 69 张表行数一致，5 个附件文件路径/内容哈希一致；明细只留上述本机 `data-verification.json`。
- IM/Gateway live cwd/CLI 已为新 checkout；IM 打开的 DB 是新路径；IM 没有旧开发主仓打开文件引用。Gateway 的两类 DSH 子进程均用固定 Node，profile integration/base 链接均指向新生产 checkout。
- Mini/Air 本人节点同 owner 且 online；现有通道 Mini 3 / Air 1 均 connected。没有重新绑定、更换节点 ID 或用户身份。
- 公网 HTTPS 首页与 `/health` 为 200，HTML 引用的 JS/CSS 均可取，HTTP 308 保持；Air 无 `:8011` IM。清单继续发布 `1.0.0`，GitHub Release asset digest 与清单相符；旧 checkout 的本地 tarball 是构建候选，未作为发布物迁入。独立 `IM_NODE_RELEASE_DIR` 只保存原正式清单，下载仍跳转原 Release URL。
- 首次 Tunnel gate 在 `/ready` 成功后立即启动，但 QUIC 四连接尚未建立而提前失败。日志显示 04:04:36–38 UTC 依次建立连接；随后只读核对同 PID、4 IPv6 UDP/4 HA、四路双向流量、closed_connections=0 后重新开始 600 秒采样，没有额外重启或改网络路径。最终采样与旧 data 收尾结果在下方补记。

## 本地 CI

- build、typecheck、check:ios-runtime 通过；Python 113 passed/28 e2e deselected；ruff check/format 通过；docs-check 通过；前端 108 files/1029 tests 通过，critical audit 通过（保留既有非 critical 告警）。
- 默认并发全量首次为 780 passed/2 failed（agent-disable-native 的 PTY cleanup、global-child-tools 的事件快照）；两文件独立复跑 9/9 通过。
- 第二次默认并发为 780 passed/2 failed，失败换为 knowledge-policy 与 task-execution-limits；首轮两项此轮通过。尚不能以窄复跑证明默认并发稳定，也没有证据归因本 unit 的脚本改动。改用 `pnpm exec vitest run --maxWorkers=2` 做完整套件验证，未修改业务代码/测试或隐藏失败。

- 完整低并发运行：`pnpm exec vitest run --maxWorkers=2`，144 files / 782 tests 全通过，285.15 秒（2026-10-28 12:07:47 Asia/Shanghai 开始）。支持并发敏感性的判断，但不宣称已确定默认并发失败的内部根因；本 unit 未触及这些 native 用例或运行时实现。
