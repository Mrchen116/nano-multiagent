# 工作区 Write/Edit 直接放行补漏

日期：2026-09-12。基线：PR #294，`ab80c695af56ee2d9270c44fc09fd5acc82d77bc`；main=`2fd84b9ac2b1949947ac899b3de7fea1488731ef`。用户在 CC 同模型对照后明确要求修改 Nano。

## 取证与范围

- Runtime observation：固定官方 CC 2.1.267 的 inside Cron session `c15094ee-115f-4c30-9c2b-616d73e9c1fc` 到点创建 `cron-review.txt`，Write 无 classifier 请求，debug 记录 acceptEdits 放行。outside session `7261727b-1188-4666-b407-1e09639b8888` 的 Write 则进入 Terra 两阶段分类并被拒。主模型均为 Sol，审批均为 Terra；两个路径各一次，不代表统计误拒率或字节相同 A/B。
- CC 只读二进制：`/private/tmp/feat552-cc267-pinned/node_modules/@anthropic-ai/claude-code/bin/claude.exe`，SHA-256 `a681f3008f0050029aeebcab3af51bb6a55ddeb625a3af3141a4416d43cd2558`。Auto acceptEdits 模拟位于 bytes 165620800–165622500；Write/Edit `AA` 检查在 161923960–161926500，先处理 deny/ask 和安全检查，再以 `Mg` 检查工作目录；`Mg` 位于 161907949，检查所有路径拼写。
- 原始可复查报告：`/private/tmp/feat552-cc-write-comparison-20260912/README.md` 与 `evidence.json`。不提交软件 bundle、配置、运行日志或文件正文。官方旁证：[permission modes](https://code.claude.com/docs/en/permission-modes)。

此补漏覆盖 Nano 的普通工作区 write/edit，未声称移植 CC 的额外目录、linked-worktree 灰度、Plan/Workflow 专属文件豁免或 Windows 环境。Nano 既有敏感路径清单与其显式确认语义继续有效；实际解析目标也经过同一检查，以免新增放行路径绕过敏感文件。

## 实现与回归

Write/Edit 共用路径权限检查，通过现有 PermissionDecision 传递 acceptEdits 放行条件；gate 只在 Auto 中且已有 deny/ask 未拦截时消费该条件。目录外继续分类，Write 的文件存在性事实继续送入需要分类的动作。覆盖/编辑的读取与外部修改检查仍由工具执行体实施。

- 干净 venv 的改动前聚焦基线：115 passed。首次借用主 checkout venv 时因缺少 `tree_sitter` 无法收集，未当作产品失败。
- 新回归先取得 8 个有效失败：write/edit 的相对新建、既有文件、绝对路径均仍被分类器拒绝，以及两类符号链接敏感目标未走原敏感检查。
- 修复后同组：135 passed。通过已有 gate dispatch seam 验证相对/绝对、既有/新建、目录外、符号链接双向跨界、敏感目标、真实 cwd 与 Auto 开关；原存在性测试转为目录外目标。既有工具执行测试继续保护读取与外部改动检查。
- 代码和永久测试固定于 `b9a61941a`。本地 CI 的 remaining 分片 1943 passed；agent/PA 分片初跑 1869 passed / 1 failed，唯一失败来自未改动的 Gateway wire 测试读取个人 `~/.nanoassistant/skills/lark-apps/SKILL.md` 时文件短暂不可用。随后确认文件已存在，不修改产品或测试代码，复跑其所属文件 12 passed。保留该初跑失败，不将其混同权限回归或声称两分片首次全绿。
- Ruff check、全仓 format check、diff check、文档完整性检查通过。前端、依赖配置、策略资产及 wheel 打包配置相对已验证的 `ab80c695a` 未变，保留前轮对应验证，远端 CI 仍执行完整 required checks。
- 本机追加观察：`tempfile` 返回 `/var/...`，session root 则为 `/private/var/...`，初版路径拼写判断因此未提供免审条件。固定 CC 的 `Xp`（byte 161909096）明确归一 `/private/var/` 与 `/private/tmp/` 系统别名；Nano 同步此规则，真实解析目标仍必须在 root 内。2 个 macOS 用例先 Red，修复后同组 137 passed；Linux 因无相同系统别名跳过这两例。代码最终固定于 `1cf086696`。

## 历史证据有效性

先前 inside Write 的 classifier/fallback 轨迹只说明当时版本，不再代表本次补漏后的 ordinary workspace write。包括原 Cron 误拒与旧修复、Heartbeat/ordinary/child 的不可达审批写入对照：它们的请求来源、入口分流和故障语义证据仍可定位，但 inside 写入如今直接放行，不能沿用其 classifier 调用或拒绝结果作为当前行为断言。目录外分类、来源投影、非文件工具、计数与故障分流的机制和回归仍适用。新增真实 Cron 及目录外对照由本次增量验收独立记录。

## 最终真实入口与交付核对

[独立产品验收 Round 5](../acceptance.md) 在 `1cf086696` 的全新隔离 Gateway/IM 上验证：真实用户与实际 Write/Edit 使用自然 `/var/...` 路径，API workspace 为 `/private/var/...`。到点 session `sess_f1673d0a59f598f5` 实际新建、编辑并读回，完整窗口 5 次 Sol / 0 次 Terra；目录外 session `sess_3974ecf412b96e3f` 有 1 次 Terra S1，允许后实际创建文件。两个单次 Cron 均完成、结果送达，没有挑选样本或修改路径隐藏问题。

最终 jobs 为空、main idle、control_items 为空；独立验收确认 Gateway PID 2815、IM PID 2760 均已退出，57627 端口已关闭。较早 `b9a61941a` 的同类旅程另列 Round 4，两轮均清理，结果没有混标版本。

聚焦代码审查无存活 findings，实现对账与 corrected-delta 为 pass / aligned；新增 delta 已逐字归并到 canonical，kernel Tools and Hooks 共有 16 项 Requirement。最后代码之后的报告与契约同步不改变权限行为，已核对 main 仍为 `2fd84b9ac`。交付以原 PR #294 的最终 required CI 为准，不合并或部署。
