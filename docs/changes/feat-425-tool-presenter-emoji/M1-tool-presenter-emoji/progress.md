# feat-425-M1 progress

## 启动说明

- milestone worktree 从 `unit/feat-425`(dd4b4a57)切出,基线绿后开工。
- 单 M1:跨包但一条内聚的展示链路垂直改动(< 800 行),不拆(design §Milestones)。

---

### R1 — C1 红测:emoji 全链路 + web_fetch/web_search presenter + 字段修复

- Context: 走 TDD 先红。emoji 复用 feat-409 的 detail 透传链(增量极小),web_fetch/web_search
  的 presenter 与字段是新行为。现有 golden(`test_presentation_golden.py`)断言 `(visible,label,
  summary,detail)` 四元组,加 emoji 字段后需扩成五元组;现有 `test_presentation.py` 的 web_fetch
  断言基于旧行为(折叠 `status=200 (title)`、读 title),要按决策 4 改写。
- Decision: 新增/改写测试覆盖六处落点 —— core emoji 字段 + `_presentation_dict` 序列化;web_fetch
  presenter(折叠 url / 读 content / 失败判 `output["ok"] is False` / emoji 🌐)+ run() 返回
  content/final_url;web_search `_WebSearchPresenter`(🔍 + results + 空/双失败通道);gateway relay
  转发 emoji;IM ToolCall emoji parse/serialize/persist 往返;前端 emoji 事件优先/名表兜底 +
  WebSearchCard + WebCard 去 title。golden `_evt_tuple` 加 emoji 维度,内置工具一律预期 `emoji=""`。
- Rationale: golden 的预期更新只来自两个有意决策(emoji 维度 + web_fetch 改读 content/final_url),
  其余 7 个内置工具的 summary/detail 预期一字不动 —— 决策 3 是行为保持的搬迁,这条红线由 golden +
  全测试树共同兜。先让这批测试红(实现未动),确认测试基础设施捕获到缺口。
- Evidence:
  - Tests(C1,实现前,预期红): `pytest tests/unit/platform/tools/test_presentation.py
    tests/unit/platform/hooks/test_realtime_stream_events.py
    tests/unit/personal_assistant/test_web_search_presenter.py
    tests/unit/agent/platform/tools/builtins/test_web_fetch_run.py` → 多条 FAIL
    (emoji KeyError / WebSearchTool 无 presenter / web_fetch content 缺失),确认红。
  - Frontend State Matrix: 见 tasks.md UI 状态矩阵(测试覆盖其每一格)。
  - Browser QA: N/A(C1 阶段)
  - E2E/Regression: N/A(本 unit 无 e2e 退出标准)
  - Visual/Interaction: N/A(C1 阶段)
- Rollback: `git revert b76d7e21`(纯测试,无运行影响)
- Commits: C1 = b76d7e21 `test(feat-425/M1): C1 红测 …`
- Next: R2 实现

---

### R2 — C2 实现:emoji 全链路透传 + web 工具 presenter 修复 + presenter 下沉

- Context: 实现 5 个决策。最易翻车点是决策 3 的下沉(7 个内置工具行为必须零变更)与 web_fetch 失败
  双通道(in-band `output["ok"] is False` 与 out-of-band `result.error`)。
- Decision(按决策):
  - 决策 1/2:`ToolPresentationEvent.emoji: str = ""` → `_presentation_dict` 序列化
    (`realtime_stream.py`)→ gateway relay(`main.py` tool_end,省略未设约定)→ IM 五层落库
    (`domain/models.py` ToolCall、`infra/repositories.py` `_tool_call_to_dict`/`_decode_tool_calls`、
    `api/ws/event_types.py`、`ws/gateway_handler.py` `_parse_tool_call`、`api/routes/messages.py`
    REST `ToolCallPayload`+`to_message_response`)→ 前端 `chat-types.ts` `emoji?` + `toolEmojiFor(call)`
    事件优先名表兜底(`tool-presentation.ts` / `tool-calls-panel.tsx`)。
  - 决策 3:9 个 `_XxxPresenter` 类从 `platform/tools/presentation.py` 下沉到各 `builtins/*.py`
    (含 web_fetch);`presentation.py` 只留 `ToolPresentationEvent`(re-export)/`ToolPresenter`/
    `resolve_presenter_for_tool`/`_DefaultPresenter`+`_DEFAULT`/共享 helper
    (`_enforce_cap`/`_truncate`/`_stringify`/`_with_path`/`_human_size`/`_summarize_*`/`display_path`)。
    各 builtin 从 presentation.py import helper,presenter 逐字搬迁(措辞/注释/helper 调用原样)。
  - 决策 4:`web_fetch.run()` 增返 `content`(剥 untrusted banner 的展示正文)+ `final_url`;
    `_WebFetchPresenter` 折叠改 url、读 content/status/final_url、失败判 `output["ok"] is False`、
    emoji=🌐;前端 `WebCard` 去 title 改正文。`serialize_result` 仍只读 text(回归保住)。
  - 决策 5:`web_search.py` 新增 `_WebSearchPresenter`(🔍 query + results/count detail + 空/双失败
    通道),product 包只 import `agent.sdk`;snippet 本地截断 `_SNIPPET_CAP=2000`(因 `_enforce_cap`
    在 platform 内部、不在 sdk 公共面)。前端 `WebSearchCard` 注册 `BESPOKE` + `searchNoResults` i18n。
