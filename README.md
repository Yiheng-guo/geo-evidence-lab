# GEO Evidence Lab

**让 AI 搜索内容实验有据可查。** 郭一恒（Yiheng Guo）维护的中文 Agent Skill 与本地分析工具，MIT 开源。

给品牌内容负责人、GEO 顾问和产品经理提供一条可复核的流程：整理读者问题与证据 → 采集发布前回答 → 制作内容任务 → 按授权写稿和发布 → 采集发布后回答 → 分析提及、引用与人工推荐判断。

> v0.2.0。CLI 不调用模型、不访问搜索引擎、不登录或发布。写作、来源核查和真实搜索由宿主 Agent 的可用工具或人工完成。所有随仓库提供的回答和效果数字均是模拟数据。

## 先看示例

需要 Python 3.10+，无需第三方 Python 依赖：

```bash
git clone https://github.com/Yiheng-guo/geo-evidence-lab.git
cd geo-evidence-lab
python3 skills/geo-evidence-lab/scripts/geo_lab.py baseline --profile examples/profile.json --plan examples/plan.json --input examples/pre.json --out examples/baseline
python3 skills/geo-evidence-lab/scripts/geo_lab.py compare --profile examples/profile.json --plan examples/plan.json --pre examples/pre.json --post examples/post.json --out examples/report
```

浏览器打开 `examples/baseline/report.html` 或 `examples/report/report.html`。每条问题可展开原始回答、采集时间、引用 URL 和人工标注。JSON 报告用于后续分析。演示中两条后测都提及品牌，但其中一条明确不推荐，因此提及率与人工推荐率不同。

## 谁在什么情况下用

| 用户 | 使用场景 | 交付物 |
| --- | --- | --- |
| 品牌内容负责人 | 发布内容前，想知道目标读者问的问题中有没有品牌 | 固定问题集、基线报告、证据缺口和内容任务 |
| GEO 顾问 / 内容服务团队 | 客户问“你做的内容有什么变化，依据在哪” | 条件匹配的前后对比、原始记录、排除样本及局限 |
| AI 产品经理 / 创业团队 | 验证 AI 搜索是否值得继续投入内容资源 | 多引擎分组结果、试验下一步；转化数据需另外收集 |

这些是根据功能推导的目标场景，尚无真实客户案例或需求访谈证明。本项目不承诺推荐提升、平台收录、排名或获客。

## 可执行能力

| 命令 | 作用 |
| --- | --- |
| `init` | 创建空白品牌项目，默认忽略客户数据，不覆盖已有项目 |
| `plan` | 固定问题、品牌别名和自有域名；阻止事后更换检测标准 |
| `worksheet` | 生成 Excel 等工具可填写的前后测 CSV，支持多个采集轮次 |
| `import-csv` | 转成分析用 JSON；未采集与搜索失败分开处理 |
| `baseline` | 只有发布前记录也能看现状和问题覆盖缺口 |
| `brief` | 生成全部问题或单个问题的写作任务，主张来源仍待核验 |
| `compare` | 配对比较，显示分组结果、排除记录及人工标注的推荐变化 |

**Skill 与脚本的分工**：脚本做确定性的文件加工和计算；Skill 指导 Agent 研究问题、核查来源、生成正文、做平台适配与解释报告。后者依赖宿主模型和可用工具，不能用生成 brief 代替成稿，也不能用分析成功代替效果验证成功。

## 实际操作流程

1. 创建项目，填写品牌、读者、业务、真实问题、别名、自有域名与主张来源。
2. 固定问题集，生成采集表，事先约定引擎、模式、会话条件和轮次。
3. 人工或有可用浏览工具的 Agent 搜索，填写原始回答、实际引用和时间；导入后看基线报告。
4. 按单个问题生成 brief，核验来源，生成文章和主张—来源对应表；做平台适配，按用户授权发布并记录 URL、时间。
5. 在预先约定的后测窗口，用同一批问题与同类条件再次采集。
6. 生成对比报告，展开证据复核推荐语境，决定补证据、调整内容或继续观察。

可复制的完整命令见 **[新手操作指南](docs/getting-started.md)**；能力差异与场景实例见 **[产品说明](docs/product-guide.md)**。

## 安装 Skill

复制 `skills/geo-evidence-lab` 到 Codex skills 目录（通常为 `~/.codex/skills`），不要覆盖已有同名 Skill。请求示例：

> 使用 $geo-evidence-lab，为我的品牌建立 GEO 内容实验。请先澄清目标用户与真实问题，整理证据缺口，建立固定问题集；指导我采集基线，再核查来源并写稿。等我提供后测记录后，用原始证据解释变化。

Skill 自带脚本和参考文档，复制该目录即可使用。仓库不会自动修改本机配置或授权外部发布。

## 指标与限制

- **品牌提及**：字符串匹配，否定提及也可能命中，不等于推荐。
- **自有来源引用**：实际引用 URL 的域名匹配，不证明网页支持结论；第三方对品牌的支持需另行核查。
- **人工确认推荐**：需要前后两条都标注并填写判断依据；未标注不算零推荐。
- **配对变化**：同一问题、引擎、模式、上下文、轮次才比较；失败和缺失不会当成未命中。总体同时给出引擎／模式／上下文分组结果。
- **覆盖缺口**：报告检查问题是否至少有一条有效记录或有效配对；不会自动知道未导入的计划轮次，需对照采集表检查。

引擎升级、个性化、索引延迟、问题选择偏差和重复采样都可能影响结果。前后变化不能单独证明内容发布造成了提升；没有统计显著性检验、控制组分析或商业转化归因。本地脚本无 API 费用，模型写作、真实采集、审稿与发布各有时间和费用。输出 HTML/JSON 包含完整回答，公开分享前需要脱敏。

## 验证与版本

```bash
python3 -m unittest discover -s tests -v
```

测试覆盖采集表导入、数据完整性、配对条件、域名匹配、人工推荐分母、HTML 转义与完整 CLI 流程。[GitHub Actions 配置示例](docs/github-actions.example.yml)尚未启用，因为发布凭证缺少 workflow 权限；有权限后可移到 `.github/workflows/tests.yml`。版本变更见 [CHANGELOG](CHANGELOG.md)。

## 来源与许可证

概念参考 [GEO: Generative Engine Optimization](https://arxiv.org/abs/2311.09735)。需求分析参考过一份用户提供的 GEO 工作流资料，其再分发授权未知。本仓库没有收录原包的代码、提示词、文档、表格或客户材料；程序、Skill、文档与模拟示例重新编写，不声称原资料属于维护者。

本仓库采用 [MIT](LICENSE)。欢迎提供脱敏复现记录或讨论真实需求。下一步候选方向是采集适配器、第三方引用支持关系和控制组实验，均尚未实现。
