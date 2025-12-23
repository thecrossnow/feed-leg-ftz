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
# ================= CONFIGURAÇÕES =================
URL_BASE = "https://www.al.ce.gov.br"
URL_NOTICIAS = "https://www.al.ce.gov.br/noticias"
FEED_FILE = "feed_alce_news.xml"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
# Desabilitar avisos de SSL inseguro
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# Palavras-chave para excluir (Segurança)
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
    'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12
}
# ================= FUNÇÕES DE LIMPEZA =================
def clean_text_content(text):
    """
    Limpa o texto removendo datas, metadados, e formatações indesejadas.
    """
    if not text: return ""
    
    text = html.unescape(text)
    
    # Remover linhas de data/hora comuns
    text = re.sub(r'(?m)^.*?\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4}.*?$', '', text, flags=re.IGNORECASE)
    
    # Remover créditos de Foto e Edição (comuns na ALCE)
    text = re.sub(r'(?m)^.*?Foto:.*?$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?m)^.*?Edição:.*?$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?m)^.*?Por\s+.*?\s+\|\s+.*?\d{4}.*?$', '', text, flags=re.IGNORECASE) # "Por Autor | Data"
    
    # Remover autoria genérica
    text = re.sub(r'(?m)^.*?(Texto|Fonte):.*?$', '', text, flags=re.IGNORECASE)
    # Remover metadados finais (lixo do rodapé capturado)
    # Remove a frase repetida, mas mantem o texto
    text = text.replace("Compartilhe esta notícia:", "")
    # Corta o rodapé real
    if "Assembleia Legislativa do Estado do Ceará" in text:
        text = text.split("Assembleia Legislativa do Estado do Ceará")[0]
        
    if "Jornal Alece -" in text:
        text = text.split("Jornal Alece -")[0]
    # Normalizar espaços
    lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 5]
    return '\n\n'.join(lines)
def parse_date_alce(date_str):
    """
    Tenta converter string de data (ex: '18 de Dezembro de 2025' ou '18/12/2025')
    """
    try:
        date_str = date_str.lower().strip()
        # Tentar formato extenso
        for mes_pt, mes_num in MESES.items():
            if mes_pt in date_str:
                dia = int(re.search(r'(\d{1,2})', date_str).group(1))
                ano_match = re.search(r'(\d{4})', date_str)
                ano = int(ano_match.group(1)) if ano_match else datetime.now().year
                return date(ano, mes_num, dia)
        
        # Tentar formato numérico dd/mm/yyyy
        if '/' in date_str:
            parts = date_str.split('/')
            return date(int(parts[2]), int(parts[1]), int(parts[0]))
            
    except:
        return None
    return None
