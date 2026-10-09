#!/usr/bin/env python3
# upnewsalece.py - Crawler para Assembleia Legislativa do Ceará (ALCE)
#
# Atualizado para o novo layout do site (out/2026):
#   - links de notícia: /noticias/<id>-<slug>
#   - datas no formato dd/mm/aaaa (listagem) e dd/mm/aaaa hh:mm (detalhe)
#   - imagem destacada em /image/<id> (antes era /storage/noticias/)
#   - sem dependência das classes CSS antigas (noticias_item, noticias_title...)

import html
import mimetypes
import re
import sys
from datetime import datetime, timedelta
from email.utils import format_datetime
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
import urllib3
from bs4 import BeautifulSoup

# ================= CONFIGURAÇÕES =================
URL_BASE = "https://www.al.ce.gov.br"
URL_NOTICIAS = "https://www.al.ce.gov.br/noticias"
FEED_FILE = "feed_alce_news.xml"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept-Language': 'pt-BR,pt;q=0.9',
}

# O runner do GitHub Actions roda em UTC; "hoje" e "ontem" são em Fortaleza.
TZ = ZoneInfo("America/Fortaleza")

# 0 = só hoje | 1 = hoje + ontem
DAYS_BACK = 1

# Máximo de páginas da listagem a consultar
MAX_PAGES = 3

TIMEOUT = 25

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SECURITY_KEYWORDS = [
    "prisão", "preso", "delegacia", "homicídio", "assassinato",
    "tráfico", "drogas", "armas", "polícia", "criminoso",
    "suspeito", "captura", "foragido", "sspds", "bombeiros",
    "policial", "crimes", "investigação"
]

NEWS_HREF = re.compile(r'/noticias/(\d+)-[^/?#\s]+')
DATE_RE = re.compile(r'(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?')

# Crédito no fim de legenda de foto: " - Fulano de Tal" / " - Foto: Fulano"
CAPTION_CREDIT = re.compile(r"\s[-–—]\s+(Foto:\s*)?[A-ZÀ-Ú][\wÀ-ÿ'. ]{2,40}$")

# Trechos que indicam que o <p> não faz parte da matéria
JUNK_MARKERS = [
    "Compartilhe esta notícia",
    "Todos os direitos reservados",
    "Última Atualização",
    "Horário de funcionamento",
]


# ================= FUNÇÕES AUXILIARES =================
def parse_datetime(text):
    """Extrai dd/mm/aaaa [hh:mm] de um texto. Retorna datetime com fuso ou None."""
    m = DATE_RE.search(text or '')
    if not m:
        return None
    d, mo, y, hh, mm = m.groups()
    try:
        return datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), tzinfo=TZ)
    except ValueError:
        return None


def clean_text_content(text):
    if not text:
        return ""
    text = html.unescape(text)
    # linhas de data por extenso e de créditos
    text = re.sub(r'(?m)^.*?\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4}.*?$', '', text, flags=re.I)
    text = re.sub(r'(?m)^.*?(Foto|Edição|Texto|Fonte):.*?$', '', text, flags=re.I)
    text = text.replace("Compartilhe esta notícia:", "")
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 5]
    return '\n\n'.join(lines)


def has_security_keyword(text):
    text = text.lower()
    return any(k in text for k in SECURITY_KEYWORDS)


# ================= LISTAGEM =================
def find_listing_date(a_tag):
    """
    Sobe a partir do link da notícia até achar uma data dd/mm/aaaa,
    parando se o bloco já contiver links de mais de uma notícia.
    """
    node = a_tag
    for _ in range(4):
        if node is None:
            return None
        ids = set()
        for x in node.find_all('a', href=True):
            m = NEWS_HREF.search(x['href'])
            if m:
                ids.add(m.group(1))
        if len(ids) > 1:
            return None
        dt = parse_datetime(node.get_text(' ', strip=True))
        if dt:
            return dt
        node = node.parent
    return None


