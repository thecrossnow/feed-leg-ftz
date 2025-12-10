#!/usr/bin/env python3
# upnewsfortaleza.py - VERSÃO CORRIGIDA PARA GITHUB ACTIONS

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta, date
import html
import hashlib
import time
from urllib.parse import urljoin, urlparse, parse_qs
import re
import os
import sys
import locale
from zoneinfo import ZoneInfo  # Python 3.9+

def criar_feed_fortaleza_hoje():
    """
    Extrai notícias do dia atual, considerando fuso horário de Brasília
    """
    
    # ================= CONFIGURAÇÃO DE FUSO HORÁRIO =================
    # GitHub Actions roda em UTC, precisamos converter para horário de Brasília
    FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")
    
    # Data atual EM BRASÍLIA
    agora_brasilia = datetime.now(FUSO_BRASILIA)
    HOJE_BR = agora_brasilia.date()
    
    print(f"⏰ Horário no GitHub Actions (UTC): {datetime.now(timezone.utc).strftime('%H:%M')}")
    print(f"⏰ Horário em Brasília: {agora_brasilia.strftime('%H:%M')}")
    print(f"📅 Data de referência (Brasília): {HOJE_BR.strftime('%d/%m/%Y')}")
    print("-" * 60)
    
    # ================= CONFIGURAÇÕES =================
    URL_BASE = "https://www.fortaleza.ce.gov.br"
    URL_LISTA = f"{URL_BASE}/noticias"
    FEED_FILE = "feed_fortaleza_hoje.xml"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9'
    }
    
    # ================= MESES EM PORTUGUÊS (minúsculo) =================
    MESES_PT = {
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
        'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
        'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12,
        # Alternativas com acentos
        'janeiro': 1, 'fevereiro': 2, 'março': 3,
        'marco': 3,  # sem acento
        'abril': 4, 'maio': 5, 'junho': 6,
        'julho': 7, 'agosto': 8, 'setembro': 9,
        'outubro': 10, 'novembro': 11, 'dezembro': 12
    }
    
    try:
        lista_noticias = []
        links_processados = set()
        
        # ================= FUNÇÃO DE EXTRATOD DE DATA =================
        def extrair_data_portugues(data_texto):
            """Extrai data do formato 'Quarta, 10 Dezembro 2025 14:54'"""
            try:
                # Remover vírgulas e normalizar espaços
                data_texto = re.sub(r'[,\s]+', ' ', data_texto.strip())
                partes = data_texto.split()
                
                if len(partes) >= 4:
                    # Encontrar o dia (primeiro número)
                    for i, parte in enumerate(partes):
                        if parte.isdigit() and 1 <= int(parte) <= 31:
                            dia = int(parte)
                            # Procurar mês após o dia
                            if i + 1 < len(partes):
                                mes_str = partes[i + 1].lower()
                                # Procurar ano após o mês
                                if i + 2 < len(partes) and partes[i + 2].isdigit() and len(partes[i + 2]) == 4:
                                    ano = int(partes[i + 2])
                                    
                                    # Encontrar mês no dicionário (tolerante)
                                    for chave_mes in MESES_PT:
                                        if chave_mes in mes_str:
                                            return date(ano, MESES_PT[chave_mes], dia)
                
                # Tentativa alternativa: regex para padrões comuns
                padrao = r'(\d{1,2})[\s/]+(?:de\s+)?(\w+)[\s/]+(?:de\s+)?(\d{4})'
                match = re.search(padrao, data_texto, re.IGNORECASE)
                if match:
                    dia = int(match.group(1))
                    mes_str = match.group(2).lower()
                    ano = int(match.group(3))
                    
                    for chave_mes in MESES_PT:
                        if chave_mes in mes_str:
                            return date(ano, MESES_PT[chave_mes], dia)
            
            except Exception as e:
                print(f"      ⚠️  Erro ao extrair data: {e}")
            
            return None
        
        # ================= PROCESSAR PÁGINAS =================
        pagina_atual = 1
        url_atual = URL_LISTA
        noticias_encontradas = 0
        max_paginas = 10
        
        while url_atual and pagina_atual <= max_paginas:
            print(f"📄 Página {pagina_atual}: {urlparse(url_atual).path}")
            
            try:
                response = requests.get(url_atual, headers=HEADERS, timeout=15)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Encontrar notícias
                containers = soup.find_all('div', class_='blog-post-item')
                print(f"   📦 Containers encontrados: {len(containers)}")
                
                noticias_pagina = 0
                todas_antigas = True
                
                for container in containers:
                    try:
                        # Extrair data
                        data_div = container.find('div', class_='blog-time')
                        if not data_div:
                            continue
                            
                        span_data = data_div.find('span', class_='font-lato')
                        if not span_data:
                            continue
                            
                        data_str = span_data.get_text(strip=True)
                        if not data_str:
                            continue
                        
                        # Converter data
                        data_noticia = extrair_data_portugues(data_str)
                        
                        if not data_noticia:
                            print(f"      ⚠️  Não consegui extrair data de: {data_str[:30]}...")
                            continue
                        
                        # DEBUG: Mostrar data extraída
                        print(f"      📅 Extraído: '{data_str}' -> {data_noticia.strftime('%d/%m/%Y')}")
                        
                        # COMPARAR COM HOJE EM BRASÍLIA
                        if data_noticia == HOJE_BR:
                            todas_antigas = False
                            
                            # Extrair link
                            link_tag = container.find('a', class_='btn-reveal')
                            if not link_tag or not link_tag.get('href'):
                                continue
                                
                            href = link_tag['href']
                            link_url = urljoin(URL_BASE, href)
                            
                            if link_url in links_processados:
                                continue
                                
                            # Extrair título
                            titulo = ""
                            intro_div = container.find('div', class_='intro')
                            if intro_div:
                                h2_tag = intro_div.find('h2')
                                if h2_tag:
                                    titulo = h2_tag.get_text(strip=True)
                            
                            if not titulo or len(titulo) < 10:
                                continue
                            
                            # Extrair hora
                            hora = "00:00"
                            if ':' in data_str:
                                hora_match = re.search(r'(\d{1,2}:\d{2})', data_str)
                                if hora_match:
                                    hora = hora_match.group(1)
                            
                            # Extrair imagem
                            imagem_url = None
                            img_tag = container.find('figure', class_='blog-item-small-image')
                            if img_tag:
                                img = img_tag.find('img')
                                if img and img.get('src'):
                                    src = img['src']
                                    if src and not src.startswith(('http://', 'https://')):
                                        imagem_url = urljoin(URL_BASE, src)
                                    else:
                                        imagem_url = src
                            
                            # Adicionar à lista
                            links_processados.add(link_url)
                            
                            lista_noticias.append({
                                'titulo': titulo[:250],
                                'link': link_url,
                                'data_str': data_str,
                                'data_obj': data_noticia,
                                'imagem': imagem_url,
                                'hora': hora,
                                'pagina': pagina_atual
                            })
                            
                            noticias_pagina += 1
                            noticias_encontradas += 1
                            print(f"    ✅ [{hora}] {titulo[:60]}...")
                        
                        elif data_noticia < HOJE_BR:
                            # Notícia antiga
                            diferenca = (HOJE_BR - data_noticia).days
                            if diferenca <= 2:
                                print(f"    ⏰ {data_noticia.strftime('%d/%m')} ({diferenca} dia(s) atrás)")
                    
                    except Exception as e:
                        print(f"    ⚠️  Erro no container: {str(e)[:50]}")
                        continue
                
                print(f"   📊 Notícias de HOJE nesta página: {noticias_pagina}")
                
                # Se só encontrou notícias antigas, pode parar
                if todas_antigas and noticias_pagina == 0:
                    print("   ⏹️  Só notícias antigas, parando varredura")
                    break
                
                # Procurar próxima página
                proxima_url = None
                paginador = soup.find('div', class_='news-pagination')
                
                if paginador:
                    # CORREÇÃO: usar string= em vez de text=
                    link_proximo = paginador.find('a', string=lambda t: t and 'próximo' in str(t).lower())
                    
                    if not link_proximo:
                        link_proximo = paginador.find('li', class_='pagination-next')
                        if link_proximo:
                            link_proximo = link_proximo.find('a')
                    
                    if link_proximo and link_proximo.get('href'):
                        href = link_proximo['href']
                        proxima_url = urljoin(URL_BASE, href)
                
                if not proxima_url:
                    break
                
                pagina_atual += 1
                url_atual = proxima_url
                time.sleep(1)
                
            except Exception as e:
                print(f"   ❌ Erro na página {pagina_atual}: {e}")
                break
        
        # ================= VERIFICAR RESULTADOS =================
        print("-" * 60)
        print(f"📈 Páginas processadas: {pagina_atual}")
        print(f"🎯 Notícias de HOJE encontradas: {noticias_encontradas}")
        
        if noticias_encontradas == 0:
            # Verificar se o problema é de data
            print("\n🔍 DIAGNÓSTICO DO PROBLEMA:")
            print(f"   1. Data de referência: {HOJE_BR.strftime('%d/%m/%Y')}")
            print(f"   2. Horário UTC atual: {datetime.now(timezone.utc).strftime('%H:%M')}")
            print(f"   3. Horário Brasília: {agora_brasilia.strftime('%H:%M')}")
            print("   4. Verificar se há notícias no site manualmente")
            
            # Criar feed vazio mas informativo
            xml_vazio = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Notícias da Prefeitura de Fortaleza - {HOJE_BR.strftime("%d/%m/%Y")}</title>
