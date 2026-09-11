# M1-fix — Tasks

> 退出标准：有效 JPEG 在 EOI 后带附加数据时进入 Gateway 本轮模型输入；缺失 EOI、下载失败与超限仍按既有失败语义处理。

- [x] 扩展 resolver 既有公开行为测试，先复现 JPEG 尾随数据被误判，随后以最小完整性判断修复；保留缺失 EOI 回归保护。— 验证：`pytest tests/unit/personal_assistant/test_image_attachment_resolver.py`
- [x] 从 Gateway 入站公开入口重放 Feishu-shaped 图文消息，确认图片进入 Kernel 且没有 fixed corrupt reply。— 验证：一次性本地 pipeline replay
- [x] 核对变更范围、静态检查与 unit 记录，提交并集成到 unit branch。— 验证：focused pytest、Ruff、`git diff --check`
