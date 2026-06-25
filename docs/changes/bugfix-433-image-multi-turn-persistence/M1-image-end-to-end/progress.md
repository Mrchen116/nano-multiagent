# bugfix-433-M1 — Progress

<!-- 每个 roadpoint 完成后实时追加。 -->

## R1 — 当前轮图片送达 provider

- Context: 断点1（render_user_text 把 image 丢成占位符 + build_chat_messages 只收 user_text）+ 断点3（两 mapper user 分支不发图）。当前轮图片从未到达 provider。
- Decision:
  - `state.render_user_content_parts(parts)`：任一 part 是 image → 返回规范块列表 `[{type:text},{type:image,image_url:data-url}]`；全文本 → None（守 content:str 路径）。`render_user_text` 文本投影**保持原样**（占位符不变，给 content:str fallback / 检索 / 日志）。
  - `build_chat_messages` 加 `user_parts` 参数：当前 user 有图 → content:list；历史侧新增 `_history_content`：`Message.parts` 含 image → list content。
  - loop 调用透传 `render_user_content_parts(state.input_parts)`。
  - `types.Message` 加 `parts` 字段（权威多模态表示，content 降为纯文本投影）。
  - 两 mapper user 分支：content 为 list → 逐块映射（anthropic 新增 `_map_user_content_blocks` 复用 `_to_anthropic_image_part`；openai 复用 `_normalize_tool_output_parts`）。
- Rationale: `LLMMessage.content` 已支持 `str|list[dict]`，顺势用；无图走 str 分支 = 纯文本零扰动（不变量1）。决策2+3 照 design。
- 决策偏差（非 design 偏差，仅 roadpoint 顺序）：把 `_message_to_entry` 写 parts + `_to_message` 读 parts 这两处持久化往返从 R2 **提前到 R1**。原因：加 `Message.parts` 字段当场触发 `test_session_persistence_fidelity` 的 field-conservation guard（要求每个新字段分类 PERSISTED/NOT_PERSISTED 且 PERSISTED 必须真往返）——R1 的 C2 gate 要全绿，就必须同时把往返写好。这是「加持久化字段即连带写其持久化」的内聚边界，非范围扩张。R2 改为：端到端往返测试 + entries.message_from_turn_entry 读 parts + runtime user_msg 携带 parts。
- Evidence:
  - Tests: `tests/unit/test_build_chat_messages_images.py`（6）+ `tests/unit/platform/llm/test_user_image_mapping.py`（4）全绿；守护 `test_core_types_contract` + `test_session_persistence_fidelity` 更新后绿。
  - 全量：`pytest tests/unit tests/contract tests/integration -m "not e2e"` = 2527 passed；ruff check + format clean。
  - Entry: 真实入口（用户发图当轮可见）的端到端验证在 R3 进程内往返 + reviewer 真栈，R1 只到「图片块进 LLMMessage / mapper 输出 provider 形态」单测层。
  - Frontend State Matrix: N/A（无前端）
  - Browser QA: N/A
  - E2E/Regression: R1 单测落库回归；端到端往返见 R2/R3。
  - Visual/Interaction: N/A
- Rollback: 回退到 C3=plan commit（图片不可见，纯文本路径不动）。
- Commits: C1=test red, C2=feat, C3=本次 docs。
- Next: R2 持久化回放——runtime user_msg 携带结构化 parts、entries.message_from_turn_entry 同步读 parts、端到端往返单测（发图→落盘→重建→下轮含 image）。

## R2 — 持久化回放（跨轮可见 + 消除双轨）

- Context: 断点2——user turn 落盘只存渲染后文本（占位符），回放 `_to_message` 不读 parts，图片单轮可见也跨轮丢失；parts 写而不读的悬空双轨。R1 已把 `_message_to_entry`/`_to_message` 的 store 主路径写好（因 guard 连带），R2 补齐 user_msg 实际携带 parts + 第二回放路径。
- Decision:
  - `runtime` user_msg 构造：`render_user_content_parts(input_parts)` → `Message.parts`（有图才落，无图 None 不写 parts 键）。这是图片真正进入持久化的源头。
  - `entries.message_from_turn_entry`：读 `entry.data["parts"]` → `Message.parts`，与 `jsonl_store._to_message` 对齐（两条回放路径都还原图片，不依赖走哪条）。
- Rationale: 决策4——parts 升为权威多模态表示，content:str 降为纯文本投影，回放消费 parts，双轨从「写而不读」变「写且读、一致」。两条回放路径必须同步，否则 append 返回值/entry-based reload 走到时图片仍丢。
- Evidence:
  - Tests: `TestImagePartsRoundTrip`（3）——经真 `JsonlSessionStore.load` 往返 + `build_chat_messages` 回放含 image 块；entries 第二路径读 parts；纯文本无 parts 键。全绿。
  - Entry: 端到端「发图→落盘→重建→下轮含 image」经真 store 往返已验（非全 mock）；真 runtime submit→真栈在 R3 进程内 + reviewer。
  - 全量：`pytest -m "not e2e"` = 2530 passed；ruff clean。重锚 contract 白名单（runtime.py .nano 行 202→208，纯行移位，非新硬编码）。
  - Frontend State Matrix / Browser QA / Visual: N/A
  - E2E/Regression: R2 往返单测落库；进程级真 submit 往返见 R3。
