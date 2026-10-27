"""Build the New Dawn blog with Python 3.10+; no third-party dependencies."""
import argparse
import datetime as dt
import html
import hashlib
import json
import math
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'docs'
MAIN = 'https://www.newdawn-horticultural.com/'
CATEGORIES = {'activity': '活動報告', 'research': '研究', 'column': 'コラム'}
args_parser = argparse.ArgumentParser()
args_parser.add_argument('--site-url', default='')
args_parser.add_argument('--preview', action='store_true')
args = args_parser.parse_args()
SITE = args.site_url.rstrip('/')
GA_MEASUREMENT_ID = 'G-XHW2ZMRL8H'
H = html.escape
STYLE_FILE = 'style-' + hashlib.sha256((ROOT/'assets/style.css').read_bytes()).hexdigest()[:12] + '.css'
PHOTO_METADATA = {p['file']: p for p in json.loads((ROOT/'photo-migration.json').read_text())} if (ROOT/'photo-migration.json').exists() else {}

def inline(text):
    value = H(text)
    def image(match):
        source = html.unescape(match[2])
        meta = PHOTO_METADATA.get(source, {})
        dimensions = f' width="{meta["width"]}" height="{meta["height"]}"' if meta else ''
        if source.startswith('assets/'):
            source = '../../' + source
        return f'<img src="{H(source, quote=True)}" alt="{match[1]}"{dimensions} loading="lazy" decoding="async">'
    value = re.sub(r'!\[([^\]]*)\]\((https?://[^\s)]+|assets/[^\s)]+)\)', image, value)
    value = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', lambda m: f'<a href="{H(html.unescape(m[2]), quote=True)}">{m[1]}</a>', value)
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', value)

def markdown(text):
    """Render the supported article format: headings, lists, paragraphs and links."""
    out, paragraph, listing = [], [], None
    def flush():
        if paragraph:
            if len(paragraph)==1 and re.fullmatch(r'!\[[^\]]*\]\((?:https?://[^\s)]+|assets/[^\s)]+)\)',paragraph[0]):
                out.append('<figure class="article-photo">' + inline(paragraph[0]) + '</figure>')
            else:
                out.append('<p>' + '<br>'.join(inline(s) for s in paragraph) + '</p>')
            paragraph.clear()
    def close_list():
        nonlocal listing
        if listing:
            out.append(f'</{listing}>')
            listing = None
    for line in text.splitlines():
        line = line.strip()
        heading = re.match(r'^(#{1,6})\s+(.+)$', line)
        bullet = re.match(r'^(?:[-*•]\s+|\d+\.\s+)(.+)$', line)
        if heading:
            flush(); close_list()
            level = max(2, len(heading[1]))
            out.append(f'<h{level}>{inline(heading[2])}</h{level}>')
        elif bullet:
            flush()
            kind = 'ol' if re.match(r'^\d+\.', line) else 'ul'
            if listing != kind:
                close_list(); listing = kind
                start = int(re.match(r'^(\d+)\.', line)[1]) if kind == 'ol' else None
                out.append(f'<ol start="{start}">' if kind == 'ol' else '<ul>')
            out.append(f'<li>{inline(bullet[1])}</li>')
        elif not line:
            flush()
            # Adjacent list blocks stay open even when authors use blank lines.
        else:
            close_list(); paragraph.append(line)
    flush(); close_list()
    return '\n'.join(out)

posts = []
for path in sorted((ROOT / 'posts').glob('*.md')):
    raw = path.read_text()
    front, body = raw.removeprefix('---\n').split('\n---\n', 1)
    post = json.loads(front)
    assert post['category'] in CATEGORIES
    dt.date.fromisoformat(post['date'])
    assert re.fullmatch(r'[a-z0-9-]+', post['slug'])
    post['body'] = body.strip()
    post['minutes'] = max(1, math.ceil(len(body) / 450))
    posts.append(post)
posts.sort(key=lambda p: p['date'], reverse=True)
assert len({p['slug'] for p in posts}) == len(posts)
OUT.mkdir(exist_ok=True)
for old in OUT.iterdir():
    if old.is_dir(): shutil.rmtree(old)
    else: old.unlink()
(OUT / 'assets').mkdir()
for path in (ROOT / 'assets').iterdir():
    if path.is_dir(): shutil.copytree(path, OUT / 'assets' / path.name)
    else: shutil.copy2(path, OUT / 'assets' / path.name)
