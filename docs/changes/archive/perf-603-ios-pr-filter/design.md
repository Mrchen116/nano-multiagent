# perf-603: As-built Design

> 本文在实现完成后根据实际 diff 和已确认规则整理，描述最终落地设计。

## 实现范围

- Executed base: `290652ada2bf5fafbd4ac9f27a1514680ff78ca9`。
- 受影响文件：`.github/workflows/ci.yml`、`docs/development/testing.md`。
- 主 checkout 的既有 dirty/untracked 内容不纳入；实现位于独立 managed worktree。

## 最终结构与数据流

PR 新增 Ubuntu `ios_changes` job，checkout 完整历史后，用事件中的 base/head SHA 执行 merge-base（三点）diff。`--no-renames` 将重命名表示成旧路径删除和新路径新增，保证从 iOS 移出的文件也会触发；NUL 分隔保留完整文件名。

内联 Python 输出 `required=true/false`：`.github/workflows/ci.yml` 或 `src/IM/ios/` 内除 `.md`、`.gitignore` 外的任一变更为 true。`ios` 依赖该输出，仅在检测 job 成功且明确输出 false 时跳过。主干 push 跳过检测、直接运行原有 iOS job；前后端无新增依赖。

检测 job 失败或输出缺失时运行原有 iOS gate，避免判断故障让必需检查被误跳过；workflow 已取消时不继续启动。模拟器选择、Xcode 版本、测试与 Release 归档步骤保持原样。

## 关键决策与边界

- 路径判断在 Ubuntu 完成，无关 PR 不启动 macOS runner。
- 使用仓库现有 checkout action 和 Python 标准库，不增加第三方过滤 action、生产模块或永久测试框架。
- 不为纯后端 API 改动触发 iOS；现有原生测试使用模拟响应，不能承担真实服务端兼容性验收。客户端模型或 fixture 适配会触发本规则。
- 本次修改 CI workflow，故本 PR 必须完整运行 iOS；本 PR 无法同时证明无关 PR 在 GitHub 上实际跳过，后者由本地真实 Git 场景覆盖，等待后续无关 PR 的平台实证。

## 验证定位

- `actionlint 1.7.12` 验证 workflow 语法通过；内联 Python 无 shellcheck 依赖。
- 从实际 workflow 提取检测脚本，在临时 Git 仓库运行 19 个场景全部通过：文档、iOS 文档、根及嵌套 `.gitignore`、Web/锁文件、后端/skills、Swift、原生测试、资源、工程、Swift 锁文件、脚本、plist、workflow、混合、删除、移出、移入、较早 Swift 提交、目标分支独立推进。
- 不新增永久测试：这是小范围可逆的 CI 配置调整；一次性验证直接执行实际脚本，未建立镜像实现。
- 独立 code review 见同目录 `code-review.md`；用户验收状态见 `motivation.md`。

## Canonical 文档与回滚

长期 CI 规则归并至 `docs/development/testing.md`，无产品 spec delta。回滚时移除 `ios_changes` job、`ios.needs/if` 和测试指南新增段落即可。
