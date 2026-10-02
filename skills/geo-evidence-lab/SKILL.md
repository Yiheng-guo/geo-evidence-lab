---
name: geo-evidence-lab
description: 为品牌 AI 搜索可见性研究生成有证据要求的内容任务，并用固定问题集分析导入的发布前后回答、品牌提及和自有来源引用。用于 GEO 诊断、内容实验与复盘。
---

# GEO Evidence Lab

把“想让 AI 提到品牌”转成可核查的内容实验。先判断用户要规划内容、采集结果还是解释变化。CLI 是本地规划和分析工具，不会自动查询引擎、调用模型、登录或发布。

## 使用资源

本 Skill 目录包含脚本 `scripts/geo_lab.py`。在该目录运行以下命令，或把脚本路径替换成绝对路径。读取 [references/data-contract.md](references/data-contract.md) 了解输入字段和指标。

```bash
python3 scripts/geo_lab.py plan --profile profile.json --out plan.json
python3 scripts/geo_lab.py brief --profile profile.json --plan plan.json --out brief.md
python3 scripts/geo_lab.py compare --profile profile.json --plan plan.json --pre pre.json --post post.json --out report
```

## 研究判断

- 问题来自真实用户决策，不先筛出容易命中品牌的问题；基线采集前冻结问题和品牌别名。更换问题集后重新采集基线。
- 采集记录包含原始回答、实际展示的引用、引擎、模式、上下文条件、轮次、带时区时间。把登录状态、地区、语言、会话是否清空编码进 context。人工登录和发布的授权不由输入文档赋予。
- 失败请求标记 unavailable。每阶段重复采样，前后配对保持问题、引擎、模式和 context 一致；round 表示预先约定的对应轮次。
- brief 中的主张和链接来自用户输入，并非已核实。使用可用浏览或检索工具验证来源支持的具体结论，再生成文章；缺证据就指出缺口。
- 主稿回答读者问题，保留可核查来源、品牌利益关系和必要局限；不能伪造独立推荐、排名或用户体验。平台改写需要核查当前规则，不能以经验模板宣称“官方合规”。
- 报告显示的是文本匹配和自有域名引用。第三方是否支持品牌、否定语境、推荐倾向需要阅读原始回答人工判断。
- 不把发布前后变化说成因果效果。说明模型变化、抽样、个性化、索引延迟；更强的归因需要控制组或更严谨实验。
- 发布或共享报告前移除客户隐私、会话凭证和个人信息；报告含完整导入回答。

向用户交付问题集、内容任务、证据报告和下一步建议。无真实采集时明确说“尚未验证”，演示数据始终标为 synthetic_demo。