shutil.copyfile(ROOT/'assets/style.css', OUT/'assets'/STYLE_FILE)

def date_label(value):
    d = dt.date.fromisoformat(value)
    return f'{d.year}年{d.month}月{d.day}日'

def route(prefix, path):
    return prefix + '/' + path if path else prefix + '/'

def document(title, description, content, prefix='.', path='', active='all', article=None):
    nav = ''.join(f'<a href="{route(prefix, "categories/" + key + "/")}"'+ (' aria-current="page"' if active == key else '')+f'>{label}</a>' for key, label in CATEGORIES.items())
    canonical = SITE + '/' + path if SITE else ''
    meta = ''
    if canonical:
        meta += f'<link rel="canonical" href="{H(canonical, quote=True)}"><meta property="og:url" content="{H(canonical, quote=True)}">'
    if args.preview:
        meta += '<meta name="robots" content="noindex,nofollow">'
    structured = ''
    if article and canonical:
        schema = {'@context': 'https://schema.org', '@type': 'BlogPosting', 'headline': article['title'], 'description': article['description'], 'datePublished': article['date'], 'mainEntityOfPage': canonical, 'publisher': {'@type':'Organization','name':'New Dawn','url':MAIN}}
        if article['author']: schema['author'] = {'@type':'Person','name':article['author']}
        if article.get('cover_image'):
            schema['image'] = SITE + '/' + article['cover_image']
        structured = '<script type="application/ld+json">'+json.dumps(schema,ensure_ascii=False).replace('<','\\u003c')+'</script>'
    social_image = (article or posts[0]).get('cover_image')
    if social_image and SITE:
        meta += '<meta property="og:image" content="'+H(SITE+'/'+social_image,quote=True)+'">'
    preview = '<div class="preview-notice">移行プレビュー <span>既存記事を引き継いだ確認用ブログです</span></div>' if args.preview else ''
    analytics = ''
    if not args.preview and SITE == 'https://newdawn-horticultural.github.io':
        analytics = f'''<!-- Google Analytics: blog audience measurement -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('js', new Date());
gtag('config', '{GA_MEASUREMENT_ID}', {{
  'allow_google_signals': false,
  'allow_ad_personalization_signals': false
}});
</script>'''
    return f'''<!doctype html>
<html lang="ja"><head>{analytics}<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{H(title)}｜New Dawn</title><meta name="description" content="{H(description, quote=True)}">
<meta name="theme-color" content="#005b5b"><meta property="og:type" content="{'article' if article else 'website'}"><meta property="og:title" content="{H(title, quote=True)}｜New Dawn"><meta property="og:description" content="{H(description, quote=True)}"><meta property="og:locale" content="ja_JP"><meta property="og:site_name" content="New Dawn ブログ">
{meta}<link rel="icon" href="{prefix}/assets/brand/favicon.png" type="image/png"><link rel="apple-touch-icon" href="{prefix}/assets/brand/logo.png"><link rel="stylesheet" href="{prefix}/assets/{STYLE_FILE}"><script src="{prefix}/assets/app.js" defer></script>{structured}</head>
<body><a class="skip-link" href="#main">本文へ進む</a>{preview}<header class="site-header"><div class="header-inner">
<a class="brand" href="{route(prefix,'')}" aria-label="New Dawn ブログのトップ"><img src="{prefix}/assets/brand/logo.png" alt="" width="42" height="42"><span>New Dawn<small>園芸療法 × 幸福学</small></span></a>
<nav class="main-nav" aria-label="メインナビゲーション"><a href="{route(prefix,'')}"{(' aria-current="page"' if active == 'all' and not article else '')}>すべての記事</a>{nav}<a class="official" href="{MAIN}">公式サイトへ <span aria-hidden="true">↗</span></a></nav>
</div></header>
<main id="main">{content}</main>
<footer class="site-footer"><div class="footer-inner"><div><a class="footer-brand" href="{route(prefix,'')}"><img src="{prefix}/assets/brand/logo.png" alt="" width="36" height="36">New Dawn</a><p>園芸療法と幸福学をめぐる、実践と研究の記録。</p></div><a href="{MAIN}" class="footer-link">New Dawn 公式サイトへ <span aria-hidden="true">↗</span></a></div><div class="footer-bottom"><span>© New Dawn</span><a href="{prefix}/feed.xml">RSSで購読</a><a href="{route(prefix,'privacy/')}">アクセス解析について</a><a href="#">ページの先頭へ ↑</a></div></footer></body></html>'''

