#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
import xml.sax.saxutils as saxutils
import re

# --------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------
URL_BASE = "https://www.al.ce.gov.br"
URL_LISTA = f"{URL_BASE}/noticias"
FEED_FILE = "feed_alce_news.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ALCEFeedBot/1.0)"
}

HOJE = datetime.now(timezone(timedelta(hours=-3))).date()

# --------------------------------------------------
# FUNÇÕES AUXILIARES
# --------------------------------------------------
def limpar_texto(texto):
    texto = re.sub(r'\s+', ' ', texto)
    lixo = [
        "Assessoria de Comunicação",
        "Ascom",
        "ALCE",
        "Assembleia Legislativa do Estado do Ceará"
    ]
    for l in lixo:
        texto = texto.replace(l, "")
    return texto.strip()

def data_para_rfc822(dt):
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")

# --------------------------------------------------
# COLETAR LINKS DO DIA
# --------------------------------------------------
print("🔍 Buscando lista de notícias...")
resp = requests.get(URL_LISTA, headers=HEADERS, timeout=30)
resp.raise_for_status()

soup = BeautifulSoup(resp.text, "html.parser")
cards = soup.select("a.card-noticia")

links = []

for c in cards:
    data_el = c.select_one(".data")
    if not data_el:
        continue

    try:
        data_pub = datetime.strptime(data_el.text.strip(), "%d/%m/%Y").date()
    except:
        continue

    if data_pub == HOJE:
        href = c.get("href")
        if href:
            links.append(urljoin(URL_BASE, href))

print(f"📰 Notícias encontradas hoje: {len(links)}")

# --------------------------------------------------
# COLETAR CONTEÚDO DAS MATÉRIAS
# --------------------------------------------------
noticias = []

for link in links:
    print(f"➡️ Processando: {link}")
    r = requests.get(link, headers=HEADERS, timeout=30)
    r.raise_for_status()

    s = BeautifulSoup(r.text, "html.parser")

    titulo_el = s.find("h1")
    conteudo_el = s.select_one(".conteudo-noticia")
    img_el = s.select_one(".conteudo-noticia img")

    if not titulo_el or not conteudo_el:
        continue

    titulo = titulo_el.text.strip()
    texto = limpar_texto(conteudo_el.get_text(" ", strip=True))

    imagem = ""
    if img_el and img_el.get("src"):
        imagem = urljoin(URL_BASE, img_el["src"])

    noticias.append({
        "title": titulo,
        "link": link,
        "text": texto,
        "image": imagem
    })

# --------------------------------------------------
# GERAR RSS
# --------------------------------------------------
print("🛠 Gerando RSS...")

now = datetime.now(timezone(timedelta(hours=-3)))
rss_items = ""

for n in noticias:
    img_html = f'<img src="{n["image"]}" />\n\n' if n["image"] else ""

    rss_items += f"""
    <item>
        <title>{saxutils.escape(n['title'])}</title>
        <link>{n['link']}</link>
        <guid>{n['link']}</guid>
        <pubDate>{data_para_rfc822(now)}</pubDate>
        <description><![CDATA[
        {img_html}
        {n['text']}
        ]]></description>
        <content:encoded><![CDATA[
        {img_html}
        {n['text']}
        ]]></content:encoded>
        {"<enclosure url=\"" + n["image"] + "\" type=\"image/jpeg\" />" if n["image"] else ""}
    </item>
    """

rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
 xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
<title>Notícias da Assembleia Legislativa do Ceará</title>
<link>{URL_BASE}</link>
<description>Notícias publicadas em {HOJE.strftime('%d/%m/%Y')}</description>
<language>pt-br</language>
<lastBuildDate>{data_para_rfc822(now)}</lastBuildDate>
{rss_items}
</channel>
</rss>
"""

with open(FEED_FILE, "w", encoding="utf-8") as f:
    f.write(rss)

print(f"✅ Feed gerado com sucesso: {FEED_FILE}")
