# 本地视觉证据

遵循合入main后的[证据保存规则](../../../../development/evidence.md)，截图不提交Git。原先24张设计及R1–R3验收图片已逐一复制并核对SHA-256，工作树本地原文件仍保留；报告中的文件名对应以下稳定目录：

`/Users/czj/.codex/artifacts/bugfix-618/visual-evidence/`

- `current-chat.png`、`prototype-web.png`、`prototype-narrow.png`、`prototype-ios.png`：设计前的真实页面与原型。
- `implemented-web.png`、`review-web-*.png`、`review-ios-*.png`：首轮实际页面与原生已观察状态，原生图片不代表后续未完成项目通过。
- `review-r2-*.png`：审批只读、媒体/撤权、历史和长内容。
- `review-r3-narrow-*.png`：窄屏补验；`review-r3-narrow-network-390.png`才是390 CSS宽，未带390的旧图不是该尺寸的证明。

后续main同步补验图片也保存至本目录，具体文件名、版本和场景以[regression.md](../regression.md)最新轮次为准。文字结论、尺寸及运行边界保留在版本化报告中，不将本地图片误写成Git中可下载的文件。