def category_pill(post, prefix):
    return f'<a class="pill {post["category"]}" href="{route(prefix,"categories/" + post["category"] + "/")}">{CATEGORIES[post["category"]]}</a>'

def post_card(post, prefix='.', extra=''):
    url = route(prefix, 'posts/' + post['slug'] + '/')
    theme = {'activity':'plant','research':'research','column':'story'}[post['category']]
    visual = post.get('cover_image', 'assets/' + theme + '.svg')
    photo_class = ' photo' if post.get('cover_image') else ''
    author = H(post['author']) if post['author'] else 'New Dawn'
    label = post.get('topic', '') or ('しめ縄づくり' if post['slug'] == 'shimenawa-workshop' else ('春の寄せ植えとハーブティー' if post['slug'] == 'spring-planting-and-herbal-tea' else ''))
    search = H(post['title']+' '+post['description']+' '+label+' '+CATEGORIES[post['category']],quote=True)
    return f'''<article class="post-card {extra}" data-search="{search}"><a class="card-visual {theme}{photo_class}" href="{url}" tabindex="-1" aria-hidden="true"><img src="{prefix}/{visual}" alt="" width="600" height="360" loading="lazy"></a><div class="card-body"><div class="card-meta">{category_pill(post,prefix)}<time datetime="{post['date']}">{date_label(post['date'])}</time></div><h3><a href="{url}">{H(post['title'])}</a></h3>{f'<p class="card-subtitle">{label}</p>' if label else ''}<p class="card-description">{H(post['description'])}</p><div class="card-bottom"><span>{author} · 約{post['minutes']}分</span><a class="read-link" href="{url}" aria-label="{H(post['title'],quote=True)}を読む">記事を読む <span aria-hidden="true">→</span></a></div></div></article>'''

def index_content(category=None):
    prefix = '.' if category is None else '../..'
    selected = [p for p in posts if category is None or p['category']==category]
    if category is None:
        featured = posts[0]
        featured_title = '春の寄せ植えと<br>ハーブティーの時間' if featured['slug'] == 'spring-planting-and-herbal-tea' else H(featured['title'])
        featured_art = {'activity': 'plant', 'research': 'research', 'column': 'story'}[featured['category']]
        featured_visual = featured.get('cover_image', 'assets/' + featured_art + '.svg')
        featured_photo_class = ' photo' if featured.get('cover_image') else ''
        featured_alt = H(featured.get('cover_alt', '植物と記録を表すイラスト'),quote=True)
        hero = f'''<div class="brand-hero"><section class="hero wrap"><div class="hero-copy"><p class="eyebrow">Horticultural therapy × well-being</p><h1>New Dawn<br><span>活動と研究のブログ</span></h1><p class="hero-description">明日を照らす、新しい評価のかたち。<br>園芸療法の実践と、幸福学をめぐる研究を綴ります。</p><a href="#articles" class="button primary">記事を読む <span aria-hidden="true">↓</span></a></div><a href="./posts/{featured['slug']}/" class="featured"><div class="featured-art{featured_photo_class}"><img src="./{featured_visual}" width="600" height="360" alt="{featured_alt}"></div><div class="featured-copy"><div class="featured-meta"><span>最新の記事</span><time datetime="{featured['date']}">{date_label(featured['date'])}</time></div><h2>{featured_title}</h2><span class="featured-link">記事を読む <span aria-hidden="true">→</span></span></div></a></section></div>'''
        intro = '実践の記録から、研究のこと、私たちの原点まで。'
        title = '記事一覧'
    else:
        texts = {'activity':'植物と関わる時間に生まれた、日々の実践の記録。','research':'園芸療法と幸福学をつなぐ研究や、学会での発表。','column':'私たちの原点や、植物と人をめぐる想い。'}
        title, intro = CATEGORIES[category], texts[category]
        hero = f'<section class="category-hero wrap"><a class="back-link" href="../../">← ブログトップ</a><p class="eyebrow">New Dawn のブログ</p><h1>{title}</h1><p>{intro}</p></section>'
    filters = f'<a href="{route(prefix,"")}#articles" class="filter'+(' selected' if not category else '')+'"'+(' aria-current="page"' if not category else '')+f'>すべて <span>{len(posts)}</span></a>'
    filters += ''.join(f'<a href="{route(prefix,"categories/"+key+"/")}" class="filter'+(' selected' if category==key else '')+'"'+(' aria-current="page"' if category==key else '')+f'>{label} <span>{sum(p["category"]==key for p in posts)}</span></a>' for key,label in CATEGORIES.items())
    cards=''.join(post_card(p,prefix) for p in selected)
    return hero + f'''<section class="article-section wrap" id="articles"><div class="section-heading"><div><p class="eyebrow">実践・研究・コラム</p><h2>{title}</h2><p>{intro}</p></div><form class="search-form" role="search"><label for="article-search" class="sr-only">表示中の記事を検索</label><span aria-hidden="true">⌕</span><input id="article-search" type="search" placeholder="記事を探す" autocomplete="off"><button type="reset" aria-label="検索をクリア">×</button></form></div><div class="article-toolbar"><nav class="filters" aria-label="記事のカテゴリ">{filters}</nav><span class="result-count" role="status" aria-live="polite">{len(selected)}件の記事</span></div><div class="card-grid">{cards}</div><p class="empty-state" hidden>一致する記事がありません。別の言葉で検索してください。</p></section><section class="about-strip wrap"><img class="about-logo" src="{prefix}/assets/brand/logo.png" alt="" width="68" height="68"><div><h2>小さな幸せを、見つめる。</h2><p>New Dawnは、園芸療法と幸福学を軸に、<br class="desktop-break">評価法の研究・普及・教育・実践に取り組んでいます。</p></div><a href="{MAIN}" class="button secondary">New Dawnについて <span aria-hidden="true">↗</span></a></section>'''

