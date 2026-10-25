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

### D 完成、证据边界与同步

- D 真正完成：执行助手 `d259d74a-bbb7-4c4c-ba0d-144c12eedd26` 只创建 review-d.md，Q 独立读取并检查后提交/推送 `d6082fff53ddb71054e97f709c8ac89d98f48c87`；本机 origin main 同值，工作区干净，B/C blob 未变、A 文件不存在。Q 对实际 PA 发送结果 `c34800c3011d41f09e2a60ec3f0ed34a`。因此修正后 B/C/D 三次独立自然表述的执行均成功，A 首次失败不被删除或改称成功。
- Q 实际通过 conversations.read(limit=50) 重读原群消息；`journey-final-q-work-items.json`、`journey-final-q-child-work-items.json`、audit 和 Git 证据可复查。执行子 Agent 的任务正文是父 Agent 摘要，不冒称其模型输入复制全部聊天；实际子 Agent 独立审核 `real-contexts/q-child-review.json` 保留原 message id `c2a5165e69b843ac972241c87dffe1ba`、用户 `u_c3ibn6j3`、PA ID 与完整原范围，未仅凭父摘要扩权。
- 独立产品 reviewer 已核普通 E Compose 最新编辑、只填稿、冲突取消/替换、同会话、无权限保留值及 ToAssistant 独立提交；最终 verdict 和剩余必验场景以其 acceptance 报告为准。
- 相邻既有现象：B 查看普通 owner↔B 私聊时标题仍是创建者保存的 B 名字；消息本身双方身份正确。DB `c_hlsapj1c.title=独立验收成员乙`，`title_is_custom=0`，`creator_id=u_c3ibn6j3`；基线与当前 Messaging.conversation 的共享 title 投影、Web 联系人创建 title 和 header 读取逻辑均未改。不在 feat-658 扩大修改私聊标题契约；独立 reviewer 保留体验判断。
- 同步 `origin/main=b4ea8f908` 到 `8a010ff834fe5b61919b78360698cf802608487d`。上游增量只有 feat-659 设计及审查文档三文件，无产品/测试/共享契约变化；本次既有代码测试、模型服务与 UI 构建结论 retained，实际执行版本不冒写为 merge head。最终门禁有效范围由独立报告明确。

### 附件复验与最终主干同步

- 产品独立 R1 保留两次附件失败：本地路径没有可用上传工具；主人真实上传后，PA 仍未识别已有原生附件引用转发方式。`cfba1fcd3` 只补固定指导，说明已有 Markdown 原生资源引用、完整披露审核、目标资源复制与不可读时拒绝；不新增工具参数或上传协议。独立 static R3 0 findings，disclosure 17 tests 通过。
- 主 Agent 用自然语言请求 `e1f6b09c8b55406c86885ffce77cdbcd` 后，PA 经真实审核 operation `dcb44009-1f9a-4084-b8c7-58e509387496` 向双方群发布用户身份消息 `dccfb651265943058949b30fbff31a48`。主 Agent 以 B 的 Web 身份点击并下载目标附件，与原文件同为 6920 bytes / SHA-256 `0a71418241a758f20131db59191ad7601b4c50d21f90696e5bf4b7c02e9158e1`。可见标签为 review-b.md，下载默认名为 attachment.md；不声称下载文件名原样保留。独立 reviewer 核对 B target 200、source 404 和字节一致。
- 用户已解锁 Mac；独立原生验收通过身份和 Compose 主要场景，但实际点击资源 Markdown 链接跳至 Safari 后因缺授权失败。主 Agent 修复：识别同源 conversation attachment 链接，复用既有 AttachmentView 的登录态下载与原生预览；外站链接保留普通处理。原始失败与后续通过分别记录，不以 Web 通过替代原生结果。
- 最终 fetch 发现 `origin/main=1219d903b` 已合入 feat-657 生命周期/运行时隔离和 feat-659 Context 工程规范。合并为 `7e67ccc7e`：PersonalActions.validate 保留生命周期校验并调用本 unit 的 destination 权限检查；Submit.source 合并生命周期版本与 sender/pa_agent_id。其它相关自动合并由独立 reviewer 局部复核；不以“无冲突”或原版本产品通过替代最终集成判断。
- 合并后首轮窄验 6 files / 54 tests 通过；完整 build/typecheck、Web 108 files / 1031 tests、Python 70 tests 通过。后端完整检查出现超时，根因仍在调查；集成版真实运行仍待完成。Web npm audit 的 critical 门禁 exit 0，现有依赖有 11 项非 critical 报告（4 low / 2 moderate / 5 high），本 unit 未改依赖版本。

