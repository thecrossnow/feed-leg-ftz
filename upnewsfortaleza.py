#!/usr/bin/env python3
# upnewsfortaleza.py - VERSÃO OTIMIZADA PARA GITHUB ACTIONS

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta, date
import html
import hashlib
import time
from urllib.parse import urljoin, urlparse
import re
import os
import sys

def extrair_conteudo_completo(url_noticia, headers):
    """
    Acessa a URL individual da notícia e extrai:
    1. Conteúdo completo do artigo
    2. Imagem destacada de alta qualidade
    3. Título refinado (se disponível)
    """
    try:
        print(f"    🌐 Acessando: {url_noticia[:70]}...")
        
        response = requests.get(url_noticia, headers=headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. TENTAR ENCONTRAR O CONTEÚDO PRINCIPAL
        conteudo_completo = ""
        
        # Lista de seletores possíveis para o conteúdo principal
        seletores_conteudo = [
            'div.itemFullText',           # Seletor mais comum
            'article .content',
            'div.article-body',
            'div.post-content',
            'div.entry-content',
            'div.conteudo-noticia',
            'div.texto-noticia',
            'section.single-article',
            'div.com-content-article__body',
            'article',
            'div.content',
            'div.blog-item-full-content'
        ]
        
        conteudo_encontrado = False
        
        for seletor in seletores_conteudo:
            container = soup.select_one(seletor)
            if container:
                # Fazer uma cópia para não modificar o original
                conteudo = BeautifulSoup(str(container), 'html.parser')
                
                # Remover elementos indesejados
                elementos_remover = ['script', 'style', 'iframe', 'nav', 'aside']
                for tag in conteudo.find_all(elementos_remover):
                    tag.decompose()
                
                # Remover elementos de compartilhamento/anúncios por classe
                classes_para_remover = [
                    'social-share', 'share-buttons', 'compartilhar',
                    'related-posts', 'posts-relacionados',
                    'comments', 'comentarios', 'newsletter',
                    'ad', 'ads', 'advertisement'
                ]
                
                for elemento in conteudo.find_all(True):
                    if elemento.get('class'):
                        classes = elemento.get('class')
                        if any(cls in str(classes) for cls in classes_para_remover):
                            elemento.decompose()
                            continue
                
                # Limpar atributos (manter estrutura)
                for tag in conteudo.find_all(True):
                    if tag.name == 'img':
                        # Para imagens: manter src, alt e tornar responsiva
                        attrs = dict(tag.attrs)
                        for attr in list(attrs.keys()):
                            if attr not in ['src', 'alt', 'title']:
                                del tag[attr]
                        if 'style' not in tag.attrs:
                            tag['style'] = 'max-width:100%; height:auto;'
                    elif tag.name == 'a':
                        # Para links: manter apenas href
                        attrs = dict(tag.attrs)
                        for attr in list(attrs.keys()):
                            if attr != 'href':
                                del tag[attr]
                    else:
                        # Para outras tags: remover atributos de estilo
                        if 'style' in tag.attrs:
                            del tag['style']
                        if 'class' in tag.attrs:
                            del tag['class']
                
                conteudo_completo = str(conteudo)
                conteudo_encontrado = True
                print(f"    ✅ Conteúdo encontrado com seletor: {seletor}")
                break
        
        # Se não encontrou conteúdo, usar um fallback
        if not conteudo_encontrado:
            print("    ⚠️  Conteúdo não encontrado, usando método alternativo...")
            
            # Tentar pegar todos os parágrafos do artigo
            article_tag = soup.find('article') or soup.find('div', {'role': 'main'})
            if article_tag:
                paragraphs = article_tag.find_all(['p', 'h2', 'h3', 'h4', 'li'])
                if paragraphs:
                    conteudo_completo = ''.join(str(p) for p in paragraphs)
                    conteudo_encontrado = True
        
        # Se ainda não tem conteúdo, usar descrição como fallback
        if not conteudo_completo:
            print("    ⚠️  Conteúdo muito curto ou não encontrado")
            return None
        
        # 2. EXTRAIR IMAGEM DESTACADA (para WordPress)
        imagem_destacada = None
        
        # Prioridade 1: Meta tags Open Graph (mais confiável)
        meta_og = soup.find('meta', property='og:image')
        if meta_og and meta_og.get('content'):
            imagem_destacada = meta_og['content']
            print("    🖼️  Imagem via Open Graph")
        
        # Prioridade 2: Meta tag Twitter
        if not imagem_destacada:
            meta_twitter = soup.find('meta', {'name': 'twitter:image'})
            if meta_twitter and meta_twitter.get('content'):
                imagem_destacada = meta_twitter['content']
                print("    🖼️  Imagem via Twitter Card")
        
        # Prioridade 3: Primeira imagem grande no conteúdo
        if not imagem_destacada:
            img_tags = soup.select('figure img, .featured-image img, .post-thumbnail img, img.wp-post-image')
            for img in img_tags:
                src = img.get('src') or img.get('data-src')
                if src and not src.startswith('data:'):  # Ignorar data URIs
                    imagem_destacada = src
                    print("    🖼️  Imagem via tag <img> no conteúdo")
                    break
        
        # Converter URL relativa para absoluta se necessário
        if imagem_destacada:
            if not imagem_destacada.startswith(('http://', 'https://')):
                if imagem_destacada.startswith('//'):
                    imagem_destacada = 'https:' + imagem_destacada
                elif imagem_destacada.startswith('/'):
                    base_url = '/'.join(url_noticia.split('/')[:3])
                    imagem_destacada = base_url + imagem_destacada
                else:
                    imagem_destacada = urljoin(url_noticia, imagem_destacada)
        
        # 3. TENTAR REFINAR O TÍTULO
        titulo_refinado = ""
        
        # Verificar meta tags primeiro
        meta_title = soup.find('meta', property='og:title') or soup.find('meta', {'name': 'twitter:title'})
        if meta_title and meta_title.get('content'):
            titulo_refinado = meta_title['content']
        else:
            # Buscar no HTML
            title_selectors = ['h1.article-title', 'h1.post-title', 'h1.entry-title', 'h1']
            for selector in title_selectors:
                title_tag = soup.select_one(selector)
                if title_tag and title_tag.get_text(strip=True):
                    titulo_refinado = title_tag.get_text(strip=True)
                    break
        
        # 4. MONTAR CONTEÚDO FINAL PARA RSS
        conteudo_final = ""
        
        # Adicionar imagem destacada no início se existir
        if imagem_destacada:
            img_html = f'''
            <div class="imagem-destaque" style="margin-bottom: 20px; text-align: center;">
                <img src="{imagem_destacada}" alt="{html.escape(titulo_refinado[:100] if titulo_refinado else 'Imagem destacada')}" 
                     style="max-width: 100%; height: auto; border-radius: 4px;">
                <p style="font-size: 12px; color: #666; margin-top: 5px; font-style: italic;">
                    Imagem: Prefeitura de Fortaleza
                </p>
            </div>
            '''
            conteudo_final += img_html
        
        # Adicionar conteúdo extraído
        conteudo_final += conteudo_completo
        
        # Adicionar rodapé com fonte
        fonte_html = f'''
        <div style="margin-top: 30px; padding: 15px; background: #f8f9fa; 
                    border-left: 4px solid #0073aa; border-radius: 4px;
                    font-size: 14px; color: #495057;">
            <p style="margin: 0 0 8px 0;"><strong>📰 Fonte Oficial:</strong></p>
            <p style="margin: 0 0 5px 0;">
                <strong>Prefeitura de Fortaleza</strong> - 
                <a href="{url_noticia}" target="_blank" style="color: #0056b3; text-decoration: none;">
                    🔗 Acessar notícia original
                </a>
            </p>
        </div>
        '''
        
        conteudo_final += fonte_html
        
        # Contar caracteres do texto limpo
        texto_limpo = BeautifulSoup(conteudo_completo, 'html.parser').get_text(strip=True)
        print(f"    📏 Conteúdo: {len(texto_limpo):,} caracteres de texto")
        if imagem_destacada:
            print(f"    🖼️  Imagem destacada: {imagem_destacada[:80]}...")
        
        return {
            'conteudo': conteudo_final,
            'imagem_destacada': imagem_destacada,
            'titulo_refinado': titulo_refinado
        }
        
    except requests.exceptions.RequestException as e:
        print(f"    ❌ Erro de rede: {e}")
        return None
    except Exception as e:
        print(f"    ❌ Erro ao extrair conteúdo: {str(e)[:50]}")
        return None

def criar_feed_fortaleza():
    """
    Versão otimizada para GitHub Actions - considera fuso horário
    """
    
    print("🚀 upnewsfortaleza.py - GITHUB ACTIONS")
    print("=" * 60)
    
    # ================= CONFIGURAÇÃO PARA GITHUB =================
    URL_BASE = "https://www.fortaleza.ce.gov.br"
    URL_LISTA = f"{URL_BASE}/noticias"
    FEED_FILE = "feed_fortaleza_hoje.xml"
    
    # IMPORTANTE: GitHub roda em UTC, Brasil é UTC-3
    # Se for entre 00:00-03:00 UTC, ainda é "ontem" no Brasil
    # Se for depois das 03:00 UTC, é "hoje" no Brasil
    utc_agora = datetime.now(timezone.utc)
    hora_utc = utc_agora.hour
    
    if hora_utc < 3:  # Antes das 03:00 UTC = antes das 00:00 em Brasília
        # Usar data de ontem (ainda é o dia anterior no Brasil)
        HOJE = (utc_agora - timedelta(days=1)).date()
        print(f"⚠️  Ajuste de fuso: UTC {hora_utc:02d}:00 = Brasil {(hora_utc+21)%24:02d}:00 (dia anterior)")
    else:
        # Usar data atual
        HOJE = utc_agora.date()
        print(f"✅ Fuso correto: UTC {hora_utc:02d}:00 = Brasil {(hora_utc-3)%24:02d}:00")
    
    print(f"📅 Data de referência (Brasília): {HOJE.strftime('%d/%m/%Y')}")
    print(f"⏰ UTC atual: {utc_agora.strftime('%H:%M')}")
    print("-" * 60)
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9'
    }
    
    MESES = {
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
        'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
        'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
    }
    
    def parse_data(data_str):
        """Converte data em português para objeto date"""
        try:
            data_str = data_str.lower()
            
            # Encontrar mês
            for mes_pt, mes_num in MESES.items():
                if mes_pt in data_str:
                    # Encontrar dia
                    dia_match = re.search(r'(\d{1,2})', data_str)
                    if dia_match:
                        dia = int(dia_match.group(1))
                        # Encontrar ano
                        ano_match = re.search(r'(\d{4})', data_str)
                        ano = int(ano_match.group(1)) if ano_match else HOJE.year
                        return date(ano, mes_num, dia)
        except:
            pass
        return None
    
    try:
        # ================= 1. TESTAR CONEXÃO =================
        print("🔍 Testando conexão com o site...")
        test_response = requests.get(URL_BASE, headers=HEADERS, timeout=10)
        if test_response.status_code == 200:
            print("✅ Conexão OK")
        else:
            print(f"⚠️  Status: {test_response.status_code}")
        
        # ================= 2. COLETAR NOTÍCIAS =================
        print("\n📰 Coletando notícias...")
        
        noticias_hoje = []
        pagina = 1
        url = URL_LISTA
        
        while url and pagina <= 3:  # Limitar a 3 páginas para GitHub
            print(f"📄 Página {pagina}")
            
            try:
                response = requests.get(url, headers=HEADERS, timeout=15)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.content, 'html.parser')
                
                containers = soup.find_all('div', class_='blog-post-item')
                print(f"   📦 Notícias na página: {len(containers)}")
                
                if len(containers) == 0:
                    print("   ⚠️  Nenhuma notícia encontrada na página")
                    break
                
                encontrou_hoje = False
                
                for container in containers:
                    try:
                        # Extrair data
                        data_div = container.find('div', class_='blog-time')
                        if not data_div:
                            continue
                            
                        span_data = data_div.find('span', class_='font-lato')
                        if not span_data:
                            continue
                            
                        data_texto = span_data.get_text(strip=True)
                        print(f"      📝 Data bruta: {data_texto}")
                        
                        data_noticia = parse_data(data_texto)
                        
                        if data_noticia:
                            print(f"      📅 Data convertida: {data_noticia.strftime('%d/%m/%Y')}")
                        
                        if not data_noticia:
                            print(f"      ⚠️  Não consegui converter data")
                            continue
                        
                        # Verificar se é de hoje
                        if data_noticia == HOJE:
                            encontrou_hoje = True
                            
                            # Link
                            link_tag = container.find('a', class_='btn-reveal')
                            if not link_tag or not link_tag.get('href'):
                                continue
                                
                            link_url = urljoin(URL_BASE, link_tag['href'])
                            
                            # Título
                            titulo = ""
                            intro_div = container.find('div', class_='intro')
                            if intro_div:
                                h2_tag = intro_div.find('h2')
                                if h2_tag:
                                    titulo = h2_tag.get_text(strip=True)
                            
                            if not titulo:
                                continue
                            
                            # Descrição (resumo da página principal)
                            descricao = ""
                            if intro_div:
                                for string in intro_div.stripped_strings:
                                    if string and string != titulo and len(string) > 30:
                                        descricao = string[:200]
                                        break
                            
                            # Hora
                            hora = "00:00"
                            hora_match = re.search(r'(\d{1,2}:\d{2})', data_texto)
                            if hora_match:
                                hora = hora_match.group(1)
                            
                            # Imagem da página principal (miniatura)
                            imagem_miniatura = None
                            img_tag = container.find('figure', class_='blog-item-small-image')
                            if img_tag:
                                img = img_tag.find('img')
                                if img and img.get('src'):
                                    src = img['src']
                                    if not src.startswith(('http://', 'https://')):
                                        imagem_miniatura = urljoin(URL_BASE, src)
                                    else:
                                        imagem_miniatura = src
                            
                            noticias_hoje.append({
                                'titulo': titulo,
                                'link': link_url,
                                'descricao': descricao,  # Resumo da página principal
                                'data_texto': data_texto,
                                'imagem_miniatura': imagem_miniatura,
                                'hora': hora,
                                'data_objeto': data_noticia,
                                'conteudo_completo': None,  # Será preenchido depois
                                'imagem_destacada': None   # Será preenchido depois
                            })
                            
                            print(f"    ✅ [{hora}] {titulo[:50]}...")
                        
                        else:
                            diferenca = (HOJE - data_noticia).days
                            if diferenca <= 3:
                                print(f"    ⏰ {data_noticia.strftime('%d/%m')} ({diferenca} dia(s) atrás)")
                    
                    except Exception as e:
                        print(f"    ⚠️  Erro: {str(e)[:30]}")
                        continue
                
                print(f"   📊 Notícias de HOJE nesta página: {sum(1 for n in noticias_hoje if n.get('pagina') == pagina)}")
                
                # Se não encontrou notícias de hoje E já viu algumas páginas, parar
                if not encontrou_hoje and pagina >= 2:
                    print("   ⏹️  Nenhuma notícia de hoje, parando busca")
                    break
                
                # Próxima página
                proxima = None
                paginador = soup.find('div', class_='news-pagination')
                
                if paginador:
                    link_proximo = paginador.find('a', string=lambda t: t and 'próximo' in str(t).lower())
                    
                    if not link_proximo:
                        li_proximo = paginador.find('li', class_='pagination-next')
                        if li_proximo:
                            link_proximo = li_proximo.find('a')
                    
                    if link_proximo and link_proximo.get('href'):
                        proxima = urljoin(URL_BASE, link_proximo['href'])
                        print(f"   🔗 Próxima página encontrada")
                
                if not proxima:
                    break
                
                pagina += 1
                url = proxima
                time.sleep(1)  # Respeitar o servidor
                
            except Exception as e:
                print(f"   ❌ Erro na página {pagina}: {e}")
                break
        
        print("-" * 60)
        print(f"📈 Busca concluída: {pagina} página(s)")
        print(f"🎯 Notícias de HOJE encontradas: {len(noticias_hoje)}")
        
        # ================= 3. EXTRAIR CONTEÚDO COMPLETO =================
        print(f"\n📥 Extraindo conteúdo completo das notícias...")
        print("-" * 60)
        
        noticias_com_conteudo = []
        
        for i, noticia in enumerate(noticias_hoje, 1):
            print(f"\n📰 Notícia {i}/{len(noticias_hoje)}: {noticia['titulo'][:60]}...")
            
            # Aguardar entre requisições para não sobrecarregar o servidor
            if i > 1:
                time.sleep(2)  # 2 segundos entre requisições
            
            # Acessar a página individual da notícia
            conteudo_extraido = extrair_conteudo_completo(noticia['link'], HEADERS)
            
            if conteudo_extraido:
                # Usar título refinado se disponível
                titulo_final = conteudo_extraido['titulo_refinado'] if conteudo_extraido['titulo_refinado'] else noticia['titulo']
                
                # Usar imagem destacada se disponível, senão usar miniatura
                imagem_final = conteudo_extraido['imagem_destacada'] if conteudo_extraido['imagem_destacada'] else noticia['imagem_miniatura']
                
                noticias_com_conteudo.append({
                    'titulo': titulo_final,
                    'link': noticia['link'],
                    'descricao': noticia['descricao'],  # Manter descrição original como fallback
                    'data_texto': noticia['data_texto'],
                    'imagem': imagem_final,
                    'hora': noticia['hora'],
                    'conteudo_completo': conteudo_extraido['conteudo'],
                    'tem_conteudo_completo': True
                })
                
                print(f"    ✅ Conteúdo completo extraído!")
            else:
                print(f"    ⚠️  Usando resumo (não consegui extrair conteúdo completo)")
                
                # Se não conseguiu extrair conteúdo, usar o resumo
                noticias_com_conteudo.append({
                    'titulo': noticia['titulo'],
                    'link': noticia['link'],
                    'descricao': noticia['descricao'],
                    'data_texto': noticia['data_texto'],
                    'imagem': noticia['imagem_miniatura'],
                    'hora': noticia['hora'],
                    'conteudo_completo': None,
                    'tem_conteudo_completo': False
                })
        
        # Contar quantas notícias têm conteúdo completo
        com_conteudo = sum(1 for n in noticias_com_conteudo if n.get('tem_conteudo_completo'))
        print(f"\n📊 Estatísticas:")
        print(f"   Total de notícias: {len(noticias_com_conteudo)}")
        print(f"   Com conteúdo completo: {com_conteudo}")
        print(f"   Apenas resumo: {len(noticias_com_conteudo) - com_conteudo}")
        
        # ================= 4. VERIFICAR RESULTADO =================
        if len(noticias_com_conteudo) == 0:
            print("\n📭 Nenhuma notícia encontrada para hoje")
            print("   Possíveis causas:")
            print("   1. Realmente não há notícias novas")
            print(f"   2. Data de referência: {HOJE.strftime('%d/%m/%Y')}")
            print(f"   3. Hora UTC: {utc_agora.strftime('%H:%M')}")
            print("   4. Site pode estar offline")
            
            # Mesmo sem notícias, criar um feed válido para o GitHub
            xml_vazio = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Notícias Fortaleza - {HOJE.strftime("%d/%m/%Y")}</title>
