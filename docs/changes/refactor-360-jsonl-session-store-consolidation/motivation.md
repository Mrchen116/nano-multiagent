# refactor-360: JSONL session store 整合 / 收尾 F-330 半截 replace

## Relations

- Depends on:
- Blocks: #25 (xfail 测试改走真实路径后自动转 pass,本 unit 顺便接通)
- Related: a33e63d9 `feat(F-330)`

## 原始诉求

> 要把多个Jsonl的问题解决，你看下是哪个feat引入的

> 大修

(澄清出处:在排查 bugfix-359 立 issue #25 时发现 `SessionManager.create_session` 调不存在的 `store.create`,深入挖到 `JsonlSessionStore` 同名撞车 + `SQLiteSessionStore` 在生产里 0 引用但 73 处测试在用。用户要求大修把 F-330 真正做完。)

## 澄清记录

- Q1: 这次大修的"成功状态"长什么样,以哪种最严判据为准?
  A(原话): ok
  Agent 解读: 采纳推荐 —— 四条最严判据:
  1. `grep -rn "SQLiteSessionStore\|from agent.platform.persistence.session import \|from .sqlite_store\|from .base import SessionStore" src/ tests/` 返回零
  2. `src/agent/platform/persistence/session/` 包内不再有死代码,只剩生产用的 `service.py + __init__.py`(2026-05-19 经 design 阶段澄清:"包整体不再存在"原是实现层污染,正确表达是"无死代码";SessionService 挪位置是 scope creep,无价值,见 design 决策 2)
  3. `pytest tests/` 全过(含原 xfail 的两个 workspace_root 测试自动转 pass)
  4. IM 对话 / Coding CLI / Gateway 冒烟通过

- Q2: 73 处用 SQLiteSessionStore 的测试迁移策略怎么定?
  A(原话): 按用途分流
  Agent 解读: 采纳推荐 —— 三分类:
  - **(a) 改走真实路径(SessionService)**: 端到端验某行为(hook/compaction/skill/e2e),迁到 SessionService.create_session + 真实 (A) JsonlSessionStore。最值钱的迁移。预估 40-50 处。
  - **(b) 直接用 (A) 平替**: 只需要个 store 用来 append/load,不在意产品语义。预估 15-20 处。
  - **(c) 删**: 测试验证的是 (B)/(C) 内部快照/事件存储语义,在测死代码。预估 5-10 处。
  design 阶段产出测试分类清单作为 milestone 拆分依据。

- Q3: 本 unit 删到哪一层?
  A(原话): ok
  Agent 解读: 采纳推荐 —— 删干净 platform-layer 老抽象:
  - 删 (C) sqlite_store.py / (B) jsonl_store.py / `SessionStore` 抽象基类 / `platform/persistence/session/` 包(只剩空 `__init__.py` 时整个删)
  - 73 处测试按 Q2 三分类迁/删
  - 接通 issue #25 的两个 xfail 测试
  不做(留单独 issue):重命名 (A)、改 (A) 模块路径、改 SessionManager/SessionService 语义、给老用户写数据迁移脚本。
  原则:纯删除 + 测试迁移,不动在用代码语义。

- Q4: (c) 类测试删除前的覆盖率底线?
  A(原话): 对
  Agent 解读: 采纳推荐 —— 删 (c) 前必须确认其"原本想验的行为"在生产路径上有等价测试覆盖;没有就先补 integration 测试再删。design 阶段做测试分类清单时每条 (c) 项要附"等价覆盖来源"栏,空着的视为"先补"。

## 范围扩张记录

- 2026-05-19 (M3 实施期, 用户授权): 迁移 compaction/runtime integration 测试时发现 F-330 还留下两处同质半成品(docstring 承诺 / dead config field),与本 unit 同源,扩入范围一并修。详见 design.md Changelog。

## 现状痛点

`feat-330` (commit `a33e63d9`, 2026-04-23) 的 commit message 自报"Replace SQLite with append-only JSONL session store",但 replace 只做了一半:

**做完的一半**(新):
- 新建 (A) `src/agent/core/session/jsonl_store.py::JsonlSessionStore`,接口 = `create / append / load / update_config / list_session_ids / writer / resolve_path / find_session_by_metadata`
- `SessionManager.__init__(*, store: JsonlSessionStore)` 类型签名锁死要 (A)
- 生产路径(`SessionService` / `bootstrap`)切到 (A)

**没做完的一半**(旧没删):
- (B) `src/agent/platform/persistence/session/jsonl_store.py::JsonlSessionStore` —— 和 (A) **同名不同模块,接口完全不同**(`append_event / load_session / save_snapshot / list_session_ids`,基于事件 + 快照,继承自 `SessionStore` 抽象基类)
- (C) `src/agent/platform/persistence/session/sqlite_store.py::SQLiteSessionStore` —— 与 (B) 同接口的 SQLite 实现。模块顶注释还自称 "Canonical SQLite-backed session store",误导性极强
- `src/agent/core/session/store.py::SessionStore` 抽象基类 —— 只有 (B)(C) 这两个死实现继承它

**死代码地图**(扫 `grep -rn` 主仓 `src/` 的实际 import):

| 类 | 路径 | src/ 引用数 | tests/ 引用数 |
|---|---|---|---|
| (A) 生产用 | `core/session/jsonl_store.py` | 真在跑(SessionManager 唯一吃这个) | — |
| (B) 死同名 | `platform/persistence/session/jsonl_store.py` | **0** | 3 |
| (C) 死 SQLite | `platform/persistence/session/sqlite_store.py` | **0**(只 `__init__.py` 导出) | **73** |

**这套留着的代价**:

1. **语义炸弹**:同名类 (A)/(B) 在不同模块,新人(或新写代码的 agent)从哪个包 import 决定走哪套语义,极易选错。我在排查 issue #25 时就是被同名误导,一度认为是 prod bug。
2. **测试假装在跑**:76 处测试(B 类 3 + C 类 73)在测**不存在于生产路径上的代码**。这个数字会越攒越多——只要旧抽象还在,新 hook / compaction / skill 测试就会继续盲选这条路径。
3. **现实证据**:`tests/e2e/test_personal_assistant_main_e2e.py::test_kernel_session_workspace_root_*` 在 bugfix-359 里被发现一直 fail,根因就是测试给 SessionManager 喂 (C) 但 SessionManager 只吃 (A)。bugfix-359 把它们标 xfail + 立 issue #25 顶着。

## 目标状态

把 F-330 的 replace 真做完。删除 (B) / (C) / `SessionStore` 抽象基类 / `platform/persistence/session/` 包(包内空了整体删)。76 处测试按 Q2 三分流(`(a)` 接通真实路径 / `(b)` 平替 (A) / `(c)` 删,删前按 Q4 补足覆盖)。Issue #25 的两个 xfail 测试随之转 pass。

完成后:

- `grep -rn "SQLiteSessionStore\|from agent.platform.persistence.session" src/ tests/` 返回零
- `src/agent/platform/persistence/session/` 目录不存在
- 全仓 `JsonlSessionStore` 字面只指向 (A),零歧义

## 用户侧验收标准(不变性)

本 unit 是面向内部的 refactor,**无新增的用户可观察行为**;用"回归基线"镜头写——既有用户旅程在变更前后必须一致。

**现状基线快照**(reviewer 验收对照):

- IM 网页前端的用户(`http://127.0.0.1:8011/`):登录 → 选/建 agent → 单聊或群聊 → 多轮对话 → 关闭浏览器 → 再打开仍能看到历史会话 + 继续往下聊。所有 mention 路由(bugfix-358 修过的)继续工作。
- Coding CLI 用户(`python -m coding_cli.main ...`):`create-session` → `send-message` 一轮一轮跑 → `--resume <session-id>` 重新进入仍能拿到完整历史。
- Gateway 操作者(`python -m personal_assistant.main`):启动 → IM 端 agent 上线 → heartbeat 正常 → `stop` 子命令能干净停掉。
- Agent skill / hook 触发:已有 hook(realtime_stream / auto_mode_gate / self_evolution_review 等)继续按既有契约触发,Compaction、Task 工具非阻塞行为不退化。

**不变性勾选**(reviewer 逐条验):

- [ ] IM 网页:登录 / 选 agent / 单聊往返 / 群聊 @ 路由 / 历史回看 与本 unit 之前一致
- [ ] Coding CLI:`create-session` / `send-message` / `--resume` 行为与本 unit 之前一致
- [ ] Gateway:启动 / 健康检查 / `stop` / 重启后 agent 仍在线 与本 unit 之前一致
- [ ] 现有 `.nano/sessions/` 下的历史 session 文件(本机已存在的真实数据)在 refactor 后仍能被 `--resume` 正常加载

## 影响范围

- **删除**:`src/agent/platform/persistence/session/` 整个包(若包内全空)、`src/agent/core/session/store.py`(`SessionStore` 抽象基类)
- **不动语义**:(A) `agent.core.session.jsonl_store.JsonlSessionStore`、`SessionManager`、`SessionService`、`SessionStore` 的所有使用方
- **测试迁移**:`tests/` 下 76 处 import,按 Q2 三分流处理
- **顺接**:bugfix-359 留下的两个 xfail 测试(`tests/e2e/test_personal_assistant_main_e2e.py::test_kernel_session_workspace_root_*`)改走真实路径,自动转 pass,关闭 issue #25
- **不影响**:`session_bindings.sqlite3` / `group_context_buffer.sqlite3` / `relay_dedup.sqlite3` 这些是 IM/personal_assistant 自己的 SQLite,跟 agent session 持久化无关

## 迁移与回滚策略

**行为不变保证**:

- (A) `JsonlSessionStore` 的实现 / 接口 / 文件格式不动。`.nano/sessions/` 下既有数据格式天然兼容,无需迁移脚本
- 删除 (B)(C) 之前先做依赖扫描,确认 src/ 0 引用(已扫,确认)
- 测试迁移每一处单独 commit,保留迁移痕迹便于审查;每个 milestone 完成后跑完整 `pytest tests/` 套不准回归
- (c) 类删除前按 Q4 硬约束:每条附"等价覆盖来源"栏,空着的先补再删

**回滚策略**:

- 本 unit 完成前所有 commit 都在 `unit/refactor-360-jsonl-session-store-consolidation` 分支上,合 main 前可整 unit revert
- 合 main 后若发现回归,按 milestone 粒度 revert(design 阶段会把测试迁移拆成与"删 store"相互独立的 milestone,让 revert 粒度最细)
- (A) 不动,所以 rollback 风险只在测试套(可读)和包结构(可机械还原),不存在用户数据兼容性风险

