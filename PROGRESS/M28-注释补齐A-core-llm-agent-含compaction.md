# M28 进度记录：注释补齐A（core/llm/agent 含 compaction）

## 基线
- `PYTHONPATH=src pytest -q`（worktree@milestone/M28）：337 passed, 4 skipped。
- 约束：仅注释/docstring 改动，行为保持；仅在 allowed scope 改动。

## 里程碑注意事项
- 注释必须解释“为什么/约束/边界/代价”，禁止复述代码。
- public API docstring 必须与真实行为一致，失败语义必须可验证。
- 关键蓝图约束必须显式落地：provider 隔离、compaction 切点完整性、runtime loop 边界策略。

### R28.1 core + llm public API docstring 补齐
- Context:
  - `core/llm` 多数 public API 缺 docstring，调用契约与失败语义分散在实现细节中。
  - 本 Roadpoint 不改变任何执行逻辑，仅补齐契约文档。
- Decision:
  - 为 module/class/function/method 增补 Google 风格 docstring（按需写 Args/Returns/Raises/Side Effects）。
  - 在 llm 工厂与协议映射处补“provider 隔离边界”意图注释。
- Rationale:
  - 先收口 core/llm，可为后续 agent/runtime docstring 提供稳定引用语义。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q` => 337 passed, 4 skipped；core+llm docstring AST 扫描 `missing_count=0`。
  - Entry: `llm/factory.py` 增加 provider 隔离边界说明；protocol mapper/client 补齐失败语义与返回契约说明。
- Rollback:
  - 回退到 `f2838d2`（仅保留先红审计）。
- Commits: C1=f2838d2, C2=1672cff, C3=77433e9
- Next:
  - 进入 R28.2，补齐 agent/compaction 及关键约束块注释。

### R28.2 agent(+compaction) public API docstring + 关键约束注释
- Context:
  - runtime/loop/compaction 承载失败恢复与边界策略，若缺注释容易误改。
  - 需要明确“哪些行为是策略，哪些行为是兼容/fail-open约束”。
- Decision:
  - 补齐 `agent(+compaction)` public API docstring。
  - 在 runtime loop、compaction planner 切点处增加块注释解释边界约束。
- Rationale:
  - 让调用方不读实现也能正确使用，让维护方快速理解不可破坏约束。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q` => 337 passed, 4 skipped；agent+compaction docstring AST 扫描无缺口。
  - Entry: 在 `agent/loop.py` 标注 runtime loop 终止/继续策略；在 `agent/runtime.py` 标注 overflow 重试边界；在 `agent/compaction/planner.py` 标注“不拆 tool-call/tool-result”切点约束。
- Rollback:
  - 回退到 `2b8b2b7`（仅保留先红审计）。
- Commits: C1=2b8b2b7, C2=bcbb102, C3=da18993
- Next:
  - 全量门禁后进行 Milestone 集成与状态回写。
