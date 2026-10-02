# 输入与指标

`profile.json`：brand、audience、offering 为非空文本；queries 为非空问题数组；aliases 为品牌别名数组；owned_domains 为自有域名数组（不带协议和路径）；claims 为含 text 与 source_url 的数组。URL 有效仅指格式，不表示网页已访问或主张已核实。data_kind 可写 synthetic_demo、manual_capture 或其他真实来源描述，标签由导入者提供。

v2 plan 命令冻结品牌、别名、自有域名与问题的摘要，问题去重并赋 ID。修改这些字段需要新计划和基线；补充 claims、audience 或 offering 不影响检测标准。v1 计划仍按完整档案摘要校验；程序同时检查问题集是否被篡改。

`pre.json` 和 `post.json` 都是观测数组，每条包含：

```json
{
  "query_id": "q001",
  "query": "如何选协作工具？",
  "engine": "doubao",
  "mode": "web-search",
  "context": "fresh-session;zh-CN;logged-in;Shanghai",
  "round": "1",
  "captured_at": "2026-10-02T10:00:00+08:00",
  "status": "ok",
  "answer": "复制的完整回答",
  "citations": ["https://example.org/page"]
}
```

status 为 unavailable 时可省略 answer。citations 只填实际展示的引用链接，不把普通回答文本中的 URL 自动视作引用。同一阶段 query_id、engine、mode、context、round 的组合唯一；后测时间必须晚于对应前测。

品牌提及：品牌或别名的文本匹配；ASCII 名称按词边界匹配，中文按子串匹配。无法排除同名、否定提及、引用文本或别名歧义，请人工复核。

自有来源引用：实际展示的引用 URL 的主机名与 owned_domains 相同，或是其子域名。example.org.evil.test 不命中 example.org。不分析网页内容或跳转后的域名。

分母：前后均有有效回答且条件匹配的观测对。百分比变化按百分点报告。无有效配对时比率为 null，状态为 not_comparable；不存在“跳过也通过”。缺少问题覆盖与被排除的记录单独展示。

report.json 保留原始记录和 SHA256 摘要，可追踪输入版本，但摘要不证明真实性。report.html 是本地静态报告，无外部脚本，打开引用链接会访问相应网站。禁止在公共仓库提交真实客户日志、私人回答或登录资料。

## 采集表与人工标注

worksheet 生成 UTF-8 BOM CSV，方便表格编辑器识别中文。citations 在同一单元格内一行一个 URL；import-csv 转成 JSON 数组。status=pending 的空白模板行跳过，不计入阴性结果；带时间、回答、来源或标注依据的 pending 行会报错。已尝试的 unavailable 需填实际时间。

JSON 可选 recommendation 为 recommended、not_recommended、neutral、unreviewed。前三种必须有非空 review_note，记录人工阅读原始回答的依据；unavailable 不接受推荐标注。compare 的人工推荐分母仅包含前后都已标注且有效的配对。这个标注由导入者提供，程序不判断语义或真实性。

baseline 接受单阶段记录，返回有效观测计数、提及率、自有引用率、覆盖缺口及原始回答，不计算提升。compare 同时返回按 engine、mode、context 分组的前后指标；groups 中不包含没有有效配对的组，其记录仍在 excluded_samples 中可查。

init 不覆盖非空目录；worksheet 不覆盖既有前后采集表。发布记录模板只供人工留档，不参与自动归因或收录核验。
