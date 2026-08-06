# bugfix-512: Code Review

## Review scope

- Base: `25dc9c818400ab66c99650316610b73ca5d2060f`
- Head: 本 unit 的未提交工作树
- Review mode: `full`
- Included commits: None
- Included uncommitted files: 本 unit 的 Feishu/Gateway/Web IM 实现、测试、incident、as-built design 与 delta-spec。

## Round 1

- Mode: full
- Validated at: 2026-08-06T15:51:18Z
- Executed base: `b8d1c3f08f88289447f906c6997c93b71b723c3f`
- Result: Changes requested
- Findings:
  1. **P1 — 未触发 Agent 的群图片在后续触发时丢失。** `InboundPipeline` 只把 `message.text` 写入 `GroupContextStore`，后续 drain 无 attachment/part projection，standalone image 变成空背景，Post 只剩 `[图片]` 文本。
  2. **P1 — 飞书图片下载失败被吞掉并可能提交空轮次。** adapter 记录 warning 后继续，standalone image 会成为无正文、无 attachment 的入站；用户看不到失败原因，模型也不知道图片缺失。
  3. **P1 — 图片上限执行太晚且无 IM fetcher 时 data URL 绕过验证。** 飞书资源可能在完整读取、base64 和 shadow/saga 持久化后才被 5 MiB resolver 拒绝；静态飞书配置的 resolver 甚至直接把 data URL 传给模型。
  4. **P2 — Post 文本归一化破坏空白。** mention normalization 对所有 text parts 执行多空格折叠和 `strip()`，会改变连续空格和代码缩进。
  5. **P2 — 出站 Markdown 图片扫描误处理代码示例且重复上传。** 单个正则会把 fenced/inline code 与 escaped syntax 当真实图片；同一来源重复下载上传，也没有来源数上限。
  6. **P1 — 远程图片的 DNS 校验与实际连接存在重绑定窗口。** 代码先解析并检查 hostname，随后 HTTP 客户端独立再次解析同一 hostname，实际连接地址不受前一次公网检查约束。
  7. **P2 — 图片网络 I/O 串行占用关键线程。** Agent 最终回复的远程图片抓取运行在 Gateway asyncio loop；单条多图入站也逐张下载，慢资源会扩大延迟和 Feishu event queue backpressure。
  8. **P2 — 入站 base64 metadata 被复制到不消费它的持久化/请求位置。** conversation find-or-create 和 reply context 重复携带完整 attachment；只有 canonical inbound recovery、shadow message attachment 与群背景真正需要图片数据。
- Resolutions:
  1. `GroupContextStore` 增加可迁移的 `metadata_json`，buffer 只保留 `attachments/kernel_input_parts/image_resolution_failure`；coordinator 对背景消息逐条恢复有序多模态 parts。新增群 Post buffer 回归测试。
  2. adapter 把下载失败稳定投影为 `download/oversize`；coordinator 在 Kernel submit 前返回可执行失败说明，shadow 对失败的 standalone image 显示 `[图片加载失败]`，避免不可见空消息。
  3. 飞书资源读取以 5 MiB + 1 byte 截断并在 base64/persistence 前拒绝；resolver 无论是否配置 fetcher 都校验 self-contained data URL 的 base64、大小、签名与结构。
  4. Post ordered parts 改用只替换 mention placeholder、不折叠空白的路径；内容投影只去除边界换行，保留首行代码缩进。
  5. 增加跳过 inline/fenced code 与 escaped syntax 的扫描器；先收集最多五个唯一来源，并发解析后每个来源只上传一次。
  6. 将通过公网检查的 IP 固定到实际 TCP connection；HTTP Host 与 HTTPS SNI 仍使用原 hostname。新增从公开 `send_message()` seam 验证私网拒绝与连接地址固定的测试。
  7. 最终与中间可见回复的 channel send 移到 `asyncio.to_thread()`；出站唯一来源和入站单消息图片均并发下载，保留 provider/part 原顺序。
  8. find-or-create 不再发送未消费 metadata；reply context 去除输入专用图片字段。canonical inbound、shadow attachment 和群背景 projection 仍各自保留恢复/展示/模型所需的唯一副本。
- Tests after fixes:
  - `pytest` focused Feishu/Gateway/IM suite: 117 passed.
  - `ruff check` / `ruff format --check` for all touched Python files: passed.
  - Public-seam regression coverage includes Post whitespace, code-example skipping, duplicate upload, pinned public IP, early oversize rejection, failure projection, group buffered image ordering, shadow standalone image, and reply-context sanitization.

## Round 2

- Mode: delta triggered by the local-CI failure after Round 1 fixes
- Validated at: 2026-08-06T15:59:03Z
- Executed base: `b8d1c3f08f88289447f906c6997c93b71b723c3f`
- Finding: **P2 — 纯文本群背景也重复调用图片 resolver。** 新的逐背景消息循环对没有 attachment 的 buffered text 执行 resolver，使 steer fallback 的“当前消息只预构建一次并复用”计数契约从 2 次变成 3 次。
- Resolution: buffered message 只在确有 attachment 时解析；当前消息仍经过原有 resolver seam，因此 fallback 继续复用 prebuilt parts，不重 drain、不重下载。
- Tests after fix:
  - `test_steer_race_reuses_group_and_image_parts_exactly_once` 与相关群背景/图片用例：21 passed.
  - Full Python CI-equivalent suite: 2996 passed.
  - Full frontend Vitest: 61 files / 575 tests passed; critical-level dependency audit exited 0.
  - Full-repository `ruff check`, `ruff format --check`, docs integrity and `git diff --check`: passed.

## Closure

- Follow-up mode: closure over the complete post-fix diff
- Validated at: 2026-08-06T16:01:55Z
- Executed base: `b8d1c3f08f88289447f906c6997c93b71b723c3f`
- Effective base: `25dc9c818400ab66c99650316610b73ca5d2060f`
- Effective through: the reviewed uncommitted unit tree at the timestamp above
- Findings closed: 9/9
- Remaining findings: 0
- Final result: Approved — 0 P0 / 0 P1 / 0 P2 actionable findings remain in the reviewed scope.

## Final main-sync assessment

- Synced range: `b8d1c3f08f88289447f906c6997c93b71b723c3f..25dc9c818400ab66c99650316610b73ca5d2060f` (`bugfix-509`).
- Overlap: canonical Gateway/IM index counts and `web-chat-ux.md`; the incoming product change adds structured self-evolution notices. Its code paths are IM system-message projection and background delivery, not Feishu content parsing, image attachment projection, group buffer reconstruction, or attachment preview CSS.
- Resolution: canonical specs retain both contracts and derive the combined counts (`External Channels=14`, `Web Chat UX=15`). No reviewed product behavior changed, so the user's real Feishu/IM acceptance and Round 1/2 findings remain valid.
- Combined-tree validation: Python 3021 passed; frontend 63 files / 604 tests passed; critical-level dependency audit, full ruff, docs integrity, and diff checks passed.