<link>{URL_BASE}</link>
<description>Nenhuma notícia nova publicada hoje (executado em {agora_brasilia.strftime("%H:%M")} Brasília)</description>
<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
<ttl>30</ttl>
</channel>
</rss>'''
            
            with open(FEED_FILE, 'w', encoding='utf-8') as f:
                f.write(xml_vazio)
            
            print(f"\n📁 Feed vazio gerado: {FEED_FILE}")
            return True
        
        # ================= GERAR FEED COMPLETO =================
        print(f"\n📥 Processando {noticias_encontradas} notícias...")
        
        # Ordenar por hora
        lista_noticias.sort(key=lambda x: x['hora'], reverse=True)
        
        # Gerar XML
        xml_parts = []
        
        xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_parts.append('<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">')
        xml_parts.append('<channel>')
        xml_parts.append(f'<title>Notícias da Prefeitura de Fortaleza - {HOJE_BR.strftime("%d/%m/%Y")}</title>')
        xml_parts.append(f'<link>{URL_BASE}</link>')
        xml_parts.append(f'<description>Notícias publicadas HOJE ({HOJE_BR.strftime("%d/%m/%Y")}) - {noticias_encontradas} notícias</description>')
        xml_parts.append('<language>pt-br</language>')
        xml_parts.append(f'<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
        xml_parts.append('<ttl>60</ttl>')
        
        for noticia in lista_noticias:
            guid = hashlib.md5(noticia['link'].encode()).hexdigest()[:12]
            
            # Criar data para RSS
            try:
                hora_partes = noticia['hora'].split(':')
                hora = int(hora_partes[0]) if len(hora_partes) > 0 else 12
                minuto = int(hora_partes[1]) if len(hora_partes) > 1 else 0
                data_rss = datetime(HOJE_BR.year, HOJE_BR.month, HOJE_BR.day, hora, minuto, 0, tzinfo=timezone.utc)
                data_rss_str = data_rss.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except:
                data_rss_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            xml_parts.append('<item>')
            xml_parts.append(f'<title>{html.escape(noticia["titulo"])}</title>')
            xml_parts.append(f'<link>{noticia["link"]}</link>')
            xml_parts.append(f'<guid isPermaLink="false">fortaleza-{HOJE_BR.strftime("%Y%m%d")}-{guid}</guid>')
            xml_parts.append(f'<pubDate>{data_rss_str}</pubDate>')
            xml_parts.append(f'<description>{html.escape(noticia["titulo"])}</description>')
            
            # Conteúdo básico (sem extrair página interna para simplificar)
            conteudo = f'<p>{html.escape(noticia["titulo"])}</p>'
            if noticia['imagem']:
                conteudo = f'<img src="{noticia["imagem"]}" alt="{html.escape(noticia["titulo"][:100])}" style="max-width:100%"><br>' + conteudo
            
            conteudo += f'<p><small>Publicado em: {noticia["data_str"]}</small></p>'
            conteudo += f'<p><a href="{noticia["link"]}">Fonte: Prefeitura de Fortaleza</a></p>'
            
            xml_parts.append(f'<content:encoded><![CDATA[ {conteudo} ]]></content:encoded>')
            
            if noticia['imagem']:
                xml_parts.append(f'<enclosure url="{noticia["imagem"]}" type="image/jpeg" length="80000" />')
                xml_parts.append(f'<media:content url="{noticia["imagem"]}" type="image/jpeg" medium="image">')
                xml_parts.append(f'<media:title>{html.escape(noticia["titulo"][:100])}</media:title>')
                xml_parts.append('</media:content>')
            
            xml_parts.append('</item>')
        
        xml_parts.append('</channel>')
        xml_parts.append('</rss>')
        
        # Salvar arquivo
        with open(FEED_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_parts))
        
        # ================= RELATÓRIO FINAL =================
        print("-" * 60)
        print(f"✅ FEED GERADO COM SUCESSO!")
        print(f"📅 Data de referência: {HOJE_BR.strftime('%d/%m/%Y')}")
        print(f"📊 Notícias encontradas: {noticias_encontradas}")
        print(f"📁 Arquivo: {FEED_FILE}")
        print(f"📏 Tamanho: {os.path.getsize(FEED_FILE):,} bytes")
        
        if lista_noticias:
            print(f"\n📋 NOTÍCIAS ENCONTRADAS:")
            for i, n in enumerate(lista_noticias, 1):
                print(f"  {i:2d}. [{n['hora']}] {n['titulo'][:60]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        
        # Criar arquivo de erro
        erro_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>ERRO: Feed Fortaleza - {HOJE_BR.strftime("%d/%m/%Y")}</title>
<link>{URL_BASE}</link>
<description>Erro ao gerar feed</description>
<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
<ttl>5</ttl>
</channel>
</rss>'''
        
        try:
            with open(FEED_FILE, 'w', encoding='utf-8') as f:
                f.write(erro_xml)
        except:
            pass
        
        return False

if __name__ == "__main__":
    print("🚀 upnewsfortaleza.py - VERSÃO COM FUSO HORÁRIO")
    print("=" * 60)
    
    sucesso = criar_feed_fortaleza_hoje()
    
    print("=" * 60)
    print(f"🏁 Status: {'✅ SUCESSO' if sucesso else '❌ FALHA'}")
    
    sys.exit(0 if sucesso else 1)
