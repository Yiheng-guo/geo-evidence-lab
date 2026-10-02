# GEO Evidence Lab

**让 AI 搜索可见性变化有据可查。** 郭一恒（Yiheng Guo）维护的 GEO 内容实验 Skill 与本地分析工具。

许多 GEO 流程能批量生成关键词和稿件，却很难回答：AI 真的提到了品牌吗？引用的是品牌来源吗？前后测是否可比？这个项目把内容任务与证据验证放在同一条工作流中。

> v0.1 是无需第三方 Python 依赖的本地工具＋Agent Skill。不会自动搜索、自动写稿或自动发布。示例全部是模拟数据，不代表真实品牌或真实豆包效果。

## 快速运行

需要 Python 3.10 或更新版本。克隆仓库后：

```bash
git clone https://github.com/Yiheng-guo/geo-evidence-lab.git
cd geo-evidence-lab
python3 skills/geo-evidence-lab/scripts/geo_lab.py plan --profile examples/profile.json --out examples/plan.json
python3 skills/geo-evidence-lab/scripts/geo_lab.py brief --profile examples/profile.json --plan examples/plan.json --out examples/brief.md
python3 skills/geo-evidence-lab/scripts/geo_lab.py compare --profile examples/profile.json --plan examples/plan.json --pre examples/pre.json --post examples/post.json --out examples/report
```

用浏览器打开 `examples/report/report.html`，展开每条问题查看前后原始回答和引用。输出 JSON 可继续用于分析。运行 `python3 -m unittest discover -s tests -v` 验证核心行为。

自动测试配置见 [GitHub Actions 示例](docs/github-actions.example.yml)。当前发布凭证没有 workflow 权限，因此配置尚未启用；有相应权限后可将其移到 `.github/workflows/tests.yml`，自动测试 Python 3.10、3.12 和 3.13。

## 能做什么

| 环节 | 产物 | 边界 |
| --- | --- | --- |
| 实验规划 | 固定问题清单、档案摘要 | 问题由用户提供，不捏造需求或搜索量 |
| 内容生产准备 | 证据驱动的文章任务 | 来源需 Agent 或人工验证，脚本不生成正文 |
| 效果复盘 | 品牌提及、自有来源引用及百分点变化 | 不等于推荐、信任或商业转化 |
| 证据检查 | 原始回答、URL、时间与采集条件 | 输入者负责真实性，程序不访问引擎 |
| 数据质量 | 缺失问题、排除记录、不可比较状态 | 搜索失败不记成未命中 |

## 作为 Skill 使用

将 `skills/geo-evidence-lab` 目录复制到你的 Codex skills 目录（通常为 `~/.codex/skills`），不要覆盖已有同名 Skill。随后可请求：

> 使用 $geo-evidence-lab，为我的品牌设计 AI 搜索内容实验。先核查证据，再建立固定问题集；我提供真实前后测记录后，请分析变化并解释局限。

Skill 内含完整脚本和数据契约，无须依赖本仓库以外的自定义 Skill。仓库不会自动修改你的本机 Skill 配置。

## 真实项目流程

1. 复制并修改 profile，填写真实用户问题、品牌、别名、自有域名与主张来源；不要把客户隐私提交到仓库。
2. 冻结 plan，在相同引擎、搜索模式、地区及会话条件下采集基线；多个轮次逐条保存原始回答和实际引用。
3. 生成 brief，核验每项主张的来源，交给 Agent 或人工写稿、改写和按授权发布；记录发布时间及内容 URL。
4. 按预先确定的窗口后测，使用同一计划与采集条件。导入 pre/post，再生成报告。
5. 人工检查品牌是否被否定提及、第三方引用是否支持结论。将有效线索用于下一轮内容改进。

详见 [数据契约](skills/geo-evidence-lab/references/data-contract.md) 和 [设计取舍](docs/design.md)。

## 成本与解读

本地命令不产生 API 费用。真实采集、来源验证、模型写作、人工审稿和媒体发布有各自的时间与费用，不能把它们算成“免费全自动”。发布到被检索到存在延迟；模型更新、用户个性化和重复抽样会影响结果。前后变化不能单独证明发布造成了提升；本项目不提供统计显著性或转化归因。

## 来源与许可证

GEO 概念可参考 [GEO: Generative Engine Optimization](https://arxiv.org/abs/2311.09735)。项目需求分析参考了一份用户提供的 GEO 工作流资料，其授权状态未知；本仓库没有分发该资料的代码、提示词、文档、表格或客户材料。此处的程序、Skill、文档和模拟示例为重新编写的实现，不声称原资料属于维护者。

本仓库以 [MIT](LICENSE) 开源。欢迎通过 Issue 提供脱敏后的输入、预期结果与复现步骤。下一步方向：真实采集适配器、第三方引用语义标注，以及带控制组的实验分析。
