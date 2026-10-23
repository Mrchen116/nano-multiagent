# M1 实施与验证

## 授权与工作区

2026-10-23，用户在已知 Gate 2 尚未完成独立复审的情况下明确要求“可以做了，直接做吧”。据此实施，不将设计审查改为 Approved。

唯一 worktree：`.worktrees/unit-feat-637`；分支：`unit/feat-637`；基线：`5462b7217421a2c27871c1c5951c1e48644e54ba`。只复制本 unit 文档。主 checkout 的已有 dirty/untracked 内容未改。本侧对话未使用 subagent。

## 实现

- 按 prompt-map 复用固定 Hermes 段落；移除更新配额，补充证据、用户约束、临时资源归属与清理条件。前台与后台采用一致质量要求，保留单操作协议。
- 两类到期只启动一个 combined fork，分别计算周期和前台维护重置点。
- 根据本轮原生 read 的实际返回登记完整原文件，支持稳定版本分页。已有 Skill 写入在锁内比对；确认成功后推进已知基线。skill 正文、未读全、读后变化不能取得修改资格。
- Memory 写入前读当前两份文件。明确不存在可按空处理；拒绝读取不可按空处理。不完整 Memory 读取使整个 combined 不结算，保留已成功的 Skill 写入。
- F4 限非 Global、自动来源及两个不同合格会话；只允许绑定目标 patch。接受时扣冻结用量，保留后续使用；成功后记录证据去重。
- combined 贯通 launch、持久记录、公开 trajectory schema 和两处用途显示，显示“记忆与技能复盘”。

## 测试策略与结果

- `knowledge.test.ts`：保留原有写入/来源/确定性扫描保护；将旧 Global 单会话 F4 正向预期改为禁止触发；验证冻结计数后新增使用不丢失。
- `knowledge-policy.test.ts`：保留快照与周期测试；通过真实文件写入接口验证完整读取、分页、内容变化、连续 patch、支持文件和读取拒绝。
- `knowledge-review.test.ts`：新增维护生命周期 owner，使用锁定 DSH 子进程和模型 fixture，覆盖 combined 单 fork/冷恢复、两会话 F4、Memory 未读全时部分成功和周期重试。
- `navigation.test.ts`：扩展既有显示测试，不创建平行 UI 套件。
- TDD：旧实现产生两个 review，combined 测试预期一个并失败；修改后通过。
- Node 24.22.1：全量 `pnpm exec vitest run --maxWorkers=1`，122 文件、581 项通过（459.79 秒）。首次并行执行曾因 ENOSPC 失败，保留失败记录；串行结果是后续成功证据。
- 最后两处测试断言调整后，定向两个文件 9 项通过。此前相关六文件 22 项通过。
- 前端独立 `npm run build` 和 `npm test -- --run` 通过：103 文件、963 项；构建仅报告既有 bundle size 提示。
- 全仓 build/typecheck、Python 非 E2E（65 passed，31 deselected）、docs-check、ruff check/format、git diff --check 通过。

## 真实模型证据

隔离目录由 `/tmp/feat637-e2e-path` 指向。IM 端口 59794；只操作本次 IM/Node/DSH。真实模型为 `deepseek:deepseek-v4-flash`。原始轨迹、凭据和数据库不提交。

会话 `c_lk4sglet`；主 session `108a72f2-1bb5-4ade-b3d6-429baa1037ba`。

1. 无增量输入 `eb097a1f62064486866726bc2edd58e0`：实际回复 READY；combined review `faaa5d49-6c40-4b80-8a4c-c7e543ccd7b9` completed，无知识写入。
2. CSV 修正输入 `e8871a259e7342ed860f4d795e2fdf9f`：实际执行 csv.reader，确认含引号换行的样本有两条数据记录。combined review `ea11cd6c-12fb-44ff-8fb0-151fec30ccc2` 保存跨任务偏好至 USER.md；Skill 修改被已有审批器模型档位配置阻塞。通知 `42e087350c9042cb872ae522bab01332` 只报告 memory。
3. 审批器为 deepseek-v4-flash 请求不支持的 low 档位。仅在隔离配置指定 codexOAuth:gpt-6.1-sol 审批模型并重启测试 Node。未改产品审批代码或生产配置。
4. 复验输入 `814791a6b71d4c3a8cd13f551bcdd2bd`；combined review `39fa2bda-6af4-4dea-ac04-1a2f2d4123ca` completed。csv-audit 原文件中的 wc -l 步骤被原位改为 csv.reader，保留只读输入约束；USER.md 未重复追加。通知 `b11085647f484fde8fd365f21a6db863` 只报告 skills。

5. 双写输入 `58b12d0f635641bfa28428b08121b3f2`；combined review `76333af5-0f77-4011-83db-01d84a429f3f` completed。USER.md 原位补充简体中文偏好；csv-audit 增加仅汇报数量和表头处理、不输出字段值的任务规则。Web IM 显示 “Background self-evolution: skills and memory updated”。
6. Global 会话 `c_qm9tt0v4`，输入 `f696d3de460846a0b5d033fb2ab6d2d9`；combined review `511de1a0-b6f3-4646-bb30-9b19231108fd` completed，子 session `156655b5-f7b1-4aeb-a446-312b439c8c1c`。真实 read 确认两份 Memory 不存在，读取 Skill 原文件；随后 memory add 和 skill_manage patch 均成功。原生轨迹显示“记忆与技能复盘”，进入后范围为 #43 → #77。浏览器刷新后父轨迹的同次入口仍存在，可重入相同范围。现有栈内导航不把子执行写入地址，刷新直接回到父执行；不把本结果写成自动恢复子执行。截图保存在 `/tmp/feat637-combined-trajectory.png`。

这些案例证明无增量、部分成功通知、后续修正、不重复保存和 ordinary/Global combined 双写。它们不代替 spec 全部 21 场景或独立产品审查。F4 硬边界由原生 DSH fixture 验证，不声称真实模型 F4 已验收。

## 清理

本次 `e2e-down.sh` 已返回 STOPPED。端口 59794 无监听，按本次隔离路径检查无剩余 Node/DSH 进程，测试浏览器已关闭。原始本地证据保留在隔离目录，不提交。唯一 worktree 保留，供后续独立审查使用。

## 交付边界

尚未完成独立 code review、verification 和产品 review；本侧对话禁止 subagent，不把作者检查记为独立门禁。尚不归档，不覆盖 current specs，不声称 Ready PR 或部署完成。feat-638 内容整理不在本次范围。
