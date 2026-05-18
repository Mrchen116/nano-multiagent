# bugfix-355-M6: BashTool 架构归位 + S3 allow-prefix 对齐 CC isReadOnly

## 目标

把 bash 专属逻辑（配置 + 策略 + 执行）从 ToolSafety 整体搬到 platform/tools/builtins/ 下新模块；
BashTool 实现 check_permissions 自持权限判定；auto_mode_gate.py step 6 整段删除；
按 CC isReadOnly 语义裁剪 BASH_ALLOWED_PREFIXES（prefix 级精度）。

## 退出标准（[worker] 轨）

- [ ] BashTool.check_permissions 返回值：allowed→behavior='allow', denied→behavior='deny', review→behavior='passthrough'，单测覆盖
- [ ] bash_policy.BASH_ALLOWED_PREFIXES 按 D9 清单逐字一致；python3 file.py / bash script.sh / pytest / sed -i / sleep / python file.py 全部判 review，单测覆盖
- [ ] git status / git log / git diff 等 13 个 git 只读子命令判 allowed；git push / git commit / git reset 判 review，单测覆盖
- [ ] auto_mode_gate.py step 6 硬编码已删除；if tool_name == "bash" 在 hook 文件中不再出现（grep 反向断言）
- [ ] BashTool.run / _run_legacy_sync / _run_foreground / _run_background 不再调用 enforce_command_policy / check_command_policy（反向 grep 断言）
- [ ] shell_runner.py 不再调用 enforce_command_policy（反向 grep 断言）
- [ ] ToolSafetyConfig 不再包含 bash_* 字段（反向 grep 断言）；剩余字段只有 read_max_bytes（和 read_max_lines）
- [ ] 集成测试：走真实 AgentRuntime + hook，python3 file.py tool call 触发 yolo classifier LLM 请求（可用 mock LLM transcript 断言）；git status 不触发
- [ ] 配置兼容：.nano/policy.toml 用户覆盖 [tool_safety.bash_policy.allow_prefixes] 在迁移后仍能加进 BASH_ALLOWED_PREFIXES，单测覆盖
- [ ] pytest tests/unit/agent/platform/tools/ 全绿；pytest tests/unit/test_auto_mode_gate.py 全绿；集成测试全绿

## 测试策略

后端/API milestone：所有 [worker] 退出标准都需要单测或集成测试证明。

关键测试文件（新建）：
- tests/unit/agent/platform/tools/builtins/test_bash_policy.py
- tests/unit/agent/platform/tools/builtins/test_bash_runner.py（最小化覆盖构造和基本运行）
- tests/unit/agent/platform/tools/builtins/test_bash.py（扩展，BashTool.check_permissions）
- tests/unit/test_auto_mode_gate.py（扩展，step 6 删除回归 + bash 走通用 dispatch）

配置兼容测试：tests/unit/agent/platform/tools/builtins/test_bash_policy.py 中覆盖 .nano/policy.toml 兼容路径。

集成测试：tests/integration/ 新建文件覆盖端到端 hook → BashTool.check_permissions 调用链。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 新建 bash_policy.py + 配套测试（C1 Red → C2 Green） | TODO |
| R2 | 新建 bash_runner.py + BashTool 改用 bash_runner（执行层迁移） | TODO |
| R3 | BashTool.check_permissions 实现 + auto_mode_gate step 6 删除 | TODO |
| R4 | ToolSafety 退化（删 bash_* 字段 + 三方法 + helpers）+ shell_runner 清理 | TODO |
| R5 | 集成测试：端到端 hook → check_permissions 调用链覆盖 | TODO |
