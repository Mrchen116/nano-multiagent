# M1 实施与验证记录

## 实施基线与职责

- 2026-10-25：用户授权按已讨论的真实场景方案实施并交付。基线 `origin/main` / `8e4054197`，Gate 2 Round 4 Approved、0 CRITICAL / 0 WARNING；从受审基线至此只有文档变化，不使代码 grounding 失效。
- 专属 checkout：`.worktrees/unit-feat-658`，分支 `unit/feat-658`；主 checkout 保持原状。
- 主 Agent：IM/PA 代表发送事务、原始证据/relay/历史传递、集成与最终交付。
- 首轮独立切片：ComposeMessage 和双端消息/输入框体验；运行时发送工具与上下文/审核适配。共享文件分工明确；后续门禁发现由主 Agent 修复。

## 用户确认的真实验收方法

此处细化 design 既有 runbook 的实施方法，不改变接口、需求范围、M1 或既有门禁；设计结论 retained。

1. **真实委托 → 真执行 → 联系 PA**：daily 栈中 Q 实际准备测试 Git 报告；主人只用自然语言在 PA 私聊委托回复，禁止提示工具名或人工伪造来源。PA 读取上下文、代表发送；Q 经正常审核提交推送隔离仓库而不合并/部署、不重复索权。之后主人要求直接联系 PA，Q 用来源 ID 定位且真实发到正确 PA。核心旅程三次独立自然表述，至少一次含已有聊天历史；保存首次结果/重复确认次数/失败原因，不能挑成功样例。
2. **普通 Agent/PA 起草 → 编辑采用 → 手动发送**：只自然要求草稿，不提示动作名。编辑后采用须只填指定目标输入框，无消息/模型运行；手动发送后接收者收到最终文字并遵守修改后的范围。Web/iOS 各实际一次，涵盖取消/替换已有草稿、无权限保留编辑；ToAssistant 另行提交本会话请求。
3. **已有任务恢复与子 Agent**：同一任务先完成一个步骤，经产品支持路径恢复节点/会话，再读取原消息、交给子 Agent完成剩余步骤；原范围/PA ID保持，已完成步骤不重做，用户后续暂停时收敛。
4. 边界对照：自身报告仍为 Agent；PA 非成员不能用普通发送但真实委托可代表主人；普通 Agent 自称批准/超范围动作不获额外许可。

证据同时记录用户可见结果、实际模型 context/工具参数/审核材料、消息和接收者 ID/Git commit+ref/真实运行副作用。模型 context 覆盖普通/PA/SingleThread、恢复/子 Agent和两种审核输入；接口手工调用只承担低层边界检查，不能替代自然模型旅程。所有验收使用隔离 daily、测试身份和测试仓库，不使用生产聊天或真实项目。

## 测试策略与进展

- 实施中按最低有效 seam 扩展已有 personal-disclosure/personal-sources/personal-assistant、Inbox/source-provenance、interactive 和客户端测试，优先合并/改写旧 reply_draft 路径覆盖；具体命令与结果随实际执行追加。
- 当前：开始实施，尚无功能通过或产品验收结论。


## 服务端与编排实施（2026-10-25）

- 已新增有意义的失败复现：owner 发送仍是 Agent 作者、self 发送放过非成员；实现后 identity/event/authorization/idempotency 两项通过。
- frozen payload 写明 self/owner，服务端 prepare 与 commit 核验所选作者当前权限；owner provenance 在 card record / message.created 之前入库，原生用户 relay 排除实际 PA。
- 用户身份与卡片 executor 分离；退出会话使卡片不可用并使许可失效，重新加入仍须重新审核。对应三项 representation 场景通过。
- Inbox、历史、SingleThread input 保存 pa_agent_id；代表消息不进入主人授权/guard，也不触发 slash 控制命令。旧 reply_draft 参数明确拒绝，新旧数据库历史不回填。
- 服务端/PA 首轮 57 文件 414 测试中 411 通过，三个失败为已变更成员资格 fixture 与迁移 fixture 缺列；相关 fixture 修正后 personal-agent 17 项通过，迁移/PA/Inbox/control 合计 33 项通过。无需因此重复无关测试。
- 新迁移 CLI 支持 dry-run/apply/verify，后者对照停流量前的数据库副本校验消息、旧操作、事件、relay 与草稿记录完整不变；自动化覆盖重复执行、旧列 NULL 和修改历史后 verify 失败。
- 真实模型/真实 Web、iOS 连续旅程尚未执行；上述测试不替代 V1–V4 产品证据。


### 真实旅程 A 首次失败（保留）

- daily node `wt-unit-feat-658-74505`，主人 Web 原话消息 `630493e593d94f30bb970a1ef7625d4c`；审核 operation `11aa962a-1a0b-4bb3-906c-085fa41ac234` allow，代发消息 `1a1c4efc89b2466aa0603b7eebbd84c3` 确认为用户作者与实际 PA 来源。
- 失败点：正文仅“Q，请…”；relay 的 mentioned_agent_ids 为空，mention_only 的 Q 未被唤醒。不能将“已发送”计作端到端成功。
- 修复：在两个工具共享的 target/text schema 中明确先查实际成员 user_id、按现有正式 mention 语法点名。没有更改群注意力策略或审核门禁；本地完整证据 `/Users/czj/.codex/reports/feat658-acceptance/journey-a-first-attempt.md`。


