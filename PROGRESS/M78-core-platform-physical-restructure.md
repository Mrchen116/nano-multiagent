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

<!-- Roadpoint 完成后补充 -->
