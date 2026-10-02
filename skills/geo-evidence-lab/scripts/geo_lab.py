#!/usr/bin/env python3
"""Local, evidence-first GEO planning and paired observation analysis."""
import argparse
import csv
import hashlib
import html
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

VERSION = '0.2.0'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def required_text(obj, key):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{key}: expected nonempty text')
    return value.strip()


def web_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return parsed.scheme in ('http', 'https') and bool(parsed.hostname) and not parsed.username


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def profile_check(profile):
    if not isinstance(profile, dict):
        raise ValueError('profile: expected an object')
    for key in ('brand', 'audience', 'offering'):
        required_text(profile, key)
    aliases = profile.get('aliases', [])
    if not isinstance(aliases, list) or any(not isinstance(a, str) or not a.strip() for a in aliases):
        raise ValueError('aliases: expected nonempty strings')
    domains = profile.get('owned_domains', [])
    if not isinstance(domains, list) or any(not isinstance(d, str) or not d or '/' in d or ':' in d or ' ' in d for d in domains):
        raise ValueError('owned_domains: use hostnames without protocol or paths')
    claims = profile.get('claims', [])
    if not isinstance(claims, list):
        raise ValueError('claims: expected a list')
    for claim in claims:
        required_text(claim, 'text')
        if not web_url(claim.get('source_url')):
            raise ValueError('claim source_url: expected HTTP(S) URL; supplied links are not automatically verified')


def experiment_hash(profile):
    return fingerprint({k: profile.get(k, []) for k in ('brand', 'aliases', 'owned_domains', 'queries')})


def frozen_check(profile, frozen):
    if frozen.get('schema_version') not in (1, 2):
        raise ValueError('unsupported plan schema_version')
    expected = fingerprint(profile) if frozen.get('schema_version') == 1 else experiment_hash(profile)
    if frozen.get('profile_hash') != expected:
        raise ValueError('experiment changed after plan freeze; regenerate plan and recollect baseline')
    if frozen.get('queries') != plan(profile)['queries']:
        raise ValueError('queries differ from frozen profile; plan may have been edited')


def plan(profile):
    profile_check(profile)
    queries = profile.get('queries', [])
    if not isinstance(queries, list) or not queries or any(not isinstance(q, str) or not q.strip() for q in queries):
        raise ValueError('queries: supply real customer questions as nonempty strings')
    queries = list(dict.fromkeys(q.strip() for q in queries))
    return {'schema_version': 2, 'profile_hash': experiment_hash(profile),
            'queries': [{'id': f'q{i:03d}', 'text': q} for i, q in enumerate(queries, 1)],
            'collection_instructions': 'Freeze this set before baseline collection. Record engine, mode, context, round and timestamp. Failed requests are unavailable, not negative observations.',
            'source_status': 'User-supplied claim URLs are unverified.'}


