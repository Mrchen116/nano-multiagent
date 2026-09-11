# M1-fix — Progress

## Done

- 从 unit branch `codex/bugfix-553` 的 `d5f3183ba5139bb342d2020c6cc0ac44626d1335` 创建独立 milestone worktree/branch。
- 在 resolver 公开 seam 复现：完整 JPEG 的 EOI 后带 trailer 时被返回 `corrupt`（`1 failed`）。
- JPEG 检测现在接受 EOI 后的附加字节；缺失 EOI 仍失败，下载/超限路径未变。
- 合成 fixture 是可解码的 2 × 2 JPEG，不包含生产图片或个人数据。

## Notes

- 回归风险 owner 是 `ImageAttachmentResolver` 的公开 `resolve()` seam；扩展既有 resolver 测试文件，避免为同一失败原因建立重复永久测试。
- Gateway 入站接线已有 `test_gateway_image_inbound.py` 保护；本次用一次性 Feishu-shaped pipeline replay 证明新输入类别经过该入口，避免重复永久断言。

## Validation

- Focused：resolver + Gateway image inbound，`18 passed in 0.59s`。
- Entry：Feishu-shaped `InboundMessage` 经 `InboundPipeline.handle_inbound()` 一次提交文字和 JPEG+trailer，固定 corrupt reply 为空，PASS。
- Decode：同一合成 JPEG+trailer 经 FFmpeg MJPEG decoder，退出码 0。
- Static：受影响 Python 文件 `ruff check` 与 `ruff format --check` 通过；`git diff --check` 通过。
- Limit：未调用真实模型、未产生生产消息或修改/重启生产服务。
