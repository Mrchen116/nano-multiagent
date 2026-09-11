# bugfix-553: 有效 JPEG 尾随数据被误判损坏

## Relations

- Related: refactor-463

## 原始报告

> 啥问题？生产版本，飞书上聊，为啥他看不到图

截图：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-58467cca-9e4c-44d3-bc0b-a01154369a4f.png`

> 所以这种是正常的图片，但是我们校对算法有问题是么？那开个unit修一下？

> 按 change-orchestrator 太重了，你在worktree 内能闭环就行，省去不必要的环节

实施方式按用户后续指示简化为 worktree 内修复与必要验证。

## 现象 / 复现

用户在生产飞书直聊发送招聘长图及文字请求，收到“这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。”，图文请求未进入模型。

2026-09-11 对 Mini 生产 revision `71734873805199d011f777791e8add7b14b80e60` 的只读取证：飞书资源下载成功，JPEG 共 1756661 字节，1125 × 5265；JPEG EOI 后有 24 字节非零附加数据。生产检测函数返回 None，去掉尾随数据的内存副本返回 image/jpeg。macOS sips 可将完整原图解码成 PNG（退出码 0，1888872 字节）。未改生产服务、数据库或原图。生产消息 id `om_x100b6501f38a1c8cb16811d9bebb391`，shadow saga `9095b6ed02c101f99b6fa366e941667c2192cb59ab0ec24a4c62ac16f897a0ec` 可用于本地追溯；不提交用户原图或聊天数据库。

本 unit 按 Bugfix lite 修复已确认的 JPEG 尾随数据误拒；保持现有大小、下载失败和损坏图片反馈，不扩大为图像格式支持或代理转换改造。用户已确认根因并要求建立 unit 修复，没有额外待定产品选择。修复不会自动重放原聊天中的 JD 编辑请求。

### Requirement: 有效 JPEG 带尾随数据时正常处理图文消息

#### Scenario: 飞书招聘长图带尾随数据
- **WHEN** 用户从飞书发送大小允许且可正常解码、结束标记后带附加数据的 JPEG 与文字请求
- **THEN** Agent 能基于图片和文字继续回复，不误报图片损坏。

#### Scenario: 真正异常的图片
- **WHEN** 图片无法下载、超限或缺失完整图片结束标记
- **THEN** 用户仍收到对应图片失败反馈，会话可继续接收后续消息。

## 根因

共享 Gateway 入站图片检测把 JPEG 的完整性等同于“去除末尾零字节后必须以 EOI 结尾”，忽略了完整 JPEG 后可存在附加数据。原图下载成功且正常解码，但该严格文件尾检查拒绝它；协调器随后返回固定 corrupt 控制回复并终止该轮，因此不是模型视觉能力或代理丢图问题。

`git blame` 将当前检查定位到 `73f268332d`（refactor-463/M2，图片解析所有权收回）；这证明当前行来源，不断言缺陷首次产生于该重构。原 unit 的 motivation 中“图片与可见失败反馈保持一致”及 design D5 要求有效图片进入本轮、坏图片整轮失败，修复必须同时保住两者。现有回归覆盖非图像和不完整 PNG，但缺少完整 JPEG 加尾随数据这一输入类别，导致误拒未被发现。

## 修复

`ImageAttachmentResolver` 的 JPEG 检测改为：确认 SOI magic 后，只要求后续字节中存在完整 EOI marker，不再要求 EOI 必须位于物理文件末尾。这样保留原有轻量完整性边界，同时允许相机、编辑器或平台在 EOI 后附加数据；完全缺失 EOI 的截断 JPEG 仍按 `corrupt` 拒绝。下载、大小上限及其他图片格式的检测路径未改变。

永久回归扩展既有 resolver 公开行为测试：使用可解码的合成 2 × 2 JPEG，分别覆盖 EOI 后有 trailer 时成功进入 `image/jpeg` data URL，以及去掉 EOI 后仍失败。Gateway 入站接线已有独立长期保护，本 unit 另以一次性 Feishu-shaped 图文消息从 `InboundPipeline.handle_inbound()` 重放到 Kernel，避免为同一 detector 失败原因重复建立高层测试。

## 验证

- 修前红测：`test_resolve_accepts_complete_jpeg_with_trailing_data` 在 `d5f3183ba` 基线返回 `failure='corrupt'`，结果 `1 failed`。
- 修后聚焦回归：`pytest -q tests/unit/personal_assistant/test_image_attachment_resolver.py tests/unit/personal_assistant/test_gateway_image_inbound.py`，结果 `18 passed in 0.59s`；包含下载失败、超限、损坏图片固定反馈和后续文本轮恢复等既有保护。
- Gateway 入站 evidence：用与 Feishu adapter 输出一致的 data-URL attachment、`kernel_input_parts` 和 channel metadata 调用 `InboundPipeline.handle_inbound()`；断言一次 Kernel submit 同时保留文字与完整 JPEG+trailer，且没有 fixed corrupt reply，结果 `PASS`。
- 合成样本解码：将同一 JPEG+trailer 输入 FFmpeg MJPEG decoder，退出码 0。
- 静态检查：`ruff check`、`ruff format --check`（受影响的 2 个 Python 文件）和 `git diff --check` 全部通过。
- 边界：未向生产用户发消息，未重放原聊天或调用真实模型，未重启/修改生产服务；生产原图的下载与可解码证据沿用本 unit 原始报告中的只读取证。

- 收尾原图验证：从生产 shadow 数据库只读取得同一附件，在修复后的本地 resolver 运行，结果 PASS / image/jpeg；输出 data URL 与原始值逐字相同，原图数据未裁剪或落盘。未调用真实模型。
- 文档契约已同步 `docs/specs/gateway/external-channels.md`。`docs-check` 仅报告 origin/main 已存在的 bugfix-549 与 feat-551 active/archive 重号；用 `git ls-tree origin/main` 确认两组目录均在基线中，本 unit 未修改这些目录。此无关问题未扩大修复范围。
- 按用户简化要求，在 worktree 中完成代码核对与必要验证；未追加多角色 review、全量 CI 或 PR 流程。已提前启动的无关全量测试已停止，不作为通过证据。

- PR #292 CI follow-up：用户报告 CI 失败后，确认唯一失败为上述两组重复活动文档。逐文件比较后保留完整 archive 版本，移除旧 active 副本；不改对应产品实现。修后 docs-check 通过（227 sources / 72 routes），全仓 Ruff check 与 format check 通过（1036 files）。
