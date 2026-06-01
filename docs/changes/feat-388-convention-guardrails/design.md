# feat-388: 把项目规范固化为机器执行的硬约束 — 技术方案

> 对齐: spec.md v2(含 Q7 前端 CI 测试套件门)
> Unit branch: `unit/feat-388` (will be created by orchestrator)

## Changelog

- 对齐 spec.md v2(Q7):D3 扩为前后端两个并行 CI job,新增前端 `frontend` job(Node 20 → `npm ci` → `npm run test`,不跑 build / 不引入 tsc);现状分析补 `src/IM/frontend/` 与 bugfix-390(已并 main,前端门依赖已兑现);风险/Runbook/Milestone 两轨退出标准同步补前端门条目。

## 现状分析

### 涉及范围

- `pyproject.toml` —— 现状无任何 lint / format 工具配置(只有 `[tool.pytest.ini_options]`),`dev` 依赖只有 pytest 系。本 unit 在此新增 `[tool.ruff]` 段并把 `ruff` 加进 `dev`。
- `tests/contract/test_cli_http_only_contract.py` —— 现状断言**产品包禁止 import `agent`**(`"agent." not in cli_source`)+ 四顶层包横向零互相 import 矩阵(`PACKAGE_IMPORT_BOUNDARIES`)。其中"禁止 import agent"这条会被 refactor-387 反转(产品改为 import `agent.sdk`),本 unit 接手把它改写成 R1 = "产品只能 import `agent.sdk`"。四包横向矩阵(R2)保留。`test_top_level_packages_keep_zero_import_boundaries` 当前 `xfail`(#39,`kernel_app.py` 为 Managed 模式 import platform)。
- `tests/contract/test_core_no_platform_imports.py` —— 现状断言 `core` 不 import `platform`/`products`/`apps`/fastapi/starlette(R3),但整条 `@pytest.mark.xfail(strict=True)`,挂 #40(`core.llm.factory → platform` 反向依赖)。本 unit 在 #40 被 refactor-387 消除后 un-xfail 锁定。
- `.claude/settings.json` —— 现状定义了 4 个 orchestration hook(SubagentStart/Stop、Stop=`stop-require-explicit-ok.py`、PreToolUse[Agent]),但 `"disableAllHooks": true` 全局关闭;**无 PostToolUse**。本 unit 在此加 PostToolUse[Edit|Write] 跑 ruff 守卫(触点 a)。
- `.claude/hooks/` —— hook 脚本目录,现有 4 个脚本。本 unit 新增 `ruff-guardrail.py`,并需令 `stop-require-explicit-ok.py` 在非 orchestrator 会话安全(见决策 D2)。
- `.github/workflows/` —— **不存在**。本 unit 新建 `ci.yml`(触点 c),内含**两个并行 job**:后端 `python`(ruff + pytest)+ 前端 `frontend`(vitest)。
- `src/IM/frontend/` —— IM 前端。测试入口 `npm run test`(`package.json` script → wrapper 调 `vitest run`),vitest 配置内联在 `vite.config.ts`(`test.environment = "jsdom"` + `setupFiles`),vitest `^3.2.4` / jsdom `^27`。存在 `package-lock.json`(CI 可 `npm ci` 锁定装包);**无** `engines`/`.nvmrc`(CI Node 版本须显式定,vitest3+jsdom27 要 Node ≥20)。本 unit 不改前端源码,只把其 vitest 套件纳入 CI 门(触点 c)。
- 全仓 `src/**`(271 文件 / 50540 行)—— 零容忍要求存量违规全修,实际触及面见"相关历史 / 量化"。

### 既有约束

- **四顶层包零互相 import + 依赖方向**(AGENTS.md / SPEC.md):`coding_cli`/`personal_assistant`/`IM`/`agent` 之间的边界,正是 R1/R2/R3 要锁的对象——规则本身不能违反它,且要沿用既有 `tests/contract/` 的 AST 验收范式。
- **内核三层**(AGENTS.md):`platform → products + core`,`core` 不反向依赖——R3 的内容即此。
- **refactor-387 进行中且未并 main**:`unit/refactor-387` + `milestone/refactor-387-M2/M3` worktree 存在,`agent.sdk` 面尚未建,产品包当前**不 import agent**(HTTP-only 现状)。R1 的前提(产品 import `agent.sdk`)、R3 的 #40 修复,都由 refactor-387 提供。⇒ 本 unit 硬依赖 refactor-387 先并 main。
- **hook 脚本落位约定**:`.claude/hooks/*.py`,在 `.claude/settings.json` 用 `python3 .../.claude/hooks/X.py` 挂载。沿用之。
- **远端**:`git@github.com:Mrchen116/nano-multiagent.git`(GitHub),CI 用 GitHub Actions。

### 可复用能力

- `tests/contract/test_cli_http_only_contract.py` 的 AST 遍历 + `PACKAGE_IMPORT_BOUNDARIES` 矩阵 —— **改写复用**:R2 直接沿用矩阵;R1 替换掉被 387 反转的"禁 import agent"断言。
- `tests/contract/test_core_no_platform_imports.py` —— **复用**:R3 的检查已写好,只需在 #40 消除后去掉 `xfail`。
- `.claude/hooks/subagent-*.py` 的 hook 脚本骨架(读 stdin JSON、写状态)—— **参考复用** ruff-guardrail.py 的 I/O 形态。
- `ruff`(format + lint)—— **新增引入**:项目零 linter,这是净新工具,但单一工具同时覆盖 format(B-1)与 correctness(B-2),无需 black+flake8+isort 多件套。

### 相关历史

- **refactor-387**(motivation/design 已定稿,实施中):内核纯 SDK 化,移除内置 HTTP API,产品改 import `agent.sdk`;其 motivation 明确"**修 core→platform 反向依赖**"(即 #40)。本 unit 的 R1 前提与 R3 前提都由它兑现 ⇒ `Depends on: refactor-387`。两者在 `test_cli_http_only_contract.py` 上有交接:387 反转/移除旧 HTTP-only 断言并让产品 import `agent.sdk`,**388 在其上加 R1 守卫锁定**。
- #40(OPEN):`core.llm.factory` 直接 import `platform`,正是 R3 现存唯一违规,由 387 修。`Refs: #40`。
- #39:`kernel_app.py` 为 Managed 模式 import platform —— 注意 refactor-387 移除内置 HTTP API / Managed 子进程模型后,`kernel_app.py` 形态会变,`test_top_level_packages_keep_zero_import_boundaries` 的 xfail 前提可能随之消失;本 unit 接手时需复核该 xfail 是否仍需要(见风险)。
- **bugfix-390**(已并 main,PR #71 / `aaaf3956`):修掉 main 上 IM 前端三处 vitest 失败(token 牌口径 / 策略页入口 / agent-edit 测试),这三处此前烂了约 2-3 周没人发现,正因 vitest 不在任何门禁里。spec 的 `Depends on: bugfix-390` 即指此——前端 CI 门要"零失败"才能开,需先有干净的 main。**该依赖已兑现**:bugfix-390 已落地,main 上前端 vitest 应已全绿,本 unit 的前端门可直接生效,不再是阻塞项(本 unit 接手时跑一遍 `npm run test` 确认基线为绿即可)。

### 量化(只读 ruff 0.15 扫描,50540 行 / 271 文件)

| 规则族 | 存量违规 | 备注 |
|---|---|---|
| B-1 formatter | **152/271 文件需重排** | 零容忍下最大一笔机械 diff,必与在途分支冲突 → 决策 D5 排序 |
| B-2 F401 未用 import | 59 | 可自动修 |
| B-2 F841 未用变量 | 6 | |
| B-2 F811 重复定义 | 1 | |
| B-2 B006 可变默认参 / E722 裸 except | **0** | spec 点名,实测无 |
| (排除)B008 默认参调函数 | 107 | FastAPI `Depends()`/`Query()` 惯用法,**误报,不纳入** → 决策 D4 |

B-2 真实违规 ≈ 66 处(57 可 `--fix` 自动修)。

## 架构总览

核心思路:**规则按"卫生 vs 架构边界"分给两个引擎(ruff / pytest 契约),每条规则单一真源;两个交付触点 (a) 编码循环 hook、(c) CI,跑同一套引擎,只是触发时机不同。**

```
                      ┌─────────────────────────────────────────────┐
   规则(单一真源)    │  引擎 1: ruff          引擎 2: pytest 契约    │
                      │  ─────────────         ──────────────────     │
   B-1 formatter ────▶│  ruff format                                  │
   B-2 correctness ──▶│  ruff check (裁剪 select)                     │
   R1 产品→only sdk ──┼──────────────────────▶ test_cli_http_only_*   │
   R2 四包横向零 ─────┼──────────────────────▶ test_cli_http_only_*   │
   R3 core 不反向 ────┼──────────────────────▶ test_core_no_platform_*│
                      └───────────────┬──────────────────┬────────────┘
                                      │                  │
        ┌─────────────────────────────┘                  └──────────────────────┐
        ▼ 触点 (a) 编码循环内 (即时)                        ▼ 触点 (c) 远端兜底
  ┌───────────────────────────────────┐          ┌──────────────────────────────┐
  │ Claude Code PostToolUse hook        │          │ GitHub Actions ci.yml          │
  │ matcher: Edit|Write on *.py         │          │ on: push / pull_request        │
  │  1. ruff format <file>  (autofix)   │          │  - ruff check                  │
  │  2. ruff check --fix <file>(autofix)│          │  - ruff format --check         │
  │  3. 余下违规 / 边界违规 → exit 2 回喂│          │  - pytest -m "not e2e"         │
  │  + 跑边界契约测试(快 AST)           │          │   (含 R1/R2/R3 契约)           │
  └───────────────────────────────────┘          └──────────────────────────────┘
```

**before**:规范全在 AGENTS.md / COMMENTING_GUIDE.md / SPEC.md 的散文里,靠"请遵守";`tests/contract/` 有 R2/R3 雏形但 R3 整条 xfail、R1 还是被 387 反转的旧语义;无 ruff、无 CI、hook 全局关闭。
**after**:卫生(format+correctness)由 ruff、架构边界(R1/R2/R3)由 pytest 契约,单一真源;每次 agent 编辑文件 hook 即时 autofix/回喂,每次 push/PR 由 CI 兜底;存量全清,无 baseline/xfail 残留。

## 关键决策

### 决策 D1: 双引擎按"卫生 / 架构边界"分工,单一真源不重复

- **选择**: ruff 只负责卫生类(B-1 format、B-2 correctness);所有 import / 架构边界(R1、R2、R3)留在 `tests/contract/` 的 AST 契约测试。每条规则只有一个 checker。
- **理由**: R2 是"四包两两不互 import"的矩阵、R3 是分层方向,ruff 的 `banned-api`(全局 + per-file-ignore 只能"去除"不能"按目录换一组禁用模块")表达不了这类带例外的结构规则;而 `tests/contract/` 本就是项目既有的 AST 边界验收范式且已实现 R2/R3。把边界硬塞进 ruff 需要 per-directory `ruff.toml` 体操,且与契约测试两处真源。卫生类则是 ruff 甜区。
- **拒绝**: (b) 全用 ruff banned-api 做边界——表达不了 R2 矩阵,且与既有契约重复。(c) 全用 AST 契约连 format/correctness 也自己写——重造 ruff,且拿不到 ruff 的 autofix。
- **风险**: 边界规则不在 ruff ⇒ 默认不进 hook 的 ruff 那步;靠"hook 额外跑边界契约测试"补即时反馈(见 D2),否则边界只在 CI 兜底。

### 决策 D2: 触点 (a) = Claude Code PostToolUse hook;autofix 可修、回喂不可修;并令休眠 hook 在普通会话安全后再开启

- **选择**: 在 `.claude/settings.json` 加 `PostToolUse` matcher `Edit|Write`,挂 `.claude/hooks/ruff-guardrail.py`:对被改的 `.py` 先 `ruff format` 再 `ruff check --fix`(可自动修的静默修好),余下不可修违规以 exit 2 + stderr 回喂 agent;并跑边界契约测试给 R1/R2/R3 即时反馈。开启需把 `disableAllHooks` 置 `false`;因翻转会连带激活 `stop-require-explicit-ok.py`(无 subagent 时 block 停止)等 orchestration hook,本 unit 先令其在非 orchestrator 会话自门控(仅当会话在 `.claude/state/active-subagents.json` 中登记为受管时才 gate,否则 exit 0),再开启。
- **理由**: "编辑后即时回喂"只有 PostToolUse hook 能做(commit/CI 都太晚);autofix/回喂的边界把零摩擦项(格式、未用 import)自动消化、把需判断项(裸 except、穿透内核)留给 agent。`disableAllHooks` 是粗暴全局开关,与"新增任何 hook"天然冲突,正确做法是让休眠 hook 自门控而非全局闷掉。
- **拒绝**: 触点 (b) git pre-commit——spec 已排除,且 commit-time 晚于 edit-time。直接翻 `disableAllHooks` 不动 stop hook——会给普通编码会话强加"停止要写魔法 token"的干扰。
- **风险**: 改 `stop-require-explicit-ok.py` 触碰 orchestrator 基础设施;需保证 orchestrator 受管会话行为不变(self-check + 实测)。

### 决策 D3: 触点 (c) = 新建 GitHub Actions CI(现状零 CI),前后端两个并行 job 任一红即阻止合并

- **选择**: 新建 `.github/workflows/ci.yml`,`on: push(仅 branches: [main])+ pull_request`(push 限主干,避免开 PR 后同一 commit 被 push 与 pull_request 双触发跑两遍),内含**两个并行 job**(`needs` 互不依赖,失败各自独立):
  - **`python`**: setup Python 3.11 → `pip install -e ".[dev]"` → `ruff check .` → `ruff format --check .` → `pytest -m "not e2e"`(契约测试 R1/R2/R3 在内)。
  - **`frontend`**: `actions/setup-node@v4` Node **20**(带 npm cache,`cache-dependency-path: src/IM/frontend/package-lock.json`)→ 在 `src/IM/frontend/` 下 `npm ci` → `npm run test`(= `vitest run`)。
  - 任一 job 失败 → workflow 红 → 阻止合并。
- **理由**: 仓里完全没有 CI,触点 (c) 必须从零搭。后端三道检查 = 两引擎全集,与 hook 对称;`not e2e` 避免 CI 依赖本地运行时。前端单独成 job 而非塞进 `python` job 串联:前后端工具链(pip vs npm)互不依赖,拆开可**并行**、各自 setup 干净、失败定位直接。spec Q7 要求 CI 门同等覆盖前端测试套件——前端 vitest 红与后端 pytest 红同等阻止合并,否则像 bugfix-390 那样前端坏数周无人知。
- **拒绝**: 复用某现有 CI——不存在。只在 hook 拦不设 CI——绕过 hook 的路径(人手改、别的机器)就漏了,spec 明确要 (c) 兜底。前后端塞进单 job 串联——无法并行、Python 步失败会挡住前端步、定位混。前端 job 跑 `npm run build`(含 `tsc -b`)——**明确不做**:spec 只把 vitest 测试套件纳入门,不引入前端 tsc 类型检查(与 Python 侧不做 mypy 对称),`build` 会把类型检查偷偷带进门。
- **风险**: 首次引入 CI,需保证 `pip install -e ".[dev]"` 在 clean runner 能装上;ruff 版本须与本地一致(见 D5)。前端侧:Node 20 须能装 jsdom27/vitest3;前端门生效前提是 main 基线全绿,已由 bugfix-390 兑现(见相关历史)。

### 决策 D4: B-2 correctness 规则集裁剪——纳真违规、排惯用法误报

- **选择**: B-2 的 ruff `select` 纳入 `F`(含 F401/F811/F841)、`B006`(可变默认参)、`E722`(裸 except);**排除 `B008`**(默认参里调函数)。
- **理由**: 实测 B008 命中 107 处基本是 FastAPI `Depends()`/`Query()` 惯用法,纳入即大面积误报、逼人加 `noqa` 反架空规则;spec 点名的 B006/E722 实测为 0(纳入零成本、防回归);F 系是真违规(66 处,57 可自动修)。
- **拒绝**: 开 `B` 全族——含 B008 误报。只开 F 不开 B006/E722——spec 点名的可变默认参/裸 except 没覆盖。
- **风险**: 后续可能冒出别的惯用法误报;约定**逐条具名排除 + 写明理由**,禁止 blanket `noqa`/`# ruff: noqa`。

### 决策 D5: 落地排序与零容忍执行——硬依赖 387 先并,再一次性清存量

- **选择**: 整个 unit 实施排在 refactor-387 并入 main **之后**;实施时把"全仓 `ruff format`(152 文件)+ 修 66 处 correctness"作为**独立机械提交**先落地,再开启 ruff 门;R2/R3 在 387 反转 HTTP-only 断言 / 消除 #40 后,改写锁定 R1 + un-xfail R3。零容忍:不留 baseline / 不加永久 `xfail`/`noqa`。
- **理由**: 152 文件重排会与 387 的大重构 worktree 严重冲突,必须等 387 落定再动,否则反复 rebase。机械重排独立成 commit 便于 review 与回滚(把"格式噪声"与"逻辑改动"分开)。R1/R3 的前提本就由 387 提供。
- **拒绝**: 与 387 并行——必然冲突。对 152 文件设 format baseline 只查新代码——违背 spec 零容忍。
- **风险**: 若 387 迟迟不并,本 unit 阻塞;期间 main 上新增的违规会扩大清理面(可接受,届时重扫即可)。

## 接口与数据流

### ruff 配置(`pyproject.toml` `[tool.ruff]`,B-1 + B-2 真源)

- `target-version = "py311"`,`line-length`/format 取默认(消风格软约定即可)。
- `[tool.ruff.lint] select = ["F", "B006", "E722"]`(B-2 裁剪集;**不含 B008**)。
- `[tool.ruff.lint.per-file-ignores]`:`tests/**` 视需要放宽(如未用 fixture 变量)。
- `dev` 依赖新增 **固定版本** `ruff==0.15.*`(format 输出跨大版本会变,CI 与本地、与 hook 必须一致,见 D3/D5 风险)。

### PostToolUse hook 契约(`.claude/hooks/ruff-guardrail.py`)

- 输入:stdin JSON,取 `tool_input.file_path`(沿用现有 hook 读 stdin 范式)。
- 行为:仅当 `*.py` 且在 `src/`|`tests/` 下才处理;`ruff format <file>` → `ruff check --fix <file>`(autofix 静默);若 file 在 `src/` 下,跑边界契约测试(`pytest tests/contract/test_cli_http_only_contract.py tests/contract/test_core_no_platform_imports.py -q`)。
- 输出:全绿 exit 0;有不可自动修违规(含边界)→ exit 2,stderr 写人类可读违规摘要(Claude Code 把 exit 2 的 stderr 回喂给 agent)。
- `.claude/settings.json`:加 PostToolUse 段;`disableAllHooks: false`。

### `stop-require-explicit-ok.py` 自门控改动

- 现状:`active==0` 且无 exempt token 时 `block`。
- 改为:仅当本 session 在 `active-subagents.json` 中**有登记**(即 orchestrator 受管会话)才进入 gate 逻辑;普通会话(无登记)直接 exit 0。orchestrator 行为不变。

### 契约测试改动(R1/R2/R3 真源)

- `test_cli_http_only_contract.py`:删/改被 387 反转的 `"agent." not in cli_source` 断言;新增 **R1** = 产品包(`coding_cli`/`personal_assistant`)的 `agent.*` import 中,凡非 `agent.sdk` 前缀即违规(沿用现有 AST 遍历)。**R2** 的 `PACKAGE_IMPORT_BOUNDARIES` 四包横向矩阵保留;`agent` 的允许集放开到含 `coding_cli`/`personal_assistant`(它们现在合法 import `agent.sdk`,但反向 `agent` import 它们仍禁)。
- `test_core_no_platform_imports.py`:#40 消除后去掉 `@pytest.mark.xfail`,**R3** 转为正向断言。

### CI 契约(`.github/workflows/ci.yml`)

- `on: push(branches: [main])+ pull_request`(push 限主干,功能分支仅由 pull_request 触发一次),两个并行 job(ubuntu):
  - **`python`**(py3.11):`pip install -e ".[dev]"` → `ruff check .` → `ruff format --check .` → `pytest -m "not e2e"`。任一步失败即该 job 红。**`dependencies` 必须声明全部运行时直接依赖(含 `pyyaml`/`websockets`)——本地靠无关全局包传递带入会在 clean runner 缺失,导致 collection error 全红(feat-388 实测教训)。**
  - **`frontend`**(Node 20):`working-directory: src/IM/frontend` → `npm ci` → `npm run test`。任一步失败即该 job 红。
- 两 job 任一红 → workflow 红 → 阻止合并;两 job 全绿才放行。前端 job 不跑 `npm run build`(不引入 tsc)。

## 风险与回退

- **152 文件重排 × 在途分支冲突**(最高):D5 已排序——硬依赖 387 先并,机械重排独立 commit。残余风险:387 之外若还有其他在途 worktree(当前另有 `bugfix-362` 等),它们 rebase 时会吃到格式 diff。缓解:重排 commit 落地后周知,在途分支各自 `ruff format` 自家改动即可对齐。
- **开 hook 连带激活 orchestration hook**:D2 自门控缓解;self-check 必须实测"普通会话能正常停止"+"orchestrator 受管会话 gate 行为不变"。回退:`disableAllHooks: true` 一键恢复关闭(代价是触点 a 失效,(c) 仍在)。
- **ruff 误报扩面**:D4 已排 B008;约定逐条具名排除。若某次升级 ruff 引入新误报,固定版本(D5)挡住非预期漂移。
- **#39 xfail 前提随 387 变化**:387 改 Managed/HTTP 模型后 `kernel_app.py` 可能不再 import platform,`test_top_level_packages_keep_zero_import_boundaries` 的 xfail 可能该转正或删除;本 unit 接手时按 387 落地后的实际复核,不预设。
- **CI clean-runner 装不上**:首引 CI;退路:CI 先只跑 ruff 两步(纯 pip 装 ruff,极轻),pytest 步若依赖问题暂标 continue-on-error 并开 issue,但**不**作为长期 baseline。
- **前端 CI 门基线不绿**:前端门生效前提是 main 上 vitest 已全绿,否则门一开就常红、逼人绕过。缓解:硬依赖 bugfix-390(已并 main,PR #71)修掉三处存量失败;本 unit 接手时**先在 main 跑一遍 `npm run test` 确认基线为绿**,再合 CI 前端 job。若届时仍有失败 → 说明 bugfix-390 之后又退化,回 spec-author/orchestrator 评估而非带病开门。
- **前端 CI Node 环境**:无 `engines`/`.nvmrc`,CI 固定 Node 20(满足 vitest3+jsdom27)。退路:若 Node 20 装包失败,降到本地实测可跑的版本并在 `ci.yml` 注明,**不**因此放宽为 continue-on-error。
- **回滚**:本 unit 改动全是叠加式(ruff 配置 / CI yaml / hook / 契约测试),可整体 `git revert` unit 合并提交;机械重排 commit 独立,可单独 revert 而不影响规则配置。

## Runbook for Reviewer

**无常驻服务。** 本 unit 改动为 ruff 配置 / GitHub Actions CI / Claude Code hook / `tests/contract/` 契约测试,无任何常驻进程需重启。

reviewer 走旅程的验证方式(非服务重启,列此备用):在干净工作树构造一处违规并观察是否被拦——
- 触点 (a):在 `src/personal_assistant/` 某文件加 `import agent.core`(或写一个含未用 import 的文件)→ 经 Edit/Write → hook 应 autofix 未用 import / 以 exit 2 回喂 import 越界。
- 触点 (c) 后端:把上述违规推到 PR → CI `python` job 应红(`ruff check` 或契约测试失败)。
- 触点 (c) 前端:故意改坏一处 IM 前端组件让某 vitest 用例失败 → 推到 PR → CI `frontend` job 应红、阻止合并;改回则绿。
- 零容忍:在 unit 分支跑 `ruff check . && ruff format --check . && pytest -m "not e2e"` → 全绿、无 xfail/baseline 残留;`cd src/IM/frontend && npm run test` → 全绿、零失败。

## Milestones

单 M1:本 unit 是"搭起一套守卫系统"的单一内聚交付。四条工作流(ruff 配置+清存量 / 契约测试改写 / hook / CI)彼此**顺序依赖**(必须先清存量再开门),非可并行的独立模块——横切式拆 milestone(配置/hook/CI 各一)正是 §4.3 禁止的反模式。152 文件重排是 `ruff format .` 一条命令的产物,非 152 文件手工活,不构成超窗。unit 内部分步用 worker 的 roadpoint(tasks.md R1/R2…)承载。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-388-M1 | guardrails | refactor-387、bugfix-390(均 unit 级外部依赖,需先并 main;bugfix-390 已并) | A | `pyproject.toml`、`.github/workflows/ci.yml`(python + frontend 两 job)、`.claude/settings.json`、`.claude/hooks/ruff-guardrail.py`、`.claude/hooks/stop-require-explicit-ok.py`、`tests/contract/test_cli_http_only_contract.py`、`tests/contract/test_core_no_platform_imports.py`、全仓 `src/**`(一次性 format + correctness 修复;`src/IM/frontend/` 仅纳入 CI 门、不改源码) | 见下方两轨 |

### feat-388-M1 退出标准(两轨)

**[reviewer]**(用户可观察,对齐 spec Scenario):
- `[reviewer]` 产品包写入 `import agent.core/platform/products` 时,编码循环内当场被回喂阻断,且推到远端 CI 红(覆盖 Req-R1 / Scenario-编码循环内、远端兜底)
- `[reviewer]` 产品包 `import agent.sdk` 检查通过、不误报(覆盖 Req-R1 / Scenario-合法不误报)
- `[reviewer]` 四顶层包横向互相 import 被拦(覆盖 Req-R2)
- `[reviewer]` `core` 反向 import `platform`/`products` 被拦;且对 `core` 全量跑检查零违规、无 xfail/baseline 残留(覆盖 Req-R3 两 Scenario,依赖 387 消除 #40)
- `[reviewer]` 格式不符代码经 Edit 后被自动规整;绕过则远端 CI 红(覆盖 Req-B-1)
- `[reviewer]` 未用 import/变量经 Edit 后被自动清除;可变默认参/裸 except 当场回喂、绕过则 CI 红(覆盖 Req-B-2)
- `[reviewer]` 本 unit 完成后对全仓现有代码跑检查零违规、无 baseline/xfail 永久豁免(覆盖 Req-零容忍)
- `[reviewer]` 破坏 IM 前端 vitest 的改动推到 PR 后 CI 红、阻止合并,与破坏后端 Python 同等对待;前后端检查全绿才放行(覆盖 Req-CI 前端门 / Scenario-破坏前端测试被拦、前后端全绿才放行)

**[worker]**(实现层):
- `[worker]` `ruff check .` 全绿(select = F, B006, E722;不含 B008)
- `[worker]` `ruff format --check .` 全绿(全仓已一次性重排)
- `[worker]` `pytest -m "not e2e"` 全绿,含改写后的 `test_cli_http_only_contract.py`(R1 新语义 + R2 矩阵)与 un-xfail 的 `test_core_no_platform_imports.py`(R3 正向)
- `[worker]` PostToolUse hook 实测:编辑含 F401 的 `src/` 文件 → 自动清除;编辑产品包加 `import agent.core` → exit 2 回喂阻断
- `[worker]` 普通会话能正常停止(`stop-require-explicit-ok.py` 自门控生效),orchestrator 受管会话 gate 行为不变
- `[worker]` `.github/workflows/ci.yml` 在 PR 上两 job 跑通:`python`(ruff check / format --check / pytest -m "not e2e")+ `frontend`(Node 20 → `npm ci` → `npm run test`),任一红阻止合并
- `[worker]` 在 main 基线 `cd src/IM/frontend && npm run test` 全绿、零失败(bugfix-390 已修绿,门处于真正生效状态;覆盖 Req-CI 前端门 / Scenario-上线时前端测试已全绿)
- `[worker]` 前端 job 不跑 `npm run build`(不引入 tsc 类型检查)
- `[worker]` `pyproject.toml` 固定 ruff 版本,`dev` 依赖含 ruff;机械重排为独立 commit
