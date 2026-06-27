# bugfix-443: subagent 与各侧链未继承父 run 的模型，回退到全局默认

## Relations

- Related: bugfix-429-per-agent-model-selection
- Related: feat-436-per-model-context-window

## 原始报告

> http://127.0.0.1:8011/chat/4ea3ee3d0459409d8da05a71bf541c73 他说subagent网络流中断，你分析日志和代码，看看具体啥问题。
> logs/session/2026-06-27_13-27-47_868_sess_69cf7b4c3e4a71d1/2026-06-27_13-35-01_845-downstream-res-anthropic_messages.json
> 关键问题是这个吧，为啥没触发压缩。Your request exceeded model token limit: 262144 (requested: 288167)"},"type":"error"}。而且为啥主agent用的mimo，subagent用的kimi，我们设计的时候要求的是subagent和主agent一致

> 最近某个unit才做了模型设自定义窗口的功能，当时应该要求了subagent和主agent必须一致，你看下对应文档

> 你再检查下，有没有其他的地方有问题，subagent，background的skill，memory 自进化agent，压缩用的llm，都得是同一个模型。

## 澄清记录

- Q1: "subagent 和主 agent 必须一致" 是硬不变量还是"默认继承、允许显式覆盖"？
  A(原话): 对
  Agent 解读: 认可推荐——默认继承父 run 模型，保留"显式指定才覆盖"的口子（当前内核未暴露该入口，故实际表现=永远继承）。
- Q2: 压缩的 `summary_model` 独立模型能力是砍掉还是保留？
  A(原话): 保留
  Agent 解读: 保留 `summary_model` 显式覆盖口子；只修"未配 summary_model 时回退到全局默认而非父 run"这个 bug。
- Q3: 回归矩阵列全五条侧链路径，还是只列两个真正要改的破口（A subagent / B 主动压缩）？
  A(原话): 对的不用了 …… 理解错了，我说的都会是现在已经是对的就不用再次回归了
  Agent 解读: 修复落点只在 A、B 两处；已经对的路径（overflow/手动压缩、background-memory fork、hook model_caller）逻辑本就正确，不单独立回归项——它们在 subagent 下的错只是 A 的连带，修好 A 即自动恢复，无需为它们各写回归。

## 现象与复现

**触发场景**：一个配置了非全局默认模型的 agent（例：`hume`，`default_model: mimo:mimo-v2.5-pro`，上下文窗口 1048576）在对话中派发了一个 subagent（Agent 工具，如 Explore 型）。

**复现步骤**（真实案例，session `sess_69cf7b4c3e4a71d1`）：
1. 用 `hume`（mimo）发起一段会触发 subagent 的任务。
2. subagent 做大量文件读取，上下文持续增长。
3. 观察 LLM proxy 日志里 subagent 发出的请求模型。

**期望**：subagent 的 LLM 请求模型 = 父 agent 的模型（mimo，窗口 1048576）。长上下文在 mimo 的百万窗口内，正常完成。

**实际**：
- subagent 的请求模型是 **kimiCoding:K2.6**（全局 `llm.default_model`，窗口仅 262144），**不是** mimo。
- 上下文一路涨到 256k 顶在 kimi 窗口附近，主动压缩**从未触发**（subagent 的压缩 summarizer 也用错了模型/未按父 run 模型判定），最终一个请求达到 288167 tokens，超过 kimi 的 262144 硬上限被拒（`Your request exceeded model token limit: 262144 (requested: 288167)`）。
- 同一个超限请求被原样重试 6 次后失败，在 IM 端表现为"subagent 网络流中断"。

**第二个独立现象（不依赖 subagent）**：即便是顶层主 agent（mimo），当它在一次 run 内压到压缩阈值时，**主动阈值压缩的 summarizer 也用全局默认 kimi 去做摘要**，而非 mimo——摘要走了错误的模型，长上下文场景下还可能让摘要请求本身超限。

## 影响范围

受影响对象：任何 `default_model` 不等于全局 `llm.default_model` 的 agent。

下表是五条"应当跟随父 run 模型"的侧链路径的实际表现（已逐条核对源码）：

| 路径 | 取模型方式 | 主 agent 下 | subagent 下 | 本单处置 |
|---|---|---|---|---|
| subagent 自身对话 | `runtime.run` 未传 model → 回退 `self._model`（全局默认） | — | ❌ 错（**根因 A**） | **修复点** |
| 主动阈值压缩 summarizer | `loop.py` 调 `summarize()` 未传 `model_override` → fork 回退构造期默认 | ❌ 错 | ❌ 错 | **修复点（根因 B）** |
| overflow / 手动压缩 summarizer | 读 `_active_run_models` | ✅ 对 | ❌ 错（A 连带） | 修 A 后自动恢复，不单独回归 |
| background skill / memory 自进化 fork | `make_fork_conversation(model=model)` | ✅ 对 | ❌ 错（A 连带） | 修 A 后自动恢复，不单独回归 |
| hook model_caller（gate 分类器等） | `call.model or _active_run_models.get(...) or 默认` | ✅ 对 | ❌ 错（A 连带） | 修 A 后自动恢复，不单独回归 |

严重度：在窗口小于父模型的全局默认模型上，长上下文 subagent **必然崩溃**（如本案的 token 超限），且无数据损坏（请求被拒，不写脏数据）；窗口足够大时则表现为"静默用错模型"（计费/行为与设计不符，难以察觉）。

