#!/usr/bin/env python3
"""WORLD PULSE: free Traditional-Chinese-first news, source-grounded summaries.
No paid APIs. Does not fabricate missing article text or promise translation.
"""
import datetime as dt
import email.utils
import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data' / 'pulse.json'
NOW = dt.datetime.now(dt.timezone.utc)
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; WorldPulse/3.0; public RSS reader)', 'Accept': 'application/rss+xml, application/xml, application/json, text/xml'}
REGIONS = {
    '全球': '國際 世界', '香港': '香港', '美國': '美國', '英國': '英國',
    '台灣': '台灣', '中國': '中國', '日本': '日本', '韓國': '韓國',
    '新加坡': '新加坡', '澳洲': '澳洲',
}
TOPICS = {'科技 AI': '人工智能 科技', '財經': '經濟 股市', '國際政治': '國際 政治', '娛樂': '娛樂 文化'}
SPORTS = re.compile(
    r'體育|運動賽事|足球|籃球|棒球|網球|羽毛球|乒乓球|高爾夫|賽馬|奧運|世界盃|世界杯|歐聯|英超|西甲|德甲|意甲|法甲|NBA|NFL|MLB|NHL|FIFA|UEFA|Premier League|Champions League|World Cup|Olympics|Grand Slam|Formula 1|F1|sports? scores?|playoffs?|touchdown|quarterback|goalkeeper',
    re.I,
)
SPORTS_EXTRA = re.compile(r'(?i)\b(?:soccer|football|basketball|baseball|tennis|cricket|rugby|badminton|athletics|wimbledon|super bowl|match highlights|live score|ufc|boxing|f1|formula one|motogp)\b|サッカー|野球|バスケ|テニス|スポーツ|축구|야구|농구|스포츠|運動員|球隊|賽事|聯賽|決賽|冠軍賽')
def is_sports(text):
    return bool(SPORTS.search(text or '') or SPORTS_EXTRA.search(text or ''))


def fetch(url, timeout=18):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(1_500_000)

def clean(value):
    value = re.sub(r'<[^>]*>', ' ', value or '')
    return re.sub(r'\s+', ' ', html.unescape(value)).strip()[:1200]

def when(value):
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed.astimezone(dt.timezone.utc).isoformat() if parsed else None
    except (TypeError, ValueError, OverflowError):
        return None

def chinese_count(value):
    return len(re.findall(r'[\u3400-\u9fff]', value))

TRANSLATION_LIMIT = 45
_translation_calls = 0

def to_zh(text):
    """Best-effort free public endpoint. May be blocked/rate limited; keep original then."""
    global _translation_calls
    text = clean(text)
    if not text or chinese_count(text) >= 5 or _translation_calls >= TRANSLATION_LIMIT:
        return text, False
    if not re.search(r'[A-Za-z\u3040-\u30ff\uac00-\ud7af]', text):
        return text, False
    _translation_calls += 1
    try:
        params = urllib.parse.urlencode({'client':'gtx','sl':'auto','tl':'zh-TW','dt':'t','q':text})
        data = json.loads(fetch('https://translate.googleapis.com/translate_a/single?' + params, timeout=7))
        translated = clean(''.join(row[0] for row in data[0] if row and row[0]))
        if translated and translated.casefold() != text.casefold():
            return translated, True
    except Exception:
        pass
    return text, False

def summary_from_description(title, description):
    """Only use source-provided RSS description; never pad with invented claims."""
    description = clean(description)
    description = re.sub(r'\s*(?:閱讀更多|Read more|Continue reading)\s*$', '', description, flags=re.I)
    if not description or description.casefold() == title.casefold():
        return '', 'insufficient_source'
    if description.startswith(title):
        description = description[len(title):].lstrip(' ：:—-')
    if chinese_count(description) < 45:
        return '', 'insufficient_source'
    result = description[:100].rstrip('，、；：,;: ')
    if chinese_count(result) < 45:
        return '', 'insufficient_source'
    return result, 'rss_description'

def parse_rss(raw, source):
    root = ET.fromstring(raw)
    output = []
    seen = set()
    for item in root.findall('.//item')[:45]:
        title = clean(item.findtext('title') or '')
        url = (item.findtext('link') or '').strip()
        if not title or not url.startswith('http') or is_sports(title):
            continue
        if title.casefold() in seen:
            continue
        seen.add(title.casefold())
        source_el = item.find('source')
        publisher = clean(source_el.text) if source_el is not None and source_el.text else source
        description = clean(item.findtext('description') or '')
        summary, summary_type = summary_from_description(title, description)
        title_zh, title_translated = to_zh(title)
        if summary:
            summary_zh, summary_translated = to_zh(summary)
        else:
            summary_zh, summary_translated = '', False
        output.append({
            'title': title_zh, 'original_title': title if title_translated else '', 'translated': title_translated, 'url': url, 'publisher': publisher,
            'published': when(item.findtext('pubDate') or ''),
            'excerpt': summary_zh or '原始新聞來源未提供足夠內容，暫時無法可靠整理 50–100 字摘要。請查看原文。',
            'summary_type': summary_type, 'summary_translated': summary_translated, 'source_type': 'rss',
        })
    return output

