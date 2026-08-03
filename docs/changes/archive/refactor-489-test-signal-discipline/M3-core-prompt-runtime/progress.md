# refactor-489-M3 — Progress

## Baseline

- Claim: M3 派发范围在清理前全绿，后续失败可归因于本 milestone。
- Baseline: `origin/unit/refactor-489@8d6cfb3e8`。
- Method: 运行 `setopt null_glob; m3_tests=(tests/unit/agent tests/unit/test_{agent,core,loop,compaction,memory,session,jsonl_store,merge_adjacent,nested_memory,build_chat,prompting}_*.py tests/unit/test_curator.py); /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q "${m3_tests[@]}"`。首次 glob 范围 `840 passed`；orchestrator 澄清无后缀 `test_curator.py` 也归 M3 后，单独补跑该文件。
- Result: PASS，原范围 `840 passed in 11.67s`；`test_curator.py` `5 passed in 0.04s`，合计 845 个测试节点。
- Limit: 零用户面测试资产重构；无浏览器或 live runtime。

## R1 — 删除迁移终态与墓碑断言

- 状态: DONE
- Context: location/removed/tombstone 测试把 refactor-387、bugfix-355/417 的迁移终态固定成永久 CI；部分文件同时含真实 resolver、path、bash policy 与 foreground wiring 行为，不能整文件粗删。
- Decision: 删除纯模块位置、旧 root 缺失、退役 HTTP 与 ToolSafety 方法墓碑；把 skill resolver 改为 workspace 输入输出测试，保留 path/read、ShellRunner、bash allow/review/deny 和 Kernel foreground stopper 的现行行为。
- Rationale: 架构回归由 contract 直接检查依赖，运行风险由当前 seam 的行为测试保护；私有字段或旧目录不存在不再作为第二套迁移 contract。
- Evidence:
  - Tests: 删除前替代保护 `223 passed in 9.35s`；删除后定向组合 `149 passed in 9.12s`，ruff `All checks passed!`。
  - Entry: `test_cross_loop_streaming_receives_run_status_event` 经 `agent.sdk` 提交并消费 Event hub；skill resolver、read、bash policy 与 foreground stopper 均从当前调用入口验证输入输出。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: 相关 contract + unit 定向回归，命令见本段 Tests；无真实进程需求。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交；计划基点为 `dcd4b8b6d`。
- Commits: `b9b45e2ad`。
- Next: R2 收敛 prompt golden、片段措辞、feature registry skeleton 与重复 assembler 测试。

## R2 — 收敛 prompt 条件与消费者输入输出

- 状态: DONE
- Context: 旧套件同时冻结 M4 迁移过程、PromptContext/dataclass 形态、banner 字节、CC 改写片段和 feature registry 字典结构；相同运行风险已在 assembler、Kernel capability、metadata 与 consumer 路径重复覆盖。
- Decision: 删除 golden/legacy/no-order/字段存在快照与 registry skeleton 测试；把保护收敛为 assembler 顺序/gate/cache-safe/override、memory/user/AGENTS 三态输入、feature+tool 条件和 legacy prompt consumer I/O。删除 background/role prompt 的固定句子断言，保留 notification XML、tool deny 与 PromptSlotSeed 对象传递。
- Rationale: prompt 文案可独立演进，但能力条件、真实 runtime 输入是否进入模型、空态是否省略以及子 agent seed 是否原样传递仍是当前风险；输入 sentinel 与动态 section render 对比能保护这些风险而不把一段自然语言升级为协议。
- Evidence:
  - Tests: 删除前候选保护组合 `163 passed in 0.35s`；改写后 prompt/capability/metadata/subagent/memory 组合 `160 passed in 0.38s`；ruff `All checks passed!`。
  - Entry: `assemble_system_prompt`、`build_kernel_prompt_skeleton`、`build_prompt_messages`、`AgentTool.run` 与 Kernel capability/metadata 查询均从消费者入口验证。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: unit 定向回归；无真实进程需求。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交；R1 基点为 `b9b45e2ad`。
- Commits: `28113705a`。
- Next: R3 将 assistant 合并保护下沉到 `build_chat_messages` 公共消费入口、去除 MemoryStore 空态重复，并运行完整 M3 门禁。

## R3 — 合并 runtime/persistence 重复并完成门禁

- 状态: DONE
- Context: assistant history 合并由两个文件直接重复调用 `_merge_adjacent_assistant` / `_coalesce_assistant_group`；MemoryStore 同一空态和非空态在一个文件内各断言多次。
- Decision: 删除私有 adjacent helper 测试文件，把文本、tool calls、reasoning 与 group restore 风险统一改经 `build_chat_messages`；MemoryStore 合并为按 target 返回条目、双 target 空态与缺失 root 三项行为保护。
- Rationale: 模型真正消费的是 `build_chat_messages` 输出；公共入口同时覆盖 persisted `Message` 转换、group coalesce 与 adjacent merge，比私有 helper 形状更接近失效后果。MemoryStore 只需证明 target 隔离、空态和使用率，banner/三态由 prompt consumer 测试负责。
- Evidence:
  - Tests: 改写前 merge/persistence/memory/prompt 替代保护 `59 passed in 0.12s`；改写后同风险组合 `45 passed in 0.12s`。
  - Entry: `build_chat_messages` 验证相邻 assistant、tool 分隔与同 group 持久化行恢复；`MemoryStore.format_for_prompt` 验证 target 输入输出。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: M3 精确范围（显式包含 `test_curator.py`）`684 passed in 11.08s`；相关架构 contract `13 passed in 1.26s`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Gates:
  - Ruff: milestone 全部保留/新增 Python 文件 `All checks passed!`。
  - Docs: `documentation integrity passed: 192 maintained Markdown sources, 65 required routes`。
  - Diff/scope: `git diff --check` 与授权范围检查通过。
- Rollback: 回退本 roadpoint 提交；R2 基点为 `28113705a`。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: rebase 最新 unit、重跑 M3 精确范围后，在 unit lock 下合并并推送。

## Promotion Candidates

None.
