# M78 Progress - core/platform 物理分层与兼容门面

## 总体策略
- 顶层包名不变（nano_multiagent）
- 每步用 shim（one-liner re-export）保留旧 import 路径
- 每步后 pytest -q 验证不破坏 548 passed 基线
- 不移动 cli/*（M79 范畴）

## 基线
- Branch: milestone/M78
- Baseline: 5 failed, 548 passed, 4 skipped（pre-existing failures from M77）
- 预期最终：同等 passed 数保持

---

### R1 - session/stores → platform/persistence/session
- Context: session/stores 含 SQLite/JSONL 持久化实现，属 platform 关心内容；core 不关心具体存储介质。
- Decision: 在 platform/persistence/session/__init__.py 中 re-export session.stores 的全部符号；旧路径不变（shim 暂留）。暂不移动物理实现文件，以最小改动通过门禁。
- Rationale: 先建立 platform 路径可 import，再逐步迁移实现，避免一次性大范围改动破坏测试。
- Evidence:
  - Tests: 5 failed(pre-existing), 550 passed, 4 skipped
  - Entry: from nano_multiagent.platform.persistence.session import SQLiteSessionStore 可用
- Rollback: revert e3b2c58
- Commits: C1=f21adff, C2=e3b2c58, C3=TBD
- Next: R2 - llm/protocols → platform/llm/providers

### R2 - llm/protocols → platform/llm/providers
- Context: llm/protocols 含 anthropic/openai_compat 两个 provider 适配器，属 platform 关心内容。
- Decision: 在 platform/llm/providers/__init__.py re-export llm.protocols 下的子模块；旧路径保持不变。
- Rationale: 同 R1 策略—先建立新路径可用，保留旧路径兼容。
- Evidence:
  - Tests: 5 failed(pre-existing), 553 passed, 4 skipped
  - Entry: from nano_multiagent.platform.llm.providers import anthropic 可用
- Rollback: revert ca8c020
- Commits: C1=eabc1db, C2=ca8c020, C3=TBD
- Next: R3 - tools/builtins+loader+safety → platform/tools

<!-- 后续 Roadpoint 在此追加 -->
