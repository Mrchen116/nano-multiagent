# bugfix-448: web_fetch 取消与 prompt 处理退化

## Relations

- Closes: #169
- Related: bugfix-355
- Related: bugfix-402
- Related: bugfix-417
- Related: feat-335
- Related: feat-425

## 原始报告

> [https://github.com/Mrchen116/nano-multiagent/issues/169](https://github.com/Mrchen116/nano-multiagent/issues/169) 结合CC的代码，分析这个问题，看是不是真问题

> 所以真问题的影响是啥

> 在issue中加评论

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 开始

GitHub issue: https://github.com/Mrchen116/nano-multiagent/issues/169

Issue #169 关键原文：

> M2 session 反复调用 `web_fetch` 抓取 npmjs.com/github.com，每次结果变成 `[orphaned]`，模型拿不到结果就无限重试（观测到同一对 URL 重试 7 次）。

> 根因：`web_fetch.run()` 内的 `_process_with_prompt` 做了一次**同步阻塞 LLM 调用**，无 timeout、无 cancel signal。

> CC 的 `WebFetchTool.call()` 接收执行框架注入的 `abortController`，**signal 贯穿全链路**。

## 澄清记录

- Q1: 这个 `bugfix-448` 的范围要覆盖“两个实际问题”吗：一是工具取消后后台同步工具仍继续跑，二是 `web_fetch(prompt=...)` 当前静默退化为原文返回？
  A(原话): 对
  Agent 解读: 本 unit 覆盖两类用户可见可靠性缺陷：取消后工具仍后台继续执行造成资源/结果不可靠，以及 `web_fetch(prompt=...)` 没有按 prompt 处理内容而静默退化。

- Q2: 用户主动 `/stop` / Ctrl-C 中断一个正在 `web_fetch` 的 run 后，用户可见的目标状态是什么？
  A(原话): 和CC的用户侧体验类似
  Agent 解读: 目标是对齐 Claude Code 的用户可见中断体验：用户能看到明确中断结果，模型上下文收到明确的用户中断工具结果，后续同会话可继续；中断后的晚到工具结果不应驱动模型继续重试同一抓取链路。

- Q3: `web_fetch(url, prompt=...)` 成功时，用户/模型应该拿到什么结果？
  A(原话): 像CC一样
  Agent 解读: prompt 存在且处理成功时，模型应拿到按 prompt 从网页内容加工后的回答/摘要，而不是未处理原文；prompt 处理失败时不能静默伪装成“已按 prompt 处理成功”。

- Q4: 取消语义这一块，本 unit 要只保证 `web_fetch`，还是要保证所有同步工具的用户可见取消体验？结合 CC 与本仓历史 unit 后，推荐定为：用户可见取消语义按既有全局不变量对齐，作为全局约束；实现范围先覆盖 `web_fetch` 这个复现工具及同类长耗时/可取消工具的接入点，不要求每个瞬时工具都写特殊取消逻辑。这样定吗？
  A(原话): 对。继续澄清
  Agent 解读: 本 unit 不把 `web_fetch` 做成孤立特例；它必须回到既有全局取消体系。全局验收关注 run 释放、transcript 闭合、IM/CLI 可继续、晚到结果不污染后续轮次；工具级改造聚焦长耗时且有可取消底层操作的工具，`web_fetch` 为必修复复现面。

- Q5: `web_fetch(prompt=...)` 的 prompt 处理如果失败，用户/模型侧应该怎么表现？按 CC 实际行为精确化：用户主动中断用 `[Request interrupted by user for tool use]`；二次 LLM 处理失败没有固定 WebFetch 专属文案，而是返回明确 error tool_result，content 保留真实错误原因，不静默 fallback 成原文。这样定吗？
  A(原话): 对。
  Agent 解读: `web_fetch(prompt=...)` 只能有两类合法终态：成功时返回 prompt 加工后的结果；失败时返回明确错误结果。用户主动中断复用既有 CC 对齐文案 `[Request interrupted by user for tool use]`，非中断错误保留真实异常原因；禁止把二次 LLM 失败吞掉并返回未加工网页原文。

- Q6: `web_fetch(prompt=...)` 的二次 LLM 处理要不要单独设一个 WebFetch 专属超时？结合 CC 实现：WebFetch 的 HTTP 抓取有自己的 fetch timeout 并接收同一取消信号；prompt 二次 LLM 处理不在 WebFetch 内另设专属 timeout，而是把同一 signal 传给 `queryHaiku`，由统一 LLM 调用层负责超时/失败/取消。这个边界是否按 CC 对齐？
  A(原话): 和CC对齐
  Agent 解读: 本 unit 不为 prompt 二次处理新增 WebFetch 专属 timeout 策略。HTTP 抓取保留工具自身请求超时并接入取消；prompt 二次 LLM 处理必须走统一 LLM client 的流式、超时、重试和取消语义，且同一用户中断信号贯穿 fetch 与 prompt 两段。

- Q7: CC 在 `content-type` 是 `text/markdown`、内容长度小于上限、且命中预批准域名时会直接返回 markdown 原文，不走 prompt 二次 LLM。这个分支本 unit 要不要引入？如果引入，是否也绑定 CC 的预批准域名条件？
  A(原话): 内容类型是 text/markdown、内容长度小于上限，直接返回 markdown 原文。这个可以。不需要预批准域名
  Agent 解读: 本 unit 允许增加一个与权限策略解耦的短 markdown 直返优化：只要抓取结果明确是 `text/markdown` 且内容长度小于上限，即可直接返回 markdown 原文；不要求命中 CC 的 preapproved host 表。该分支属于结果处理策略，不改变 `web_fetch` 的访问权限判定。

## 现象与复现

这个问题有两层现象，issue #169 里的“根因描述”只命中了其中一部分，而且与当前 `main`
已有版本漂移：

1. 用户让 agent 抓取网页资料时，模型会调用 `web_fetch`。如果网页抓取或后续处理耗时较长，用户在
   IM 里 `/stop` 或在 CLI 里 Ctrl-C 后，run 层可以进入中断收尾，但底层同步工具线程并不会被
   Python 的 async cancel 直接杀掉。`web_fetch` 的 HTTP 请求仍可能继续跑到自己的请求超时或自然返回。
2. `web_fetch(url, prompt=...)` 在当前实现中没有可靠地执行“抓网页后按 prompt 二次处理”的承诺。
   `_process_with_prompt()` 仍按旧的非流式接口构造 `LLMGenerateRequest(stream=False)`，而当前
   `LLMGenerateRequest` 已没有 `stream` 字段；异常随后被吞掉，工具静默返回原始网页正文。
3. issue 中观察到的 `[orphaned]` 无限重试是历史/特定会话上的坏结果表现。当前仓已有
   `bugfix-402`/`bugfix-417` 的 transcript recovery 和用户中断回填，用户主动中断应回填
   `[Request interrupted by user for tool use]`。但这不代表问题已经消失：底层工具取消链路仍未贯穿，
   prompt 处理仍会静默退化。

稳定复现路径：

1. 让模型调用 `web_fetch` 抓取一个响应慢或内容较大的网页。
2. 在工具执行中对当前 run 执行 `/stop` 或 CLI Ctrl-C。
3. 观察用户侧是否能立即看到中断收尾、同会话继续可用，并确认没有晚到的 `web_fetch` 结果污染下一轮。
4. 让模型调用 `web_fetch(url, prompt="总结/提取某信息")` 抓取普通网页。
5. 观察模型拿到的是按 prompt 加工后的结果，还是未经处理的网页正文。

## 用户场景 / 目标状态

用户在 IM 或 CLI 里让 agent 查 npm、GitHub、文档站等网页资料。agent 可能先抓网页，再按 prompt
提取版本、API、错误原因或摘要。用户看到工具卡开始运行后，如果觉得方向错了、耗时太久，或者想改问法，
会用 `/stop` / Ctrl-C 主动停止这一轮。

修复后，用户主动停止时，这一轮应像 CC 一样明确收口：工具卡显示已中断，模型上下文里也得到同一份
“用户主动中断工具使用”的结果，因此后续不会把它理解成网页抓取失败再自动重试。同一会话马上可以继续提问。

当用户没有中断，而 `web_fetch` 携带 prompt 成功抓到网页时，模型拿到的应是按 prompt 处理后的内容，
不是原始网页正文。若二次 LLM 处理失败，用户/模型应看到明确错误，而不是一个看似成功、实则未按 prompt
处理的结果。

对于短 markdown 文档，若响应明确是 `text/markdown` 且内容长度小于上限，可以直接返回 markdown 原文；
这个优化不改变访问权限，只避免对已经是合适格式的短内容做无意义二次处理。

## 验收标准 / 目标状态

### Requirement: 用户中断 web_fetch 后会话可继续

#### Scenario: IM 中 `/stop` 一个正在执行的 web_fetch
- **GIVEN** agent 当前正在执行一次耗时的 `web_fetch`
- **WHEN** 用户在 IM 中发送 `/stop`
- **THEN** 当前工具卡收口为“已中断”
- **AND** 工具返回内容包含 `[Request interrupted by user for tool use]`
- **AND** 同一会话可以立刻继续提问并得到新回复

#### Scenario: CLI 中 Ctrl-C 一个正在执行的 web_fetch
- **GIVEN** CLI 当前正在执行一次耗时的 `web_fetch`
- **WHEN** 用户按 Ctrl-C
- **THEN** 当前轮次停止，CLI 保持可继续输入
- **AND** 模型上下文中的工具结果表达用户主动中断，而不是网页抓取失败

#### Scenario: 中断后的晚到结果不污染下一轮
- **GIVEN** 用户已经中断了一次 `web_fetch`
- **WHEN** 用户在同一会话继续提出新问题
- **THEN** 下一轮不应收到上一轮晚到的网页内容
- **AND** 模型不应因为上一轮工具结果缺失而反复重试同一 URL

### Requirement: web_fetch(prompt) 返回符合 prompt 的处理结果

#### Scenario: prompt 二次处理成功
- **GIVEN** 网页抓取成功，且调用参数包含 `prompt`
- **WHEN** 二次 LLM 处理成功
- **THEN** 模型收到按 prompt 加工后的回答或摘要
- **AND** 不应收到未经 prompt 处理的原始网页正文作为“成功结果”

#### Scenario: prompt 二次处理失败
- **GIVEN** 网页抓取成功，但 prompt 二次 LLM 处理失败
- **WHEN** 工具返回给模型
- **THEN** 工具结果是明确错误
- **AND** 错误内容保留真实失败原因
- **AND** 不允许静默 fallback 成原始网页正文

#### Scenario: 用户在 prompt 二次处理中断
- **GIVEN** 网页抓取已完成，`web_fetch` 正在按 prompt 做二次处理
- **WHEN** 用户中断当前 run
- **THEN** 工具结果按用户主动中断收口
- **AND** 内容使用 `[Request interrupted by user for tool use]`

### Requirement: 短 markdown 可以直接返回

#### Scenario: text/markdown 且内容长度小于上限
- **GIVEN** `web_fetch` 成功抓取到 `content-type` 为 `text/markdown` 的响应
- **AND** 响应内容长度小于本工具设定的 prompt 处理上限
- **WHEN** 工具需要返回结果
- **THEN** 模型收到 markdown 原文
- **AND** 这个直返分支不依赖预批准域名

### Requirement: 既有 WebFetch 用户体验不回退

#### Scenario: 普通网页抓取展示正文
- **GIVEN** `web_fetch` 成功抓取普通 HTML 网页
- **WHEN** 用户展开 IM 工具卡
- **THEN** 工具卡仍显示 URL、状态码和抓到的正文

#### Scenario: 访问权限策略保持不变
- **GIVEN** 用户触发 `web_fetch` 访问一个未自动允许的域名
- **WHEN** 权限系统需要决策
- **THEN** 仍按既有 WebFetch 权限规则要求确认或拒绝
- **AND** 本 unit 不因为短 markdown 直返而绕过权限判定

## 影响范围

受影响的是所有依赖 `web_fetch` 查网页资料的用户旅程，尤其是：

- IM 用户在长网页抓取中使用 `/stop` 后，希望 agent 停止当前方向并继续对话。
- CLI 用户在长网页抓取中使用 Ctrl-C 后，希望 CLI 不退出、同一会话继续可用。
- 模型需要从 npm、GitHub、文档站等网页里按 prompt 提取信息，而不是只把原文塞回上下文。

严重性：中高。它不会直接损坏用户文件或业务数据，但会造成三类用户可见问题：

- 资源浪费：用户已中断，底层 HTTP/处理链路仍可能继续跑到超时或自然结束。
- 交互失真：模型可能把“用户主动停止”误解成抓取失败或缺结果，从而重复抓同一 URL。
- 内容错误：`web_fetch(prompt=...)` 看似成功，实际返回未加工正文，模型后续回答可能建立在错误输入上。

持久化风险：当前 `bugfix-402`/`bugfix-417` 已经建立 transcript recovery，不应再把这类中断写成裸
orphaned tool call；本 unit 的风险主要是保持这个不变量，并补上底层取消和 prompt 处理语义。

## 根因分析（RCA）

### 直接根因

1. `ToolRegistry.execute()` 仍以 `await asyncio.to_thread(tool.run, ...)` 执行同步工具。
   取消外层 await 只能取消等待者，不能强杀 Python worker thread。`bugfix-417/M6` 给所有长工具补了
   通用 liveness 心跳，解决“沉默工具被 watchdog 误收尸”，但没有让每个工具的底层 I/O 都可取消。
2. `web_fetch` 的 HTTP 抓取使用同步 `httpx.Client(...).get(...)`，只有固定请求 timeout，没有接收 run
   的取消信号。因此用户主动停止后，HTTP 请求可能继续在 worker thread 里跑。
3. `_process_with_prompt()` 仍按旧的非流式 LLM 调用形态写：它向 `LLMGenerateRequest` 传入已不存在的
   `stream=False` 字段，并把所有异常吞掉后返回原始 content。结果是 prompt 分支静默退化，且没有把取消、
   超时、错误结果统一交给现有 LLM 调用层。

### 为什么能进来

- `feat(web_fetch): platform builtin with markdownify and prompt-based LLM processing` 引入了 prompt 分支，
  但当时缺少覆盖“prompt 确实触发二次 LLM”“二次 LLM 失败不能伪装成功”的单测。
- 后续 `bugfix-355` 只围绕 WebFetch 权限模型对齐 CC；它没有审阅或重定 WebFetch 结果处理语义。
- `feat-425` 只修工具展示字段，明确不改抓取逻辑、权限模型、SSRF 等非展示层行为；它增加了 `content`/
  `final_url` 这类展示字段，但没有验证 prompt 分支仍然有效。
- `bugfix-417` 把用户中断文案、前台 bash stopper 和通用 liveness 做成不变量，但 WebFetch 没有像 bash
  那样把“如何停止底层工作”登记进取消链路，导致长同步工具仍有取消债。

### 原始设计意图追溯

- `bugfix-355` 的 WebFetch 原意图：权限层严格对齐 CC。修复时必须保住 URL 校验、preapproved host、
  hostname rule、fallback ask 这些访问决策，不得因为修结果处理绕过权限。
- `feat-425` 的 WebFetch 原意图：工具展示随工具走，成功卡片显示 URL、状态码和正文；失败卡片显示可读错误。
  修复时必须保住 `content`/`final_url` 展示面，不得让 IM 展开卡重新变空或回到机器串。
- `bugfix-402` 的原意图：任何进入下一次模型请求的 transcript 都不能有未闭合 tool call。修复时必须保证中断、
  错误、取消都产生合法 tool result。
- `bugfix-417` 的原意图：用户主动中断要用 CC 原串 `[Request interrupted by user for tool use]`，
  且同一份 content 进入模型 transcript 和用户工具卡。修复时必须复用这个全局不变量，而不是为
  `web_fetch` 发明另一套中断文案。

### 回归 / 引入点

- Prompt 静默退化的坏行为来自 `2be76c27 feat(web_fetch): platform builtin with markdownify and prompt-based LLM processing`。
  这里同时引入了旧式 `stream=False` 调用和“LLM failed → return original content”的吞错策略。
- `web_fetch` 取消链路缺口不是单个回归提交，而是同步工具模型的历史债：`60724631 feat(bugfix-417/M6)`
  把 liveness 上提后明确让 `web_fetch` 这类长工具不再沉默，但它的目标不是取消底层 I/O；本 unit 要补的是
  这条剩余生命周期边界。

## 修复方向

本 unit 要修用户可见语义，不在 spec 阶段指定具体代码结构：

- `web_fetch` 的 HTTP 抓取和 prompt 二次处理都必须接入同一用户中断链路；用户 `/stop` / Ctrl-C 后，
  工具结果按 CC 对齐的用户中断内容收口。
- `web_fetch(prompt=...)` 成功时必须返回 prompt 加工后的内容；二次 LLM 处理失败时返回明确错误，禁止静默返回原文。
- prompt 二次处理不新增 WebFetch 专属超时策略；它应走统一 LLM 调用层已有的超时、失败、取消语义。
- 短 markdown 直返作为结果处理策略允许存在：`content-type` 是 `text/markdown` 且内容长度小于上限时，
  直接返回 markdown 原文；该分支不依赖预批准域名，也不改变权限判定。
- 保持既有 WebFetch 权限、SSRF 校验、展示字段、transcript recovery、中断文案不变量。

## 范围与非目标

范围内：

- `web_fetch` 长耗时执行中的用户主动中断体验。
- `web_fetch(prompt=...)` 的成功、失败、中断三类结果语义。
- 与 `web_fetch` 同类、已有可取消底层操作的长耗时工具接入点盘点；但验收必修复面是 `web_fetch`。
- 覆盖 IM `/stop` 与 CLI Ctrl-C 两个用户入口。

非目标：

- 不重做 WebFetch 权限模型，不新增或删除 preapproved host 表。
- 不改变 SSRF 校验策略、URL 解析规则、hostname rule 行为。
- 不改变 WebFetch 的用户可见展示目标：成功仍显示 URL、状态码、正文；失败仍显示可读错误。
- 不要求每个瞬时同步工具都实现专属取消逻辑。
- 不引入 WebFetch 专属 prompt LLM timeout 策略。
- 不恢复或兼容历史 `[orphaned]` 文案作为用户主动中断结果；用户主动中断统一使用 CC 原串。
