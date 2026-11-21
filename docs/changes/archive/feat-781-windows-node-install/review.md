# feat-781 Windows 电脑安装验收

初版实现基于 `7bcb6b25d`，桌面验收最终使用[候选 J](https://github.com/Mrchen116/nano-multiagent/releases/tag/node-9a53b14bed3eab7db518f67ea129dc0cf5254c03)。独立代码审查覆盖 `6519ffe44`，差量复审关闭跨浏览器问题后，审查者又复核精简归档、安装器进度显示（`109ccf5b5`）与持续运行的 Windows PR 检查。最终 delta 与受审实现一致。

| 检查 | 证据 | 结果 |
|---|---|---|
| 版本分发、平台匹配、进程生命周期与更新 | 独立审查者检查安装器、宿主、受管更新、绑定流程及两份 delta | 初审发现原页面无法恢复跨浏览器确认。用户现可在原网页选择自己刚确认的电脑，必须实际在线才可继续。对应回归测试先失败再通过，复审关闭该问题，最终 delta 与实现一致。 |
| 网页下载、连接、重试与不可用状态 | 隔离 IM、SQLite、登录测试账号与真实 Chrome，切换 Windows UA，下载测试响应为 13 字节。见[桌面](M1-windows-node/windows-1200.png)、[窄窗口](M1-windows-node/windows-390.png)、[正在等待](M1-windows-node/windows-waiting-390.png)及[尚未发布](M1-windows-node/windows-unavailable-390.png)。 | 作者走查。网页不会在点连接时提前显示在线。临时栈和测试浏览器已回收。跨浏览器补丁另有 18 项 onboarding 测试。 |
| Windows 隔离工作区中的宿主和进程树 | [候选 A 的原生测试](https://github.com/Mrchen116/nano-multiagent/actions/runs/44771705408)运行两个配置、真实 Windows 任务与子进程，检查出生标识、优雅退出、超时收拢、异常和独立更新进程。 | Windows Server 2022 runner 通过。普通本地账户的桌面登录和系统重启需由客户机实测。 |
| 安装器、运行图和缓存 | [候选 A](https://github.com/Mrchen116/nano-multiagent/actions/runs/44771705408)和[候选 B](https://github.com/Mrchen116/nano-multiagent/actions/runs/44772109381)执行按用户静默安装，验证协议注册，在 ZIP 解压后的版本目录中启动私有 Node、pnpm 和 DSH，实际创建会话、查询工具，然后关闭资产服务验证热缓存。 | 两次通过。包含空格和中文的目录覆盖真实宿主和 DSH。运行器测试使用本地资产 fixture。 |
| Windows 10 x64 普通用户 | [J 全新安装、两次系统重启与四次真实回复](https://github.com/Mrchen116/nano-multiagent/actions/runs/44845056713)、[E → G 受管更新](https://github.com/Mrchen116/nano-multiagent/actions/runs/44826432787) | LTSC 21H2 build 19044，无系统 Node、npm、pnpm 或 WSL，标准用户独立执行。登录自启、异常恢复、关闭自启及手动启动全部通过，更新保留原账号、电脑身份、助手、聊天和工作文件。另在 22H2 build 19045 验证 C 的安装及协议注册。 |
| Windows 11 x64 普通用户 | [J 的完整桌面回归](https://github.com/Mrchen116/nano-multiagent/actions/runs/44851124367)、[I → J 受管更新](https://github.com/Mrchen116/nano-multiagent/actions/runs/44845287991) | Windows 11 Enterprise build 26300，普通账号，无系统 Node、npm、pnpm 或 WSL。安装、首轮对话、两次重启、异常恢复、关闭自启后正常手动启动均通过。原位更新保留绑定、聊天和工作文件。 |

早期用于桌面验收的是[候选 C](https://github.com/Mrchen116/nano-multiagent/actions/runs/44773547448)（`d3390ef8e9b3ab6113aff34f1dadd8804651af34`）和[候选 D](https://github.com/Mrchen116/nano-multiagent/actions/runs/44773636434)（`109ccf5b542f01aee6dbc8dce8eb83cc00990eb4`）。两次原生安装、离线复用、DSH 会话和工具发现均通过。D 增加了下载字节进度。核对其 EXE 的 PE 证书目录，偏移与大小均为 0，本次测试安装器未签 Authenticode；实际系统发布者提示由桌面验收记录。两版运行环境 ZIP 的 SHA-256 均为 `ee9852cc1d5edc86eb2655c794ec0520c201af9ee0b092c81da07a2478502df9`。

| 体积 | 候选 B | 候选 D |
|---|---:|---:|
| 用户双击的安装器 | 2,110,169 B | 2,110,427 B |
| 运行环境 ZIP | 99,029,227 B | 78,689,983 B |
| 应用 ZIP | 3,207,648 B | 2,629,727 B |
| 全部首次安装产品资产（含元数据） | 104,348,347 B | 83,431,440 B |
| 两份 ZIP 中普通文件解压字节合计 | 353,802,567 B | 253,323,673 B |

从 GitHub 下载后分别校验 A、B、C、D 的工件包 SHA-256，按清单逐项重算四份资产的大小与哈希。D 的首次资产合计 79.57 MiB，较 B 减少 20.0%。运行环境中最大的三项压缩内容为私有 node.exe（35,081,382 B）、图像处理的 sharp 原生组件（8,363,928 B）和受管包操作所需的 pnpm（4,658,848 B）。应用归档中的个人助手包为 1,872,318 B，DSH 集成为 416,694 B。构建剔除了仅其他 DSH 界面使用的 Office 预览、语音识别、Inspector，以及编译器类型声明和调试映射。D 的实际 Windows 会话仍列出 `read`、`write`、`pwsh`、`skill` 等 34 个工具。

[Windows Server 实际传输测试](https://github.com/Mrchen116/nano-multiagent/actions/runs/44777807452)使用原始 C/D 工件，按发布清单核对哈希，再由本地资产服务器计量响应正文。已取得安装器后，C 首次准备下载 81,319,915 B。升级到 D 下载 2,630,235 B，共用运行环境的下载量为 0 B。故意提供损坏的 D 应用包时，更新被拒绝，C 仍可运行。恢复正确资产后升级成功，关闭资产服务器后重复准备并安装 D，传输 0 B。客户机的真实回复和安装目录占用见下方后续执行。

跨机预览在初始化附带的 Mac 测试节点时两次遇到能力查询或应用失败，两次实例均自动回收。Windows 10 x64 测试机已进入桌面并保存干净快照，系统报告为 22H2 build 19045，初始 PATH 中无 Node.js，WSL 可选功能关闭。已通过 SSH 进入隔离宿主，启动候选 D 的 IM/Web，验证健康接口，以及独立真实测试模型的推理。此时只完成了宿主模型检查。

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

Windows 10 LTSC 从干净普通用户安装 F 后，三次在原聊天得到真实回复。首次回复为 39，重启登录自动上线后回复 66，强制结束经创建时间确认的 Gateway 后自动恢复并回复 63。关闭登录自启并再次重启，连续 180 秒确认 Gateway 未启动、IM 也显示离线；手动启动后原节点再次上线。这次测试的模型转发进程在最后一题前退出，手动启动后该题没有收到回复。另一次创建助手时返回了可重试的 `capability_usage_unavailable`。按普通文件身份去除硬链接重复、不遍历连接目录，安装目录逻辑大小为 255,471,768 字节（243.64 MiB），未测 NTFS 实际分配块数。[登录、自启、故障恢复和落盘计量](https://github.com/Mrchen116/nano-multiagent/actions/runs/44820406588) · [创建助手失败记录](https://github.com/Mrchen116/nano-multiagent/actions/runs/44818227719)

另一台 Windows 10 LTSC 在 F 上重现重启后的手动启动缺陷。该次首轮、自动登录、异常退出恢复分别收到 36、58、65；关闭自启并重启后，原 Gateway 的 PID 已被本次系统启动中的其他进程使用，手动启动返回 PID identity changed。G 将记录中的创建时间与 Windows 本次开机时间用同一 FILETIME 单位比较，忽略前次开机留下的记录。本次开机中的 PID 与创建时间不匹配时仍保留现场并拒绝发送信号。独立代码审查复核了两类情况和原生宿主的停机路径。[F 上的复现](https://github.com/Mrchen116/nano-multiagent/actions/runs/44823122066) · [G 修复](https://github.com/Mrchen116/nano-multiagent/commit/45d34317b)

G 的原生打包回归将当前活进程的 PID 写入旧状态，分别验证前次开机记录已失效，以及本次开机创建时间不符时 stop 拒绝操作。G 安装器为 2,110,428 字节，首次全部产品资产为 83,432,625 字节（79.57 MiB）。应用压缩包 2,630,911 字节，运行环境与 F 相同。GitHub 上五个文件的大小和 SHA-256 已逐项核对。[原生构建及运行测试](https://github.com/Mrchen116/nano-multiagent/actions/runs/44826133809) · [候选 G](https://github.com/Mrchen116/nano-multiagent/releases/tag/node-45d34317b43aa741d3bfb46e2ee7ca53cae46254)

Windows 10 LTSC 普通账户在 E 版用原助手回答“22 + 6”为“28”。从同一 IM 的受管更新入口升级到 G，IM 报告成功，原账号、电脑身份、工作区中的随机校验内容及原对话均保留。之后在这台客户机切换登录自启并强制结束 Gateway，原助手再次回答“24 + 6”为“30”。[Windows 10 客户机真实升级](https://github.com/Mrchen116/nano-multiagent/actions/runs/44826432787)

Windows 10 LTSC 的 G 在同一助手、同一对话里给出四次真实回复：首轮 33，重启登录后 57，强制退出自动恢复后 63。关闭自启、再次重启并观察 180 秒确认电脑离线，手动启动后原助手回答“69 + 27”为“96”，自启设置仍为关闭。新安装目录按文件身份去重的逻辑大小为 255,472,230 字节（243.64 MiB）。[G 的 Windows 10 客户端全程执行](https://github.com/Mrchen116/nano-multiagent/actions/runs/44826221155)

Windows 11 Enterprise x64（build 26300）上，G 的普通账户安装、绑定、上线、DSH 原生工具及真实模型服务验证成功。在第一次创建个人助手时，六次能力检查耗时 7.1–8.9 秒并超时，随后的一次清理失败使检查器拒绝后续请求。该轮未收到首条聊天回复。H 保留隔离和取消机制，给受管 Windows 的冷启动检查留出 30 秒执行、32 秒节点和 35 秒 RPC/目录读取期限。新增测试验证第 12 秒返回的结果可通过 RPC 和共享目录两层。独立审查发现并复核了共享目录原先单独的 9 秒截止时间。[Windows 11 失败现场](https://github.com/Mrchen116/nano-multiagent/actions/runs/44827780596) · [H 原生包检查](https://github.com/Mrchen116/nano-multiagent/actions/runs/44832334062)

H 的五个产品文件合计 83,432,874 字节（79.57 MiB），其中安装器 2,110,426 字节，应用压缩包 2,631,162 字节，一次性运行环境 78,689,983 字节。已对照 GitHub 核对五个文件的大小和 SHA-256。[H 测试安装包](https://github.com/Mrchen116/nano-multiagent/releases/tag/node-c3a18aa544b1ffe1b01dc174f4a541ad455ddd00)

H 的 Windows 10 干净客户机在同一原会话依次答出 42、67、58、95，覆盖首次使用、真实重启登录、异常退出恢复、关闭自启再重启后的手动恢复。H 安装目录按文件身份去重后为 255,472,897 字节（243.64 MiB）。Windows 11 的首个 H 试验完成安装及真实绑定，但首次启动等待约 67 秒超时；IM 有绑定记录，没有收到这次 Gateway 的注册或心跳。[H 的 Windows 10 全程](https://github.com/Mrchen116/nano-multiagent/actions/runs/44832613802) · [H 的 Windows 11 启动超时](https://github.com/Mrchen116/nano-multiagent/actions/runs/44832471571)

Windows 11 再次从 H 干净安装，以 8 GiB、4 vCPU 的普通账户直接完成绑定、Gateway 就绪和模型验证。节点分别用 10.273、24.685、13.486、11.760 秒成功计算能力目录，前四次 IM 均返回 504。同一创建请求重试后，原助手在 IM 实际回答“29 + 5”为“34”。检查发现 Channels 在第 10 秒提前释放了请求编号。用真实 WebSocket 在 10.3 秒回传结果，修复前稳定重现 Server inspection request expired；I 让临时回复使用 IM 声明的有界期限。修复后包含到期拒绝和迟到前成功在内的 19 项真实传输测试全部通过，独立复核未发现阻塞。[H 的 Windows 11 执行](https://github.com/Mrchen116/nano-multiagent/actions/runs/44835314150) · [I 修复](https://github.com/Mrchen116/nano-multiagent/commit/c37c66236)

Windows 10 LTSC 在 Edge 的 IM 点击设置和下载，保存的 H 安装器有 Windows 互联网安全区域标记，且 SHA-256 与公开候选一致。经 Windows Shell 打开，真实安装向导的 Install 和 Finish 控件均完成；HKCU 协议指向已安装文件。客体持久化的 pass.json 为 true。本次宿主回执超时使工作流为红，关机后从客体磁盘读回了完整结果。Windows 11 另一次执行已核对相同的网页下载和安全区域标记，未完成向导确认。[Windows 10 客体安装向导](https://github.com/Mrchen116/nano-multiagent/actions/runs/44834091111) · [Windows 11 浏览器下载](https://github.com/Mrchen116/nano-multiagent/actions/runs/44832658348)

I 的全新 Windows 构建运行了原生宿主、安装器、私有 Node、DSH 会话和工具回归。公开的 EXE 为 2,110,429 字节、应用包为 2,631,282 字节，运行环境沿用 78,689,983 字节；首次下载合计 83,432,997 字节（79.57 MiB）。Windows 11 在原 IM 对话中发送“27 + 4”，原助手回复“31”。[原生构建与回归](https://github.com/Mrchen116/nano-multiagent/actions/runs/44837688430) · [I 公开测试包](https://github.com/Mrchen116/nano-multiagent/releases/tag/node-fb427015ad829153906b25baa948d6adb890edda)

候选 I 的 Windows 10 客户机在同一聊天里依次回复 30、62、64、94。关闭自启重启后，先观察了 180 秒离线，再手动启动得到最后一个答案。安装目录逻辑大小为 255,473,233 字节（243.64 MiB），去重计量方法同上。[I 的 Windows 10 完整验收](https://github.com/Mrchen116/nano-multiagent/actions/runs/44837753289)

在 Windows 11 build 26300、8 GiB / 4 vCPU 的 I 客户机，首次真实回复 31，重启登录回复 61，强制退出并自动恢复后回复 63。关闭自启并重启后观察 180 秒，电脑保持离线。手动启动后的第 41 秒 IM 收到该节点心跳，但 CLI 约 65 秒时报告 readiness 超时。本次未完成最后一条消息；H 在该步骤也观察到同一现象。[Windows 11 I 客户机](https://github.com/Mrchen116/nano-multiagent/actions/runs/44837750416)

在同配置的 Windows 11 上复现 I 的手动启动误报。CLI 在第 65 秒报告超时。同一 Gateway 在第 80 秒发布就绪状态，第 90 秒连上 IM，原聊天随后收到正确的新回复 95，期间没有重试、重启或修改自启设置。J 将 Windows 默认启动等待延长到 120 秒，启动时等状态文件就绪后才查询进程出生时间。受管更新也使用该预算；配置中的显式期限仍有效。独立复核通过，本地生命周期与更新的 8 项测试通过。[原始故障与同进程恢复](https://github.com/Mrchen116/nano-multiagent/actions/runs/44841810653) · [修复](https://github.com/Mrchen116/nano-multiagent/commit/9a53b14be)

J 的原生 Windows 构建通过。下载 EXE 为 2,110,415 字节，应用 ZIP 为 2,631,466 字节。运行环境 ZIP 与 I 相同，首次安装的五份公开资产共 83,433,167 字节（79.57 MiB）。逐一核对了公开发布记录中的长度和 SHA-256。[原生构建](https://github.com/Mrchen116/nano-multiagent/actions/runs/44845041640) · [J 的安装包](https://github.com/Mrchen116/nano-multiagent/releases/tag/node-9a53b14bed3eab7db518f67ea129dc0cf5254c03)

Windows 10 的 Edge 从 IM 下载 I 后，经 Windows Shell 启动，安装向导、完成按钮与当前用户协议注册均通过。Windows 11 的 Edge 也取得一致的 EXE，带有互联网安全区域标记；Windows 显示未签名发布者的系统确认，自动化选择 Run 后没有观测到安装向导。[Windows 10 和 11 的 Shell 启动记录](https://github.com/Mrchen116/nano-multiagent/actions/runs/44841753397)

Windows 10 LTSC 使用 J 依次验证首装、登录自启、进程异常后恢复，以及禁用自启并重启后手动启动。原助手在原会话依次回复 30、66、64、85。安装目录逻辑大小为 255,473,688 字节（243.64 MiB），按文件身份去重，未计入连接目录。[Windows 10 J 回归](https://github.com/Mrchen116/nano-multiagent/actions/runs/44845056713)

Windows 11 的独立普通用户安装 I，从已绑定节点的原聊天得到 30。隔离 IM 随后发布 J，经既有受管更新入口切到 J。更新前写入的工作文件按内容核对一致，电脑身份、账号、助手和聊天编号均保留，原聊天也保留上一条回复，更新后新题答出 33。[Windows 11 I → J 原位更新](https://github.com/Mrchen116/nano-multiagent/actions/runs/44845287991)

Windows 10 和 11 的 Edge 从实际 IM 入口下载 J，核对 SHA 后分别完成原生安装向导的 Install 和 Finish，并验证协议处理器指向已安装文件。Windows 10 经 Windows Shell 打开，Windows 11 以无参数普通进程打开。Windows 11 的 Shell 发布者确认仍以上一条观察为准。[Windows 10/11 的 J 图形安装](https://github.com/Mrchen116/nano-multiagent/actions/runs/44845414291)

J 的首次 Windows 11 全程执行中，隔离 IM 保存了首次、重启登录和异常恢复后的三组题答，助手分别回复 39、58、63。宿主 32 分钟取回执超时，测试销毁了客体；该次运行没有取得关闭自启后手动启动的退出码或最终回复。[首轮 J 桌面运行](https://github.com/Mrchen116/nano-multiagent/actions/runs/44845080906)

J 的最终 Windows 11 客体执行中，首装、重启登录和异常退出恢复分别得到真实助手回复 41、59、64。关闭登录自启并重启后持续观察 180 秒，系统保持离线。首次手动启动用时 53.598 秒，退出码为 0，原聊天对于“63 + 21”回复“84”，自启仍处于禁用状态。[Windows 11 J 完整回归](https://github.com/Mrchen116/nano-multiagent/actions/runs/44851124367)