- Rationale: emoji 走 feat-409 detail 趟过的同一序列化路径,每跳多带一字段,不新铺管道;旧行解码缺省
  None,前端 `||` 兜底,无迁移负担。决策 3 贯彻"presentation travels with the Tool object"到类定义
  层级,改一个工具的展示只动它自己的文件。web_fetch 的 content 与 LLM-facing 的 text(带 banner)分开,
  符合"展示数据由 presenter/工具产"。
- Evidence:
  - Tests(kernel 层): `pytest …/test_presentation.py …/test_presentation_golden.py
    …/test_presentation_cap.py …/test_realtime_stream_events.py …/test_web_fetch_run.py` → 69 passed
  - Tests(IM/gateway/web_search): `pytest …/test_tool_call_detail.py …/test_messages_route_detail.py
    …/test_tool_end_detail_passthrough.py …/test_web_search_presenter.py …/test_web_search_tool.py`
    → 44 passed
  - Tests(全树,含 im_service): `pytest -m "not e2e" -q` → 2761 passed, 0 failed, 1 skipped
  - Tests(contract): `pytest tests/contract -q` → 126 passed(依赖方向不破)
  - Lint: `ruff check src/ tests/` → No issues found;`ruff format --check` → 干净
  - Frontend: `npm run test` → Test Files 59 passed / Tests 448 passed;`npm run build` → ✓ built
  - Frontend State Matrix: tasks.md UI 状态矩阵每格均有 vitest 断言(emoji 事件优先/名表兜底/历史降级、
    WebSearchCard 有结果/空态/失败、WebCard 正文非空)
  - Browser QA: 留给 reviewer(IM 聊天面板真实旅程需重启 IM+Gateway,见 design Runbook)
  - E2E/Regression: N/A
  - Visual/Interaction: 同 Browser QA,留 reviewer
- Rollback: `git revert 5749f698`;presenter 类位置是纯内部结构,撤回不涉数据。
- Commits: C2 = 5749f698 `feat(feat-425/M1): C2 实现 …`
- Next: R3 文档

#### R2 越界修复(message-pane 基线 tsc 阻塞 build 闸)

- Context: `npm run build` 在 unit 分支基线即红 —— `message-pane.test.tsx` 的
  `querySelectorAll("tbody td")` 被 TS 推断为 `Element`(无 `.style`),以及 `message-pane.tsx`
  的 `MD_REMARK_PLUGINS = […] as const` 与 react-markdown `Pluggable[]`(mutable)冲突。两处均
  **非本 unit 引入**(stash 掉本 unit 前端改动后 build 仍报这两条),但 `npm run build` 绿是本
  milestone 的硬退出标准,被它阻塞。
- Rationale: 二者是类型层 30 秒可修、零运行行为、且在本 unit 工作的 `chat/v2/components` 子树内
  (`querySelectorAll<HTMLTableCellElement>` 加泛型实参 / 去 `as const`)。为不被基线债阻塞交付,
  以最小型修解除,并显式记入 design changelog + 此处,供 lead 知会(若倾向单列 issue 可回退这两行)。
- Evidence: 修前 stash 验证两条报错独立于本 unit;修后 `npm run build` → ✓ built;无运行逻辑变更。
- Rollback: `git checkout unit/feat-425 -- src/IM/frontend/src/features/chat/v2/components/message-pane.tsx
  src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx`(随之 build 闸恢复基线红)

---

### R3 — C3 文档:delta-spec + design changelog

- Context: 本 unit 显式修订两份契约 —— kernel presentation 字段集增 emoji;im web_fetch 展开契约
  原声明"网页标题"是漂移(工具从不返回 title),需删并改为 URL+状态+正文,同时补 web_search 折叠/展开
  Scenario 与"工具自带 emoji"Requirement。
- Decision:
  - `docs/specs/kernel/spec.md`「工具展示由工具自带的 presenter 决定」:presentation 字段集增 `emoji`,
    加"presenter 声明的 emoji 随事件透传"Scenario。
  - `docs/specs/im/spec.md`:折叠态增 web_search `🔍`/web_fetch `🌐` Scenario + 新 Requirement
    "工具折叠行图标随工具自带,自定义工具可拥有专属图标"(声明 emoji 显该图标 / 未声明回退 🔧);
    展开态 web_fetch 改 URL+状态+正文(删 title 漂移)、新增 web_search 结果卡 Scenario(含空态)。
  - design.md Changelog:记决策 5 的 `_SNIPPET_CAP` 实现落定 + message-pane 越界修复说明。
- Rationale: 契约与代码重新一致(im title 漂移修正);delta 严格对应已实现行为,不超前声明。
  gateway/cli 无 spec delta(relay 仅多透传一字段,无新增可观察契约;本 unit 不动 CLI 渲染)。
- Evidence: kernel/im spec grep 确认无残留 `网页标题` 误述(line 449 是描述被删除的旧坏格式的说明文,
  line 81 是无关的 conversation title API)。
- Rollback: `git revert 85e15069`
- Commits: C3 = 85e15069 `docs(feat-425/M1): C3 …`
- Next: 合并到 unit/feat-425

---

## 收尾

- 三提交全部合入 `unit/feat-425`,merge commit `9cefd643`
  (`merge(feat-425/M1): tool-presenter-emoji …`)。
- unit 集成分支上复验全绿:contract 126 / 全树 2761 passed 0 failed 1 skipped / vitest 448 /
  `npm run build` ✓ / ruff check + format 干净。
- 7 个内置工具行为零变更(决策 3 红线),emoji 唯一新增;web_fetch(决策 4)/web_search(决策 5)
  为有意行为变化。
