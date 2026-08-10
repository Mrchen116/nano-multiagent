# feat-532-M0 — Progress

## Baseline

- Claim: feat-532 M0 从未修改的 unit branch 开始，现有共享 suite 可作为绿色基线。
- Baseline: `unit/feat-532` at `29e8a8d1a743c4df5dd972f6efacf2bbe3451586`。
- Method: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q evals/spec_design_alignment/base_repo/tests`; `.../python evals/spec_design_alignment/validate_dataset.py`; `.../python scripts/docs_check.py`。
- Result: 共享 base 10 tests 与 docs-check 通过；dataset validator 在 baseline commit 已有 4 条 feat-397 断链错误：`evals/spec_design_alignment/README.md` 指向缺失的 `user-journey.md` / `user-profile-draft.md`，`experiments/feat_397_agent_team/protocol.md` 两处指向缺失的 `user-journey.md`。
- Baseline attribution: 两个报错 source 相对 `29e8a8d1a743c4df5dd972f6efacf2bbe3451586` 均 `git diff --quiet`（byte-identical），两个 target 在该 commit 的 `git cat-file -e` 均为不存在；本 milestone diff 不包含 feat-397 protocol/dataset。按范围不修改 feat-397 语义，也不夹带断链 side fix。
- Locator: 本 milestone plan 前的 worker command output。
- Limit: 尚未包含 feat-532 overlay 或任何真实 Codex pilot。

## R1 — Overlay 契约与确定性控制面

- Context: feat-397 的 H02 base 可复用，但它的 workflow/终点是 spec+design；M0 必须另建 spec-only overlay，并先把 provisional context、whole-lineage corpus exclusion、唯一 Skill closure、neutral repo 和封存身份变成可执行契约。
- Decision: 新建 feat-532 独立 overlay；复用共享 H02 materializer 后重写为无父历史 neutral/candidate projection，Candidate 只保留 `.agents/skills/change-spec-author`；匿名 corpus 用固定 seed 重排并只给 builder 暴露 opaque document/source locator，private receipt 单独保存真实来源；owner/judge context 使用不同 schema，所有资产固定 `formal_eligible=false`。
- Rationale: 共享 case/base 继续是单一事实来源，但 feat-397 protocol/dataset 零改动；投影和 hash 由 Python 控制面生成，不依赖 Agent 自觉隔离。
- Debug evidence: 首次真实 prepare 看似长期无输出；按 `systematic-debugging` 分层检查后，采样显示进程仍在共享 materializer 内持续 fork Git、对象数增长且 CPU 活跃。根因是正式 H02 物化要为约 4.5k 文件建立 byte-canonical Git objects，而最初基线的 10 个测试只使用小 fixture；并发启动的 pytest 又被 90 秒门禁中断后留下子进程，放大了“挂死”表象。物化完成后又准确暴露两份 legacy archive 没有当前四类首文档；根因是 corpus 枚举把旧 archive 目录误当成现行 change unit。新增红测后改为跳过无首文档 legacy 目录、仍对多个首文档 fail closed。没有增加 timeout/retry 或修改共享 materializer；永久测试改为最低层的快速投影契约，正式重物化留给一次 live/replay 证据。
- Evidence:
  - Tests: Red 为 runner 缺失导致 2 failed；Green 为 overlay 3 tests + shared base 10 tests，共 13 passed in 7.75s；Ruff 与 `git diff --check` 通过。共享 dataset validator 的 4 条 feat-397 baseline 断链单独记录于 Baseline，不归因给 overlay。
  - Entry: `runner.py prepare` 是确定性 CLI 入口；正式 H02 重物化和封存由 R4 live/replay 执行，R1 不把重外部依赖伪装成日常 unit test。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `evals/spec_design_alignment/experiments/feat_532_spec_memory/tests/test_pilot_control_plane.py` 保护 anonymous whole-lineage projection、single-Skill/parentless candidate projection 和 provisional schema/结论边界；真实 LLM E2E 由 R2-R4 durable pilot evidence 承担。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert R1 commit；共享 feat-397 资产未修改。
- Commits: R1 commit（本段同 commit）。
- Next: 实现 manifest-driven Codex adapter、一次 Memory build、direct-load consumption 与双 arm Candidate/Owner 持久会话。

## 2026-08-11 — R2 真实 CLI schema 联调

- Claim: 当前环境的隔离认证与真实 `codex exec` 可用；首次正式 builder 请求失败于 response-format schema 兼容性，而不是认证、模型生成或 corpus 规模。
- Evidence: 一次性 isolated-home 探针在补齐 `const/enum` 的显式 JSON type 后返回 `{"formal_eligible": false, "ready": true}`。首次正式 pilot 请求在 `thread.started` / `turn.started` 后收到 HTTP 400 `invalid_json_schema`，精确原因为 `source_refs.uniqueItems is not permitted`；未出现模型生成事件，runner 按零重试直接退出。
- Decision: 将所有真实角色的 output schema 收窄到 Codex Structured Outputs 支持的子集；原先的唯一性、格式、数量和非空约束转由同一 runner 在响应后 fail closed 校验。该失败 seal 与临时 workspace 删除后，从修订资产创建新 seal；不续跑失败 session，也不把失败样本冒充 pilot 结果。
- Safety: 诊断只记录错误类型和阶段，不保留 auth copy、session home 或完整失败会话。
- Second development seal: 修订后的 response schema 已通过真实单项探针；正式 builder 随后真实读取 196 份匿名首文档并完成一次生成（24 entries、所有 opaque source refs 有行号），但使用了 `mem-01..mem-24`，被 runner 的冻结 `M01..M24` 语义闸拒绝。根因是为兼容 Structured Outputs 移除 schema `pattern` 后，role prompt 没有承接 ID 格式约束。runner 未消费该 store、未启动 Candidate，也未续跑 session；补充明确格式指令后再次创建全新 seal。
- Third development seal: builder 一次生成与 provenance 校验通过，Baseline 的独立 Owner session 也真实初始化；首个 Candidate 读取完整单一 Skill、ground repo 后按 Skill 执行 `next_unit_id.py`，但 Codex `workspace-write` 默认将 `.git` 保护为只读，脚本向 Git common dir 原子预留编号时收到 `PermissionError`，Candidate 正确返回 `blocked`，runner 未启动 Treatment。根因是 Candidate 的合法 Git 写入需求与默认 metadata carve-out 冲突；最小修复是在两条 arm 创建后把 parentless `.git` 目录机械迁到 workspace 内非保护名并留下 `.git` pointer，两条 arm 相同、无额外历史、网络与 workspace 边界不变。
- Fourth development seal: 真实 gitdir 写探针通过，builder/provenance 与 Owner 初始化通过，Baseline Candidate 首轮成功创建 provisional 首文档并提出开放 Q1，Owner 直接使用 O01 回答；但 `codex exec resume` 的 OS cwd 仍沿用 runner 的 milestone worktree，Candidate 识别到 workspace 被切换且只读后返回 `blocked`。根因是 CLI resume 没有 `-C` 选项，runner 又未给 subprocess 显式设置 `cwd`。修复为每次初始/续轮都以角色 workspace 作为进程 cwd；并用 parentless repo 自己的 `.git/info/exclude` 排除 gitdir 与 `.experiment` 控制资产，防止进入 Candidate commit。
- Fifth development seal: 两轮 `pwd` 探针及正式 Candidate 证明 resume cwd 已保持；Baseline 完成三轮开放问答，但第四轮准备落盘时发现续轮 sandbox 为只读并返回 `blocked`。根因是 `codex exec resume` 同样没有 `-s` 参数，而 `--ignore-user-config` 下 resume 未继承首轮 CLI sandbox flag。修复为每个 invocation 都通过受支持的 `-c sandbox_mode="workspace-write|read-only"` 封存角色 sandbox，初始调用仍保留同值 `-s`；网络仍固定关闭。
- Sixth development seal: 两轮真实写探针与正式首轮证明 resume workspace-write 生效；builder/provenance 通过，Baseline Candidate 的开放 Q1 把 global/workspace 覆盖当成产品决定，Owner 用 O01/O07/O08 纠正 PA scope 并指出需查仓，但仍返回 `needs_real_owner`，runner 按 provisional 缺口 fail closed。现有 atom 已明确字段/实现形态委托 Author、仓库拓扑应自行查证，根因是 prompt 没拍死“可研究/可委托时先 redirect，不能升级为真实 Owner 缺口”。只修开放问答优先级，不新增 H02 truth/answer atom。
- Seventh development seal: builder、Baseline 四轮问答/Gate 1/commit/空 trace 均通过；Treatment 完成四轮开放问答后，把“无 Agent 级覆盖、无 Web UI”作为范围选择询问，Owner 可确认 O04/O06，但因 O07 的“implementation shape”没有显式覆盖新入口/覆盖层而返回 `needs_real_owner`。H02 既有 judge-only inventory 将 per-Agent override/new UI 归为 Candidate 应从 repo 和最小范围推导的 D07-D12，而非新增 owner answer；因此只扩展 provisional O07 的委托边界与 prompt redirect，未投影任何 judge truth 或 Candidate 本轮建议。
- Eighth development seal: 完整 27 次真实角色调用已运行至 Loop experimenter，两个 Candidate/Owner 持久 session、两次 audit、一次 batch audit、两次 burden scoring、两个 blind judge 和 next-scheme 均产生产物；deterministic projection 因 leakage checker 把 neutral repo 中合法的产品 `memory` 文件名误判为 arm signal 而得到 `infrastructure_fail`。角色 manifest 证明 judge 的实验 overlay 实际只有 public brief、两份匿名 conclusion 与 provisional judge context，未见 Memory、Q/A 或 trace；根因是 checker 对整个 neutral repo 做了模糊子串扫描，而不是检查控制 overlay 闭包。修复为严格禁止 `.agents/`、`.claude/`、`evals/` 并要求 `.experiment/` 精确等于四个获准文件，同时增加允许 neutral 产品 memory 路径、拒绝 task-memory/transcript 的单测。由于 runner hash 属于 seal，失败 seal 与 workspace 不复用，修后重新执行全新真实 seal。
- Ninth development seal: 全链 29 次真实角色调用完成，live deterministic projection 得到 `infrastructure_pass`，leakage 全绿、Owner auditor 无 critical error；两个 judge 分歧按预注册政策只记 `pilot_inconclusive_no_third_call`，没有效果结论。随后离线 replay 在读取已生成的 `next-scheme.json` 后触发 `AttributeError: 'dict' object has no attribute 'read_text'`：live path 已按 schema 校验输出，replay path 却把已加载对象传给只接受文件路径的 helper。增加 loaded-object schema 校验入口与回归测试；runner hash 已变化，因此该 seal 不作为最终证据，完整产物只用于定位后移入废纸篓，最终 seal 从零重跑。
- Tenth development seal: 27 次真实角色调用、live `infrastructure_pass` 与离线 `replay=verified` 均通过；仓库级 dataset validator 随后发现匿名 corpus 以 `.md` 搬到 evidence 目录后，其原文相对链接被当成当前权威文档检查，新增 7 条 broken-link 错误。根因不是 source 文档失效或 corpus 内容漂移，而是证据副本沿用了 Markdown 扩展名。匿名 corpus 改为内容等价的 opaque `.txt` 文件，builder/provenance 仍逐字读取并 hash，文档链接检查不再误收编搬家副本。另有 4 条 feat-397 既有断链在本 milestone baseline commit 已存在，本 milestone 不修改 feat-397 protocol/dataset；最终验证分别报告 overlay 归因与共享基线状态。

## Promotion Candidates

None.

## Round 1 independent-gate fixes — pre-seal implementation

- Context: unit head `30a2be4fb953f6a552c06ddc1883f4fb341ea925` 的 verifier/code-review 指出 role manifest 自证、Gate 1/corpus/result replay 与若干 semantic validation 缺口；任何 runner/seal/input 变化都必须废弃旧 bundle 并从零实跑。
- Decision: 执行层新增独立 macOS Seatbelt wrapper。每次调用前封存 expected；wrapper 对 host home、artifacts、parent/sibling/control workspace 和同一临时根的其他 entry 施加 `file-read*`/`file-write*` deny，在实际 subprocess 后独立写 actual attestation。Codex 的只读角色仍真实拥有 shell，因此 manifest 统一声明 `shell=true`，另以 `workspace_write` 区分写权限并记录实际 `command_execution_observed`。
- Decision: corpus 固定到 clean tracked `HEAD/tree` 并用 `git show` 读取 bytes；Gate 1 同时检查 clean status、base diff、初末 manifest 和 symlink；Owner refs 由加载的 atoms 推导；audit/judge/result/config 均 fail closed。
- Red evidence: 新增对抗/语义测试在旧实现上为 12 failed（缺少 OS confinement、Gate1/corpus/audit/judge/Owner helper，result/actual/config replay 未拒绝）；旧实现的 Ruff format 仍为 2 files `Would reformat`。
- Green evidence: 新 seal 前可独立完成的 focused/shared 门禁为 25 passed、4 replay cases deselected；canary 在 read-only 与 workspace-write 两种 profile 下均收到 OS `Operation not permitted`，Ruff check 与 diff-check 通过。4 个 replay cases 必须等新 durable bundle 生成后转绿，不能拿旧 bundle 验证新 runner。
- First Round 1 development seal: clean commit `1f5f2533955cb184feb9e89589de971a276f6e79` 上的首个真实调用 `memory-builder-01` 已在 Seatbelt 下完成，但 expected/actual 对账因 `scheme.json` 与嵌套 `documents/` 的遍历顺序不同而 fail closed。字段级比较证明唯一差异是相同 path/hash 集合的顺序；新增对应目录形态的红测后，将独立 wrapper 输出统一按相对路径 canonical sort。失败 bundle 未继续运行、不得作为修后证据。
- Scope: 未修改 feat-397 protocol/dataset/shared H02 truth；原 baseline commit 与 4 条既有断链归因保持不变。
- Next: 提交 runner/schema/prompt/tests，使 source worktree clean；向独立临时 artifacts 从零运行新 seal，替换旧结果并完成 R7。

## R2-R4 — 最终真实 Pilot、独立评价与重放

- Final seal: `feat-532-h02-infrastructure-pilot-v1`；H02，`1 case × 1 repeat`，`formal_eligible=false`，`effect_claim=null`，结论 `infrastructure_pass`。seal SHA-256 为 `1439a797cd1982e50037df786634e907629ece78cd8d01a0ed39f904b9ddd270`，evidence manifest SHA-256 为 `fac6adc449d20c234d2dae9a620a010c8a0f673db5f8740fb18da82b298b0ee1`。
- Memory: 196 份 allowed first-document 被固定 seed 匿名投影；唯一一次真实 builder 产出 24 条 `M01..M24`，全部 source ref 有 opaque locator/行号且 provenance 闭合。Treatment direct-load 后逐条 trace 为 used 3、loaded 7、rejected 13、overridden 1；Baseline 保持空 trace。
- Native dialogue: Baseline 使用 1 个 Candidate session（5 次真实 invocation）+ 1 个 Owner session（初始化后 4 次开放回复）；Treatment 使用另一组独立 session（4 次 Candidate invocation、初始化后 3 次 Owner 回复）。两条 arm 的初始文件/hash 机械比较只有 `.experiment/task-memory.md` 差异；两者均由 Candidate 自己通过 Gate 1 并提交唯一首文档。
- Independent evaluation: 2 次 run audit 与 1 次 batch audit 均 `critical_error=false`；两份 burden 分别为 5/7 contribution units；neutral repo 上 2 个 blind judge 均完成。judge 的逐项 rating 有差异，按 pilot 预注册政策只记录 `judge_disagreement=true` / `pilot_inconclusive_no_third_call`，不追加第三位 judge，也不形成方案优劣结论。
- Loop: 真实 Loop experimenter 生成 `relevance-gated-first-docs-v1`，提议从 broad direct-load 改为 applicability-gated selection，并保留现有 task-blind、跨 case、source-located extraction；runner 对禁止 case-specific atoms 扫描通过。
- Isolation: 29 份 role invocation 均有真实 Codex receipt、expected/actual visible files、input envelope hash、独立临时 HOME/CODEX_HOME 与 network-off sandbox；leakage checker 检查 29 份 manifest，`findings=[]`。最终 bundle 未保留 `auth.json`、host config/history、sqlite session、临时 role home 或 runtime marker；临时 workspace 已移入 macOS 废纸篓。
- Replay: `runner.py replay --artifacts .../h02-pilot-v1` 返回 `replay=verified`、`role_invocations=29`、`conclusion=infrastructure_pass`，未调用模型。
- Shared validator boundary: `.txt` corpus 后 overlay 不再新增 broken-link 错误；`validate_dataset.py` 只剩与 baseline 完全相同的 4 条 feat-397 断链。focused overlay/shared tests、replay、docs-check、Ruff、compile 与 diff-check 通过。
- Scope: `git diff --name-only unit/feat-532...HEAD` 与最终未提交清单均未包含 `evals/spec_design_alignment/protocols/feat_397_agent_team/`、共享 `dataset.json` 或共享 H02 private truth；feat-397 继续由既有 validator/base tests 保护。