# ================= CRAWLER =================
def extract_news_alce():
    print(f"Iniciando extracao ALCE em {datetime.now()}")
    
    # Definir HOJE - Garantir que pega a data correta do servidor
    # Se rodar antes das 3AM UTC, pode ser dia anterior no Brasil, mas 
    # o usuário pediu data de execução. Vamos usar datetime.now() local.
    HOJE = datetime.now().date()
    print(f"Data de referencia (Execucao): {HOJE}")
    session = requests.Session()
    session.headers.update(HEADERS)
    
    noticias_finais = []
    
    try:
        response = session.get(URL_NOTICIAS, timeout=20, verify=False)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # O site tem uma estrutura de listagem em div.noticias_item.row
        items = soup.find_all('div', class_='noticias_item')
        
        count = 0
        for item in items:
            if count >= 20: break 
            
            # Link e Título
            # O link principal geralmente envolve o h3 ou está separada
            # No HTML fornecido: 
            # <a href="..." title="..."> <h3 class="noticias_title">...</h3> </a>
            
            h3 = item.find('h3', class_='noticias_title')
            if not h3: continue
            
            link_tag = h3.find_parent('a')
            if not link_tag: continue
            
            url_noticia = urljoin(URL_BASE, link_tag['href'])
            titulo = h3.get_text(strip=True)
            
            # Filtro Rápido de Título
            if any(k in titulo.lower() for k in SECURITY_KEYWORDS):
                continue
                
            # Data na listagem (Classe .noticias_data)
            # <span class="noticias_data">23/12/2025</span>
            data_listagem = None
            span_data = item.find('span', class_='noticias_data')
            if span_data:
                data_listagem = parse_date_alce(span_data.get_text())
                
            # Se tiver data na listagem, já filtra
            if data_listagem and data_listagem != HOJE:
                 # print(f"   Noticia antiga (Listagem): {data_listagem}")
                 continue
                 
            # Imagem na listagem (Fallback)
            # <div class="noticias_item--image"> <a...> <img src="...">
            img_thumb = None
            div_img = item.find('div', class_='noticias_item--image')
            if div_img:
                img_tag = div_img.find('img')
                if img_tag and img_tag.get('src'):
                    img_thumb = img_tag['src']
            
            print(f"Analisanado: {titulo[:40]}...")
            
            # Extrair Detalhes
            try:
                # Vamos entrar na página para pegar conteúdo completo
                resp_detalhe = session.get(url_noticia, timeout=15, verify=False)
                soup_detalhe = BeautifulSoup(resp_detalhe.content, 'html.parser')
                
                # DATA
                # Prioridade: Usar a data que já pegamos na listagem (data_listagem)
                data_obj = data_listagem
                
                # Se ainda null, tenta achar no detalhe
                if not data_obj:
                    # Tentar achar padrão de data no começo do texto
                    texto_pag = soup_detalhe.get_text()[:500]
                    match_data = re.search(r'(\d{2}/\d{2}/\d{4})', texto_pag)
                    if match_data:
                        data_obj = parse_date_alce(match_data.group(1))
                
                if not data_obj:
                    # Ultima tentativa: data de hoje se o usuario quiser forçar (mas arriscado)
                    # print("   Data nao encontrada. Ignorando.")
                    # Como estamos na listagem e ela geralmente é cronológica, se não achou data explicita
                    # mas o titulo passou, é estranho.
                    pass
                    
                # Se mesmo assim não achou ou não é de hoje
                if not data_obj:
                     print("   Data nao identificada. Ignorando.")
                     continue
                     
                if data_obj != HOJE:
                    print(f"   Noticia antiga ({data_obj}). Ignorando.")
                    continue
                
                # CONTEÚDO
                # A pesquisa indicou que o conteúdo está solto ou em parágrafos.
                # Vamos pegar todos os Ps dentro da área principal
                # Tentar identificar área principal:
                
                content_area = soup_detalhe.select_one('article, [itemprop="articleBody"], .news-item-detail, .item-page')
                
                if not content_area:
                    # Fallback genérico: maior bloco de texto
                    content_area = soup_detalhe.body
                
                # Limpar scripts, estilos
                for tag in content_area.find_all(['script', 'style', 'iframe', 'form', 'nav']):
                    tag.decompose()
                
                # Extrair texto dos parágrafos
                ps = content_area.find_all('p')
                full_text = "\n\n".join([p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 20])
                
                if not full_text:
                    print("   Conteudo vazio.")
                    continue
                
                # Limpeza final
                clean_text = clean_text_content(full_text)
                
                # FILTRO CONTEÚDO
                if any(k in clean_text.lower() for k in SECURITY_KEYWORDS):
                    print("   Filtro de Seguranca (Conteudo).")
                    continue
                
                # IMAGEM
                img_url = None
                
                # 1. Tentar meta tags de redes sociais, mas com filtro RIGOROSO
                og_img = soup_detalhe.find('meta', property='og:image')
                if og_img and og_img.get('content'): 
                    candidato = og_img['content']
                    # Filtra placeholders comuns da ALCE
                    bad_terms = ['logo', 'sem_imagem', 'preview.png', 'padrao', 'icon']
                    if not any(bad in candidato.lower() for bad in bad_terms):
                        img_url = candidato
                # 2. Se a imagem do OG for nula ou suspeita, ou se tivermos um thumb confiável da listagem,
                # vamos dar preferência ao thumb da listagem se ele for uma foto real (caminho /storage/noticias/)
                
                # O thumb da listagem (img_thumb) pegamos lá em cima. 
                # Geralmente ele é: https://www.al.ce.gov.br//storage/noticias/...
                
                if img_thumb and '/storage/noticias/' in img_thumb:
                    # Se tivermos um thumb de notícia real, usamos ele (muito mais seguro que o OG genérico)
                    img_url = img_thumb
                
                # 3. Se ainda não temos imagem, tenta caçar no body
                if not img_url:
                    # Tenta achar imagens grandes no topo do content_area
                    imgs = content_area.select('figure img, .noticia-imagem img, img.img-fluid')
                    for i in imgs:
                        src = i.get('src')
                        # Filtra logos comuns
                        if src and not any(bad in src.lower() for bad in ['logo', 'icon', 'preview', 'al.ce.gov.br/img']):
                            img_url = src
                            break
                            
                if not img_url:
                    # Última tentativa: qualquer imagem grande no corpo
                    imgs = content_area.select('img')
                    for i in imgs:
                         src = i.get('src')
                         if src and not any(bad in src.lower() for bad in ['logo', 'icon', 'preview', 'al_ce_gov']):
                            img_url = src
                            break
                if not img_url:
                    print("   Sem imagem valida.")
                    continue
                    
                # Fix URL relativa
                if img_url and not img_url.startswith('http'):
                    img_url = urljoin(URL_BASE, img_url)
                
                # ADICIONAR
                noticias_finais.append({
                    'title': titulo,
                    'link': url_noticia,
                    'description': clean_text,
                    'image': img_url,
                    'date': data_obj
                })
                print(f"   Adicionada!")
                count += 1
                
            except Exception as e:
                print(f"   Erro ao processar detalhe: {e}")
                continue
    except Exception as e:
        print(f"Erro fatal no crawler: {e}")
    # ================= GERAR RSS =================
    
    print(f"\nGerando XML com {len(noticias_finais)} noticias...")
    
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
<title>Notícias ALCE - Clean Feed</title>
<link>{URL_BASE}</link>
<description>Notícias da Assembleia Legislativa do Ceará</description>
<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
"""
    
    for n in noticias_finais:
        # Escapar XML
        clean_desc = n['description'].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        clean_title = n['title'].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        rss += f"""<item>
<title>{clean_title}</title>
<guid>{n['link']}</guid>
<link>{n['link']}</link>
<description><![CDATA[{clean_desc}]]></description>
<content:encoded><![CDATA[{clean_desc}]]></content:encoded>
<enclosure url="{n['image']}" type="image/jpeg"/>
<pubDate>{n['date'].strftime("%a, %d %b %Y 00:00:00 -0300")}</pubDate>
</item>"""
    rss += "</channel></rss>"
    
    try:
        with open(FEED_FILE, 'w', encoding='utf-8') as f:
            f.write(rss)
        print(f"Feed salvo em: {FEED_FILE}")
    except Exception as e:
        print(f"Erro ao salvar arquivo: {e}")
if __name__ == "__main__":
    extract_news_alce()
