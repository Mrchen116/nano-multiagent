# TESTING_GUIDE

目标：让 worker 写出**证明产品能用、且不腐烂**的测试。原则——测试的价值在"每次改动被它挡一次",不在数量。写之前先问"该不该写、写在哪、归谁"，而不是想到什么测什么。

> 适用面：本指南是 `change-impl-worker` 写测试时的硬规范。能被机械校验的条目(命名/落层/marker/依赖/行数)由 `tests/contract/` 兜底；其余靠 worker 遵守 + reviewer 复核。

## 1) 测什么 / 不测什么（停止条件）

- 测试来源 = **首文档/design.md 里每条可观察行为(退出标准)**。每条对应一个测试。**覆盖完即停。**
- 不测假想场景、不写防御性测试凑数。spec 没要求的边界不主动补。
- MUST NOT 测：私有函数/实现细节、框架本身、语言特性(getter 返回了它该返回的)。
- 改个内部写法就变红的测试是**负债**——它测的是实现不是行为，删掉或重写。
- 一个行为一个测试函数。函数名描述行为，不写编号。

## 2) 先定位，再决定新建（对治文件爆炸）

写任何测试前 MUST 先回答：**"这个行为现在在哪个文件测?"**

- 已有覆盖它的文件 → **扩它**(加用例/参数化)，不新建。
- 确实没有合适文件才新建，并在 `tasks.md` 测试策略段写明新建理由。
- 默认动作是"找到并扩展现有文件"，不是"新建 `test_<milestone>.py`"。
- 新测试覆盖了旧测试的断言 → 删旧的。

## 3) 命名与落层

**命名**：文件名/函数名描述**被测行为**。
- ✅ `test_loop_compact.py` / `test_mark_stale_for_node`
- ❌ MUST NOT 用流水号：`test_m170_*` / `test_bugfix358_*` / `test_refactor353_corrigendum` / `*_rerun_acceptance`。milestone 编号是"写的时候"的上下文，半年后无人能解读。

**落层**：目录即分层，按"被测范围最低能覆盖它的那一层"选：

| 测什么 | 目录 | marker |
|---|---|---|
| 纯逻辑、单模块 | `tests/unit/` | — |
| 跨模块/真实入口(HTTP/CLI 子进程,本地无浏览器) | `tests/integration/` | — |
| 架构边界/契约(依赖方向、事件 schema) | `tests/contract/` | — |
| 起真进程 / 真浏览器 / 真 LLM / 重外部依赖 | `tests/e2e/` | `@pytest.mark.e2e` |

- 浏览器(playwright)、真实 LLM、真实长驻进程的测试 **MUST 放 `tests/e2e/` 且打 `@pytest.mark.e2e`**。放错目录会让 `pytest -m "not e2e"` 误跑它。
- **目录与 marker 必须一致**:放进 `tests/e2e/` 就 MUST 打 `@pytest.mark.e2e`。只放目录不打 marker 会让 `pytest -m "not e2e"` 照跑它，而它需要真实进程/浏览器 → 失败。(用 `tests/conftest.py` 给 e2e 目录自动打 marker 也可，但每个文件显式写更稳。)

## 4) 跨层不重复

- 一个行为只在**最低能覆盖它的那一层**断言一次。
- unit 已覆盖的逻辑，integration **只验"接起来了/跨边界正确"**，不重新断言同一逻辑。
- 不要为同一个 milestone 在 unit + integration + e2e 各写一遍同样的断言。

## 5) 可选/重依赖必须优雅跳过

外部或可选依赖(playwright、需要起服务的库等)**MUST NOT 在模块顶层裸 import**——否则缺依赖时整个 `pytest --co` 收集中断，全套测试一个都跑不了。

```python
import pytest
playwright = pytest.importorskip("playwright")   # 缺依赖 → skip 本文件，不炸收集
```

## 6) 临时验收证据 ≠ 永久回归测试

TDD 过程里产生两种东西，去向不同：

- **一次性验收证据**(手动验收脚本、截图、"这次交付时验一下"的清单)：路径/结论记进 `progress.md`，**MUST NOT 作为 `test_*.py` 提交进测试套件**。milestone 收尾删掉一次性脚本。
- **永久回归测试**(以后每次改动都该跑、有长期回归价值的断言)：才进 `tests/` 套件。

判据:问自己"半年后这个测试还该每次 CI 都跑吗?"——否 → 它是验收证据，不是回归测试。

**被测逻辑 MUST 住在 `src/`，不靠 `importlib` exec 一次性脚本取用。** 反模式:把有回归价值的纯逻辑(DB 读取、解析、状态判定)留在 `ACCEPTANCE/*.py` 这类一次性验收脚本里，测试用 `importlib.util.spec_from_file_location` 把整个脚本 exec 进来取函数。后果:① 脚本的顶层依赖(playwright 等)会连坐进收集，缺依赖就炸；② 被测逻辑不在产品代码里，等于没真正落地。正确做法:有长期价值的逻辑提进 `src/`，测试直接 `import`；一次性脚本不作为被测对象。

## 7) 结构与上限

- AAA 结构(Arrange-Act-Assert)，一个测试一个清晰主题。
- 单测试文件软上限 **400 行**，超了按行为拆分。(现存 2000+ 行文件是反面教材。)
- MUST NOT `skip`/`xfail` 蒙混过关。测试该绿就让它绿，该删就删。
- 复用现有 fixture/helper，不重复造。

## 8) tasks.md 测试策略段必填

`tasks.md` 的"测试策略"不写散文，按以下填空(逼出第 2/3/6 节的决策)：

```markdown
## 测试策略

- 被测行为(来自退出标准): <逐条列>
- 已有测试在: `<file>`(扩展) / 无,新建 `<file>`,理由: ___
- 落层/目录/marker: tests/<unit|integration|contract|e2e>/ , marker: <e2e|无>
- 可选依赖 importorskip: <有,哪些> / 无
- 本 milestone 产生的一次性验收证据(收尾删除,不进套件): <列出> / 无
```