<link>{URL_BASE}</link>
<description>Sem notícias novas hoje. Última verificação: {utc_agora.strftime("%H:%M")} UTC</description>
<lastBuildDate>{utc_agora.strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
<ttl>30</ttl>
</channel>
</rss>'''
            
            with open(FEED_FILE, 'w', encoding='utf-8') as f:
                f.write(xml_vazio)
            
            print(f"\n📁 Feed vazio gerado (para manter workflow): {FEED_FILE}")
            
            # Criar também arquivo com data no nome (para histórico)
            arquivo_data = f"feed_fortaleza_{HOJE.strftime('%Y%m%d')}.xml"
            with open(arquivo_data, 'w', encoding='utf-8') as f:
                f.write(xml_vazio)
            
            print(f"📁 Backup histórico: {arquivo_data}")
            
            return True  # Sucesso mesmo sem notícias
        
        # ================= 5. GERAR FEED COM NOTÍCIAS =================
        print(f"\n📝 Gerando feed com {len(noticias_com_conteudo)} notícias...")
        
        # Ordenar por hora
        noticias_com_conteudo.sort(key=lambda x: x['hora'], reverse=True)
        
        xml_parts = []
        
        xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_parts.append('<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">')
        xml_parts.append('<channel>')
        xml_parts.append(f'<title>Notícias Fortaleza - {HOJE.strftime("%d/%m/%Y")}</title>')
        xml_parts.append(f'<link>{URL_BASE}</link>')
        xml_parts.append(f'<description>{len(noticias_com_conteudo)} notícias publicadas hoje ({com_conteudo} com conteúdo completo)</description>')
        xml_parts.append('<language>pt-br</language>')
        xml_parts.append(f'<lastBuildDate>{utc_agora.strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
        xml_parts.append('<ttl>60</ttl>')
        
        for noticia in noticias_com_conteudo:
            guid = hashlib.md5(noticia['link'].encode()).hexdigest()[:12]
            
            # Data para RSS
            try:
                hora_partes = noticia['hora'].split(':')
                hora = int(hora_partes[0]) if hora_partes else 12
                minuto = int(hora_partes[1]) if len(hora_partes) > 1 else 0
                data_rss = datetime(HOJE.year, HOJE.month, HOJE.day, hora, minuto, 0, tzinfo=timezone.utc)
                pub_date = data_rss.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except:
                pub_date = utc_agora.strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            xml_parts.append('<item>')
            xml_parts.append(f'<title>{html.escape(noticia["titulo"])}</title>')
            xml_parts.append(f'<link>{noticia["link"]}</link>')
            xml_parts.append(f'<guid isPermaLink="false">fortaleza-{HOJE.strftime("%Y%m%d")}-{guid}</guid>')
            xml_parts.append(f'<pubDate>{pub_date}</pubDate>')
            xml_parts.append(f'<description>{html.escape(noticia["titulo"])} - {noticia["data_texto"]}</description>')
            
            # CONTEÚDO COMPLETO OU RESUMO
            if noticia.get('conteudo_completo'):
                # Usar conteúdo completo extraído
                conteudo = noticia['conteudo_completo']
                xml_parts.append(f'<content:encoded><![CDATA[ {conteudo} ]]></content:encoded>')
            else:
                # Usar resumo (fallback)
                conteudo = f'<h3>{html.escape(noticia["titulo"])}</h3>'
                conteudo += f'<p><strong>Publicado:</strong> {noticia["data_texto"]}</p>'
                
                if noticia.get('imagem'):
                    conteudo += f'<p><img src="{noticia["imagem"]}" alt="{html.escape(noticia["titulo"][:100])}" style="max-width:100%"></p>'
                
                if noticia.get('descricao'):
                    conteudo += f'<p>{html.escape(noticia["descricao"])}</p>'
                
                conteudo += f'<p><a href="{noticia["link"]}" target="_blank">🔗 Ver notícia completa no site</a></p>'
                
                xml_parts.append(f'<content:encoded><![CDATA[ {conteudo} ]]></content:encoded>')
            
            # Imagem (para WordPress)
            if noticia.get('imagem'):
                xml_parts.append(f'<enclosure url="{noticia["imagem"]}" type="image/jpeg" />')
                xml_parts.append(f'<media:content url="{noticia["imagem"]}" type="image/jpeg" medium="image">')
                xml_parts.append(f'<media:title>{html.escape(noticia["titulo"][:100])}</media:title>')
                xml_parts.append('</media:content>')
            
            xml_parts.append('</item>')
        
        xml_parts.append('</channel>')
        xml_parts.append('</rss>')
        
        # Salvar arquivo principal
        with open(FEED_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_parts))
        
        # Salvar backup com data
        arquivo_data = f"feed_fortaleza_{HOJE.strftime('%Y%m%d')}.xml"
        with open(arquivo_data, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_parts))
        
        # ================= 6. RELATÓRIO =================
        print("-" * 60)
        print(f"✅ FEED GERADO COM SUCESSO!")
        print(f"📅 Data: {HOJE.strftime('%d/%m/%Y')}")
        print(f"📊 Notícias: {len(noticias_com_conteudo)} ({com_conteudo} com conteúdo completo)")
        print(f"📁 Arquivo principal: {FEED_FILE}")
        print(f"📁 Backup histórico: {arquivo_data}")
        
        if noticias_com_conteudo:
            print(f"\n📋 NOTÍCIAS ENCONTRADAS:")
            for i, n in enumerate(noticias_com_conteudo, 1):
                conteudo_icon = "📄" if n.get('tem_conteudo_completo') else "📝"
                imagem_icon = "🖼️" if n.get('imagem') else "📷"
                print(f"  {i:2d}. [{n['hora']}] {conteudo_icon}{imagem_icon} {n['titulo'][:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        
        # Criar feed de erro (para o workflow não falhar)
        erro_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>ERRO: Feed Fortaleza</title>
<link>{URL_BASE}</link>
<description>Erro ao gerar feed. Última tentativa: {datetime.now(timezone.utc).strftime("%H:%M")} UTC</description>
<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
<ttl>5</ttl>
</channel>
</rss>'''
        
        try:
            with open(FEED_FILE, 'w', encoding='utf-8') as f:
                f.write(erro_xml)
            print(f"⚠️  Feed de erro gerado: {FEED_FILE}")
        except:
            pass
        
        return False

if __name__ == "__main__":
    sucesso = criar_feed_fortaleza()
    
    print("=" * 60)
    print(f"🏁 Status: {'✅ SUCESSO' if sucesso else '❌ FALHA'}")
    
    sys.exit(0 if sucesso else 1)