(OUT/'index.html').write_text(document('ブログ', 'New Dawnの活動報告、研究、コラム。園芸療法と幸福学をめぐる実践と研究の記録を届けます。', index_content()))
for category, label in CATEGORIES.items():
    directory = OUT/'categories'/category
    directory.mkdir(parents=True)
    (directory/'index.html').write_text(document(label, f'New Dawnの{label}の記事一覧です。', index_content(category),'../..',f'categories/{category}/',category))

for post in posts:
    directory = OUT/'posts'/post['slug']
    directory.mkdir(parents=True)
    body = markdown(post['body'])
    headings = re.findall(r'<h([23])>(.*?)</h\1>', body)
    toc=[]
    for i,(level,label) in enumerate(headings):
        identifier='section-'+str(i+1)
        body=body.replace(f'<h{level}>{label}</h{level}>',f'<h{level} id="{identifier}">{label}</h{level}>',1)
        toc.append(f'<li><a href="#{identifier}">{label}</a></li>')
    toc_html = '<details class="toc" open><summary>この記事の内容</summary><ol>'+''.join(toc)+'</ol></details>' if len(toc)>1 else ''
    author = f'<span>{H(post["author"])} 著</span>' if post['author'] else '<span>New Dawn</span>'
    source_note = f'<aside class="source-note"><p>この記事はNew Dawnの既存記事を引き継いでいます。</p><a href="{H(post["source_url"],quote=True)}">移行元の記事を見る ↗</a></aside>' if post.get('source_url') else ''
    topic = f'<span class="topic-label">{H(post["topic"])}</span>' if post.get('topic') else ''
    content = f'''<div class="article-shell wrap"><nav class="breadcrumbs" aria-label="パンくずリスト"><a href="../../">ブログ</a><span aria-hidden="true">/</span><a href="../../categories/{post['category']}/">{CATEGORIES[post['category']]}</a></nav><article class="article"><header class="article-header"><div class="article-category">{category_pill(post,'../..')}{topic}</div><h1>{H(post['title'])}</h1><p class="article-description">{H(post['description'])}</p><div class="article-meta"><time datetime="{post['date']}">{date_label(post['date'])}</time>{author}<span>読了 約{post['minutes']}分</span></div></header>{toc_html}<div class="article-body">{body}</div>{source_note}<div class="article-actions"><a class="back-link" href="../../#articles">← 記事一覧へ</a><button class="copy-url" type="button">記事のURLをコピー</button><span class="copy-status" role="status" aria-live="polite"></span></div></article></div>'''
    related = [p for p in posts if p['slug']!=post['slug']]
    related.sort(key=lambda p:p['category']!=post['category'])
    content += '<section class="related wrap"><h2>あわせて読みたい</h2><div class="card-grid">'+''.join(post_card(p,'../..') for p in related[:2])+'</div></section>'
    (directory/'index.html').write_text(document(post['title'],post['description'],content,'../..',f'posts/{post["slug"]}/',post['category'],post))