def get_listing(session, page):
    url = URL_NOTICIAS if page == 1 else f"{URL_NOTICIAS}?page={page}"
    resp = session.get(url, timeout=TIMEOUT, verify=False)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')

    found = {}
    for a in soup.find_all('a', href=True):
        m = NEWS_HREF.search(a['href'])
        if not m:
            continue
        nid = m.group(1)
        dt = find_listing_date(a)
        if nid not in found:
            found[nid] = {'url': urljoin(URL_BASE, m.group(0)), 'date': dt}
        elif found[nid]['date'] is None and dt:
            found[nid]['date'] = dt
    return found


# ================= DETALHE =================
def is_junk_paragraph(p):
    txt = p.get_text(' ', strip=True)
    if len(txt) <= 20:
        return True
    if p.find_parent(['header', 'footer', 'aside', 'figure', 'figcaption']):
        return True
    if any(mk in txt for mk in JUNK_MARKERS):
        return True
    # legenda: parágrafo curto logo após um bloco só de imagem e terminado
    # em crédito ("... - Fulano de Tal" ou "... - Foto: Fulano")
    prev = p.find_previous_sibling()
    if prev is not None and len(txt) < 200:
        has_img = prev.name == 'img' or prev.find('img') is not None
        if has_img and not prev.get_text(strip=True) and CAPTION_CREDIT.search(txt):
            return True
    return False


def pick_image(container, title, soup):
    def valid(src):
        if not src:
            return False
        path = urlparse(src).path.lower()
        if path.endswith('.svg') or path.startswith('/img/'):
            return False
        return bool(re.search(r'/image/\d+', path) or '/userfiles/' in path
                    or '/storage/' in path)

    if container is not None:
        for img in container.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if valid(src):
                return urljoin(URL_BASE, src)

    # fallback: imagem cujo alt é o próprio título
    for img in soup.find_all('img'):
        if (img.get('alt') or '').strip() == title:
            src = img.get('src') or img.get('data-src')
            if valid(src):
                return urljoin(URL_BASE, src)
    return None


def fetch_detail(session, url):
    resp = session.get(url, timeout=TIMEOUT, verify=False)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')

    for tag in soup.find_all(['script', 'style', 'iframe', 'form', 'nav', 'noscript']):
        tag.decompose()

    h1 = None
    for cand in soup.find_all('h1'):
        if cand.get_text(strip=True).lower() != 'notícias':
            h1 = cand
            break
    if h1 is None:
        return None

    title = h1.get_text(' ', strip=True)

    date_node = h1.find_next(string=DATE_RE)
    dt = parse_datetime(str(date_node)) if date_node else None

    # container da matéria: primeiro ancestral do h1 com parágrafos úteis depois dele
    after = {id(p) for p in h1.find_all_next('p')}
    container = h1
    paragraphs = []
    for _ in range(8):
        container = container.parent
        if container is None:
            break
        paragraphs = [p for p in container.find_all('p')
                      if id(p) in after and not is_junk_paragraph(p)]
        if paragraphs:
            break

    full_text = "\n\n".join(p.get_text(' ', strip=True) for p in paragraphs)

    return {
        'title': title,
        'date': dt,
        'text': clean_text_content(full_text),
        'image': pick_image(container, title, soup),
    }