def news_url(query):
    # Google News Chinese-language search, not a guaranteed machine translation.
    q = query + ' when:2d -足球 -籃球 -體育 -NBA -英超 -奧運'
    return 'https://news.google.com/rss/search?' + urllib.parse.urlencode({
        'q': q, 'hl': 'zh-HK', 'gl': 'HK', 'ceid': 'HK:zh-Hant',
    })

def trends_url(region):
    geo = {'香港':'HK','美國':'US','英國':'GB','台灣':'TW','日本':'JP','澳洲':'AU','韓國':'KR'}.get(region,'US')
    return 'https://trends.google.com/trending/rss?geo=' + geo

def traffic_value(raw):
    raw = (raw or '').replace(',', '').strip().upper()
    m = re.search(r'(\d+(?:\.\d+)?)\s*([KMB]?)', raw)
    if not m:
        return 0
    return int(float(m.group(1)) * {'':1,'K':1000,'M':1000000,'B':1000000000}[m.group(2)])

def parse_trends(raw, region):
    root = ET.fromstring(raw)
    output, seen = [], set()
    for item in root.findall('.//item'):
        title = clean(item.findtext('title') or '')
        if not title or is_sports(title) or len(title) > 100:
            continue
        key = re.sub(r'\W+', '', title).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        context = []
        traffic = ''
        for el in item.iter():
            tag = el.tag.split('}')[-1]
            if tag == 'approx_traffic':
                traffic = clean(el.text or '')
            if tag == 'news_item':
                data = {c.tag.split('}')[-1]: clean(c.text or '') for c in el}
                headline = data.get('news_item_title', '')
                if headline and not is_sports(headline):
                    context.append({'title': headline, 'source': data.get('news_item_source',''), 'url': data.get('news_item_url','')})
        # Skip sports trends even if ambiguous title is a player/team name but context identifies sports.
        all_context = [clean(c.text or '') for el in item.iter() if el.tag.split('}')[-1]=='news_item' for c in el if c.tag.split('}')[-1]=='news_item_title']
        if all_context and sum(is_sports(t) for t in all_context) >= max(1, len(all_context)//2 + 1):
            continue
        translated, translated_ok = to_zh(title)
        geo = {'香港':'HK','台灣':'TW','日本':'JP','韓國':'KR','美國':'US'}.get(region,'US')
        output.append({'topic': translated, 'original_topic': title if translated_ok else '', 'region':region,
            'platform':'Google Trends','url':'https://trends.google.com/trending?geo='+geo,
            'traffic':traffic,'traffic_value':traffic_value(traffic),'context':context[:2],
            'summary':'相關報道：'+'；'.join(x['title'] for x in context[:2]) if context else 'Google Trends 搜尋量上升；未取得足夠可靠資料解釋原因。',
            'summary_type':'related_headlines' if context else 'unavailable'})
    # RSS is already a trending list; use estimated search volume as a secondary ordering signal.
    output.sort(key=lambda x:x['traffic_value'], reverse=True)
    return output[:10]

def main():
    report = {'generated_at':NOW.isoformat(),
        'method':'繁體中文來源優先；非中文內容嘗試免費翻譯（不保證成功）；只按 RSS 內容提供摘要；體育關鍵字過濾；全球榜為地區選集，非全球精確排名。',
        'regions':{},'topics':{},'trends':[],'errors':[]}
    total = 0
    for region, query in REGIONS.items():
        try:
            articles = parse_rss(fetch(news_url(query)), 'Google News RSS')[:12]
            report['regions'][region] = articles
            total += len(articles)
            print(region, len(articles))
        except Exception as exc:
            report['regions'][region] = []
            report['errors'].append(f'{region} 新聞暫不可用：{type(exc).__name__}')
        time.sleep(.15)
    for topic, query in TOPICS.items():
        try:
            report['topics'][topic] = parse_rss(fetch(news_url(query)), 'Google News RSS')[:10]
        except Exception as exc:
            report['topics'][topic] = []
            report['errors'].append(f'{topic} 專題暫不可用：{type(exc).__name__}')
    for region in ['香港','台灣','日本','韓國','美國']:
        try:
            report['trends'].extend(parse_trends(fetch(trends_url(region)),region))
        except Exception as exc:
            report['errors'].append(f'{region} Google Trends 暫不可用：{type(exc).__name__}')
    # Global is a cross-region selection, NOT a measured worldwide ranking.
    by_region = {r:[t for t in report['trends'] if t['region']==r] for r in ['香港','台灣','日本','韓國','美國']}
    global_items, global_seen = [], set()
    for i in range(10):
        for r in by_region:
            if i < len(by_region[r]):
                item = by_region[r][i]
                key = re.sub(r'\W+', '', item['topic']).casefold()
                if key not in global_seen:
                    global_seen.add(key)
                    global_items.append(dict(item, region='全球', origin_region=r))
    report['trends'].extend(global_items[:10])
    report['status'] = 'ok' if total else 'unavailable'
    OUT.parent.mkdir(parents=True,exist_ok=True)
    temp = OUT.with_suffix('.tmp')
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(OUT)
    print('News items:',total,'trends:',len(report['trends']),'errors:',report['errors'])

if __name__ == '__main__':
    main()
