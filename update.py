#!/usr/bin/env python3
"""World Pulse: public RSS + optional Reddit public JSON, no API keys.
Summaries are extractive headline digests, not fabricated AI reporting.
"""
import datetime as dt, email.utils, html, json, os, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data'/'pulse.json'
NOW=dt.datetime.now(dt.timezone.utc)
HEADERS={'User-Agent':'WorldPulse/2.0 (+public informational dashboard; contact via repository)', 'Accept':'application/rss+xml, application/xml, application/json, text/xml'}
REGIONS={'全球':('WORLD','zh-HK','HK','HK:zh-Hant'),'香港':('HK','zh-HK','HK','HK:zh-Hant'),'美國':('US','en-US','US','US:en'),'英國':('GB','en-GB','GB','GB:en'),'台灣':('TW','zh-TW','TW','TW:zh-Hant'),'中國':('CN','zh-CN','CN','CN:zh-Hans'),'日本':('JP','ja','JP','JP:ja'),'韓國':('KR','ko','KR','KR:ko'),'新加坡':('SG','en-SG','SG','SG:en'),'澳洲':('AU','en-AU','AU','AU:en')}
TOPICS={'科技 AI':'AI technology','財經':'global economy stocks','國際政治':'world politics','娛樂':'entertainment culture'}

def fetch(url, timeout=14):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        return resp.read(1_500_000)

def clean(s):
    s=re.sub(r'<[^>]*>',' ',s or '')
    return re.sub(r'\s+',' ',html.unescape(s)).strip()[:500]

def when(s):
    try:
        v=email.utils.parsedate_to_datetime(s)
        return v.astimezone(dt.timezone.utc).isoformat() if v else None
    except (TypeError,ValueError,OverflowError):return None

def parse_rss(raw, source):
    root=ET.fromstring(raw)
    items=[]
    for x in root.findall('.//item')[:24]:
        def field(k):
            el=x.find(k)
            return (el.text or '').strip() if el is not None else ''
        title=clean(field('title'))
        url=field('link')
        if not title or not url.startswith('http'):continue
        src=x.find('source')
        publisher=clean(src.text) if src is not None and src.text else source
        # RSS descriptions often repeat title or include syndicated markup; do not claim full-article summary.
        desc=clean(field('description'))
        if title.lower() in desc.lower() or len(desc)<50:desc=''
        items.append({'title':title,'url':url,'publisher':publisher,'published':when(field('pubDate')),'excerpt':desc[:220], 'source_type':'rss'})
    return items

def google_news(region, topic=None):
    code,hl,gl,ceid=REGIONS[region]
    base='https://news.google.com/rss/'
    if topic:
        query=urllib.parse.quote(topic+' when:2d')
        base+='search?q='+query+'&'
    else:base+='headlines?'
    return base+urllib.parse.urlencode({'hl':hl,'gl':gl,'ceid':ceid})

def trends_feed(region):
    geo={'香港':'HK','美國':'US','英國':'GB','台灣':'TW','日本':'JP','澳洲':'AU'}.get(region,'US')
    return 'https://trends.google.com/trending/rss?geo='+geo

def parse_trends(raw, region):
    root=ET.fromstring(raw)
    out=[]
    for item in root.findall('.//item')[:12]:
        title=clean(item.findtext('title') or '')
        url=(item.findtext('link') or '').strip()
        if not title:continue
        # Related news items, if present, are verifiable context, not evidence of a specific social-platform ranking.
        news=[]
        for el in item.iter():
            if el.tag.endswith('news_item'):
                values={child.tag.split('}')[-1]:clean(child.text or '') for child in el}
                if values.get('news_item_title'):
                    news.append({'title':values['news_item_title'],'source':values.get('news_item_source',''), 'url':values.get('news_item_url','')})
        if not url.startswith('https://'):
            url='https://trends.google.com/trending?geo='+urllib.parse.quote({'香港':'HK','美國':'US','英國':'GB','台灣':'TW','日本':'JP','澳洲':'AU'}.get(region,'US'))
        out.append({'topic':title,'region':region,'platform':'Google Trends','url':url,'context':news[:3], 'summary':('相關報道：'+'；'.join(n['title'] for n in news[:2])) if news else '此話題出現在 Google Trends；暫未取得足夠內容作可靠摘要。', 'summary_type':'related_headlines' if news else 'unavailable'})
    return out

def reddit():
    # Reddit may deny automated access; optional source only.
    url='https://www.reddit.com/r/worldnews/hot.json?limit=12&raw_json=1'
    raw=fetch(url)
    entries=json.loads(raw).get('data',{}).get('children',[])
    out=[]
    for row in entries:
        d=row.get('data',{})
        if d.get('stickied') or d.get('over_18'):continue
        title=clean(d.get('title',''))
        path=d.get('permalink','')
        if title and path.startswith('/r/'):
            out.append({'topic':title,'region':'全球','platform':'Reddit r/worldnews','url':'https://www.reddit.com'+path,'context':[],'summary':'Reddit 熱門討論帖標題；未取得留言內容，不能可靠概括網民意見。','summary_type':'headline_only'})
    return out[:8]

def main():
    report={'generated_at':NOW.isoformat(),'method':'公開 RSS 標題與相關報道整理；非生成式 AI 摘要，未讀取新聞全文。','regions':{},'topics':{},'trends':[],'errors':[]}
    count=0
    for region in REGIONS:
        try:
            items=parse_rss(fetch(google_news(region)), 'Google News RSS')
            report['regions'][region]=items[:12]
            count+=len(items)
            print(region,len(items))
        except Exception as e:
            report['regions'][region]=[]
            report['errors'].append(f'{region} 新聞暫不可用：{type(e).__name__}')
        time.sleep(.12)
    for topic,q in TOPICS.items():
        try:report['topics'][topic]=parse_rss(fetch(google_news('香港',q)),'Google News RSS')[:10]
        except Exception as e:
            report['topics'][topic]=[]
            report['errors'].append(f'{topic} 專題暫不可用：{type(e).__name__}')
    for region in ['香港','台灣','美國','英國','日本']:
        try:report['trends']+=parse_trends(fetch(trends_feed(region)),region)
        except Exception as e:report['errors'].append(f'{region} Google Trends 暫不可用：{type(e).__name__}')
    try:report['trends']+=reddit()
    except Exception as e:report['errors'].append(f'Reddit 暫不可用：{type(e).__name__}')
    # Only publish fresh content, never silently preserve stale records as current.
    report['status']='ok' if count else 'unavailable'
    OUT.parent.mkdir(exist_ok=True)
    tmp=OUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(OUT)
    print('News items:',count,'trends:',len(report['trends']),'errors:',report['errors'])

if __name__=='__main__':main()
