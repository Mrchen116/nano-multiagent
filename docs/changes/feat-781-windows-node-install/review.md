# feat-781 Windows 电脑安装验收

实现基于 `7bcb6b25d`。独立代码审查覆盖 `6519ffe44`，差量复审关闭跨浏览器问题后，审查者又复核精简归档、安装器进度显示（`109ccf5b5`）与持续运行的 Windows PR 检查。最终 delta 与受审实现一致。

| 检查 | 证据 | 结果 |
|---|---|---|
| 版本分发、平台匹配、进程生命周期与更新 | 独立审查者检查安装器、宿主、受管更新、绑定流程及两份 delta | 初审发现原页面无法恢复跨浏览器确认。用户现可在原网页选择自己刚确认的电脑，必须实际在线才可继续。对应回归测试先失败再通过，复审关闭该问题，最终 delta 与实现一致。 |
| 网页下载、连接、重试与不可用状态 | 隔离 IM、SQLite、登录测试账号与真实 Chrome，切换 Windows UA，下载测试响应为 13 字节。见[桌面](M1-windows-node/windows-1200.png)、[窄窗口](M1-windows-node/windows-390.png)、[正在等待](M1-windows-node/windows-waiting-390.png)及[尚未发布](M1-windows-node/windows-unavailable-390.png)。 | 作者走查。网页不会在点连接时提前显示在线。临时栈和测试浏览器已回收。跨浏览器补丁另有 18 项 onboarding 测试。 |
| Windows 隔离工作区中的宿主和进程树 | [候选 A 的原生测试](https://github.com/Mrchen116/nano-multiagent/actions/runs/44771705408)运行两个配置、真实 Windows 任务与子进程，检查出生标识、优雅退出、超时收拢、异常和独立更新进程。 | Windows Server 2022 runner 通过。普通本地账户的桌面登录和系统重启需由客户机实测。 |
| 安装器、运行图和缓存 | [候选 A](https://github.com/Mrchen116/nano-multiagent/actions/runs/44771705408)和[候选 B](https://github.com/Mrchen116/nano-multiagent/actions/runs/44772109381)执行按用户静默安装，验证协议注册，在 ZIP 解压后的版本目录中启动私有 Node、pnpm 和 DSH，实际创建会话、查询工具，然后关闭资产服务验证热缓存。 | 两次通过。包含空格和中文的目录覆盖真实宿主和 DSH。运行器测试使用本地资产 fixture。 |
| Windows 10/11 真实用户旅程 | 在 Windows 10 22H2 x64（19045.2006）的普通账户中，确认 PATH 无 Node，核对候选 C 安装器的 SHA-256 后执行安装。 | 安装退出 0。当前用户的 `crewden://` 处理器指向已安装的 Crewden.exe。运行过程中的宿主离线，尚未取得该客户机的模型回复或 Windows 11 结果。 |

最终用于桌面验收的是[候选 C](https://github.com/Mrchen116/nano-multiagent/actions/runs/44773547448)（`d3390ef8e9b3ab6113aff34f1dadd8804651af34`）和[候选 D](https://github.com/Mrchen116/nano-multiagent/actions/runs/44773636434)（`109ccf5b542f01aee6dbc8dce8eb83cc00990eb4`）。两次原生安装、离线复用、DSH 会话和工具发现均通过。D 增加了下载字节进度。核对其 EXE 的 PE 证书目录，偏移与大小均为 0，本次测试安装器未签 Authenticode；实际系统发布者提示由桌面验收记录。两版运行环境 ZIP 的 SHA-256 均为 `ee9852cc1d5edc86eb2655c794ec0520c201af9ee0b092c81da07a2478502df9`。

| 体积 | 候选 B | 候选 D |
|---|---:|---:|
| 用户双击的安装器 | 2,110,169 B | 2,110,427 B |
| 运行环境 ZIP | 99,029,227 B | 78,689,983 B |
| 应用 ZIP | 3,207,648 B | 2,629,727 B |
| 全部首次安装产品资产（含元数据） | 104,348,347 B | 83,431,440 B |
| 两份 ZIP 中普通文件解压字节合计 | 353,802,567 B | 253,323,673 B |

从 GitHub 下载后分别校验 A、B、C、D 的工件包 SHA-256，按清单逐项重算四份资产的大小与哈希。D 的首次资产合计 79.57 MiB，较 B 减少 20.0%。运行环境中最大的三项压缩内容为私有 node.exe（35,081,382 B）、图像处理的 sharp 原生组件（8,363,928 B）和受管包操作所需的 pnpm（4,658,848 B）。应用归档中的个人助手包为 1,872,318 B，DSH 集成为 416,694 B。构建剔除了仅其他 DSH 界面使用的 Office 预览、语音识别、Inspector，以及编译器类型声明和调试映射。D 的实际 Windows 会话仍列出 `read`、`write`、`pwsh`、`skill` 等 34 个工具。

[Windows Server 实际传输测试](https://github.com/Mrchen116/nano-multiagent/actions/runs/44777807452)使用原始 C/D 工件，按发布清单核对哈希，再由本地资产服务器计量响应正文。已取得安装器后，C 首次准备下载 81,319,915 B。升级到 D 下载 2,630,235 B，共用运行环境的下载量为 0 B。故意提供损坏的 D 应用包时，更新被拒绝，C 仍可运行。恢复正确资产后升级成功，关闭资产服务器后重复准备并安装 D，传输 0 B。首个真实模型回复、Windows 10/11 桌面操作和完整安装后的磁盘占用仍待客户机实测。

跨机预览在初始化附带的 Mac 测试节点时两次遇到能力查询或应用失败，两次实例均自动回收。Windows 10 x64 测试机已进入桌面并保存干净快照，系统报告为 22H2 build 19045，初始 PATH 中无 Node.js，WSL 可选功能关闭。已通过 SSH 进入隔离宿主，启动候选 D 的 IM/Web，验证健康接口，以及独立真实测试模型的推理。客户机的 IM 与模型回复仍须从实际入口验证。

[候选 C 测试版](https://github.com/Mrchen116/nano-multiagent/releases/tag/node-d3390ef8e9b3ab6113aff34f1dadd8804651af34)和[候选 D 测试版](https://github.com/Mrchen116/nano-multiagent/releases/tag/node-109ccf5b542f01aee6dbc8dce8eb83cc00990eb4)已公开到仓库的 GitHub Pre-release。两版各五份资产的大小和 GitHub SHA-256 与本地逐项相符。独立 IM 选择对应清单，客户端从 GitHub 下载原始资产。正式 Latest 仍为 v2.0.0，生产 IM 没有部署此改动。

[候选 C 的真实模型试验](https://github.com/Mrchen116/nano-multiagent/actions/runs/44789198104)从 GitHub 下载原始安装器，在 Windows Server 2022 上由安装器获取正式地址的资产。移除系统 Node 路径后，私有 Node v24.22.1、DSH 及具有 34 项工具的会话均正常启动。本地 Qwen 推理服务收到请求并生成了两个 token，后续应用助手配置时出现 `Temporary inspection cleanup could not be confirmed`。检查发现临时进程退出后仍调用仅 POSIX 提供的 `ps` 查询进程组。修复提交 `9d5232de2` 改用 Windows 进程树终止和存活检查，并让打包验收实际应用一次新配置。

[候选 E 的 Windows 构建与回归](https://github.com/Mrchen116/nano-multiagent/actions/runs/44790882552)在完整安装的版本中，成功为首个助手应用配置、回收临时进程并建立实际 DSH 会话。对应的 8 项配置检查进程测试在本地支持的 Node v24.22.1 下也全部通过。[候选 E 测试版](https://github.com/Mrchen116/nano-multiagent/releases/tag/node-4acc9145a62bddf5790a600baa1a970e885c91e4)共 83,431,741 字节，安装器 2,110,423 字节；5 份发布文件已逐项核对 GitHub SHA-256。