- Rollback: 回退到 R2 C1 commit（图片当前轮可见但跨轮丢——半程态）。
- Commits: C1=test red, C2=feat, C3=本次 docs。
- Next: R3——gateway 入站 IM HTTP URL 下载转 base64（决策1）、决策5 异常图失败 outbound-only 回发、M246 多图展开携带 parts（CRITICAL-1）、main.py 注入真 fetcher、进程内往返。

## R3 — gateway base64 边界 + 决策5 失败路径 + 多图 + 端到端

- Context: 断点1 的入站侧（IM HTTP URL 对远端 provider 不可达）、决策5（异常图不静默不喂假占位）、CRITICAL-1（M246 多图除末图外被渲成占位丢失）。
- Decision:
  - **决策1（入站转 base64）**：`InboundPipeline` 加 `attachment_fetcher`（`async url→bytes`，默认 None 透传保持 product-agnostic）+ `max_image_bytes`（默认 5MB，对齐最严格 provider）。`_resolve_image_parts` 下载→大小校验→magic bytes 识别→`data:<mime>;base64,<...>`。`main.py._build_attachment_fetcher`（复用 `_token_getter` + `_im_http_headers` 鉴权）在 im_service 配置时注入真下载。
  - **决策5（失败 outbound-only）**：下载/超大/损坏任一失败 → `_resolve_image_parts` 返回 `(_, failure_kind)`，`_reply_image_failure` 走 `_deliver_stop_ack` 同款 `_bg_reply_sender` 回发**固化文案**（三条一字不差，模块常量 `_IMAGE_FAILURE_MESSAGES`），**不 submit kernel、不写历史**。本轮未 submit → 下轮上下文天然干净，无需回放过滤（对齐 CC `return {reason:'image_error'}`）。多图任一失败整轮停（不做部分送达）。
  - **CRITICAL-1（M246 多图）**：runtime M246 extra_message 的 image part 携带 `render_user_content_parts([part])` 产的 `Message.parts`，经 history 侧 `build_chat_messages` 还原为 image 块——与决策4 同一通道，多图全送达。
  - `_detect_image_mime`：PNG/JPEG/GIF/WEBP magic bytes，未知→corrupt（用户收到「无法识别」）。
- Rationale: IO（下载）归 gateway 入站边界，core/mapper 保持纯净（满足 core 不 IO + 产品只 import sdk）；base64 自包含、落盘不依赖 IM URL 存活。失败彻底归 gateway 入站，内核不背中途回退。
- Evidence:
  - Tests:
    - `tests/unit/personal_assistant/test_gateway_image_inbound.py`（5）：成功下载→data URL 进 submit；download/oversize/corrupt 三类→不 submit + 固化文案 outbound；无 fetcher 透传。全绿。
    - `tests/unit/test_agent_runtime.py::test_multiple_image_parts_all_reach_provider`：多图经真 runtime + M246 全送达 provider（CRITICAL-1 守护）。
    - `tests/unit/test_agent_runtime.py::test_image_survives_persist_reload_and_replays_to_provider`：**端到端跨轮**——图片经真 runtime 落盘 → 新 runtime 重载（disk）→ `build_chat_messages` 回放 → provider 请求含 image 块。
  - Entry: 真实入口（进程内真 runtime + 真 store 跨轮）已覆盖「发图→送达 mapper→落盘 entry.parts→重建 Message.parts→下轮含 image」整条；reviewer 真栈（IM→Gateway 进程）补端到端浏览器旅程。
  - 全量：`pytest tests/unit tests/contract tests/integration -m "not e2e"` = 2536 passed；`tests/im_service -m "not e2e"` = 332 passed/1 skipped；ruff check + format clean（全树）。
  - Frontend State Matrix / Browser QA / Visual: N/A（无前端改动）
  - E2E/Regression: 上述三个进程内真栈测试均落库回归。
- env_caveats: worker 侧未起真 IM/Gateway 进程做 live 浏览器旅程（决策5 文案 + 真下载鉴权那段经 `main.py` 注入，单测用 fetcher double 覆盖逻辑、真 httpx 下载未跑活栈）——这部分 live 端到端由 reviewer 真栈旅程验（design Runbook 已列）。worker 范围内逻辑全部经真 runtime/真 store/真 pipeline（非全 mock）覆盖。
- Rollback: 回退到 R3 C2 commit（多图修好、gateway 下载在，但少端到端跨轮回归）；整 unit 可 revert 回现状（图片不可见，纯文本零回归）。
- Commits: C1=test red（M246+gateway）, C2=feat（M246+gateway+main 注入）, C2'=test（端到端跨轮）, C3=本次 docs。
- Next: 本 milestone 全 roadpoint DONE，进入 §6 集成。

---

## Round 1 reviewer 反馈循环 — fix1（损坏图 robustness + code review correctness）