### 本地完整验证与独立静态 Round 1

- `pnpm build` 与 `pnpm typecheck`、`pnpm check:ios-runtime` 通过；Node v24.22.1。
- `pnpm exec vitest run --maxWorkers=2`：134 files / 717 tests 通过；`npm --prefix src/IM/frontend run test -- --maxWorkers=2`：107 files / 1025 tests 通过。
- `pytest -m 'not e2e' -q`：70 passed / 32 deselected；`ruff check .` 与 `ruff format --check .` 通过。输出保留 `/tmp/feat658-{full-tests,full-frontend,pytest,ruff-check,ruff-format}.log`，归档前另存报告目录。
- 独立 static reviewer 对 `3689a8b84` 完整 review，确认 historical sender.kind/type 差异和模型卡片投影保留 wire 常量两项。主 Agent 先把 fixture 改为真实 read/search shape 并加入 41 后续工具记录，两个窄测试均真实失败；修复后 approval-sources + personal-sources 23 项全过，IM/integration 重建通过。未改公开客户端 wire 协议。
- iOS 本轮独立模拟器 `1E3643A5-F66C-46FB-818B-9A37871A7DC9`；build 成功。原生人工式 UI 验收当前受 Mac 锁屏阻断，已向用户请求解锁；不以浏览器截图代替原生截图。

### 真实模型 B/C、恢复及迁移证据

- 本地完整日志已保存 `/Users/czj/.codex/reports/feat658-acceptance/`。iOS `build.sh test` 完整通过，`build.sh archive` 无签名 Release 归档成功；专用模拟器与构建根 `/tmp/nano-ios-feat658-compose`。原生 UI 仍待 Mac 解锁，不将自动化测试当作原生旅程通过。
- B：主人自然请求 `c0ae9c3ba9d847c5b2dbf5cb2475cce3` → PA 正式 @ 的用户代发 `bb1ad1d86a474674ae5e06c280179b12` → Q 经 Codex Auto 正常审核，仅新增 review-b.md，真实提交/本机 origin main `18bed6d8903a144aa6718a8637fba2901eb87f78`。无重复主人批准；Q 群回执 `40cc680c7f3d4329964c2b319d6af3c4`，PA 独立核对后回报 `09212bc6d780420883be622ebd94e969`。review-a 文件不存在，暂停有效。
- 20:41 在保留同一 DB、workspace、node identity、会话与 Git 状态的条件下重启本次 IM/Node 至 `9c5aecd55`（产品代码 `abdf2afc7`，后者以来仅测试），Node ready/connected。后续 Q 同 session `1db9a6a4-6c94-4080-9a3b-79f8c7d47c19` 继续，B 已完成提交未重做。
- C：主人已有历史上的自然追加 `c9309fb2de3b426db592881b6f2f74da` → 用户代发 `9c2f85cba1f74c6ea59d08b81bd409ba` → Q 仅新增 review-c.md，提交/本机 origin `c47c03e7605fd25a768e3cdfec3335c6020cb41b`；B 的 blob 与父提交一致。Q 通过 `agent:pa_8b3969af44b2` 实际发送 `524e64c69b6d4947bba19bdb0ac78ba9`，目标直聊 `c_s1q2jv7s`。PA 核对后于 `6a7ba13f33104a179eac463a1bf66d25` 回报。收件人 ID 与原始代发 PA 一致；该模型也把 PA ID 写在公开正文，因此不把这次声称为“仅凭 metadata 定位”的实验。
- D：已发起独立自然表述 `797eddc60054403489a79df9fe76d7c6`，要求回看原群历史、由执行助手新增 review-d.md、保持 B/C 和暂停 A、Q 核对后经 PA 汇报。代发 `c2a5165e69b843ac972241c87dffe1ba`；最终结果待验证，不能计入成功次数。
- 实际 Q model 请求、重启后请求及 Codex reviewer 输入已保存 `real-contexts/`，并移除 replayed thinking block；真实 sender/pa_agent_id/原文范围保留。`journey-b-q-work-items.json` 与 `journey-b-q-audit.json` 关联实际 commit/push call id，审核明确基于用户原授权放行。普通/PA/SingleThread/child 与 CC 的完整注入矩阵仍参考 runtime-context 的真实 DSH + synthetic provider 样本，不能将其混写成真实模型执行。
- 文件库副本演练 `migration/results.json`：使用基线 schema 和明确标注的 synthetic 旧业务行，真实 CLI dry-run → apply → verify → apply → verify 全部 exit 0；旧库启动被 migration guard 拒绝，迁移后启动成功；messages=1 / operations=3（prepared/allowed/confirmed）/ delegation=1 / event=1 / relay=1 / draft=1 全保留，旧 provenance NULL。不是生产数据库演练，未触碰生产。
- 新增旧 payload 缺 representation 的 confirmed 重试与身份冲突回归，迁移/representation 7 tests 通过；`docs-check` 在项目 Python 环境通过（291 sources / 67 required routes）。版本协调由部署提示词规定停流量后统一升级，未进行生产或旧客户端混跑。