无数据损坏。

## 根因分析（RCA）

### 直接根因

- **根因 A（subagent run 不携带 model）**：Agent 工具派发 subagent 走 `agent.py → subagent_runner.start() → runtime.run(...)`，调用处**不传 model**（`runtime_runner.py:59`）。`runtime.run` 内 `if model: self._active_run_models[session_id] = model`（`runtime.py:353-354`）——model 为 None 时这张表**不登记** subagent，且 loop 内 `active_model = model_override or self._model` 回退到构造期注入的全局默认（`loop.py:204`）。于是 subagent 自身、以及所有读 `_active_run_models` 跟随 run 模型的下游侧链，全部拿不到父模型 → 集体回退全局默认。
- **根因 B（主动阈值压缩 summarizer 漏传 model_override）**：`summarize()` 有三个调用方；overflow 恢复（`runtime.py:_compact_session`）和手动 `compact()`（`runtime.py:1937`）都传了 `model_override=_active_run_models.get(session_id)`，唯独 loop 内的主动阈值压缩（`loop.py:910`）**没传**——而这恰是正常长对话里最常触发的那条。结果该路径的 summarizer 永远用构造期默认模型。

### 为什么这种错能进来（深层）

- **原始设计意图追溯**：本块行为属 **bugfix-429（per-agent model selection）**。其契约（`docs/specs/kernel/spec.md` "Scenario: 同一 run 的内核续跑复用本 run 的 model"）明确要求：run 的模型由消费者每轮提供，**续跑/侧链复用本 run 模型，不回退任何内核默认**。**必须保住的不变量**：同一 run 及其全部侧链全程使用同一个（消费者指定的）模型，绝不回退到内核构造期的全局默认。本单是对该不变量的**补全**，不得为修复而破坏该契约（例如不能反过来把主 agent 也钉死全局默认）。
- **bugfix-429 的覆盖盲区**：bugfix-429 把 model 改为 per-run，并枚举了"新 run 入口"逐个补 model 透传——但只列了 Gateway inbound_pipeline / heartbeat / cron / coding_cli（design.md 决策2），**漏掉了 subagent_runner 这条入口**。subagent 派发**绕过** `kernel.submit → RunRecord` 透传链，直接调 `runtime.run`，所以 bugfix-429 加的透传完全没覆盖它（根因 A）。
- **测试盲区**：bugfix-429 的红测（commit `bf1ba9bd`）声称覆盖"侧链 per-run model（hook/compaction）"，但 compaction 部分只测了 runtime.py 的 overflow/手动两条路径，**没测 loop 内主动阈值压缩**那条（根因 B）。
- **验证误判**：bugfix-429 `verification.md:99` 断言"所有真实调用方现均传 model_override"——该论断未经审计即写入，`subagent_runner` 就是一个**不传**的真实调用方，反证此论断为假。

### 放大因子（非本单修复，记录在案）

- 错误分类器（`error_classifier.py`）的 permanent 文本白名单只含 "context window"/"context length"，不含 "token limit"，导致 "exceeded model token limit" 这个本应一次判死的超限错误被当作可重试，**同一超限请求白白重试了 6 次**才失败，放大了故障表现。属独立的健壮性问题，列入非目标（见下），可另开单。

## 修复方向

> 高层方向；行级实现留 milestone。

1. **修根因 A（源头，一处修复连锁恢复全部侧链）**：让 subagent 派发链把**父 run 的模型**透传进 subagent 的 `runtime.run(model=...)`——从派发上下文 / `_active_run_models[parent_session]` 取父模型，经 `subagent_runner.start(..., model=)` → `runtime.run(model=)` 传入。subagent run 一旦登记自己的 model 到 `_active_run_models`，overflow 压缩 / background-memory fork / hook model_caller 这些已正确读该表的路径**自动跟随**，无需各自再改。
   - 保留 Q1 决策的"显式覆盖"语义口子：未指定 → 继承父 run；将来若暴露 per-subagent model 入口，显式值优先（当前内核未暴露该入口，故实际表现=永远继承）。
2. **修根因 B（独立）**：`loop.py:910` 的主动阈值压缩给 `summarize()` 补上 `model_override`，与另两个调用方对齐——遵循 Q2 决策：未配 `summary_model` → 用本 run 模型；显式配了 `summary_model` → 仍用该独立模型。
3. **补契约 + 纠正验证**：在 `docs/specs/kernel/spec.md` 补一条"子 agent 复用父 run 模型"的 Scenario，把 bugfix-429 漏掉的不变量显式化；并纠正 bugfix-429 `verification.md:99` 那条错误论断（subagent_runner 是不传 model 的真实调用方）。

**非目标（本单不做）**：
- 不修错误分类器对 "token limit" 的 permanent 判定（放大因子，独立健壮性问题，可另开单）。
- 不暴露面向用户的 per-subagent 模型选择入口（只保留内核侧的覆盖语义口子，不做 UI/配置面）。
- 不改主 agent / 续跑 / 已正确侧链的现有行为（仅补 subagent 与主动压缩两处，不得破坏 bugfix-429 既有不变量）。
- 不为"已经正确"的路径（overflow/手动压缩、background-memory fork、hook model_caller）新增独立回归项（Q3 决策）。
