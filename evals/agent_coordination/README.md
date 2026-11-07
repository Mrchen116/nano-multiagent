# Agent 内部协作评测

[GC-01](cases/gc01/case.json) 保留 iOS、Computer use、Work、卡片、菜单和附件六条线。[GC-02](cases/gc02/case.json) 是单任务多轮调研。同一份 case.json 驱动 DAG 页面、回放与代码核验。新增案例放入 cases/<id>/case.json 和引用正文，自动出现在统一评测页面。

## 统一入口

```sh
pnpm eval-ui
```

同一服务展示 Memory、Intelligent UI、Spec/design alignment、Agent 内部协作。选择协作 case 后，可以按任务筛选、切 DAG/按序列表、缩放、点节点看完整正文、原始附件声明、来源、前置条件、备用措辞和检查项。

```sh
pnpm eval-ui --coord-run /absolute/path/to/private-run --output /absolute/path/to/viewer-state
```

挂接运行记录时核验 frozen case 版本，显示各组节点状态和收据，IM 链接保留。静态定义标为未运行。旧版手写回放的归档保留原始证据，不能当作新版 DAG 的实验记录挂接。

## 五种原语

| type | 谁到谁 | 执行方式 |
|---|---|---|
| user_message | 用户 → 主 Agent | 脚本通过真实 IM 发送 |
| delegate | 主 Agent → 子 Agent | 等待真实派工或已有执行者收到任务，绑定逻辑 worker |
| worker_message | 子 Agent → 主 Agent | mock 子 Agent 通过原生内部 send_message 回报 |
| user_reply | 主 Agent → 用户 | 观察 IM 公开回复，after_report 要求根模型已经实际收到内部回报 |
| child_message | 主 Agent → 子 Agent | 观察对应子模型实际收到续派 |

固定检查项在 primitives.json。派工和续派核对原话、可读附件，以及主 Agent 自己的判断是否标明。子 Agent 提问核对当时已有授权，真正需要用户决定时观察公开问题和决定回传。各 case 的 rubric.md 保留语义检查要点，全案审阅每次实验做一次。

## 定义与依赖

```json
{
  "version": 1,
  "id": "example",
  "title": "单任务交接",
  "description": "用户交办后，等待真实委派",
  "context": "默认 Global 配置",
  "tasks": {"research": "调研"},
  "attachments": {},
  "nodes": [
    {"id":"U01","type":"user_message","task":"research","title":"用户交办","after":[],"content":{"text":"帮我调研 macOS 开源桌面操作工具。"}},
    {"id":"D01","type":"delegate","task":"research","title":"等待实际派工","worker":"researcher","after":["U01"],"matcher":{"source_node":"U01"}}
  ]
}
```

content/fallback 可以用 text 或相对 file 引用完整 Markdown；引用限本 suite 材料。节点 attachments 使用顶层登记键，原图在私有 images 映射里提供。source 保存历史来源和清洗说明，checks 追加节点特有关注点。

- after 的前置必须成功，否则本节点 blocked。order_after 仅保证先后，不传播前置失败，用于在一条任务中插入另一条独立需求。
- delegate 和观察节点使用 matcher.all/any/not 正则以及 source_node（核对该次实际用户正文）。只有一个实际候选时自动绑定。多候选保留证据并等待运行目录 bindings.json，例如 {"B":{"ios":"实际直属子会话 UUID"}}。所选会话仍必须通过相同收件匹配。
- user_reply.after_report 指定一条或多条 worker_message，公开问题必须晚于根模型实际收到所有回报。
- user_message.when 可以引用 evidence_node 的成功收据，或 source=public 观察当前窗口。成立用 content；截止无匹配时用 fallback；没有 fallback 时 untriggered，并阻断硬依赖。after/order_after 决定观察起点，每个节点单独计时，默认 120 秒。
- worker_message.final=true 表示有实质内容的最终回报，内部发信成功后该轮正常结束。没有交付内容的停机不算完成。
- 已排队但未被子模型消费的续派有单独证据。fixture 可安排一次只读 AGENTS.md 推进等待中的 mock，再核验真正的模型请求。该动作带 fixture 收据，不归给主 Agent。

## 运行与核验

主模型固定 Sol 6.1 high。除 A/B 冻结的 Prompt/Skill 变量外，复用默认 Global 工具、Feature 与 Skill。两个候选使用同一版本的独立 Nano 源码快照，保留 AGENTS.md 与项目技能，控制材料留在工作区外。普通子 Agent 用脚本，Dreaming 和工具审核继续真实调用。

```sh
mkdir -p "$run"
evals/agent_coordination/start.sh "$run" "$new_prompt_patch"
PYTHONPATH=.:evals/agent_coordination python3 evals/agent_coordination/run.py evals/agent_coordination/cases/gc02/case.json "$run"
PYTHONPATH=.:evals/agent_coordination python3 evals/agent_coordination/score.py "$run" --code-only
```

GC-01 加 --images /private/images.json，内容为 U01、U09e、U13、U17 到各自原图路径的映射。缺图在发送前报错。图片探针随回放执行，只打开实际交给子 Agent、文件指纹与原图一致的本地路径。代码核验实际 read_image 结果。

run_gc01.py 和 run_gc02.py 是指定对应 case 的短入口，接受共享 runner 的参数。任意新 case 都可直接传给 run.py。--arms B 可只跑一组，--validate 只校验定义，无模型调用。

运行目录保存 case.json 的冻结正文与 SHA256、<case>-A/B.json 状态、实际正文与条件选择、各 worker 绑定及观察收据。--resume 拒绝不同 case 版本，沿用已终态节点和内容选择。发送前写 intent；意外中断且无可靠回执时标 uncertain，先查真实 IM，不自动重发。登录在长回放中续期。

score.py 自动遍历用户节点，收集实际子模型原话、排队证据、图片指纹、主子通信和工具结果，生成匿名全案审阅包。未触发不是自动判 Agent 错误，审阅需区分合理内部决定、环境限制与 case 缺前文。默认再做一次整体 LLM 审阅，--code-only 可交独立 Agent 阅读，不逐节点调用 judge。

停止自建隔离栈用 scripts/e2e-down.sh --wt "$run"，评测 provider PID 在 provider.json。前端服务只读案例与登记运行证据，Ctrl-C 关闭自己的 viewer。
