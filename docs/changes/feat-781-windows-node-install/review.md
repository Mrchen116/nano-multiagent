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

[候选 E 的 Windows Server 2022 实机模型与 IM 试验](https://github.com/Mrchen116/nano-multiagent/actions/runs/44791673050)将系统 Node 从 PATH 移除。安装的 DSH 向真实 Qwen 提交“11 + 6”并得到“11 + 6 equals 17.”。随后从安装目录运行正式 setup，使用隔离账号确认绑定。IM 观察到该托管版本在线、模型服务配置成功并创建了个人助手。IM 聊天收到用户发出的“26 + 9”，五分钟截止时没有助手回复，这次完整聊天验收未通过。

[候选 E 的 IM 端到端验收（Windows Server 2022）](https://github.com/Mrchen116/nano-multiagent/actions/runs/44794072668/attempts/2)通过：从 GitHub 安装未修改的 EXE，使用私有 Node 完成 setup，以正式账号确认接口接受绑定，在 IM 查看节点上线，配置真实 DeepSeek 服务并创建个人助手。用户在同一个 IM 会话发出“22 + 7”，收到该助手回复“29”。由正式聊天 HTTP 接口发消息和读取回复，独立 IM 数据库也保存了这两条消息。模型测试专用凭据按工作流签名限时发放，无需用户提供模型密钥。

[通过 IM 从 C 升级到 E](https://github.com/Mrchen116/nano-multiagent/actions/runs/44795685103)。Windows 用旧版本正常绑定并在线，用户工作区写入校验文件；隔离 IM 发布 E 后，通过节点设置页使用的更新接口发起升级。升级操作返回成功，新 Gateway 在线，原账号、电脑 ID 和文件内容一致。随后关闭自启、手动启动、重新打开自启，再强制结束经创建时间确认的本机 Gateway，210 秒内未观察到恢复在线。

独立复核 `4933326e1..4acc9145a` 的临时进程清理与安装回归测试，未发现阻塞项。[Windows 专项验证](https://github.com/Mrchen116/nano-multiagent/actions/runs/44796545814)使检查进程在其子进程启动后主动退出。通过 PID 与创建时间确认，清理完成和一秒后两个进程均已退出，临时目录已回收。

用两个独立安装复现了 Gateway 异常退出后未能恢复。默认开启自启的电脑和曾经切换自启的电脑均在终止 Gateway 后持续离线，任务计划程序返回 Ready。[Windows 对照实验](https://github.com/Mrchen116/nano-multiagent/actions/runs/44796851157)

候选 F 在当前用户的后台宿主内等待旧进程退出，回收其子进程，在锁过期后重新检查用户的自启设置并启动 Gateway。原生回归测试实际注册并运行 Windows 计划任务、终止子进程、观察新的进程 ID，随后正常停止服务。独立复核修复与设计的差异后没有发现阻塞项。[Windows 构建与回归](https://github.com/Mrchen116/nano-multiagent/actions/runs/44797807954)

F 的五个公开文件合计 83,432,429 字节（79.57 MiB），其中双击安装器 2,110,422 字节，运行环境压缩包 78,689,983 字节，应用压缩包 2,630,721 字节。已核对所有文件的大小和 SHA-256。[候选 F 测试版](https://github.com/Mrchen116/nano-multiagent/releases/tag/node-876525e0d2c94bdacc006809e7d56d0b36beeff2)

Windows Server 2022 完成真实升级与异常恢复的全程验收。E 安装后，同一助手在 IM 回答了“21 + 7”为“28”。从 IM 触发升级到 F，原账号、节点 ID 和工作区文件均保留。关闭自启、手动启动、再打开自启后，脚本核对进程创建时间并强制结束 PID 7324；新进程 8180 自动就绪并连接。原助手、会话与旧回复仍在，随后回答“30 + 8”为“38”。隔离 IM 数据库同时保留了两次问答。安装器使用静默参数，绑定和聊天使用正式 HTTP 接口。之前两个独立执行分别在首轮就绪检查和创建个人助手时超时（HTTP 504）；第三次全程执行成功。[通过的执行](https://github.com/Mrchen116/nano-multiagent/actions/runs/44800187164) · [就绪超时](https://github.com/Mrchen116/nano-multiagent/actions/runs/44798577635) · [创建超时](https://github.com/Mrchen116/nano-multiagent/actions/runs/44799775310)

在 Windows Server 2022 的 Edge 中使用隔离 IM 的已登录新账号，从欢迎页点击设置助手，再点击网页的 Download Windows installer。浏览器从 GitHub 下载原始 F 安装器，校验 2,110,422 字节和 SHA-256，原网页随后显示 Open Crewden to connect。用无参数普通进程启动该下载文件，在真实安装向导中按控件名点击 Install、Finish，进程退出 0，当前用户协议处理器指向安装后的正确版本。[网页下载和普通安装向导](https://github.com/Mrchen116/nano-multiagent/actions/runs/44804867676)

另一次由 Windows Shell 打开相同下载文件，系统显示 Open File - Security Warning。该候选没有代码签名；自动化未完成系统警告的确认。上一项的普通安装向导验证从启动安装进程开始。[系统提示记录](https://github.com/Mrchen116/nano-multiagent/actions/runs/44804254815)

Windows 10 Enterprise LTSC x64（build 19044）使用微软评估镜像启动，Secure Boot 开启、WSL 关闭，普通用户 nanoqa 没有预装 Node、npm 或 pnpm。F 安装器退出 0，注册了正确的协议处理器，从公开发布源取得运行环境和应用。安装后的私有 Node 和 DSH 跑通，电脑绑定并在 IM 上线，配置了真实模型。该助手在 IM 对话中收到“26 + 6”并回复“32”，隔离 IM 数据库保存了这两条消息。随后 Windows PowerShell 验收驱动读到了空的子进程退出码，这次执行在重启前中止。[Windows 10 客户机首次对话](https://github.com/Mrchen116/nano-multiagent/actions/runs/44816199522)
