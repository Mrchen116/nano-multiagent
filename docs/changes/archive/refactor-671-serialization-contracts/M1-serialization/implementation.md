# 实施与验证记录

## 兼容基线

字节与合成信封在产品代码修改前由 a34af8473 的原实现生成。可提交固定向量在 contracts serialization 测试、IM configuration/identity/message-attempts 测试、Workflow 历史 replay 测试和 Channels `tests/fixtures/credential-envelopes-v1.json`。fixture 私钥仅为本次离线生成的测试材料，从未用于账号/服务；无生产数据。旧实现脚本和原报告副本保留在本 worktree ignored `output/refactor-671/`，不作为运行依赖。

固定序列化覆盖中文、emoji、DEL/U+0080/U+2028、孤立代理项、组合字符、非 ASCII 与数字索引键、嵌套数组/对象；另核对 missing/null 与原 traversal 差异。配置摘要明确保留 DEL 的既有差异，不声称修复当前协议。旧 IM/Node 信封均由实际 ChannelKey 解封；新 IM seal 既经 ChannelKey 又用固定 AAD/明文字节独立解密，防止 JSON.parse 隐藏转义漂移。Workflow 使用旧 key 重放完成结果，不以新算法生成 expected。

## 测试资产处置

- keep：现有配置 pre-strategy receipt 恢复、Task/迁移、device-binding、Channels revision/owner 拒绝与其他幂等测试，测试中旧名称随生产入口更新。
- extend：上述已有 owner 测试增加固定历史字节/摘要/信封或 replay 输入。
- new：contracts serialization.test.ts 为新公开纯字节 seam 的最低层固定向量；不新建跨层通用测试框架。
- 删除的仅为无消费者的 interactive canonicalJson 实现，没有删除有效测试。

## 已执行

- 改动前基线：Node 24.22.1，4 文件 14 tests passed。
- 初次实现：Node 24.22.1，contracts build、IM typecheck 通过；8 文件 56 tests passed，见本地 `output/refactor-671/narrow-tests.log`。

## 集成边界

从 a34af8473 开始隔离工作；该本地主干的两笔尚未在 origin/main 的文档提交不属于本 PR，实施完成后仅把本 unit 提交 rebase 到远端 main。原报告副本仍在本地工作现场，固定向量保留其原始代码基线。原报告不回写。

另一聊天的 IM 类型职责重构可能与本 PR 在 channels/control/gateway/identity/task-graphs 的 import 或签名附近相交；本任务仅修改 serializer 定义、名称/导入/调用，不改 Row/ImContext 或领域接口。需要保留另一任务的类型改动，同时保留这里选定的字节 encoder。

## 最终本地检查（源码 8289e5634 / base ff326c351）

- Node 24.22.1 / pnpm 11.7.0；`pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime` 全部退出 0。build 只生成本地 installer candidate，未发布。
- `pnpm exec vitest run --maxWorkers=2`：144 files / 780 tests passed，369.22s，exit 0，完整测试集合；日志 `output/refactor-671/backend-controlled.log`。
- 默认 `pnpm test` 在高并发现场出现多项 native 测试超时，主动中止（exit 130），保留 `backend-tests.log`。最先失败的四个文件以单 worker 原样重跑：4 files / 22 tests passed，110.50s，exit 0，`isolation-tests.log`。完整重跑仅限制 worker 数，未调整任何断言、超时或源码。现场负载采样曾为 49.85，其他工作也在测试；这支持资源竞争解释，但不声称已证明所有超时的唯一根因。
- Python 非 E2E：100 passed / 28 deselected，62.69s，`python-tests.log`。
- Frontend：108 files / 1029 tests passed，89.11s，`frontend-tests.log`；audit critical 门槛退出 0，仍有原依赖的 11 项非 critical 漏洞（5 high），本次无依赖/lockfile 修改。
- `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check`：285 maintained Markdown / 68 required routes passed；ruff check 与 format --check 通过（91 files）。首次系统 Python 缺 yaml，使用已有 dev .venv 后完成，不改依赖文件。
- 独立静态审查：8 files / 56 tests、架构 13 tests、4 个旧函数 × 12 输入直接比对与 5 个捕获值核对全部通过，详见 code-review/verification。

## 门禁有效性与收尾

设计实际验证 a55c9b999 / 执行基线 a34af8473；实现/静态验证实际树 8289e5634 / 执行基线 ff326c351。设计后仅修正文档 `workflow/engine.ts` 来源路径；main 增量未改变原编码算法、AAD 或摘要投影，静态审查在最新基线上完整核对。因此 Gate 2 retained，静态门禁适用最终产品树；最后同步 origin/main 仍为 ff326c351。

`no spec delta` 已由独立 verifier 核对，无 current spec 归并。后续仅提交门禁报告、该记录及 unit 整体归档，无产品/测试变更；保留独立审查结论，不重跑已通过测试。最终 PR 明列各门禁 validated_at/executed_base 和 effective_base/effective_through，后者包含归档提交。

测试清理：最终全量完成后发现最初失败/中断运行遗留的 10 个 DSH 子进程；逐一核实 executable 来自本 worktree 且 cwd 为测试临时目录后发送 SIGTERM。未触碰其他 worktree 或生产服务；测试日志/证据保留。
