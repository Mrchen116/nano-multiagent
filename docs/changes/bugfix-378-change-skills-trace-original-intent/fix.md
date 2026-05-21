# bugfix-378: change skills 修 bug 时不追溯原始设计意图，导致阉割式修复

## Relations

- Related: 无（本 unit 改动对象是 `.claude/skills/change-*`，不涉及产品代码）

## 原始报告

> 我发现现在用 change-spec-author，change-design-author，change-orchestrator 这套 skill 去做 bugfix 的时候，agent 不会主动去看 bug 对应代码的对应之前 change 的原始设计意图，然后就可能出现错误修复，比如某功能出错了，没看设计意图导致该功能以阉割的方式被修复。你看下应该是哪个/些 skill 的责任。

（本 unit 为回顾性记录：修改已先行完成，再补 spec 立单。）

## 现象 / 复现

用 `change-*` 这套 skill 修 bug 时，agent 拿到一个报错/异常，直接奔向"怎么让它不报"。最省事的修法往往是把触发出错的那条代码路径砍掉——症状消失，但被修功能的原始能力同时被阉割成残废。事后没人发现，因为没有任何环节记录过"这功能本来该干什么"。

复现路径（结构性，非偶发）：任意一个 bugfix unit，被修代码属于某个既有功能 → 走 spec → (full 才有 design) → orchestrator → worker。全程无人要求"先找到引入这块功能的原始 change unit、读它的设计意图"。

## 根因

三个 skill 没有任何一处要求"追溯被修代码所属的原始 change unit、读它的设计意图、记下不能违背的不变量"。逐层定位：

- **spec-author（主责，唯一在 lite/full 都跑的阶段）**：§4 bugfix RCA 只要求挖"哪行错了 + 为什么这种错能进来"，完全不挖"这块功能原本想达成什么"。fix.md 模板根因段注释同样只到"为什么这种错能进来"。
- **design-author（次责，仅 full）**：§3.0 必读清单【历史相关变更】行存在但弱——框定为"近期改过同一区域的 unit"（找冲突），不是"被修功能的原始意图"（找约束）；且 lite 路径根本不走这个 skill。
- **lite 结构空洞**：lite 跳过 design-author，worker 只读 `fix.md`，而 fix.md 模板不承载原功能意图，worker 手里没有任何意图锚点。

为什么这种错能进来：RCA 的定义只覆盖"错误如何进入"，遗漏了对偶的"功能本应如何"。修复方向的正确性约束从未被文档化，于是每个 agent 各凭临场判断，系统性地倒向"消症状"而非"保功能"。

## 修复

把"追溯原始设计意图 + 记下必须保住的不变量"钉进文档化输入，让约束随文档流向下游：

- `change-spec-author/SKILL.md` §4：bugfix-full RCA 下新增"原始设计意图追溯"子条目——grep `docs/changes/` 找到引入功能的 unit，读 spec/design，写下"本来要达成什么"+"修复必须保住的不变量"，并解释为何不写就会滑向阉割式修复。
- `change-spec-author/assets/fix.md`：根因段注释增补意图追溯指引，专门点出"lite 没有 design 阶段、worker 只读这份 fix.md"，所以意图必须在 spec 阶段落进 fix.md（覆盖 lite 路径）。
- `change-design-author/SKILL.md` §3.0：【历史相关变更】行强化为"历史相关变更 / 原始意图"，并新增"bugfix 专属"段，把原意图当作 §3.2 关键决策的**硬约束**带入；显式说明 incident RCA 已写则沿用，避免 full 路径重复挖掘（覆盖 full 路径二次保险）。

措辞遵循 skill-creator 指南：祈使句、解释 why（不写意图→最省事修法=砍路径→功能阉割），不堆 ALL-CAPS MUST，贴合各 skill 既有"先给规则再给为什么"的风格。改动克制，未触碰澄清流程、门禁、milestone 拆分等无关段落。

## 验证

- 修前：三个 skill 全文 grep "设计意图 / 原意图 / 不变量"在 bugfix 根因/调研语境下无命中——约束不存在。
- 修后：spec-author RCA、fix.md 模板、design-author §3.0 三处均落下"追溯原始意图 + 记不变量"的指引，且 lite（fix.md）/ full（incident RCA + design §3.0）两条路径都被覆盖。
- 一致性：三处措辞互相呼应（同一句"砍路径→症状消→功能阉割"的因果），design-author 显式引用 incident RCA 产物避免重复劳动，闭环无悬空。
