# 从零完成一次内容实验

这份指南用于真实项目。`examples/` 是模拟演示，不能用其中的回答当作你品牌的检测结果。

## 1. 新建项目并填写资料

在仓库根目录运行：

```bash
python3 skills/geo-evidence-lab/scripts/geo_lab.py init --brand '你的品牌' --out private/my-brand
```

打开 `private/my-brand/profile.json`：

- audience：目标读者是谁，例如“正在选择协作软件的小型企业负责人”。
- offering：你提供什么产品或服务。
- queries：从客户咨询、搜索问题、访谈中收集的实际问题数组。品牌词与不带品牌的决策问题分开解读；不能只挑有利问题。
- aliases：确实指向该品牌的别名；同名或过短别名可能造成误判。
- owned_domains：你控制的网站域名，不带 https:// 或路径。没有自有网站就留空，此时该指标没有业务解释价值。
- claims：含 text 和 source_url 的主张数组。公开链接只是待核验线索，不等于已经证实。
- data_kind：人工真实采集保留 manual_capture；模拟数据设为 synthetic_demo。

init 不凭空补齐资料；audience、offering 和 queries 留空时 plan 会报错。项目默认忽略数据，不提交真实客户日志。

## 2. 冻结问题与准备采集表

```bash
python3 skills/geo-evidence-lab/scripts/geo_lab.py plan --profile private/my-brand/profile.json --out private/my-brand/plan.json
python3 skills/geo-evidence-lab/scripts/geo_lab.py worksheet --plan private/my-brand/plan.json --engine doubao --mode web-search --context 'fresh-session;zh-CN;logged-in;Shanghai' --rounds 3 --out private/my-brand/capture-doubao
```

引擎、模式和上下文要填写你的真实条件。这里的 3 轮只是演示，不是经过计算的统计样本量。多引擎分别生成采集目录，导入后的 JSON 数组可合并；不要把多个引擎的记录覆盖到同一个文件。

`pre.csv` 和 `post.csv` 可用 Excel 或其他 CSV 编辑器打开。脚本不查询豆包，也不处理登录、验证码或发布。

## 3. 采集基线

按 pre.csv 的问题逐条搜索，避免沿用携带前题信息的会话。保留完整回答、实际展示的引用与真实采集时间。

| 列 | 怎么填 |
| --- | --- |
| query_id / query | 保留计划原文与 ID |
| engine / mode / context / round | 保留预先约定的条件；条件变化如实记录 |
| captured_at | 带时区，如 2026-10-02T14:00:00+08:00 |
| status | pending：未采集；ok：有有效回答；unavailable：尝试后失败 |
| answer | 原始回答，不要改写成对品牌有利的版本 |
| citations | 引擎实际展示的 HTTP(S) 来源 URL；同一单元格内每行一条，无引用留空 |
| recommendation | recommended / not_recommended / neutral / unreviewed |
| review_note | 完成人工标注时，填具体原文依据；未标注留空 |

unavailable 也要填实际尝试时间，不能标注推荐。pending 含回答或时间时导入会报错，避免误丢结果。保存为 UTF-8 CSV；多行回答和 URL 在同一单元格，不拆成新记录。

```bash
python3 skills/geo-evidence-lab/scripts/geo_lab.py import-csv --input private/my-brand/capture-doubao/pre.csv --plan private/my-brand/plan.json --out private/my-brand/pre.json
python3 skills/geo-evidence-lab/scripts/geo_lab.py baseline --profile private/my-brand/profile.json --plan private/my-brand/plan.json --input private/my-brand/pre.json --out private/my-brand/baseline
```

打开 baseline/report.html 看现状。pending 被跳过，命令会告知数量；报告检查问题覆盖，但不知道你遗漏了多少完整计划轮次，需要同时检查 CSV。

## 4. 做内容任务、写稿和发布

```bash
python3 skills/geo-evidence-lab/scripts/geo_lab.py brief --profile private/my-brand/profile.json --plan private/my-brand/plan.json --query-id q001 --out private/my-brand/article-q001-brief.md
```

把 brief 交给 Agent 或作者。完整要求见 [内容生产流程](../skills/geo-evidence-lab/references/content-workflow.md)：核验来源 → 整理证据缺口 → 写文章 → 输出主张—来源对应表 → 适配目标平台 → 按授权发布。

发布后使用 [发布记录模板](../skills/geo-evidence-lab/assets/publication-log.template.csv) 记录 URL、时间和改动。这些记录用于人工解释实验，不由 compare 自动验证。补充证据和调整文章可以修改 claims、audience、offering，不会改变 v2 计划的检测标准；更换品牌、别名、自有域名或问题需要新计划和新基线。

## 5. 后测与复盘

先约定一个与检索延迟相适应的后测窗口；没有统一适用于所有引擎的天数保证。填写 post.csv，保持问题和条件匹配，后测时间晚于前测。

```bash
python3 skills/geo-evidence-lab/scripts/geo_lab.py import-csv --input private/my-brand/capture-doubao/post.csv --plan private/my-brand/plan.json --out private/my-brand/post.json
python3 skills/geo-evidence-lab/scripts/geo_lab.py compare --profile private/my-brand/profile.json --plan private/my-brand/plan.json --pre private/my-brand/pre.json --post private/my-brand/post.json --out private/my-brand/comparison
```

打开 comparison/report.html。先检查配对数和缺口，再看分组变化，再展开原始回答。核查提及是否在否定语境、引用是否真正支持结论，以及推荐标注依据是否一致。结果可支持下一轮内容判断，不能单独证明带来客户或收入。

## 常见错误

- `experiment changed`：检测字段改了。保留旧实验，另开新计划；不要修改摘要绕过检查。
- `query differs`：CSV 改了问题或 ID。恢复原题；新题要新基线。
- `duplicate observation key`：同一轮记录重复。确认真正的重复还是新轮次；不要直接删掉不利结果。
- `post ... later`：前后时间相同或倒置。核对真实采集时间，不伪造时间通过校验。
- `review_note`：人工推荐判断缺少依据。补原文依据或改回 unreviewed。
- 无有效配对：检查是否填完、是否都是 unavailable、是否引擎或上下文不一致。
