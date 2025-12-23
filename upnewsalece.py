#!/usr/bin/env python3
# upnewsalece.py - Crawler ALCE (somente notícias do dia, sem logo)

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, date
import html
import re
from urllib.parse import urljoin
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= CONFIG =================

URL_BASE = "https://www.al.ce.gov.br"
URL_NOTICIAS = "https://www.al.ce.gov.br/noticias"
FEED_FILE = "feed_alce_news.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

SECURITY_KEYWORDS = [
    "prisão", "preso", "delegacia", "homicídio", "assassinato",
    "tráfico", "drogas", "armas", "criminoso", "foragido"
]

MESES = {
    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
    'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
    'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12,
    'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5,
    'jun': 6, 'jul': 7, 'ago': 8, 'set': 9,
    'out': 10, 'nov': 11, 'dez': 12
}

# ================= FUNÇÕES =================

def parse_date_alce(text):
    if not text:
        return None
    text = text.lower().strip()

    try:
        if '/' in text:
            d, m, y = text.split('/')
            return date(int(y), int(m), int(d))
    except:
        pass

    try:
        for mes, num in MESES.items():
            if mes in text:
                dia = int(re.search(r'(\d{1,2})', text).group(1))
                ano = int(re.search(r'(\d{4})', text).group(1))
                return date(ano, num, dia)
    except:
        return None

    return None


def clean_text(text):
    text = html.unescape(text)
    text = re.sub(r'(?m)^.*?(Foto|Edição|Fonte|Texto):.*$', '', text, flags=re.I)
    text = re.sub(r'(?m)^.*?#.*$', '', text)
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 40]
    return "\n\n".join(lines)

# ================= CRAWLER =================

def extract_news_alce():
    print(">>> Iniciando crawler ALCE (somente HOJE)")

    hoje = datetime.now().date()

    session = requests.Session()
    session.headers.update(HEADERS)

    noticias = []

    resp = session.get(URL_NOTICIAS, verify=False, timeout=20)
    soup = BeautifulSoup(resp.content, "html.parser")

    items = soup.find_all("div", class_="noticias_item")

    for item in items[:20]:

        h3 = item.find("h3", class_="noticias_title")
        if not h3:
            continue

        titulo = h3.get_text(strip=True)
        if any(k in titulo.lower() for k in SECURITY_KEYWORDS):
            continue

        link = h3.find_parent("a")
        if not link:
            continue

        url = urljoin(URL_BASE, link["href"])

        # ===== DATA NA LISTAGEM (OBRIGATÓRIA) =====
        span = item.find("span", class_="noticias_data")
        data_listagem = parse_date_alce(span.get_text()) if span else None

        if data_listagem != hoje:
            continue

        # ===== THUMB DA LISTAGEM =====
        img_thumb = None
        div_img = item.find("div", class_="noticias_item--image")
        if div_img and div_img.find("img"):
            img_thumb = div_img.find("img").get("src")

        print(f">>> Analisando: {titulo}")

        # ===== DETALHE =====
        det = session.get(url, verify=False, timeout=15)
        sd = BeautifulSoup(det.content, "html.parser")

        # ===== CONFIRMA DATA NO DETALHE =====
        data_obj = None
        date_el = sd.select_one(".itemDateCreated, .date, .data")
        if date_el:
            data_obj = parse_date_alce(date_el.get_text())

        if data_obj and data_obj != hoje:
            continue

        # ===== CONTEÚDO =====
        content = sd.select_one("article, .item-page, [itemprop='articleBody']")
        if not content:
            content = sd.body

        for t in content.find_all(["script", "style", "nav", "form"]):
            t.decompose()

        ps = content.find_all("p")
        texto = "\n\n".join(
            p.get_text(strip=True)
            for p in ps
            if len(p.get_text(strip=True)) > 40
        )

        if not texto:
            continue

        texto = clean_text(texto)

        if any(k in texto.lower() for k in SECURITY_KEYWORDS):
            continue

        # ===== IMAGEM FINAL (ANTI-LOGO) =====
        img = None

        # 1️⃣ imagem real do conteúdo
        for im in sd.select("article img, .item-page img, figure img"):
            src = im.get("src", "").strip()
            if not src:
                continue
            if any(x in src.lower() for x in ["logo", "brasao", "header", "rodape"]):
                continue
            img = src
            break

        # 2️⃣ fallback: thumb da listagem
        if not img and img_thumb:
            if not any(x in img_thumb.lower() for x in ["logo", "brasao"]):
                img = img_thumb

        # 3️⃣ último fallback: og:image (se não for logo)
        if not img:
            og = sd.find("meta", property="og:image")
            if og:
                og_img = og.get("content", "")
                if og_img and not any(x in og_img.lower() for x in ["logo", "brasao"]):
                    img = og_img

        if not img:
            continue

        if not img.startswith("http"):
            img = urljoin(URL_BASE, img)

        noticias.append({
            "title": titulo,
            "link": url,
            "text": texto,
            "image": img,
            "date": hoje
        })

        print("   ✔ Adicionada")

    # ================= RSS =================

    print(f">>> Gerando feed com {len(noticias)} notícias")

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
<title>Notícias ALCE - Hoje</title>
<link>{URL_BASE}</link>
<description>Notícias da Assembleia Legislativa do Ceará (dia atual)</description>
<lastBuildDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
"""

    for n in noticias:
        rss += f"""
<item>
<title><![CDATA[{n['title']}]]></title>
<link>{n['link']}</link>
<guid>{n['link']}</guid>
<description><![CDATA[{n['text']}]]></description>
<content:encoded><![CDATA[{n['text']}]]></content:encoded>
<enclosure url="{n['image']}" type="image/jpeg"/>
<pubDate>{hoje.strftime('%a, %d %b %Y 00:00:00 -0300')}</pubDate>
</item>
"""

    rss += "</channel></rss>"

    with open(FEED_FILE, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f">>> Feed salvo: {FEED_FILE}")

# ================= MAIN =================

if __name__ == "__main__":
    extract_news_alce()
