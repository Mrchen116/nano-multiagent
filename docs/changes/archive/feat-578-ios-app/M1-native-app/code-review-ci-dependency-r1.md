# Code Review / Verification: CI tinypool correction R1

2026-10-07。独立使用 `change-code-review`（patch）和 `change-verifier`（delta validity）执行一次限定delivery follow-up。`source_review_base=0a5bda0ce6f0d03fc847ce6f1d33f1d0076a76f0`，`validated_at=08fa4691ddf334e033382b71e40697481947fa6c`。diff仅frontend package.json/package-lock.json，7 add /4 delete，不重审整条feat-578，不改源码/测试/配置、不开GUI/服务、不重复执行测试或轮询caller全测。PR #324为既有Draft；本报告不推送或改变PR状态。

## Independent code review

```json
[]
```

`src/IM/frontend/package.json:45-47` 精确覆盖tinypool为2.1.2；`package-lock.json:6040-6048` 与其version/resolved/integrity一致，标记dev=true，engine `^20.0.0 || >=22.0.0`。Vitest仍锁3.2.7（其声明的tinypool范围仍^1.1.1，由npm override替换），没有升级Vitest或其它runtime依赖、改测试文件/超时阈值/CI配置、跳过audit。此major覆盖的实际兼容性要由安装和Vitest执行证明，不能只凭锁文件声称通过。

官方[GHSA-5gmw-xhrv-c9v3](https://github.com/tinylibs/tinypool/security/advisories/GHSA-5gmw-xhrv-c9v3)列patched2.1.1，官方[GHSA-85c8-ppgw-ccpr](https://github.com/tinylibs/tinypool/security/advisories/GHSA-85c8-ppgw-ccpr)列patched2.1.2；本覆盖选择第二项修复版本，未停在2.1.1。两公告为worker选项原型污染利用面的修复，不将公告本身当成本仓已有遭利用证据。

`.github/workflows/ci.yml:115-127` 仍setup-node20→npm ci→`npm audit --audit-level=critical`→npm run test；原CI log实际Node v20.20.2满足tinypool engine。安装的Vitest使用的Tinypool构造、child_process runtime、run/recycleWorkers/destroy等入口仍在2.1.2的公开types内；这是静态接线支持，不代替测试。tinypool无frontend/src runtime import，lock标记dev，不进入本次产品/API/权限实现变更。

## Evidence and verifier status

| Evidence / locator | 已核对结果 | 能力边界 |
|---|---|---|
| `/tmp/nano-feat578-ci-frontend-324.log` | 原CI npm audit退出1；tinypool<=2.1.1 aggregate severity critical，两GHSA被列出，Vitest依赖传播；Node20.20.2 | 原PR首轮失败保留，不称新候选远端CI已绿。公告页severity与audit aggregate记录各按实际来源，不能偷换 |
| `/tmp/nano-feat578-tinypool-ci.log` / `...audit-final.log` | npm ci装358包、审359包；最终audit仅8项（2low/3moderate/3high），无critical；caller交接critical audit命令退出成功 | **critical门修复证据**；不宣称所有漏洞清零、不扩大修复其它依赖 |
| `/tmp/nano-feat578-tinypool-build.log` | tsc -b /vite build实际成功；已有分块/体积warning保留 | 产品构建可完成，不当UI验收 |
| `/tmp/nano-feat578-tinypool-tests.log` | 首轮86文件：84pass/2fail，808测试：806pass/2fail；router找不到You & Teammate、nodes测试5000ms超时 | 保留真实失败，不以复跑直接抹除或确定根因为机器负载 |
| `/tmp/nano-feat578-tinypool-targeted.log` | 原两文件、未改测试，以maxWorkers=2执行，5tests/2files通过 | 证明该窄输入可运行，不是808全测通过 |
| `/tmp/nano-feat578-tinypool-tests-bounded.log` | 最终trim锁文件npm ci/audit后，以maxWorkers=2全测，**86files /808tests全绿**；Start02:07:19、Duration115.63s，caller主动交接exit0 | 没有改测试/断言/timeout或CI默认命令；是本地有界并行全测通过，不是远端默认并行已经通过 |

静态finding为[]，verifier **0 CRITICAL /0 WARNING /0 SUGGESTION，限定依赖修正pass**。本地运行时Node v25.8.2；CI Node20.20.2 engine静态兼容已核对，但新head远端CI尚待caller触发，不能把本地808结果写成Node20远端执行成功。首轮2fail原始结果保留，针对及全测复跑通过不单独证明失败根因。无需为纯dev worker依赖增加镜像实现测试或重跑原生/Python。

## Retained native / delta validity

已核对`383a5a9b1..08fa -- src/IM/ios specs/im/ios-client.md`无diff。原生产品仍383a，native36项证据及[静态R4](verification-simulator-r4.md)在原scope有效；[实际R6](acceptance-simulator-r6.md)由独立reviewer关闭S21反馈/停止故障/重试及受控历史，27个现行可达Scenario的接受范围保留，不能由本次frontend测试新授予。

另核首轮 `/tmp/nano-feat578-ci-324-native.log` 的真实36 native tests及Release archive成功，仍是首轮PR产物/原native范围证据，不扩张为最新head远端全CI绿，也不替代物理签名/安装验收。

现有iOS delta仍5 Requirements：原生业务与权限、会话恢复/退出隔离、授权媒体、前台提醒/后台边界、免费安装维护。本次不改产品源码/API/wire/权限/设计或任何delta正文，必要validity核对为**retained / aligned**；没有新spec delta，也不做canonical归并或archive。原Full未完物理范围继续保留：S2完整VoiceOver、S29/S30按用户deferred；模拟器/AX与依赖audit不得替代物理、签名续期或自然到期。无需因为角色更换重验未失效范围。

只有dev/test worker变更，既有受控S21条件及证据限度未改变。本轮最终本地测试绿只说明本依赖修正的验证结果；不构成Full accepted、Ready PR、merge、waive或部署批准。报告只写本角色文件，progress/PR scope由caller维护，output与其它dirty状态保留。

暂存本报告后文档检查通过322 maintained Markdown sources /75 required routes（包括caller progress对本报告的引用），本报告staged diff check通过。仅提交本报告，无push。
