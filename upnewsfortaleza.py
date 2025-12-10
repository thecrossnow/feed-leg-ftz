#!/usr/bin/env python3
# upnewsfortaleza.py - Script para GitHub Actions
# Extrai apenas as notícias publicadas no dia atual da Prefeitura de Fortaleza

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

def criar_feed_fortaleza_hoje():
    """
    Extrai TODAS as notícias publicadas HOJE (dia da execução)
    da Prefeitura de Fortaleza, varrendo TODAS as páginas paginadas
    e salva o feed XML no diretório atual.
    """
    
    # ================= CONFIGURAÇÕES =================
    URL_BASE = "https://www.fortaleza.ce.gov.br"
    URL_LISTA = f"{URL_BASE}/noticias"
    
    # Nome do arquivo de saída (mantido para compatibilidade com GitHub Actions)
    HOJE = date.today()
    DATA_STR = HOJE.strftime('%Y%m%d')
    FEED_FILE = f"feed_fortaleza_hoje.xml"  # Nome fixo para o workflow
    FEED_FILE_DATA = f"feed_fortaleza_{DATA_STR}.xml"  # Backup com data
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    # ================= Mapeamento de meses =================
    MESES_PT = {
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
        'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
        'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
    }
    
    print(f"🔍 Buscando notícias publicadas HOJE: {HOJE.strftime('%d/%m/%Y')}")
    print(f"📁 Diretório atual: {os.getcwd()}")
    print(f"📄 Arquivo será salvo como: {FEED_FILE}")
    print("-" * 60)
    
    try:
        lista_noticias = []
        links_processados = set()
        
        # ================= FUNÇÃO PARA PROCESSAR PÁGINAS =================
        def processar_pagina(url_pagina, pagina_num):
            """Processa uma página específica da listagem de notícias"""
            print(f"📄 Página {pagina_num}: {urlparse(url_pagina).path}")
            
            try:
                # Request com timeout e verificação
                response = requests.get(url_pagina, headers=HEADERS, timeout=15)
                response.raise_for_status()
                
                # Verificar encoding
                if response.encoding is None or response.encoding.lower() != 'utf-8':
                    response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Encontrar containers de notícias
                noticias_containers = soup.find_all('div', class_='blog-post-item')
                print(f"   📦 Encontrados {len(noticias_containers)} containers de notícias")
                
                noticias_hoje_pagina = 0
                encontrou_noticia_antiga = False
                
                for container in noticias_containers:
                    try:
                        # Extrair data da notícia
                        data_div = container.find('div', class_='blog-time')
                        if not data_div:
                            continue
                        
                        span_data = data_div.find('span', class_='font-lato')
                        if not span_data:
                            continue
                        
                        data_str = span_data.get_text(strip=True)
                        if not data_str:
                            continue
                        
                        # Converter data do formato "Quarta, 10 Dezembro 2025 14:54"
                        data_noticia = None
                        hora_noticia = "00:00"
                        
                        try:
                            partes = data_str.split()
                            if len(partes) >= 4:
                                dia_noticia = int(partes[1])
                                mes_pt = partes[2].lower()
                                ano_noticia = int(partes[3])
                                
                                if mes_pt in MESES_PT:
                                    mes_noticia = MESES_PT[mes_pt]
                                    data_noticia = date(ano_noticia, mes_noticia, dia_noticia)
                                    
                                    # Extrair hora se disponível
                                    if len(partes) > 4:
                                        hora_noticia = partes[4]
                        except (ValueError, IndexError, AttributeError) as e:
                            print(f"      ⚠️  Erro ao processar data '{data_str}': {e}")
                            continue
                        
                        if not data_noticia:
                            continue
                        
                        # VERIFICAR SE É NOTÍCIA DE HOJE
                        if data_noticia == HOJE:
                            # Notícia de HOJE - extrair detalhes
                            link_tag = container.find('a', class_='btn-reveal')
                            if not link_tag or not link_tag.get('href'):
                                continue
                            
                            href = link_tag['href']
                            link_url = urljoin(URL_BASE, href)
                            
                            # Evitar duplicatas
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
                            
                            # Extrair descrição/resumo
                            descricao = ""
                            if intro_div:
                                # Pegar primeiro texto significativo após o título
                                textos = []
                                for elemento in intro_div.find_all(['p', 'span', 'div']):
                                    texto = elemento.get_text(strip=True)
                                    if texto and texto != titulo and len(texto) > 20:
                                        textos.append(texto)
                                
                                if textos:
                                    descricao = textos[0][:300]
                            
                            # Extrair imagem destacada
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
                            
                            # Adicionar à lista
                            links_processados.add(link_url)
                            
                            lista_noticias.append({
                                'titulo': titulo[:250],
                                'link': link_url,
                                'descricao': descricao,
                                'data_str': data_str,
                                'data_obj': data_noticia,
                                'imagem': imagem_url,
                                'hora': hora_noticia,
                                'pagina': pagina_num
                            })
                            
                            noticias_hoje_pagina += 1
                            print(f"    ✅ [{hora_noticia}] {titulo[:70]}...")
                            
                        elif data_noticia < HOJE:
                            # Notícia de dia ANTERIOR
                            encontrou_noticia_antiga = True
                            diferenca = (HOJE - data_noticia).days
                            if diferenca <= 3:  # Log apenas para últimos 3 dias
                                print(f"    ⏰ {data_noticia.strftime('%d/%m')} ({diferenca} dia(s) atrás)")
                    
                    except Exception as e:
                        print(f"    ⚠️  Erro no container: {str(e)[:50]}")
                        continue
                
                print(f"   📊 Notícias de HOJE nesta página: {noticias_hoje_pagina}")
                
                # ================= ENCONTRAR PRÓXIMA PÁGINA =================
                proxima_url = None
                paginador = soup.find('div', class_='news-pagination')
                
                if paginador:
                    # *** CORREÇÃO DO DEPRECATION WARNING ***
                    # Usar 'string=' em vez de 'text='
                    link_proximo = paginador.find('a', string=lambda t: t and any(
                        palavra in str(t).lower() for palavra in ['próximo', 'next', '»', '>']
                    ))
                    
                    # Fallback: procurar por classe específica
                    if not link_proximo:
                        link_proximo = paginador.find('li', class_='pagination-next')
                        if link_proximo:
                            link_proximo = link_proximo.find('a')
                    
                    if link_proximo and link_proximo.get('href'):
                        href_proximo = link_proximo['href']
                        proxima_url = urljoin(URL_BASE, href_proximo)
                        
                        # Evitar loop infinito
                        if proxima_url == url_pagina:
                            proxima_url = None
                            print("   ⚠️  Próxima URL igual à atual, parando paginação")
                
                # Decidir se continua varrendo páginas
                continuar_varredura = True
                if encontrou_noticia_antiga and noticias_hoje_pagina == 0:
                    continuar_varredura = False
                    print("   ⏹️  Apenas notícias antigas, parando varredura")
                
                return noticias_hoje_pagina, proxima_url, continuar_varredura
                
            except requests.exceptions.RequestException as e:
                print(f"   ❌ Erro de rede: {e}")
                return 0, None, False
            except Exception as e:
                print(f"   ❌ Erro geral: {e}")
                return 0, None, False
        
        # ================= VARRE TODAS AS PÁGINAS =================
        pagina_atual = 1
        url_atual = URL_LISTA
        total_noticias_hoje = 0
        max_paginas = 15  # Limite de segurança
        
        while url_atual and pagina_atual <= max_paginas:
            noticias_pagina, proxima_url, continuar = processar_pagina(url_atual, pagina_atual)
            total_noticias_hoje += noticias_pagina
            
            if not continuar or not proxima_url:
                break
            
            pagina_atual += 1
            url_atual = proxima_url
            
            # Pausa para respeitar o servidor
            time.sleep(1.5)
        
        print("-" * 60)
        print(f"📈 VARREURA COMPLETA: {pagina_atual} página(s) processada(s)")
        
        # ================= VERIFICAR SE ENCONTROU NOTÍCIAS =================
        if total_noticias_hoje == 0:
            print(f"ℹ️  Nenhuma notícia publicada HOJE ({HOJE.strftime('%d/%m/%Y')}) encontrada.")
            print("   Gerando feed vazio para manter o fluxo do GitHub Actions...")
            
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
            
            # Salvar arquivo principal
            with open(FEED_FILE, 'w', encoding='utf-8') as f:
                f.write(xml_vazio)
            
            # Também salvar backup com data
            with open(FEED_FILE_DATA, 'w', encoding='utf-8') as f:
                f.write(xml_vazio)
            
            print(f"📁 Feed vazio gerado: {FEED_FILE}")
            print(f"📁 Backup com data: {FEED_FILE_DATA}")
            
            # GitHub Actions precisa que o arquivo exista mesmo se vazio
            return True
        
        print(f"🎯 TOTAL DE NOTÍCIAS DE HOJE ENCONTRADAS: {total_noticias_hoje}")
        
        # ================= ORDENAR POR HORA =================
        lista_noticias.sort(key=lambda x: x['hora'], reverse=True)
        
        # ================= EXTRAIR CONTEÚDO COMPLETO =================
        print(f"\n📥 Extraindo conteúdo completo das {len(lista_noticias)} notícias...")
        
        noticias_completas = []
        
        for i, noticia in enumerate(lista_noticias, 1):
            try:
                # Respeitar o servidor
                time.sleep(2)
                
                print(f"🔗 ({i}/{len(lista_noticias)}) [{noticia['hora']}] {noticia['link'][:70]}...")
                
                # Acessar página da notícia
                resp = requests.get(noticia['link'], headers=HEADERS, timeout=15)
                
                if resp.status_code != 200:
                    print(f"    ⚠️  HTTP {resp.status_code}, usando apenas resumo")
                    # Usar dados básicos mesmo com erro
                    noticia['conteudo'] = f'<p>{noticia["descricao"] or noticia["titulo"]}</p>'
                    noticias_completas.append(noticia)
                    continue
                
                # Processar página da notícia
                resp.encoding = 'utf-8'
                soup_noticia = BeautifulSoup(resp.content, 'html.parser')
                
                # Atualizar título se encontrar um melhor
                titulo_tag = soup_noticia.find('h1', class_='bold') or \
                            soup_noticia.find('h1') or \
                            soup_noticia.find('h2')
                
                if titulo_tag and titulo_tag.get_text(strip=True):
                    noticia['titulo'] = titulo_tag.get_text(strip=True)[:250]
                
                # Buscar imagem melhor se não tiver
                if not noticia['imagem'] or 'placeholder' in str(noticia['imagem']).lower():
                    img_figure = soup_noticia.find('figure', class_='blog-item-small-image')
                    if img_figure:
                        img = img_figure.find('img')
                    else:
                        # Buscar qualquer imagem destacada
                        img = soup_noticia.find('img', class_='img-responsive') or \
                              soup_noticia.find('img', class_='img-fluid') or \
                              soup_noticia.find('img', {'src': re.compile(r'\.(jpg|jpeg|png|gif)$', re.I)})
                    
                    if img and img.get('src'):
                        src = img['src']
                        if src and not src.startswith(('http://', 'https://', 'data:')):
                            noticia['imagem'] = urljoin(URL_BASE, src)
                        else:
                            noticia['imagem'] = src
                
                # Extrair conteúdo principal
                conteudo_html = ""
                
                # Estratégias para encontrar conteúdo
                div_conteudo = soup_noticia.find('div', class_='item-page') or \
                             soup_noticia.find('div', {'itemprop': 'articleBody'}) or \
                             soup_noticia.find('article') or \
                             soup_noticia.find('div', class_='blog-item-small-content') or \
                             soup_noticia.find('div', id=re.compile(r'content|conteudo|article', re.I))
                
                if div_conteudo:
                    # Limpar elementos indesejados
                    for elemento in div_conteudo.find_all(['script', 'style', 'iframe', 'nav', 'aside', 'form', 'button']):
                        elemento.decompose()
                    
                    # Remover atributos de estilo e classe
                    for tag in div_conteudo.find_all(True):
                        # Manter apenas atributos essenciais
                        attrs_to_keep = {}
                        if tag.name == 'a' and tag.get('href'):
                            href = tag['href']
                            if not href.startswith(('http://', 'https://')):
                                href = urljoin(noticia['link'], href)
                            attrs_to_keep['href'] = href
                        if tag.name == 'img' and tag.get('src'):
                            src = tag['src']
                            if not src.startswith(('http://', 'https://')):
                                src = urljoin(noticia['link'], src)
                            attrs_to_keep['src'] = src
                            if tag.get('alt'):
                                attrs_to_keep['alt'] = tag['alt'][:100]
                        
                        tag.attrs = attrs_to_keep
                    
                    # Converter para HTML
                    conteudo_html = str(div_conteudo)
                    
                    # Limpar HTML excessivo
                    conteudo_html = re.sub(r'\n\s*\n+', '\n', conteudo_html)
                    conteudo_html = re.sub(r'<br\s*/?>\s*<br\s*/?>', '<br/>', conteudo_html)
                
                # Fallback se conteúdo for muito pequeno
                if not conteudo_html or len(conteudo_html) < 200:
                    conteudo_html = f'<p>{noticia["descricao"] or noticia["titulo"]}</p>'
                
                # Adicionar imagem destacada no início
                if noticia['imagem']:
                    img_html = f'<div class="imagem-destaque" style="margin-bottom: 20px;">'
                    img_html += f'<img src="{noticia["imagem"]}" alt="{html.escape(noticia["titulo"][:100])}" '
                    img_html += 'style="max-width: 100%; height: auto; border-radius: 5px;">'
                    img_html += '</div>'
                    conteudo_html = img_html + conteudo_html
                
                # Adicionar fonte no final
                fonte_html = f'''
                <div style="margin-top: 25px; padding: 15px; background: #f8f9fa; 
                     border-left: 4px solid #0073aa; font-size: 14px; color: #495057;">
                    <p style="margin: 0 0 8px 0;"><strong>📅 Publicado em:</strong> {noticia['data_str']}</p>
                    <p style="margin: 0;"><strong>📌 Fonte:</strong> 
                    <a href="{noticia['link']}" target="_blank" style="color: #0073aa; text-decoration: none;">
                    Prefeitura de Fortaleza - Ver notícia original</a></p>
                </div>
                '''
                conteudo_html += fonte_html
                
                # Preparar notícia final
                noticia_final = {
                    'titulo': noticia['titulo'],
                    'link': noticia['link'],
                    'imagem': noticia['imagem'],
                    'conteudo': conteudo_html,
                    'data_str': noticia['data_str'],
                    'hora': noticia['hora']
                }
                
                noticias_completas.append(noticia_final)
                print(f"    ✅ Conteúdo extraído ({len(conteudo_html):,} caracteres)")
                
            except Exception as e:
                print(f"    ❌ Erro: {str(e)[:60]}")
                # Adicionar notícia básica mesmo com erro
                noticias_completas.append(noticia)
                continue
        
        # ================= GERAR XML RSS =================
        xml_parts = []
        
        xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_parts.append('<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">')
        xml_parts.append('<channel>')
        xml_parts.append(f'<title>Notícias da Prefeitura de Fortaleza - {HOJE.strftime("%d/%m/%Y")}</title>')
        xml_parts.append(f'<link>{URL_BASE}</link>')
        xml_parts.append(f'<description>Notícias publicadas HOJE ({HOJE.strftime("%d/%m/%Y")}) pela Prefeitura de Fortaleza - {len(noticias_completas)} notícias encontradas</description>')
        xml_parts.append('<language>pt-br</language>')
        xml_parts.append('<generator>upnewsfortaleza.py v2.0 (GitHub Actions)</generator>')
        xml_parts.append(f'<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
        xml_parts.append(f'<pubDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</pubDate>')
        xml_parts.append('<ttl>60</ttl>')
        
        for noticia in noticias_completas:
            guid = hashlib.md5(noticia['link'].encode()).hexdigest()[:12]
            
            # Processar data para formato RSS
            data_rss = ""
            try:
                # Extrair hora para timestamp mais preciso
                hora_partes = noticia['hora'].split(':')
                if len(hora_partes) >= 2:
                    hora = int(hora_partes[0])
                    minuto = int(hora_partes[1])
                else:
                    hora, minuto = 12, 0
                
                data_rss_obj = datetime(HOJE.year, HOJE.month, HOJE.day, hora, minuto, 0, tzinfo=timezone.utc)
                data_rss = data_rss_obj.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except:
                data_rss = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            xml_parts.append('<item>')
            xml_parts.append(f'<title>{html.escape(noticia["titulo"])}</title>')
            xml_parts.append(f'<link>{noticia["link"]}</link>')
            xml_parts.append(f'<guid isPermaLink="false">fortaleza-{HOJE.strftime("%Y%m%d")}-{guid}</guid>')
            xml_parts.append(f'<pubDate>{data_rss}</pubDate>')
            xml_parts.append(f'<description>{html.escape(noticia["titulo"][:150])} (Publicado: {noticia["hora"]})</description>')
            
            # Content:encoded já inclui imagem e formatação
            xml_parts.append(f'<content:encoded><![CDATA[ {noticia["conteudo"]} ]]></content:encoded>')
            
            # Incluir imagem também como enclosure/media
            if noticia['imagem']:
                xml_parts.append(f'<enclosure url="{noticia["imagem"]}" type="image/jpeg" length="80000" />')
                xml_parts.append(f'<media:content url="{noticia["imagem"]}" type="image/jpeg" medium="image">')
                xml_parts.append(f'<media:title>{html.escape(noticia["titulo"][:100])}</media:title>')
                xml_parts.append(f'<media:description>{html.escape(noticia["titulo"][:200])}</media:description>')
                xml_parts.append('</media:content>')
            
            xml_parts.append('</item>')
        
        xml_parts.append('</channel>')
        xml_parts.append('</rss>')
        
        # ================= SALVAR ARQUIVOS =================
        # Salvar arquivo principal (feed_fortaleza_hoje.xml)
        with open(FEED_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_parts))
        
        # Salvar backup com data no nome
        with open(FEED_FILE_DATA, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_parts))
        
        # ================= RELATÓRIO FINAL =================
        print("-" * 60)
        print(f"✅ FEED GERADO COM SUCESSO!")
        print(f"📅 Data de referência: {HOJE.strftime('%d/%m/%Y')}")
        print(f"📊 Notícias processadas: {len(noticias_completas)}")
        print(f"📖 Páginas varridas: {pagina_atual}")
        print(f"📁 Arquivo principal: {FEED_FILE}")
        print(f"📁 Backup com data: {FEED_FILE_DATA}")
        print(f"📏 Tamanho do arquivo: {os.path.getsize(FEED_FILE):,} bytes")
        
        # Resumo das notícias
        if noticias_completas:
            print(f"\n📋 RESUMO DAS NOTÍCIAS:")
            for i, n in enumerate(noticias_completas, 1):
                print(f"  {i:2d}. [{n['hora']}] {n['titulo'][:65]}...")
        
        # Informação para GitHub Actions
        print(f"\n🔗 URL do feed (após commit no GitHub):")
        print(f"   https://raw.githubusercontent.com/SEU-USUARIO/SEU-REPOSITORIO/main/{FEED_FILE}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        
        # Criar arquivo de erro para o GitHub Actions não falhar completamente
        erro_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>ERRO: Feed Fortaleza - {HOJE.strftime("%d/%m/%Y")}</title>
<link>{URL_BASE}</link>
<description>Erro ao gerar feed: {str(e)[:100]}</description>
<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
<ttl>5</ttl>
</channel>
</rss>'''
        
        try:
            with open(FEED_FILE, 'w', encoding='utf-8') as f:
                f.write(erro_xml)
            print(f"⚠️  Arquivo de erro gerado: {FEED_FILE}")
        except:
            pass
        
        return False

if __name__ == "__main__":
    # Log inicial para GitHub Actions
    print("=" * 60)
    print("🚀 upnewsfortaleza.py - INICIANDO")
    print("=" * 60)
    
    # Executar função principal
    sucesso = criar_feed_fortaleza_hoje()
    
    print("=" * 60)
    print("🏁 upnewsfortaleza.py - FINALIZADO")
    print(f"📋 Status: {'✅ SUCESSO' if sucesso else '❌ FALHA'}")
    print("=" * 60)
    
    # Terminar com código de saída apropriado
    sys.exit(0 if sucesso else 1)