def validate_observations(records, frozen):
    if not isinstance(records, list):
        raise ValueError('observations: expected a JSON list')
    known = {q['id']: q['text'] for q in frozen['queries']}
    seen = set()
    for row in records:
        if not isinstance(row, dict):
            raise ValueError('each observation must be an object')
        for key in ('query_id', 'query', 'engine', 'mode', 'context', 'round', 'captured_at', 'status'):
            required_text(row, key)
        if row['query_id'] not in known or row['query'] != known[row['query_id']]:
            raise ValueError('query differs from frozen plan')
        stamp = datetime.fromisoformat(row['captured_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('captured_at: timezone is required')
        key = pair_key(row)
        if key in seen:
            raise ValueError(f'duplicate observation key: {key}')
        seen.add(key)
        if row['status'] not in ('ok', 'unavailable'):
            raise ValueError('status: expected ok or unavailable')
        if row['status'] == 'ok':
            required_text(row, 'answer')
        if not isinstance(row.get('citations', []), list) or any(not web_url(u) for u in row.get('citations', [])):
            raise ValueError('citations: expected a list of HTTP(S) URLs')
        review = row.get('recommendation', 'unreviewed')
        if review not in ('recommended', 'not_recommended', 'neutral', 'unreviewed'):
            raise ValueError('recommendation: invalid review label')
        if review != 'unreviewed':
            required_text(row, 'review_note')
            if row['status'] != 'ok':
                raise ValueError('unavailable observations cannot have a recommendation review')
    return records


def pair_key(row):
    return tuple(row[k] for k in ('query_id', 'engine', 'mode', 'context', 'round'))


def mention(answer, alias):
    # Latin aliases must be separate tokens: Acme must not match Acmeology.
    if re.fullmatch(r'[\x00-\x7f]+', alias):
        return bool(re.search(r'(?<![\w])' + re.escape(alias) + r'(?![\w])', answer, re.I))
    return alias.casefold() in answer.casefold()


def measure(row, profile):
    aliases = [profile['brand']] + profile.get('aliases', [])
    domains = [d.lower().rstrip('.') for d in profile.get('owned_domains', [])]
    urls = row.get('citations', [])
    owned = [u for u in urls if any((urlsplit(u).hostname or '').lower().rstrip('.') == d or
             (urlsplit(u).hostname or '').lower().rstrip('.').endswith('.' + d) for d in domains)]
    return {'mentioned': any(mention(row['answer'], a) for a in aliases),
            'owned_source_cited': bool(owned), 'owned_citations': owned,
            'answer_hash': hashlib.sha256(row['answer'].encode()).hexdigest()}


def compare(profile, frozen, before, after):
    profile_check(profile)
    frozen_check(profile, frozen)
    before = validate_observations(before, frozen)
    after = validate_observations(after, frozen)
    left, right = ({pair_key(r): r for r in rows} for rows in (before, after))
    paired, excluded = [], []
    for key in sorted(left.keys() | right.keys()):
        a, b = left.get(key), right.get(key)
        if not a or not b or a['status'] != 'ok' or b['status'] != 'ok':
            excluded.append({'key': list(key), 'reason': 'missing_or_unavailable'})
            continue
        if datetime.fromisoformat(b['captured_at'].replace('Z', '+00:00')) <= datetime.fromisoformat(a['captured_at'].replace('Z', '+00:00')):
            raise ValueError('post observation must be later than pre observation')
        paired.append({'key': list(key), 'query': a['query'], 'pre': measure(a, profile),
                       'post': measure(b, profile), 'pre_record': a, 'post_record': b})
    n = len(paired)
    metrics = {}
    for metric in ('mentioned', 'owned_source_cited'):
        pre = sum(r['pre'][metric] for r in paired)
        post = sum(r['post'][metric] for r in paired)
        metrics[metric] = {'pre_count': pre, 'post_count': post, 'denominator': n,
                           'pre_rate': pre / n if n else None, 'post_rate': post / n if n else None,
                           'delta_pp': (post - pre) * 100 / n if n else None}
    groups = []
    for group in sorted({tuple(r['key'][1:4]) for r in paired}):
        samples = [r for r in paired if tuple(r['key'][1:4]) == group]
        groups.append({'engine': group[0], 'mode': group[1], 'context': group[2],
                       'metrics': paired_metrics(samples)})
    reviewed = [r for r in paired if all(r[t + '_record'].get('recommendation', 'unreviewed') != 'unreviewed' for t in ('pre', 'post'))]
    metrics['recommended'] = count_change(
        sum(r['pre_record']['recommendation'] == 'recommended' for r in reviewed),
        sum(r['post_record']['recommendation'] == 'recommended' for r in reviewed), len(reviewed))
    observed = {r['key'][0] for r in paired}
    missing = [q['id'] for q in frozen['queries'] if q['id'] not in observed]
    return {'version': VERSION, 'brand': profile['brand'], 'data_kind': profile.get('data_kind', 'user_supplied_unverified'),
            'status': 'descriptive_comparison' if n else 'not_comparable',
            'metrics': metrics, 'groups': groups, 'paired_samples': paired, 'excluded_samples': excluded,
            'missing_queries': missing, 'inputs_hash': fingerprint([profile, frozen, before, after]),
            'limitations': ['前后变化不证明内容发布造成变化；模型更新、个性化、索引延迟和抽样波动均可能影响结果。',
                           '品牌提及不代表推荐；自有域名引用不代表引用内容支持品牌结论。第三方品牌引用需人工标注。',
                           '多个轮次可能相关；这里的分母是观测对数，不是独立用户数。',
                           '仅分析用户导入的记录；未访问引擎或核验引用网页。',
                           '人工推荐判断只统计前后都已标注的配对记录；未标注不等于没有推荐。',
                           '总体指标受引擎和问题的样本构成影响，应同时检查分组结果。']}


def count_change(pre, post, n):
    return {'pre_count': pre, 'post_count': post, 'denominator': n,
            'pre_rate': pre / n if n else None, 'post_rate': post / n if n else None,
            'delta_pp': (post - pre) * 100 / n if n else None}


def paired_metrics(samples):
    return {key: count_change(sum(r['pre'][key] for r in samples),
                             sum(r['post'][key] for r in samples), len(samples))
            for key in ('mentioned', 'owned_source_cited')}


def baseline(profile, frozen, records):
    profile_check(profile)
    frozen_check(profile, frozen)
    records = validate_observations(records, frozen)
    valid = [r for r in records if r['status'] == 'ok']
    samples = [{'key': list(pair_key(r)), 'query': r['query'], 'record': r,
                'measurement': measure(r, profile)} for r in valid]
    n = len(samples)
    metrics = {k: {'count': sum(r['measurement'][k] for r in samples), 'denominator': n,
                   'rate': sum(r['measurement'][k] for r in samples) / n if n else None}
               for k in ('mentioned', 'owned_source_cited')}
    return {'version': VERSION, 'brand': profile['brand'], 'data_kind': profile.get('data_kind', 'user_supplied_unverified'),
            'status': 'baseline_only' if n else 'no_valid_observations', 'metrics': metrics,
            'samples': samples, 'excluded_samples': [{'key': list(pair_key(r)), 'reason': 'unavailable'} for r in records if r['status'] != 'ok'],
            'missing_queries': [q['id'] for q in frozen['queries'] if q['id'] not in {r['query_id'] for r in valid}],
            'inputs_hash': fingerprint([profile, frozen, records]),
            'limitations': ['仅为发布前现状，不代表效果变化。品牌提及不等于推荐，自有引用不证明支持品牌结论。',
                            '样本来自导入记录，未访问引擎或核验网页；多个轮次可能相关。']}


def render(report):
    esc = lambda x: html.escape(str(x))
    is_baseline = 'samples' in report
    cards = []
    labels = [('mentioned', '品牌提及'), ('owned_source_cited', '自有来源引用')]
    if not is_baseline:
        labels.append(('recommended', '人工确认推荐'))
    for key, label in labels:
        m = report['metrics'][key]
        if not m['denominator']:
            rates = '无有效数据' if is_baseline else '不可比较 / 未完成标注'
        elif is_baseline:
            rates = f"{m['rate']:.1%}（{m['count']}/{m['denominator']}）"
        else:
            rates = f"{m['pre_rate']:.1%} → {m['post_rate']:.1%}（{m['delta_pp']:+.1f} 个百分点）"
        cards.append(f'<section><h2>{label}</h2><strong>{rates}</strong><p>有效观测{"对" if not is_baseline else ""}：{m["denominator"]}</p></section>')
    rows = []
    for r in report.get('samples', report.get('paired_samples', [])):
        evidence = ''
        stages = [('baseline', r['record'])] if is_baseline else [(t, r[t + '_record']) for t in ('pre', 'post')]
        for stage, raw in stages:
            links = ' '.join(f'<a href="{esc(u)}" rel="noreferrer">{esc(u)}</a>' for u in raw.get('citations', []))
            evidence += f'<h4>{stage} · {esc(raw["captured_at"])}</h4><pre>{esc(raw["answer"])}</pre><p>{links}</p><p>人工判断：{esc(raw.get("recommendation", "unreviewed"))} · {esc(raw.get("review_note", "未标注"))}</p>'
        rows.append(f'<article><h3>{esc(r["query"])}</h3><p>{esc(" / ".join(r["key"]))}</p><details><summary>查看原始回答与来源</summary>{evidence}</details></article>')
    group_rows = []
    for g in report.get('groups', []):
        rates = [f"{g['metrics'][k]['pre_rate']:.1%} → {g['metrics'][k]['post_rate']:.1%}" for k in ('mentioned', 'owned_source_cited')]
        group_rows.append(f'<tr><td>{esc(g["engine"])}</td><td>{esc(g["mode"])}</td><td>{esc(g["context"])}</td><td>{g["metrics"]["mentioned"]["denominator"]}</td><td>{rates[0]}</td><td>{rates[1]}</td></tr>')
    groups = '<h2>按采集条件拆分</h2><div class="table"><table><tr><th>引擎</th><th>模式</th><th>上下文</th><th>观测对</th><th>提及</th><th>自有引用</th></tr>' + ''.join(group_rows) + '</table></div>' if group_rows else ''
    excluded = ''.join(f'<li>{esc(" / ".join(r["key"]))}：{esc(r["reason"])}</li>' for r in report['excluded_samples'])
    limits = ''.join(f'<li>{esc(s)}</li>' for s in report['limitations'])
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GEO Evidence Lab</title>
<style>body{{margin:0;background:#f3f5f7;color:#172c37;font:16px/1.7 system-ui}}main{{max-width:1100px;margin:auto;padding:40px 20px}}header{{border-top:5px solid #008576}}h1{{font-size:38px;line-height:1.2}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}section,article{{background:white;padding:24px;border-radius:12px;margin:16px 0}}strong{{font-size:23px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f7;padding:16px}}a{{color:#00776b;overflow-wrap:anywhere}}summary{{cursor:pointer}}.tag{{color:#995311}}footer{{font-size:13px;overflow-wrap:anywhere}}.table{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #dde4e8}}</style>
<main><header><p>YIHENG GUO / GEO EVIDENCE LAB</p><h1>让 AI 可见性变化有据可查</h1><p>{esc(report['brand'])} · {esc(report['status'])}</p><p class="tag">数据类型：{esc(report['data_kind'])} · 这是描述性诊断，不是效果归因</p></header><div class="cards">{''.join(cards)}</div><p>排除记录：{len(report['excluded_samples'])}；缺少有效问题：{esc(', '.join(report['missing_queries']) or '无')}</p>{groups}<h2>证据记录</h2>{''.join(rows) or '<p>没有有效记录。</p>'}<details><summary>查看排除记录</summary><ul>{excluded or '<li>无</li>'}</ul></details><h2>解读边界</h2><ul>{limits}</ul><footer>输入摘要 SHA256：{esc(report['inputs_hash'])} · v{VERSION} · 本地生成，无远程脚本</footer></main></html>'''


def brief(profile, frozen, query_id=None):
    profile_check(profile)
    claims = '\n'.join(f'- {c["text"]}；待核验来源：{c["source_url"]}' for c in profile.get('claims', [])) or '- 尚无证据，先补资料。'
    selected = [q for q in frozen['queries'] if query_id is None or q['id'] == query_id]
    if not selected:
        raise ValueError('query_id not found in frozen plan')
    questions = '\n'.join(f'- [{q["id"]}] {q["text"]}' for q in selected)
    return f'''# 内容研究任务：{profile['brand']}

目标读者：{profile['audience']}
业务：{profile['offering']}

## 要回答的真实问题
{questions}

## 用户提供的主张（不是已核实事实）
{claims}

## 交给写作 Agent 的任务
先核对每条来源能否支持对应主张，记录访问日期、适用范围与证据缺口。
围绕读者决策组织文章；提供选择标准、限制与替代方案，品牌出现须与问题相关。
不虚构测评、排名、体验或第三方背书。保留利益关系披露与可核查来源。
输出主稿和主张—来源对应表。平台改写保持事实不变，查阅当前平台规则；没有官方依据的经验规则只能列为假设。
本文档是写作任务，不是文章；需要模型或人工完成成稿，发布遵循用户授权。
'''


CSV_FIELDS = ['query_id', 'query', 'engine', 'mode', 'context', 'round', 'captured_at',
              'status', 'answer', 'citations', 'recommendation', 'review_note']


def init_project(out, brand):
    target = Path(out)
    if target.exists() and any(target.iterdir()):
        raise ValueError('init target must be empty; existing project will not be overwritten')
    target.mkdir(parents=True, exist_ok=True)
    save(target / 'profile.json', {'brand': brand, 'audience': '', 'offering': '', 'aliases': [],
         'owned_domains': [], 'claims': [], 'queries': [], 'data_kind': 'manual_capture'})
    (target / '.gitignore').write_text('*\n!.gitignore\n', encoding='utf-8')
    (target / 'START-HERE.md').write_text('填写 profile.json 的读者、业务与真实用户问题。先生成 plan，再生成采集 CSV。pending 表示未采集；不要将模板当作真实记录。\n项目默认忽略全部数据，不提交真实客户日志。\n', encoding='utf-8')


def worksheet(frozen, out, engine, mode, context, rounds):
    if rounds < 1 or rounds > 100:
        raise ValueError('rounds: expected 1..100; this is a practical file-size limit, not a statistical recommendation')
    target = Path(out)
    if any((target / f'{stage}.csv').exists() for stage in ('pre', 'post')):
        raise ValueError('worksheet files already exist; use a new output directory')
    target.mkdir(parents=True, exist_ok=True)
    for stage in ('pre', 'post'):
        with (target / f'{stage}.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for q in frozen['queries']:
                for i in range(1, rounds + 1):
                    writer.writerow({'query_id': q['id'], 'query': q['text'], 'engine': engine,
                                     'mode': mode, 'context': context, 'round': str(i),
                                     'status': 'pending', 'recommendation': 'unreviewed'})


def import_csv(path, frozen):
    records, pending = [], 0
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not set(CSV_FIELDS[:10]).issubset(reader.fieldnames or []):
            raise ValueError('CSV header is incomplete; start with worksheet output')
        for row in reader:
            if row.get('status', '').strip() == 'pending':
                if any((row.get(k) or '').strip() for k in ('answer', 'citations', 'captured_at', 'review_note')):
                    raise ValueError('pending row contains results; change status to ok or unavailable')
                pending += 1
                continue
            row = {k: (v or '').strip() for k, v in row.items() if k}
            row['citations'] = [u.strip() for u in row.get('citations', '').splitlines() if u.strip()]
            row['recommendation'] = row.get('recommendation') or 'unreviewed'
            records.append(row)
    validate_observations(records, frozen)
    return records, pending


def write_report(out, report):
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)
    save(target / 'report.json', report)
    (target / 'report.html').write_text(render(report), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=VERSION)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('init'); p.add_argument('--brand', required=True); p.add_argument('--out', required=True)
    p = sub.add_parser('worksheet')
    for name in ('plan', 'out', 'engine', 'mode', 'context'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--rounds', type=int, default=1)
    p = sub.add_parser('import-csv'); p.add_argument('--input', required=True); p.add_argument('--plan', required=True); p.add_argument('--out', required=True)
    p = sub.add_parser('plan'); p.add_argument('--profile', required=True); p.add_argument('--out', required=True)
    p = sub.add_parser('brief'); p.add_argument('--profile', required=True); p.add_argument('--plan', required=True); p.add_argument('--out', required=True); p.add_argument('--query-id')
    p = sub.add_parser('baseline')
    for name in ('profile', 'plan', 'input', 'out'):
        p.add_argument('--' + name, required=True)
    p = sub.add_parser('compare')
    for name in ('profile', 'plan', 'pre', 'post', 'out'):
        p.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'init':
            if not args.brand.strip():
                raise ValueError('brand is required')
            init_project(args.out, args.brand.strip())
        elif args.command == 'worksheet':
            worksheet(load(args.plan), args.out, args.engine, args.mode, args.context, args.rounds)
        elif args.command == 'import-csv':
            records, pending = import_csv(args.input, load(args.plan))
            save(args.out, records)
            print(f'Imported {len(records)} observations; skipped {pending} pending rows (not negative observations).')
        else:
            profile = load(args.profile)
            if args.command == 'plan':
                save(args.out, plan(profile))
            elif args.command == 'brief':
                frozen = load(args.plan)
                frozen_check(profile, frozen)
                output = Path(args.out); output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(brief(profile, frozen, args.query_id), encoding='utf-8')
            elif args.command == 'baseline':
                write_report(args.out, baseline(profile, load(args.plan), load(args.input)))
            else:
                write_report(args.out, compare(profile, load(args.plan), load(args.pre), load(args.post)))
        print(f'Written: {args.out}')
    except (ValueError, KeyError, TypeError, OSError, AttributeError, csv.Error) as exc:
        parser.exit(2, f'Input error: {exc}\n')


if __name__ == '__main__':
    main()
