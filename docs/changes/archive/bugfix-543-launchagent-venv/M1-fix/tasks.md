# M1-fix — Tasks

> 退出标准：修复 `../fix.md` 记录的 LaunchAgent 虚拟环境解释器链接被解析问题，保持 feat-542 其余语义不变。

- [x] 为真实临时符号链接补充 plist 回归测试，并记录修复前 RED — 验证：`.venv/bin/pytest tests/unit/personal_assistant/test_macos_launch_agent.py`
- [x] 保留绝对虚拟环境解释器路径，同时继续解析源码根路径 — 验证：聚焦单测
- [x] 校正真 macOS LaunchAgent E2E 的 plist 断言，并完成风险相称验证 — 验证：聚焦单测、shell 语法检查及隔离 E2E