# ================= CRAWLER =================
def extract_news_alce():
    now = datetime.now(TZ)
    valid_dates = {(now - timedelta(days=i)).date() for i in range(DAYS_BACK + 1)}

    print(f"Agora (Fortaleza): {now:%Y-%m-%d %H:%M}")
    print(f"Datas consideradas: {sorted(str(d) for d in valid_dates)}")

    session = requests.Session()
    session.headers.update(HEADERS)

    # ---------- coleta candidatos na listagem ----------
    candidates = {}
    for page in range(1, MAX_PAGES + 1):
        try:
            found = get_listing(session, page)
        except Exception as e:
            print(f"ERRO ao ler listagem página {page}: {e}")
            if page == 1:
                raise
            break

        new = {k: v for k, v in found.items() if k not in candidates}
        candidates.update(new)
        print(f"Página {page}: {len(found)} links, {len(new)} novos")

        in_window = [v for v in new.values()
                     if v['date'] is None or v['date'].date() in valid_dates]
        if not new or not in_window:
            break

    if not candidates:
        print("ERRO: nenhuma notícia encontrada na listagem (layout mudou de novo?)")
        sys.exit(1)

    # ---------- processa cada notícia ----------
    noticias_finais = []
    stats = {'fora_janela': 0, 'seguranca': 0, 'sem_imagem': 0, 'sem_texto': 0, 'erro': 0}

    for nid, c in sorted(candidates.items(), key=lambda kv: int(kv[0]), reverse=True):
        url_noticia = c['url']
        listing_date = c['date']

        if listing_date and listing_date.date() not in valid_dates:
            stats['fora_janela'] += 1
            continue

        print(f"[{nid}] {url_noticia}")

        try:
            d = fetch_detail(session, url_noticia)
        except Exception as e:
            print(f"   -> erro ao baixar: {e}")
            stats['erro'] += 1
            continue

        if not d:
            print("   -> ignorada: não achei o título (h1)")
            stats['erro'] += 1
            continue

        dt = d['date'] or listing_date
        if dt is None or dt.date() not in valid_dates:
            print(f"   -> ignorada: data {dt}")
            stats['fora_janela'] += 1
            continue

        if has_security_keyword(d['title']) or has_security_keyword(d['text']):
            print("   -> ignorada: palavra-chave de segurança")
            stats['seguranca'] += 1
            continue

        if not d['text']:
            print("   -> ignorada: sem texto")
            stats['sem_texto'] += 1
            continue

        if not d['image']:
            print("   -> ignorada: sem imagem")
            stats['sem_imagem'] += 1
            continue

        titulo = d['title']
        description = (
            f'<p><img src="{html.escape(d["image"], quote=True)}" '
            f'alt="{html.escape(titulo, quote=True)}" /></p>\n\n{d["text"]}'
        )

        noticias_finais.append({
            'title': titulo,
            'link': url_noticia,
            'description': description,
            'image': d['image'],
            'date': dt,
        })
        print("   -> INCLUÍDA")

    noticias_finais.sort(key=lambda n: n['date'], reverse=True)

    # ================= RSS =================
    def cdata(s):
        return s.replace(']]>', ']]]]><![CDATA[>')

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
<title>Notícias ALCE - Clean Feed</title>
<link>{URL_BASE}</link>
<description>Notícias da Assembleia Legislativa do Ceará</description>
<lastBuildDate>{format_datetime(now)}</lastBuildDate>
"""

    for n in noticias_finais:
        mime = mimetypes.guess_type(urlparse(n['image']).path)[0] or 'image/jpeg'
        rss += f"""
<item>
<title><![CDATA[{cdata(n['title'])}]]></title>
<link>{html.escape(n['link'], quote=True)}</link>
<guid isPermaLink="true">{html.escape(n['link'], quote=True)}</guid>
<description><![CDATA[{cdata(n['description'])}]]></description>
<content:encoded><![CDATA[{cdata(n['description'])}]]></content:encoded>
<enclosure url="{html.escape(n['image'], quote=True)}" type="{mime}" length="0"/>
<pubDate>{format_datetime(n['date'])}</pubDate>
</item>
"""

    rss += "</channel></rss>"

    with open(FEED_FILE, 'w', encoding='utf-8') as f:
        f.write(rss)

    print()
    print(f"Candidatas: {len(candidates)} | Incluídas: {len(noticias_finais)} | {stats}")
    print(f"Feed salvo em: {FEED_FILE}")


if __name__ == "__main__":
    extract_news_alce()
