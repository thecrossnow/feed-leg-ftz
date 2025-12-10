#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta, date
import html
import hashlib
import time
from urllib.parse import urljoin, urlparse, parse_qs
import re
import os
import locale

# Configurar locale para português
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')
    except:
        pass

def criar_feed_fortaleza_hoje():
    """
    Extrai TODAS as notícias publicadas HOJE (dia da execução)
    da Prefeitura de Fortaleza, varrendo TODAS as páginas paginadas
    """
    URL_BASE = "https://www.fortaleza.ce.gov.br"
    URL_LISTA = f"{URL_BASE}/noticias"
    FEED_FILE = "feed_fortaleza_hoje.xml"
    
    # Data atual para filtragem
    HOJE = date.today()
    HOJE_DIA = HOJE.day
    HOJE_MES = HOJE.month
    HOJE_ANO = HOJE.year
    
    print(f"🔍 Buscando notícias publicadas HOJE: {HOJE_DIA:02d}/{HOJE_MES:02d}/{HOJE_ANO}")
    print("📖 Varrendo todas as páginas paginadas...")
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9'
    }
    
    try:
        # Mapeamento de meses em português para números
        MESES_PT = {
            'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
            'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
            'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
        }
        
        lista_noticias = []
        links_processados = set()
        
        # 1. FUNÇÃO PARA PROCESSAR UMA PÁGINA ESPECÍFICA
        def processar_pagina(url_pagina, pagina_num):
            """
            Processa uma página específica e retorna:
            - Lista de notícias de hoje encontradas
            - Próxima URL de página (ou None se não houver)
            - Flag indicando se devemos continuar varrendo
            """
            print(f"\n📄 Página {pagina_num}: {url_pagina}")
            
            try:
                response = requests.get(url_pagina, headers=HEADERS, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Encontrar todos os containers de notícias nesta página
                noticias_containers = soup.find_all('div', class_='blog-post-item')
                print(f"   Encontrados {len(noticias_containers)} containers nesta página")
                
                noticias_hoje_pagina = 0
                encontrou_noticia_antiga = False
                
                for container in noticias_containers:
                    try:
                        # Extrair data da notícia
                        data_str = ""
                        data_div = container.find('div', class_='blog-time')
                        if data_div:
                            span_data = data_div.find('span', class_='font-lato')
                            if span_data:
                                data_str = span_data.get_text(strip=True)
                        
                        if not data_str:
                            continue
                        
                        # Converter data do formato "Quarta, 10 Dezembro 2025 14:54"
                        data_noticia = None
                        try:
                            partes = data_str.split()
                            if len(partes) >= 4:
                                dia_noticia = int(partes[1])
                                mes_pt = partes[2].lower()
                                ano_noticia = int(partes[3])
                                
                                if mes_pt in MESES_PT:
                                    mes_noticia = MESES_PT[mes_pt]
                                    data_noticia = date(ano_noticia, mes_noticia, dia_noticia)
                        except (ValueError, IndexError) as e:
                            continue
                        
                        if not data_noticia:
                            continue
                        
                        # VERIFICAR SE É NOTÍCIA DE HOJE
                        if data_noticia == HOJE:
                            # Notícia de HOJE - processar
                            link_tag = container.find('a', class_='btn-reveal')
                            if not link_tag or not link_tag.get('href'):
                                continue
                            
                            href = link_tag['href']
                            link_url = urljoin(URL_BASE, href)
                            
                            if link_url in links_processados:
                                continue
                            
                            # Extrair título
                            intro_div = container.find('div', class_='intro')
                            titulo = ""
                            if intro_div:
                                h2_tag = intro_div.find('h2')
                                if h2_tag:
                                    titulo = h2_tag.get_text(strip=True)
                            
                            if not titulo or len(titulo) < 10:
                                continue
                            
                            # Extrair descrição
                            descricao = ""
                            if intro_div:
                                for texto in intro_div.stripped_strings:
                                    if texto and texto != titulo and len(texto) > 30:
                                        descricao = texto[:300]
                                        break
                            
                            # Extrair imagem
                            imagem_url = None
                            img_tag = container.find('figure', class_='blog-item-small-image')
                            if img_tag:
                                img = img_tag.find('img')
                                if img and img.get('src'):
                                    src = img['src']
                                    if src and not src.startswith(('http://', 'https://', 'data:')):
                                        if src.startswith('/'):
                                            imagem_url = urljoin(URL_BASE, src)
                                        else:
                                            imagem_url = urljoin(f"{URL_BASE}/", src)
                                    else:
                                        imagem_url = src
                            
                            links_processados.add(link_url)
                            
                            lista_noticias.append({
                                'titulo': titulo[:250],
                                'link': link_url,
                                'descricao': descricao,
                                'data_str': data_str,
                                'data_obj': data_noticia,
                                'imagem': imagem_url,
                                'hora': partes[4] if len(partes) > 4 else "00:00",
                                'pagina': pagina_num
                            })
                            
                            noticias_hoje_pagina += 1
                            print(f"    ✅ [{data_str}] {titulo[:60]}...")
                            
                        elif data_noticia < HOJE:
                            # Notícia de dia ANTERIOR
                            encontrou_noticia_antiga = True
                            diferenca = (HOJE - data_noticia).days
                            if diferenca <= 2:  # Log apenas para últimos 2 dias
                                print(f"    ⏰ Notícia anterior: {data_noticia.strftime('%d/%m/%Y')} ({diferenca} dia(s) atrás)")
                        
                    except Exception:
                        continue
                
                print(f"   📊 Notícias de HOJE nesta página: {noticias_hoje_pagina}")
                
                # 2. ENCONTRAR PRÓXIMA PÁGINA (paginador)
                proxima_url = None
                paginador = soup.find('div', class_='news-pagination')
                if paginador:
                    # Encontrar link "Próximo" ou "Next"
                    link_proximo = paginador.find('a', string=lambda t: t and any(palavra in t.lower() for palavra in ['próximo', 'next', '>']))
                    if not link_proximo:
                        # Procurar pelo link com classe 'pagination-next'
                        link_proximo = paginador.find('li', class_='pagination-next')
                        if link_proximo:
                            link_proximo = link_proximo.find('a')
                    
                    if link_proximo and link_proximo.get('href'):
                        href_proximo = link_proximo['href']
                        proxima_url = urljoin(URL_BASE, href_proximo)
                        
                        # Verificar se é a mesma página atual (para evitar loop)
                        if proxima_url == url_pagina:
                            proxima_url = None
                
                # Se não encontrou link próximo, tentar lógica numérica
                if not proxima_url and paginador:
                    # Extrair todos os links numéricos
                    links_numericos = []
                    for link in paginador.find_all('a', class_='pageway'):
                        href = link.get('href')
                        if href:
                            links_numericos.append(href)
                    
                    if links_numericos:
                        # Encontrar o maior número atual
                        numeros = []
                        for href in links_numericos:
                            # Extrair parâmetro start=XX
                            parsed = urlparse(href)
                            query = parse_qs(parsed.query)
                            if 'start' in query:
                                try:
                                    numeros.append(int(query['start'][0]))
                                except:
                                    pass
                        
                        if numeros:
                            maior_numero = max(numeros)
                            # Construir próxima URL baseada no padrão
                            # Supondo padrão: /noticias?start=5, /noticias?start=10, etc.
                            proximo_start = maior_numero + 5
                            proxima_url = f"{URL_BASE}/noticias?start={proximo_start}"
                            
                            # Verificar se já processamos esta página
                            if proxima_url == url_pagina:
                                proxima_url = None
                
                # Decidir se continua varrendo páginas
                continuar_varredura = True
                if encontrou_noticia_antiga and noticias_hoje_pagina == 0:
                    # Se nesta página só tem notícias antigas e nenhuma de hoje
                    # pode parar de varrer (assumindo que as páginas seguintes são mais antigas)
                    continuar_varredura = False
                    print(f"   ⏹️  Apenas notícias antigas nesta página. Parando varredura.")
                
                return noticias_hoje_pagina, proxima_url, continuar_varredura
                
            except Exception as e:
                print(f"   ❌ Erro ao processar página {pagina_num}: {e}")
                return 0, None, False
        
        # 2. PROCESSAR TODAS AS PÁGINAS
        pagina_atual = 1
        url_atual = URL_LISTA
        total_noticias_hoje = 0
        max_paginas = 20  # Limite de segurança para evitar loop infinito
        
        while url_atual and pagina_atual <= max_paginas:
            noticias_pagina, proxima_url, continuar = processar_pagina(url_atual, pagina_atual)
            total_noticias_hoje += noticias_pagina
            
            if not continuar or not proxima_url:
                break
            
            pagina_atual += 1
            url_atual = proxima_url
            
            # Pequena pausa entre páginas
            time.sleep(1)
        
        print(f"\n📈 VARREURA COMPLETA: {pagina_atual} página(s) processada(s)")
        
        # 3. VERIFICAR RESULTADOS
        if total_noticias_hoje == 0:
            print(f"\nℹ️  Nenhuma notícia publicada HOJE ({HOJE.strftime('%d/%m/%Y')}) encontrada.")
            print("   O script será executado novamente amanhã para novas notícias.")
            
            xml_vazio = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Notícias da Prefeitura de Fortaleza - {HOJE.strftime("%d/%m/%Y")}</title>
<link>{URL_BASE}</link>
<description>Nenhuma notícia nova publicada hoje</description>
<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
<ttl>60</ttl>
</channel>
</rss>'''
            
            with open(FEED_FILE, 'w', encoding='utf-8') as f:
                f.write(xml_vazio)
            
            print(f"📁 Arquivo XML vazio gerado: {FEED_FILE}")
            return True
        
        print(f"\n🎯 TOTAL DE NOTÍCIAS DE HOJE ENCONTRADAS: {total_noticias_hoje}")
        
        # 4. Ordenar por hora (mais recente primeiro)
        lista_noticias.sort(key=lambda x: x['hora'], reverse=True)
        
        # 5. Extrair conteúdo completo
        print(f"\n📥 Extraindo conteúdo completo das {len(lista_noticias)} notícias...")
        
        noticias_completas = []
        
        for i, noticia in enumerate(lista_noticias, 1):
            try:
                time.sleep(1.5)
                print(f"🔗 ({i}/{len(lista_noticias)}) [{noticia['hora']}] {noticia['link'][:80]}...")
                
                resp = requests.get(noticia['link'], headers=HEADERS, timeout=30)
                
                if resp.status_code != 200:
                    print(f"    ⚠️  Erro HTTP {resp.status_code}")
                    continue
                
                soup_noticia = BeautifulSoup(resp.content, 'html.parser')
                
                # Buscar título na página interna
                titulo_tag = soup_noticia.find('h1', class_='bold')
                if not titulo_tag:
                    titulo_tag = soup_noticia.find('h1') or soup_noticia.find('h2')
                
                if titulo_tag and titulo_tag.get_text(strip=True):
                    noticia['titulo'] = titulo_tag.get_text(strip=True)[:250]
                
                # Buscar imagem destacada
                if not noticia['imagem']:
                    img_figure = soup_noticia.find('figure', class_='blog-item-small-image')
                    if img_figure:
                        img = img_figure.find('img')
                    else:
                        img = soup_noticia.find('img', class_='img-responsive') or \
                              soup_noticia.find('img', class_='img-fluid')
                    
                    if img and img.get('src'):
                        src = img['src']
                        if src and not src.startswith(('http://', 'https://', 'data:')):
                            noticia['imagem'] = urljoin(URL_BASE, src)
                        else:
                            noticia['imagem'] = src
                
                # Extrair conteúdo
                conteudo_html = ""
                div_conteudo = soup_noticia.find('div', class_='item-page') or \
                             soup_noticia.find('div', {'itemprop': 'articleBody'}) or \
                             soup_noticia.find('article') or \
                             soup_noticia.find('div', class_='blog-item-small-content')
                
                if div_conteudo:
                    # Limpar elementos indesejados
                    for elemento in div_conteudo.find_all(['script', 'style', 'iframe', 'nav', 'aside']):
                        elemento.decompose()
                    
                    # Manter formatação básica
                    for tag in div_conteudo.find_all(True):
                        if tag.name not in ['p', 'br', 'strong', 'em', 'b', 'i', 'a', 'img', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4']:
                            tag.unwrap()
                    
                    conteudo_html = str(div_conteudo)
                
                if not conteudo_html or len(conteudo_html) < 200:
                    conteudo_html = f'<p>{noticia["descricao"] or noticia["titulo"]}</p>'
                
                # Adicionar imagem
                if noticia['imagem']:
                    img_html = f'<div class="imagem-destaque"><img src="{noticia["imagem"]}" alt="{html.escape(noticia["titulo"][:100])}" style="max-width:100%; height:auto; margin-bottom:20px;"></div>'
                    conteudo_html = img_html + conteudo_html
                
                # Adicionar fonte
                fonte_html = f'''
                <div style="margin-top:20px; padding:10px; background:#f5f5f5; border-left:3px solid #0073aa; font-size:13px; color:#666;">
                    <p style="margin:0;"><strong>Publicado em:</strong> {noticia['data_str']}<br>
                    <strong>Fonte:</strong> Prefeitura de Fortaleza - <a href="{noticia['link']}" target="_blank">Ver notícia original</a></p>
                </div>
                '''
                conteudo_html += fonte_html
                
                noticias_completas.append({
                    'titulo': noticia['titulo'],
                    'link': noticia['link'],
                    'imagem': noticia['imagem'],
                    'conteudo': conteudo_html,
                    'data_str': noticia['data_str'],
                    'hora': noticia['hora'],
                    'pagina': noticia['pagina']
                })
                
                print(f"    ✅ Conteúdo extraído ({len(conteudo_html)} chars)")
                
            except Exception as e:
                print(f"    ❌ Erro: {str(e)[:80]}...")
                continue
        
        # 6. Gerar XML RSS
        xml_parts = []
        
        xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_parts.append('<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">')
        xml_parts.append('<channel>')
        xml_parts.append(f'<title>Notícias da Prefeitura de Fortaleza - {HOJE.strftime("%d/%m/%Y")}</title>')
        xml_parts.append(f'<link>{URL_BASE}</link>')
        xml_parts.append(f'<description>Todas as notícias publicadas HOJE ({HOJE.strftime("%d/%m/%Y")}) pela Prefeitura de Fortaleza - {len(noticias_completas)} notícias encontradas</description>')
        xml_parts.append('<language>pt-br</language>')
        xml_parts.append(f'<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
        xml_parts.append(f'<pubDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</pubDate>')
        xml_parts.append('<ttl>60</ttl>')
        
        for noticia in noticias_completas:
            guid = hashlib.md5(noticia['link'].encode()).hexdigest()[:12]
            
            # Data para RSS
            try:
                hora_partes = noticia['hora'].split(':')
                if len(hora_partes) >= 2:
                    hora = int(hora_partes[0])
                    minuto = int(hora_partes[1])
                else:
                    hora, minuto = 12, 0
                
                data_rss_obj = datetime(HOJE_ANO, HOJE_MES, HOJE_DIA, hora, minuto, 0, tzinfo=timezone.utc)
                data_rss = data_rss_obj.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except:
                data_rss = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            xml_parts.append('<item>')
            xml_parts.append(f'<title>{html.escape(noticia["titulo"])}</title>')
            xml_parts.append(f'<link>{noticia["link"]}</link>')
            xml_parts.append(f'<guid isPermaLink="false">fortaleza-{HOJE.strftime("%Y%m%d")}-{guid}</guid>')
            xml_parts.append(f'<pubDate>{data_rss}</pubDate>')
            xml_parts.append(f'<description>{html.escape(noticia["titulo"][:150])} (Publicado: {noticia["hora"]})</description>')
            
            xml_parts.append(f'<content:encoded><![CDATA[ {noticia["conteudo"]} ]]></content:encoded>')
            
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
        
        print(f"\n✅ FEED DIÁRIO COMPLETO GERADO: {FEED_FILE}")
        print(f"📅 Data: {HOJE.strftime('%d/%m/%Y')}")
        print(f"📊 Notícias encontradas: {len(noticias_completas)}")
        print(f"📖 Páginas varridas: {pagina_atual}")
        print(f"📁 Tamanho do arquivo: {os.path.getsize(FEED_FILE):,} bytes")
        
        # Resumo por página
        if noticias_completas:
            print(f"\n📋 DISTRIBUIÇÃO POR PÁGINA:")
            noticias_por_pagina = {}
            for n in noticias_completas:
                pagina = n.get('pagina', 1)
                noticias_por_pagina[pagina] = noticias_por_pagina.get(pagina, 0) + 1
            
            for pagina, count in sorted(noticias_por_pagina.items()):
                print(f"  Página {pagina}: {count} notícia(s)")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO GERAL: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    criar_feed_fortaleza_hoje()
