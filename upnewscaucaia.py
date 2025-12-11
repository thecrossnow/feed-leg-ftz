#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import html
import hashlib
import time
from urllib.parse import urljoin
import re
import os

def criar_feed_caucaia_limpo():
    
    URL_BASE = "https://www.caucaia.ce.gov.br"
    URL_LISTA = f"{URL_BASE}/informa.php"
    FEED_FILE = "feed_caucaia_limpo.xml"
    
    HEADERS = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(URL_LISTA, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        lista_noticias = []
        links_processados = set()
        
        for link in soup.find_all('a', href=lambda x: x and '/informa/' in x):
            href = link['href']
            
            if href not in links_processados:
                titulo = link.get_text(strip=True)
                
                if titulo and len(titulo) > 20 and 'Continue' not in titulo:
                    link_url = urljoin(URL_BASE, href)
                    links_processados.add(href)
                    
                    lista_noticias.append({
                        'titulo': titulo[:300],
                        'link': link_url
                    })
        
        lista_noticias = lista_noticias[:10]
        
        noticias_completas = []
        
        for i, noticia in enumerate(lista_noticias, 1):
            try:
                time.sleep(1)
                resp = requests.get(noticia['link'], headers=HEADERS, timeout=30)
                
                if resp.status_code != 200:
                    continue
                
                soup_noticia = BeautifulSoup(resp.content, 'html.parser')
                
                titulo_tag = soup_noticia.find('h1', class_='DataInforma')
                if titulo_tag:
                    noticia['titulo'] = titulo_tag.get_text(strip=True)
                
                img_tag = soup_noticia.find('img', class_='imginfo')
                imagem_url = None
                if img_tag and img_tag.get('src'):
                    src = img_tag['src']
                    if not src.startswith(('http://', 'https://')):
                        src = urljoin(URL_BASE, src)
                    imagem_url = src
                
                div_conteudo = soup_noticia.find('div', class_='p-info')
                conteudo_html = ""
                
                if div_conteudo:
                    # EXTRAIR PARÁGRAFOS SEM DUPLICAÇÃO
                    paragrafos_set = set()
                    paragrafos_texto = []
                    
                    for p in div_conteudo.find_all('p'):
                        texto = p.get_text(strip=True)
                        if texto and len(texto) > 10:
                            if texto not in paragrafos_set:
                                paragrafos_set.add(texto)
                                paragrafos_texto.append(f'<p>{texto}</p>')
                    
                    if paragrafos_texto:
                        conteudo_html = ''.join(paragrafos_texto)
                    else:
                        # Fallback: apenas se não houver <p>
                        texto_completo = div_conteudo.get_text("\n", strip=True)
                        linhas = [linha.strip() for linha in texto_completo.split('\n') if linha.strip()]
                        for linha in linhas:
                            if len(linha) > 20 and linha not in paragrafos_set:
                                conteudo_html += f'<p>{linha}</p>'
                else:
                    # Fallback original: parágrafos da página
                    todos_p = soup_noticia.find_all('p')
                    paragrafos = []
                    for p in todos_p:
                        texto = p.get_text(strip=True)
                        if len(texto) > 50:
                            paragrafos.append(f'<p>{html.escape(texto)}</p>')
                    
                    if paragrafos:
                        conteudo_html = ''.join(paragrafos[:10])
                
                texto_pagina = soup_noticia.get_text()
                data_match = re.search(r'(\d{2}/\d{2}/\d{4})', texto_pagina[:2000])
                data_str = data_match.group(1) if data_match else None
                
                noticias_completas.append({
                    'titulo': noticia['titulo'],
                    'link': noticia['link'],
                    'imagem': imagem_url,
                    'conteudo': conteudo_html,
                    'data': data_str
                })
                
            except Exception:
                continue
        
        xml_parts = []
        
        xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_parts.append('<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">')
        xml_parts.append('<channel>')
        xml_parts.append(f'<title>Notícias da Prefeitura de Caucaia</title>')
        xml_parts.append(f'<link>{URL_BASE}</link>')
        xml_parts.append('<description>Conteúdo limpo para WordPress</description>')
        xml_parts.append('<language>pt-br</language>')
        xml_parts.append('<generator>Scraper Caucaia</generator>')
        xml_parts.append(f'<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
        xml_parts.append('<ttl>180</ttl>')
        
        for i, noticia in enumerate(noticias_completas, 1):
            guid = hashlib.md5(noticia['link'].encode()).hexdigest()[:12]
            
            if noticia['data'] and '/' in noticia['data']:
                try:
                    partes = noticia['data'].split('/')
                    dia, mes, ano = map(int, partes)
                    data_obj = datetime(ano, mes, dia, 12, 0, 0, tzinfo=timezone.utc)
                except:
                    data_obj = datetime.now(timezone.utc) - timedelta(hours=i*2)
            else:
                data_obj = datetime.now(timezone.utc) - timedelta(hours=i*2)
            
            data_rss = data_obj.strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            xml_parts.append('<item>')
            xml_parts.append(f'<title>{html.escape(noticia["titulo"])}</title>')
            xml_parts.append(f'<link>{noticia["link"]}</link>')
            xml_parts.append(f'<guid isPermaLink="false">caucaia-{guid}</guid>')
            xml_parts.append(f'<pubDate>{data_rss}</pubDate>')
            xml_parts.append(f'<description>{html.escape(noticia["titulo"][:200])}</description>')
            
            conteudo_final = noticia['conteudo']
            fonte_html = f'<div style="margin-top:30px;padding:15px;background:#f8f9fa;border-left:4px solid #0073aa"><strong>Fonte:</strong> <a href="{noticia["link"]}">Prefeitura de Caucaia</a></div>'
            conteudo_final += fonte_html
            
            xml_parts.append(f'<content:encoded><![CDATA[ {conteudo_final} ]]></content:encoded>')
            
            if noticia['imagem']:
                xml_parts.append(f'<enclosure url="{noticia["imagem"]}" type="image/jpeg" length="80000" />')
                xml_parts.append(f'<media:content url="{noticia["imagem"]}" type="image/jpeg" medium="image">')
                xml_parts.append(f'<media:title>{html.escape(noticia["titulo"][:100])}</media:title>')
                xml_parts.append(f'<media:description>{html.escape(noticia["titulo"][:200])}</media:description>')
                xml_parts.append('</media:content>')
            
            xml_parts.append('</item>')
        
        xml_parts.append('</channel>')
        xml_parts.append('</rss>')
        
        with open(FEED_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_parts))
        
        if os.path.exists(FEED_FILE):
            with open(FEED_FILE, 'r', encoding='utf-8') as f:
                conteudo = f.read()
                if conteudo.startswith('<?xml'):
                    print("✅ XML gerado corretamente")
                else:
                    print("⚠️  Verifique o início do arquivo")
        
        return True
        
    except Exception as e:
        print(f"Erro: {e}")
        return False

if __name__ == "__main__":
    criar_feed_caucaia_limpo()