> §FL 小修快车道（复用原 worker 上下文）；8 项跨 5 文件 + 根因调查，超单 commit，按主流程 TDD 走，不新建 milestone 目录，fix 列表记此续段。worktree: `.worktrees/bugfix-433-fix1`，从 `unit/bugfix-433` 切，改完 merge 回 unit。

### 根因调查（systematic-debugging，Issue #2）

- 现象：发损坏图（41 字节，合法 PNG magic header + 损坏体）→ provider stream error → 同会话后续纯文字得空回复。
- 数据流追踪（runtime.py）：user_msg（含损坏 image parts）在进 loop **前**就 enqueue+flush 落盘（:540-544）；provider ModelError 分支只合成 is_provider_error 消息后 re-raise，**不移除触发错误的 user turn**；下轮重建历史→`_to_message` 还原 parts→`build_chat_messages` 再发损坏 image block→再 error→空回复。**损坏图确定性毒化会话历史**。
- 结论：#1（损坏图入站只验 magic bytes，41 字节损坏 PNG 有合法 header 过检测）与 #2 **同根**。修 #1（入站结构校验拦截→不 submit→不进历史）即根除 #2 报告症状。

### Fixes（C1 红测 → C2 实现）

| # | 文件 | 修复 |
|---|---|---|
| 1/2 | inbound_pipeline `_detect_image_mime` | 增结构校验：PNG 验 IHDR 紧跟签名 + IEND；JPEG 验 EOI；GIF 验 trailer 0x3B；WEBP 验 RIFF size。stdlib-only（**不引 Pillow**——本仓未声明该依赖，仅传递带入，clean CI 缺失即红，feat-388 注释警告过）。损坏图拦截→不 submit→不毒化 |
| 3 | state `render_user_content_parts` | 触发条件 `any(image)` → `any(image and image_url is not None)`，与块构建条件对齐（无 url image 不进 list 路径，守「无可用图→None」契约） |
| 4 | entries `new_turn_appended_entry` | 仅非空才写 parts（对齐 `_message_to_entry`，消除「text-only 写 `parts:[]`」的两写路径结构不对称 → golden 漂移） |
| 5 | prompting `build_prompt_messages` | 加 `user_parts` 形参并透传给 build_chat_messages（公共 API 不静默丢图） |
| 6 | inbound_pipeline | data URL mime 取 `detected_mime or mime`（magic-byte 探测值优先于客户端 content_type，防伪造） |
| 7 | runtime M246 | extra_messages `parent_message_id` 锚 `user_msg`（原锚 `loop_history[-1]`=本轮前一条，逻辑树错位；内存only低影响） |
| 8 | entries `parse_parts` 新增 | 抽公共 parse_parts 供 `_to_message` + `message_from_turn_entry` 共用（两回放路径一致）；guard 加非空 parts 往返 case |

#7 未写专门测试：extra_messages 仅内存不落盘，parent_message_id 非可观察行为，按 TESTING_GUIDE「MUST NOT 测实现细节」省红测（typo/内部写法类豁免），fix 本身随 M246 既有测试守住「多图全送达」不回归。

### Evidence

- Tests: 新增/扩展 red→green：`test_gateway_image_inbound.py`（损坏图拦截/mime优先/会话不毒化）、`test_build_chat_messages_images.py`（render条件/build_prompt透传）、`test_session_persistence_fidelity.py`（entries空parts/非空往返guard）。全测试树 `pytest tests/{unit,contract,integration,im_service} -m "not e2e"` = 2877 passed/1 skipped；ruff check+format clean。重锚 contract 白名单 jsonl_store .nano 行 89→90。
- **LIVE（§3.3 live-critical 签收）**：真 IM(:65523)+真 Gateway 进程，IM HTTP API 驱动三条边界旅程（leader 要求两头都验，防误杀合法图）：
  - ① 损坏图（合法 sig 截断、无 IEND）→ agent「这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。」；后续文字「3+4等于几？」→「3 + 4 = 7」（#1 固化文案 + #2 不毒化）✓
  - ② 合法 100×100 红 PNG → agent「这是**红色**…」；合法蓝 PNG → agent「这是**蓝色**…」——结构校验**未误杀**合法图，agent 真看到并答对颜色（核心视觉功能完好）✓
  - ③ 6MB 超大 PNG → agent「这张图片太大了，超出可接收的大小，我没能收到它，无法据此回复。请压缩或换一张更小的图片后重新发送。」✓
  - 驱动脚本：scratchpad/live_image_boundaries.py（一次性验收，不入库）。
  - 排除假阴性：首版 live 脚本读 REST messages 时 agent 回复 streaming 未定稿→空 content race，误判会话毒化；改「轮询非空 content」后全 PASS。
  - 单测同步加「合法多块 PNG 不被误杀」guard（红/蓝 100×100，IHDR+IDAT+IEND）。
- **Scope（leader 定 A）**：报告的损坏图 #1/#2 已 live 完全闭合。「任意 provider-error 后那条触发错误的 user turn 留史毒化后续轮」是**非本 unit 引入的**更广既有 robustness 面（合法图遇 provider 瞬时错误亦可触发），leader gh create out-of-unit issue 记录、PR body Refs；本 unit 不顺手扩（§0.8）。
