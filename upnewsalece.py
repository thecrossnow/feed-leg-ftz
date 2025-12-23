#!/usr/bin/env python3
# upnewsalce.py - Crawler para Assembleia Legislativa do Ceará (ALCE)

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta, date
import html
import hashlib
import time
from urllib.parse import urljoin
import re
import sys
import os
import urllib3

# ================= CONFIGURAÇÕES =================
URL_BASE = "https://www.al.ce.gov.br"
URL_NOTICIAS = "https://www.al.ce.gov.br/noticias"
FEED_FILE = "feed_alce_news.xml"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SECURITY_KEYWORDS = [
    "prisão", "preso", "delegacia", "homicídio", "assassinato",
    "tráfico", "drogas", "armas", "polícia", "criminoso",
    "suspeito", "captura", "foragido", "sspds", "bombeiros",
    "policial", "crimes", "investigação"
]

MESES = {
    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
    'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
    'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12,
    'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4,
    'mai': 5, 'jun': 6, 'jul': 7, 'ago': 8,
    'set': 9, 'out': 10, 'nov': 11, 'dez': 12
}

# ================= FUNÇÕES =================
def clean_text_content(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r'(?m)^.*?\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4}.*?$', '', text, flags=re.I)
    text = re.sub(r'(?m)^.*?(Foto|Edição|Texto|Fonte):.*?$', '', text, flags=re.I)
    text = text.replace("Compartilhe esta notícia:", "")
    if "Assembleia Legislativa do Estado do Ceará" in text:
        text = text.split("Assembleia Legislativa do Estado do Ceará")[0]
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 5]
    return '\n\n'.join(lines)


def parse_date_alce(date_str):
    try:
        date_str = date_str.lower()
        for mes, num in MESES.items():
            if mes in date_str:
                dia = int(re.search(r'(\d{1,2})', date_str).group(1))
                ano = int(re.search(r'(\d{4})', date_str).group(1))
                return date(ano, num, dia)
        if '/' in date_str:
            d, m, y = date_str.split('/')
            return date(int(y), int(m), int(d))
    except:
        return None
    return None


# ================= CRAWLER =================
def extract_news_alce():
    HOJE = datetime.now().date()
    session = requests.Session()
    session.headers.update(HEADERS)

    noticias_finais = []

    response = session.get(URL_NOTICIAS, timeout=20, verify=False)
    soup = BeautifulSoup(response.content, 'html.parser')

    items = soup.find_all('div', class_='noticias_item')

    for item in items:
        h3 = item.find('h3', class_='noticias_title')
        if not h3:
            continue

        link_tag = h3.find_parent('a')
        titulo = h3.get_text(strip=True)
        url_noticia = urljoin(URL_BASE, link_tag['href'])

        if any(k in titulo.lower() for k in SECURITY_KEYWORDS):
            continue

        span_data = item.find('span', class_='noticias_data')
        data_obj = parse_date_alce(span_data.get_text()) if span_data else None
        if data_obj != HOJE:
            continue

        resp = session.get(url_noticia, timeout=15, verify=False)
        soup_detalhe = BeautifulSoup(resp.content, 'html.parser')

        content_area = soup_detalhe.select_one('article, .item-page') or soup_detalhe.body
        for tag in content_area.find_all(['script', 'style', 'iframe', 'form', 'nav']):
            tag.decompose()

        ps = content_area.find_all('p')
        full_text = "\n\n".join(p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 20)
        clean_text = clean_text_content(full_text)

        if any(k in clean_text.lower() for k in SECURITY_KEYWORDS):
            continue

        # ===== IMAGEM =====
        img_url = None
        imgs = content_area.select('figure img, .noticia-imagem img, img')

        for img in imgs:
            src = img.get('src')
            if src and '/storage/noticias/' in src:
                img_url = urljoin(URL_BASE, src)
                break

        if not img_url:
            continue

        # ===== ALTERAÇÃO ÚNICA =====
        clean_text = f'<p><img src="{img_url}" alt="{titulo}" /></p>\n\n{clean_text}'

        noticias_finais.append({
            'title': titulo,
            'link': url_noticia,
            'description': clean_text,
            'image': img_url,
            'date': data_obj
        })

    # ================= RSS =================
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
<title>Notícias ALCE - Clean Feed</title>
<link>{URL_BASE}</link>
<description>Notícias da Assembleia Legislativa do Ceará</description>
<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
"""

    for n in noticias_finais:
        rss += f"""
<item>
<title><![CDATA[{n['title']}]]></title>
<link>{n['link']}</link>
<guid>{n['link']}</guid>
<description><![CDATA[{n['description']}]]></description>
<content:encoded><![CDATA[{n['description']}]]></content:encoded>
<enclosure url="{n['image']}" type="image/jpeg"/>
<pubDate>{n['date'].strftime("%a, %d %b %Y 00:00:00 -0300")}</pubDate>
</item>
"""

    rss += "</channel></rss>"

    with open(FEED_FILE, 'w', encoding='utf-8') as f:
        f.write(rss)

    print(f"Feed salvo em: {FEED_FILE}")


if __name__ == "__main__":
    extract_news_alce()