### 集成复验进展

- 原生修复提交 `8b517546d`；XCTest 46 项与 Swift Testing 25 项通过，Markdown 3 项覆盖同源资源、外站链接及原有富文本顺序；Release archive 成功。独立产品 R4 实际以 B 打开原生报告预览、验证身份及 Compose 本地行为后关闭 G4，其余已通过项 retained。
- 后端首轮 141 files / 756 tests 中 752 pass，4 个失败均为时间预算内未完成。首轮与构建、Web 测试并发，不作为最终全绿结论；构建全部结束后，同码、单 worker 对 4 文件串行复验，12/12 pass（160.68s），没有修改产品或放宽测试超时。首轮日志与复验均保留；只据此说未稳定复现，不宣称已证明唯一负载根因。
- 新主干 runtime migration 的 plan 对旧日常验收数据报 workspace domain、preview/reviewer session 与 schedule 归属 blocker，未执行 apply。完整旧 runtime / IM 已备份到本地 `pre-final-sync-backup`，旧 Node 停止，旧消息库仅重启新版 IM 供原生读/采用验收。本 unit 的 PA 数据列迁移副本演练仍有效；不把新主干运行时迁移写成通过，部署包含该主干时需单独处理该迁移问题。
- 集成执行另用官方 `--profile daily --wt .e2e-final-integration` 新实例，独立端口 49803、node identity、home、workspace 和数据库。自然请求 `7f8985ec34f84a90a17a81d306405a61` → owner 代发 `1e77adad641b4d038bda8cefaeb20c84` → Q 正常审核真实提交 `04420a5a8e42d266bb0f3a34d42fb263a58da945`，仅新增 final-integration.md，原三份模板文件未修改；Q 实际联系正确 PA，PA 核查后说明未推送。
- 此新实例起初遗漏前一实例已保存的“仅允许本机测试 origin”配置增量，daily 默认禁推送生效，因此保留首次 partial 结果，不将其计作一次授权 push 通过；按同一获准验收范围补入 Q/PA 配置后，以自然续办要求仅推送已有提交、不改文件或重复 commit，结果另行核对。真实 Q/PA provider 请求与 Q Codex review 已保留 `final-integration-contexts/`，Q 无 send_user_message，根 PA 有该工具，收到的原用户/PA/message/限制完整。
- 续办最终完成：Q 向正确 PA 的实收回执 `3cb1efe6ed364dd7b69bb263340bb008`；PA 核实后向主人回报 `0165f8e6401641e781001cadce2a3b8c`。主 Agent 真实 Web 查看并保存截图，独立产品 R5 以正式 API/Git/本机远端复核后最终 pass；HEAD 与 origin/main 同为 `04420a5a8e42d266bb0f3a34d42fb263a58da945`，相对初始化仅一个业务提交、仅新增 final-integration.md。
- 最终再次 fetch，origin/main 仍为 `1219d903b`，无新增上游差异。两套本轮测试栈与专用模拟器已停止，49303/49803 无 listener，无本 worktree 遗留进程；原数据、迁移拒绝报告、备份、上下文与截图保留在本地。开发 worktree 保留供 PR 审查，不部署、不发布安装包。
