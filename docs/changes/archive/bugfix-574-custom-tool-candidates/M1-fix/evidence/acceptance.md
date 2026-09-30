# 配置候选真实验收

- Claim：已注册的共享及所属工作区工具可在真实 IM 配置页面被发现、启用、取消，不自动扩大权限。
- Baseline：`e8f61810a`，同一 isolated worktree 中运行真实 IM/Gateway/Vite，未触碰个人生产实例；2026-10-01（Asia/Shanghai）。
- Method：`scripts/e2e-up.sh --wt <unit-worktree>`；两个工作区分别放入只返回常量的 unit_reader/peer_reader。用默认隔离 nano 测试身份登录 Playwright，并从真实 IM API 核对保存值及能力响应。

## Result

1. Agent 编辑页显示四个共享社交工具及本工作区 unit_reader，均默认未选中；unit_reader 的 title 为注册描述。peer_reader 不在该 Agent 目录，peer 页反之。已有 12 个默认工具保持选中。
2. 新建页显示共享社交工具但不含任一工作区测试工具；自定义工具默认未选中。
3. 在编辑页勾选 unit_reader、Save Agent、reload，unit_reader 保持选中、profile_version 递增，真实 GET config 白名单包含它。截图本地 locator：`output/playwright/bugfix-574-tool-candidates.png`（不提交截图缓存）。
4. 经真实 IM 聊天与配置代理模型调用 unit_reader，工具记录 `status=completed`、输出 `{"marker":"bugfix-574-tool-executed"}`，最终回复 `bugfix-574-tool-executed`。conversation 本地 locator：`c_08iihnwb`。
5. UI 取消 unit_reader 并保存，reload 后保持未选中，GET config 的白名单不含它、profile_version=3。下一轮确认实际工具列表时未发生工具调用。

## Fixture correction and limit

第一次临时 Reader 继承 Tool Protocol，意外继承空的审批投影和序列化方法，造成审批无 verdict、错误结果序列化为 null、上游后续请求失败；这是临时夹具错误，不是候选发现失效。只将临时插件改为鸭子类型并对常量操作显式 preapprove，重启隔离栈后上述真实调用通过，未修改生产审批/序列化代码。

不请求社交第三方平台，不验证平台凭据/抓取/下载；插件热更新不在范围。长期白名单执行拒绝、显式空集及 global 固定基础工具复用已有全量测试。浏览器/服务/临时插件/凭据和运行数据由本次创建者清理；PR 附完成清理结果。
