# bugfix-433-M1: 图片输入端到端送达 + 跨轮持久化 — Tasks

> 对齐: ../design.md（design-review 第3轮 Approved）

## 目标

用户经 personal_assistant（IM）给 agent 发图：当前轮 agent 即可看到图片作答；同会话下一轮只发文字追问该图，agent 仍能看到；纯文本对话零回归；异常图片（无法获取/过大/损坏）本轮停下、回发明确「未送达模型」提示、不调模型、不编造、会话不崩。

## 退出标准

- [ ] 用户发图当轮 agent 即可作答（单轮发图即问、单轮发多张图）
- [ ] 上轮发图、下轮只发文字仍可追问（跨轮保留）
- [ ] 纯文本多轮与修复前无可观察差异（无回归）
- [ ] 异常图片：用户收到「未送达模型 + 原因 + 建议」明确提示、不调模型、对话不崩
- [ ] 端到端往返单测：发图→送达 provider mapper→落盘 entry.parts→重建 Message.parts→下一轮含 image 块
- [ ] 多图单测：单条消息多 image part 经 M246 展开后**全部**送达（守 CRITICAL-1）
- [ ] Anthropic / OpenAI-compat mapper user 分支 image 块映射各有单测
- [ ] 纯文本 session 持久化/回放既有测试 + golden 不回归
- [ ] `pytest -m "not e2e"` 全绿、ruff check + format clean

## 测试策略

- 被测行为（来自退出标准）：
  1. 当前轮图片随结构化 parts 透传到 build_chat_messages → LLMMessage.content 为 list（R1）
  2. 两 provider mapper user 分支把 content:list 的 image 块映射成各自 image 形态（R1）
  3. Message 加 parts；submit 路径 _message_to_entry 写 parts、_to_message/entries 读回（R2）
  4. 端到端往返：发图→落盘 entry.parts→重建 Message.parts→下轮 build_chat_messages 仍含 image 块（R2）
  5. 多图经 M246 展开全部送达（R3）
  6. 纯文本 parts=None 走 str 分支零扰动；守护测试更新（R2）
  7. gateway 入站把 IM HTTP URL 下载转 base64 data URL（R3）
  8. 决策5 异常图：入站下载/校验/解析失败 → 不 submit、经 outbound 回发固化文案、不写 kernel 历史（R3）
- 已有测试在：
  - `tests/unit/test_agent_state.py`（扩展：render_user_text 文本投影保持 + 新结构化 parts 提取）
  - `tests/unit/test_prompting_merge_adjacent.py` 同目录 `tests/unit/`（新建 `test_build_chat_messages_images.py`，理由：build_chat_messages 多模态 content:list 行为现无专门文件，merge_adjacent 文件主题不同）
  - `tests/unit/test_session_persistence_fidelity.py`（扩展：parts 往返 + 更新 field-conservation guard）
  - `tests/contract/test_core_types_contract.py`（更新 Message 字段清单加 parts）
  - mapper：新建 `tests/unit/platform/llm/test_user_image_mapping.py`（理由：现有 mapper 测试聚焦 tool-result/response 解析，user 分支 image 无覆盖文件）。先定位：现有 `tests/unit/test_llm_*` 无 user-branch image 映射，确需新建。
  - gateway：扩展 `tests/unit/personal_assistant/`（新建 `test_gateway_image_inbound.py`，理由：inbound 图片下载转 base64 + 决策5 失败回发是新行为，现 attachments 测试只覆盖 relay adapter 解析层，不覆盖 pipeline 下载/失败）
- 落层/目录/marker：tests/unit/（纯逻辑 + 进程内 pipeline）、tests/contract/（Message 字段契约）；marker：无
- 可选依赖 importorskip：无（httpx 已是核心依赖；下载用注入的 fetcher double，不起真服务）
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：reviewer 真栈旅程证据由 reviewer/orchestrator 跑，worker 侧 e2e 用进程内真 runtime 往返（落库回归，非一次性）

前端 UI：N/A（本 unit 无前端改动，图片输入 UI 已由 feat-340 提供）

## Roadpoints

### R1 — 当前轮图片送达 provider

- 步骤:
  - state.py：新增结构化 parts 提取（render_user_text 文本投影保持 placeholder 不变，给 content:str fallback）
  - prompting.build_chat_messages：加 `user_parts` 参数；当前 user 有 image → content:list，否则 content=user_text；历史侧遍历 Message，`m.parts` 含 image → list content
  - loop.py:230 / runtime._execute_loop：把当前轮结构化 parts 透传给 build_chat_messages（经 AgentState）
  - anthropic mapper user 分支：content 为 list → 逐块（text→text block，image 复用 _to_anthropic_image_part）
  - openai_compat mapper user 分支：content 为 list → 逐块（复用 image-block 归一）
- 验证: build_chat_messages 多模态单测 + 两 mapper user 分支 image 单测 + 已有 prompting/state 测试不回归

### R2 — 持久化回放（跨轮可见 + 消除双轨）

- 步骤:
  - types.Message 增 `parts: tuple[Mapping[str,Any],...] | None = None`
  - runtime._message_to_entry：parts 非空时 `entry["parts"]` 写出（守纯文本 golden：None/空不写）
  - runtime user_msg 构造：携带结构化 parts
  - jsonl_store._to_message：读 `entry.get("parts")` → Message.parts
  - entries.message_from_turn_entry：同步读 parts（保两路一致）
  - 更新守护：core_types_contract 字段清单 + field-conservation guard 把 parts 分类为 PERSISTED
- 验证: parts 往返单测 + 端到端往返单测（发图→落盘→重建→下轮含 image）+ 纯文本 fidelity/golden 不回归

### R3 — gateway base64 边界 + 决策5 失败路径 + 多图 + e2e

- 步骤:
  - inbound_pipeline：注入 attachment_fetcher（默认 None，product-agnostic）；入站把 attachment IM HTTP URL 下载转 base64 data URL（决策1）
  - 决策5：下载/大小/解析失败 → 不 submit，经 _bg_reply_sender outbound 回发固化文案（三条一字不差照抄 design 决策5 表），不写 kernel 历史
  - runtime M246 展开：image part 构造带 parts 的 Message（CRITICAL-1，多图全送达）
  - main.py：用 _token_getter + im base_url 构造真 fetcher 注入 pipeline
  - e2e/进程内往返：发图→真 runtime→落盘→下轮回放（落库回归）
- 验证: 多图 M246 单测 + gateway 下载转 base64 单测 + 决策5 三类失败回发单测 + 进程内往返
