<!--
模板说明（定稿后删除本块）

bugfix lite 的单一文档。默认走 lite。
若发现影响面扩大（跨多 milestone / 跨多模块）需升 full：拆为 incident.md + regression.md。

填写顺序：原始报告原话 → 澄清 → 现象 → 根因 → 修复 → 验证。
"修复"和"验证"段在 milestone 完成后补全。
-->

# <bugfix-id>: <短描述>

## Relations

- Related:

## 原始报告

<!-- 原话/截图保留。 -->

## 现象 / 复现

## 根因

<!-- 不止"哪行错了"，还要"为什么这种错能进来"。
     并追溯原始设计意图：grep docs/changes/ 找到引入这块功能的 unit，读它的 spec/design，
     写下"这块功能本来要达成什么"+"修复必须保住的不变量"。
     lite 没有 design 阶段，worker 只读这份 fix.md——不在这里写下意图，修复就容易把功能阉割掉来消症状。 -->

## 修复

<!-- 改了什么 + commits。 -->

## 验证

<!-- 修前能复现 → 修后不能；相关功能回归正常。 -->