if not args.preview:
    for path in (OUT/'posts').glob('*/index.html'):
        page = path.read_text()
        page = re.sub(r'<aside class="source-note">.*?<a href="([^"]+)">.*?</aside>', lambda m: '<!-- Original article: ' + m[1] + ' -->', page, flags=re.S)
        path.write_text(page)

privacy_content = '''<div class="article-shell wrap"><article class="article"><header class="article-header"><h1>アクセス解析について</h1></header><div class="article-body">
<p>New Dawnブログでは、記事の閲覧状況を把握し、内容や使いやすさを改善するためにGoogle アナリティクス（GA4）を使用しています。</p>
<p>Googleタグを通じて、閲覧したページ、参照元、端末・ブラウザの情報、Cookieなどの識別子に基づく利用状況がGoogleへ送信されます。当ブログから氏名やメールアドレスを測定データとして送信する設定は行っていません。</p>
<p>当ブログのタグでは、Googleシグナルと広告のパーソナライズ機能を無効にしています。</p>
<p>詳しくは<a href="https://policies.google.com/technologies/partner-sites?hl=ja">Googleによるサイトやアプリから収集した情報の使用</a>と<a href="https://policies.google.com/privacy?hl=ja">Googleのプライバシーポリシー</a>をご覧ください。対応するパソコンのブラウザでは、<a href="https://tools.google.com/dlpage/gaoptout?hl=ja">Google アナリティクス オプトアウト アドオン</a>を利用できます。</p>
<p>2026年10月28日 制定</p></div><div class="article-actions"><a class="back-link" href="../">← ブログへ戻る</a></div></article></div>'''
(OUT/'privacy').mkdir(exist_ok=True)
(OUT/'privacy/index.html').write_text(document('アクセス解析について', 'New Dawnブログのアクセス解析とデータの取り扱いについて。', privacy_content, '..', 'privacy/'))

# RSS uses absolute URLs when a hosting origin is known.
feed_items=[]
for post in posts:
    link = SITE + '/posts/'+post['slug']+'/' if SITE else post['source_url']
    timestamp = dt.datetime.fromisoformat(post['date']).replace(tzinfo=dt.timezone(dt.timedelta(hours=9))).strftime('%a, %d %b %Y %H:%M:%S %z')
    feed_items.append(f'<item><title>{H(post["title"])}</title><link>{H(link)}</link><guid isPermaLink="true">{H(link)}</guid><description>{H(post["description"])}</description><pubDate>{timestamp}</pubDate></item>')
(OUT/'feed.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>New Dawn ブログ</title><link>'+H(SITE or MAIN)+'</link><description>園芸療法と幸福学をめぐる実践と研究の記録</description><language>ja</language>'+''.join(feed_items)+'</channel></rss>')
routes=['', 'privacy/']+[f'categories/{key}/' for key in CATEGORIES]+[f'posts/{p["slug"]}/' for p in posts]
if SITE:
    (OUT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+H(SITE+'/'+route)+'</loc></url>' for route in routes)+'</urlset>')
(OUT/'robots.txt').write_text('User-agent: *\nDisallow: /\n' if args.preview else ('User-agent: *\nAllow: /\n'+('Sitemap: '+SITE+'/sitemap.xml\n' if SITE else '')))
(OUT/'.nojekyll').write_text('')
missing=document('ページが見つかりません','ページが見つかりません。New Dawnのブログトップから記事をお探しください。','<section class="category-hero wrap"><h1>ページが見つかりません</h1><p>ブログトップから記事をお探しください。</p><a class="button primary" href="./">ブログトップへ</a></section>')
# 404 resources must resolve from the hosting root, including a GitHub project subpath.
base=urlparse(SITE).path.rstrip('/') if SITE else ''
missing=missing.replace('href="./','href="'+base+'/').replace('src="./','src="'+base+'/')
(OUT/'404.html').write_text(missing)
print(f'Built {len(posts)} articles, {len(CATEGORIES)} categories and RSS into {OUT}')
