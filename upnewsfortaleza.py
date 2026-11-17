#!/usr/bin/env python3
# upnewsfortaleza.py - VERSÃO OTIMIZADA PARA GITHUB ACTIONS

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timezone, timedelta, date
import html
import hashlib
import time
from urllib.parse import urljoin, urlparse, quote, unquote, urlunparse
import re
import os
import sys
import subprocess
import shutil
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def criar_sessao():
    sessao = requests.Session()

    tentativas = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False
    )

    adaptador = HTTPAdapter(max_retries=tentativas)

    sessao.mount("https://", adaptador)
    sessao.mount("http://", adaptador)

    return sessao


SESSAO = criar_sessao()
CURL_BIN = shutil.which('curl') or shutil.which('curl.exe') or 'curl'

HEADERS_PADRAO = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive'
}



def encodificar_url(url):
    if not url:
        return url
    try:
        if url.startswith('data:'):
            return url
        # Decodifica a URL para normalizar
        url_decodificada = unquote(url)
        
        # Se for uma imagem do portal de Fortaleza, passa pelo CDN gratuito do WordPress (Jetpack)
        # Isso contorna o bloqueio de User-Agent/IP/Referer do servidor da prefeitura
        if 'fortaleza.ce.gov.br' in url_decodificada and any(ext in url_decodificada.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            url_clean = url_decodificada
            if url_clean.startswith('https://'):
                url_clean = url_clean[8:]
            elif url_clean.startswith('http://'):
                url_clean = url_clean[7:]
            return f"https://i0.wp.com:443/{url_clean}"
            
        return url_decodificada
    except:
        return url


def requisitar_pagina(url, headers=None, timeout=30):
    """
    Obtém o conteúdo da página ou feed utilizando:
    1. curl nativo com User-Agent curl/8.13.0
    2. Fallback requests com Connection: close
    3. Fallback r.jina.ai para contornar qualquer WAF/bloqueio de datacenter
    Retorna (html_texto, status_code, url_final).
    """
    # 1. Tentar com curl nativo (mais confiável em ambientes CI/CD e Linux)
    try:
        cmd = [
            CURL_BIN,
            '-s',
            '-L',
            '--max-time', str(timeout),
            '-A', 'curl/8.13.0',
            '-H', 'Accept: */*',
            url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if res.returncode == 0 and len(res.stdout) > 500 and ('bobcmn' not in res.stdout and 'DOSL7' not in res.stdout):
            return res.stdout, 200, url
    except Exception as e_curl:
        print(f"    ⚠️ Curl nativo falhou: {e_curl}")

    # 2. Fallback via requests com Connection: close (força novo socket limpo)
    try:
        hdrs = {
            'User-Agent': 'curl/8.13.0',
            'Accept': '*/*',
            'Connection': 'close'
        }
        resp = requests.get(url, headers=hdrs, timeout=(15, 30))
        if resp.status_code == 200 and len(resp.text) > 500 and ('bobcmn' not in resp.text and 'DOSL7' not in resp.text):
            return resp.text, resp.status_code, resp.url
    except Exception as e_req:
        pass

    # 3. Fallback via r.jina.ai (leitor em nuvem com headless browser que executa JS do WAF)
    try:
        jina_url = f"https://r.jina.ai/{url}"
        resp_jina = requests.get(jina_url, timeout=(15, 30))
        if resp_jina.status_code == 200 and len(resp_jina.text) > 300:
            txt = resp_jina.text
            if '<?xml' in txt:
                txt = txt[txt.find('<?xml'):].strip()
            elif '<rss' in txt:
                txt = txt[txt.find('<rss'):].strip()
            return txt, resp_jina.status_code, url
    except Exception as e_jina:
        pass

    return None, 0, url

def extrair_conteudo_completo(url_noticia, headers, imagem_miniatura=None):
    """
    Acessa a URL individual da notícia e extrai:
    1. Conteúdo completo do artigo
    2. Imagem destacada de alta qualidade
    3. Título refinado (se disponível)
    """
    try:
        print(f"    🌐 Acessando: {url_noticia[:70]}...")

        html_texto, status_code, url_final = requisitar_pagina(url_noticia, headers=headers, timeout=(15, 30))
        if not html_texto:
            print("    ❌ Não foi possível carregar a notícia")
            return None

        soup = BeautifulSoup(html_texto, 'html.parser')
        print("URL acessada:", url_final)
        print("Status HTTP:", status_code)
        print("Título da página:", soup.title.get_text(strip=True) if soup.title else "Sem título")
        print("HTML recebido (início):", html_texto[:500])
        
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
            'div.noticia-conteudo',
            'div.conteudo',
            'section#all-news',
            'section.single-article',
            'div.com-content-article__body',
            'article',
            'div.content',
            'div.blog-item-full-content'
        ]
        
        conteudo_encontrado = False
        container_conteudo_original = None
        
        for seletor in seletores_conteudo:
            container = soup.select_one(seletor)
            if container:
                container_conteudo_original = container
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
                
                # Limpar atributos (manter estrutura) e converter links relativos para absolutos codificados
                for tag in conteudo.find_all(True):
                    if tag.name == 'img':
                        # Suportar lazy load (buscar o link real em atributos de dados antes)
                        possible_src_attrs = ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-actual-src']
                        src = None
                        for attr in possible_src_attrs:
                            val = tag.get(attr)
                            if val and not val.startswith('data:'):
                                src = val
                                break
                        if not src:
                            src = tag.get('src')
                            
                        if src:
                            src = src.strip().replace('\n', '').replace('\r', '')
                            # Converter para absoluta se necessário
                            if not src.startswith(('http://', 'https://', 'data:')):
                                if src.startswith('//'):
                                    src = 'https:' + src
                                elif src.startswith('/'):
                                    base_url = '/'.join(url_noticia.split('/')[:3])
                                    src = base_url + src
                                else:
                                    src = urljoin(url_noticia, src)
                            tag['src'] = encodificar_url(src)
                            
                        # Limpar outros atributos para não quebrar no WordPress
                        attrs = dict(tag.attrs)
                        for attr in list(attrs.keys()):
                            if attr not in ['src', 'alt', 'title']:
                                del tag[attr]
                        tag['style'] = 'max-width:100%; height:auto;'
                        
                    elif tag.name == 'a':
                        # Converter link relativo para absoluto
                        href = tag.get('href')
                        if href:
                            href = href.strip().replace('\n', '').replace('\r', '')
                            if not href.startswith(('http://', 'https://', 'mailto:', 'tel:', 'javascript:', '#')):
                                if href.startswith('//'):
                                    href = 'https:' + href
                                elif href.startswith('/'):
                                    base_url = '/'.join(url_noticia.split('/')[:3])
                                    href = base_url + href
                                else:
                                    href = urljoin(url_noticia, href)
                            tag['href'] = encodificar_url(href)
                            
                        attrs = dict(tag.attrs)
                        for attr in list(attrs.keys()):
                            if attr != 'href':
                                del tag[attr]
                    else:
                        # Para outras tags: remover atributos de estilo e classe
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
        
        # Prioridade 3: Primeira imagem no container do conteúdo principal
        if not imagem_destacada and container_conteudo_original:
            first_img = container_conteudo_original.find('img')
            if first_img:
                src = first_img.get('src') or first_img.get('data-src')
                if src and not src.startswith('data:'):
                    imagem_destacada = src
                    print("    🖼️  Imagem via primeira <img> no container de conteúdo")
        
        # Prioridade 4: Primeira imagem em seletores comuns no conteúdo
        if not imagem_destacada:
            img_tags = soup.select('figure img, .featured-image img, .post-thumbnail img, img.wp-post-image, .itemFullText img, .com-content-article__body img')
            for img in img_tags:
                src = img.get('src') or img.get('data-src')
                if src and not src.startswith('data:'):  # Ignorar data URIs
                    imagem_destacada = src
                    print("    🖼️  Imagem via tag <img> no conteúdo (seletor amplo)")
                    break
        
        # Prioridade 5: Usar a miniatura da listagem como fallback final se não achou nada interno
        if not imagem_destacada and imagem_miniatura:
            imagem_destacada = imagem_miniatura
            print("    🖼️  Imagem via miniatura da listagem (fallback)")
        
        # Converter URL relativa para absoluta se necessário e codificar
        if imagem_destacada:
            imagem_destacada = imagem_destacada.strip().replace('\n', '').replace('\r', '')
            if not imagem_destacada.startswith(('http://', 'https://')):
                if imagem_destacada.startswith('//'):
                    imagem_destacada = 'https:' + imagem_destacada
                elif imagem_destacada.startswith('/'):
                    base_url = '/'.join(url_noticia.split('/')[:3])
                    imagem_destacada = base_url + imagem_destacada
                else:
                    imagem_destacada = urljoin(url_noticia, imagem_destacada)
            imagem_destacada = encodificar_url(imagem_destacada)
        
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

def coletar_noticias_via_rss(datas_alvo, fuso_brasilia, headers_padrao):
    """
    FONTE PRIMÁRIA: Consome o feed RSS nativo oficial do Joomla
    (https://www.fortaleza.ce.gov.br/noticias?format=feed&type=rss).
    Feed XML é imune a desafios JS/WAF e já inclui o conteúdo dos artigos.
    """
    print("\n📡 Tentando coletar via Feed RSS oficial (Zero WAF)...")
    noticias = []
    
    # 1. Mapa de imagens auxiliares (extraídas do card oficial via Jina)
    mapa_imagens = {}
    try:
        for pg_url in [
            "https://r.jina.ai/https://www.fortaleza.ce.gov.br/noticias",
            "https://r.jina.ai/https://www.fortaleza.ce.gov.br/noticias?start=5"
        ]:
            resp_jina = requests.get(pg_url, timeout=15)
            if resp_jina.status_code == 200:
                blocks = resp_jina.text.split('![Image')
                for b in blocks[1:]:
                    img_m = re.search(r'\]\((https?://[^\)]+)\)', b)
                    link_m = re.search(r'\[Leia Mais\]\((https?://[^\)]+)\)', b)
                    if img_m and link_m:
                        clean_link = link_m.group(1).rstrip('/')
                        mapa_imagens[clean_link] = img_m.group(1)
        if mapa_imagens:
            print(f"   🖼️  Mapa de imagens oficiais criado ({len(mapa_imagens)} imagens)")
    except Exception as e_map:
        print(f"   ⚠️ Mapa de imagens auxiliar: {e_map}")

    # 2. Iterar pelo feed RSS (página 1 e 2 = até 20 notícias)
    for start_offset in [0, 10]:
        url_rss = "https://www.fortaleza.ce.gov.br/noticias?format=feed&type=rss"
        if start_offset > 0:
            url_rss += f"&start={start_offset}"
            
        xml_content, code, _ = requisitar_pagina(url_rss, timeout=25)
        if not xml_content or '<item>' not in xml_content:
            continue
            
        try:
            xml_clean = xml_content
            if '<?xml' in xml_clean:
                xml_clean = xml_clean[xml_clean.find('<?xml'):]
            elif '<rss' in xml_clean:
                xml_clean = xml_clean[xml_clean.find('<rss'):]
            root = ET.fromstring(xml_clean.strip().encode('utf-8', errors='ignore'))
            channel = root.find('channel')
            if channel is None:
                continue
                
            items = channel.findall('item')
            print(f"   📦 {len(items)} itens recebidos no RSS (offset {start_offset})")
            
            for it in items:
                title_tag = it.find('title')
                link_tag = it.find('link')
                pubdate_tag = it.find('pubDate')
                
                if title_tag is None or link_tag is None:
                    continue
                    
                title = title_tag.text.strip()
                link = link_tag.text.strip()
                
                if any(n['link'] == link for n in noticias):
                    continue
                    
                pubdate_str = pubdate_tag.text.strip() if pubdate_tag is not None else ""
                
                try:
                    dt = parsedate_to_datetime(pubdate_str)
                    dt_local = dt.astimezone(fuso_brasilia)
                    data_noticia = dt_local.date()
                    hora = dt_local.strftime('%H:%M')
                    data_texto = dt_local.strftime('%d/%m/%Y %H:%M')
                except Exception:
                    data_noticia = datetime.now(fuso_brasilia).date()
                    hora = "12:00"
                    data_texto = data_noticia.strftime('%d/%m/%Y')
                    
                if data_noticia not in datas_alvo:
                    continue
                    
                desc_html = it.find('description').text or ''
                soup_desc = BeautifulSoup(desc_html, 'html.parser')
                
                # Imagem: 1) do HTML interno, 2) do mapa Jina, 3) do artigo
                img_tag = soup_desc.find('img')
                imagem = encodificar_url(img_tag['src']) if img_tag and img_tag.get('src') else None
                
                if not imagem:
                    clean_link = link.rstrip('/')
                    if clean_link in mapa_imagens:
                        imagem = encodificar_url(mapa_imagens[clean_link])
                        
                # Parágrafos formatados
                p_tags = soup_desc.find_all('p')
                conteudo_formatado = ""
                if p_tags:
                    conteudo_formatado = ''.join(str(p) for p in p_tags)
                if not conteudo_formatado or len(conteudo_formatado) < 200:
                    conteudo_formatado = desc_html
                    
                descricao_resumo = soup_desc.get_text(' ', strip=True)[:250]
                
                noticias.append({
                    'titulo': title,
                    'link': link,
                    'descricao': descricao_resumo,
                    'data_texto': data_texto,
                    'imagem': imagem,
                    'hora': hora,
                    'data_objeto': data_noticia,
                    'conteudo_completo': conteudo_formatado,
                    'tem_conteudo_completo': len(conteudo_formatado) > 100
                })
                img_status = "🖼️" if imagem else "📷"
                print(f"    ✅ [{hora}] {img_status} {title[:48]}...")
        except Exception as e_parse:
            print(f"   ⚠️ Erro ao processar XML do RSS: {e_parse}")

    return noticias

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
    fuso_brasilia = timezone(timedelta(hours=-3))
    hora_utc = utc_agora.hour
    
    if hora_utc < 3:  # Antes das 03:00 UTC = antes das 00:00 em Brasília
        # Usar data de ontem (ainda é o dia anterior no Brasil)
        HOJE = (utc_agora - timedelta(days=1)).date()
        print(f"⚠️  Ajuste de fuso: UTC {hora_utc:02d}:00 = Brasil {(hora_utc+21)%24:02d}:00 (dia anterior)")
    else:
        # Usar data atual
        HOJE = utc_agora.date()
        print(f"✅ Fuso correto: UTC {hora_utc:02d}:00 = Brasil {(hora_utc-3)%24:02d}:00")
        
    ONTEM = HOJE - timedelta(days=1)
    DATAS_ALVO = [HOJE, ONTEM]
    
    print(f"📅 Data de referência (Brasília): {HOJE.strftime('%d/%m/%Y')} e {ONTEM.strftime('%d/%m/%Y')}")
    print(f"⏰ UTC atual: {utc_agora.strftime('%H:%M')}")
    print("-" * 60)
    
    HEADERS = HEADERS_PADRAO
    
    MESES = {
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
        'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
        'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
    }
    
    def parse_data(data_str):
        """Converte data em português para objeto date"""
        try:
            data_str = data_str.lower()

            # 1. Suporte a formato numérico DD/MM/YYYY
            num_match = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', data_str)
            if num_match:
                dia = int(num_match.group(1))
                mes = int(num_match.group(2))
                ano = int(num_match.group(3))
                return date(ano, mes, dia)

            # 2. Formato textual por extenso (ex: "Terça, 17 Novembro 2026 13:15")
            for mes_pt, mes_num in MESES.items():
                if mes_pt in data_str:
                    dia_match = re.search(r'(\d{1,2})\s+(?:de\s+)?' + mes_pt, data_str)
                    if not dia_match:
                        dia_match = re.search(r'(\d{1,2})', data_str)
                    if dia_match:
                        dia = int(dia_match.group(1))
                        ano_match = re.search(r'(\d{4})', data_str)
                        ano = int(ano_match.group(1)) if ano_match else HOJE.year
                        return date(ano, mes_num, dia)
        except:
            pass
        return None
    
    try:
       
        
        # ================= 2. COLETAR NOTÍCIAS =================
        # Tentativa 1: RSS Nativo Oficial (Zero WAF, 100% resiliente em CI/CD)
        noticias_com_conteudo = coletar_noticias_via_rss(DATAS_ALVO, fuso_brasilia, HEADERS)
        
        if len(noticias_com_conteudo) > 0:
            print(f"\n🎯 Sucesso com RSS Oficial! {len(noticias_com_conteudo)} notícias obtidas.")
            com_conteudo = sum(1 for n in noticias_com_conteudo if n.get('tem_conteudo_completo'))
        else:
            print("\n📰 RSS indisponível. Tentando raspagem HTML direta...")
        # ================= 2. COLETAR NOTÍCIAS =================
            print("\n    📰 Coletando notícias...")
        
            noticias_hoje = []
            pagina = 1
            url = URL_LISTA
        
            while url and pagina <= 3:  # Limitar a 3 páginas para GitHub
                print(f"📄 Página {pagina}")
            
                try:
                    html_texto, status_code, url_final = requisitar_pagina(url, headers=HEADERS, timeout=(15, 30))
                    if not html_texto:
                        raise RuntimeError(f"Falha ao obter conteúdo da página {url}")

                    soup = BeautifulSoup(html_texto, 'html.parser')
                
                    print("URL acessada:", url_final)
                    print("Status HTTP:", status_code)
                    print("Título da página:", soup.title.get_text(strip=True) if soup.title else "Sem título")
                    print("HTML recebido (início):", html_texto[:1000])

                    # 1. Tentar formato do novo portal (Home: a.link-noticia ou .card-noticia)
                    # 0. Suporte a Markdown do Jina se retornado em modo texto
                    if 'Markdown Content:' in html_texto or 'Title: Notícias' in html_texto:
                        print("   💡 Conteúdo retornado em formato Markdown (via Jina)")
                        blocks = re.split(r'\n##\s+', html_texto)
                        for b in blocks[1:]:
                            blines = b.strip().split('\n')
                            m_title = blines[0].strip()
                            m_link_m = re.search(r'\[Leia Mais\]\((https?://[^\)]+)\)', b)
                            m_link = m_link_m.group(1) if m_link_m else None
                            if not m_link or any(n['link'] == m_link for n in noticias_hoje):
                                continue
                            m_data_m = re.search(r'([A-Za-zçãéíóú]+,\s+\d{1,2}\s+[A-Za-zçãéíóú]+\s+\d{4}(?:\s+\d{1,2}:\d{2})?)', b)
                            m_data_txt = m_data_m.group(1) if m_data_m else HOJE.strftime('%d/%m/%Y')
                            m_data_obj = parse_data(m_data_txt) or HOJE
                            if m_data_obj in DATAS_ALVO:
                                encontrou_alvo = True
                                m_hora = "12:00"
                                m_hora_m = re.search(r'(\d{1,2}:\d{2})', m_data_txt)
                                if m_hora_m:
                                    m_hora = m_hora_m.group(1)
                                m_resumo = '\n'.join([l for l in blines[1:] if not l.startswith('[Leia Mais]') and not l.startswith('![')]).strip()[:200]
                                m_img_m = re.search(r'!\[.*?\]\((https?://[^\)]+)\)', b)
                                m_img = encodificar_url(m_img_m.group(1)) if m_img_m else None
                                noticias_hoje.append({
                                    'titulo': m_title,
                                    'link': m_link,
                                    'descricao': m_resumo,
                                    'data_texto': m_data_txt,
                                    'imagem_miniatura': m_img,
                                    'hora': m_hora,
                                    'data_objeto': m_data_obj,
                                    'conteudo_completo': None,
                                    'imagem_destacada': None
                                })
                                print(f"    ✅ [{m_hora}] {m_title[:50]}...")

                    containers = soup.select('a.link-noticia')
                    if not containers:
                        containers = soup.select('.card-noticia')
                    # 2. Se não encontrou, tentar formato de listagem do K2/Joomla (/noticias: div.blog-post-item)
                    if not containers:
                        containers = soup.find_all('div', class_='blog-post-item')
                    # 3. Fallback adicional para itens do slider
                    if not containers:
                        containers = soup.select('#pmf-slider li article')
                
                    print(f"   📦 Notícias na página: {len(containers)}")
                
                    if len(containers) == 0:
                        print("   ⚠️  Nenhuma notícia encontrada na página")
                        break
                
                    encontrou_alvo = False
                
                    for container in containers:
                        try:
                            # Extrair data
                            data_texto = None
                            span_data = container.select_one('.data, span.data, span.bloco-ultimas-data')
                            if span_data:
                                data_texto = span_data.get_text(strip=True)
                            else:
                                data_div = container.find('div', class_='blog-time')
                                if data_div:
                                    span_lato = data_div.find('span', class_='font-lato') or data_div.find('span')
                                    if span_lato:
                                        data_texto = span_lato.get_text(strip=True)
                        
                            if not data_texto:
                                continue
                            
                            print(f"      📝 Data bruta: {data_texto}")
                        
                            data_noticia = parse_data(data_texto)
                        
                            if data_noticia:
                                print(f"      📅 Data convertida: {data_noticia.strftime('%d/%m/%Y')}")
                        
                            if not data_noticia:
                                print(f"      ⚠️  Não consegui converter data")
                                continue
                        
                            # Verificar se é de hoje ou ontem
                            if data_noticia in DATAS_ALVO:
                                encontrou_alvo = True
                            
                                # Link
                                link_url = None
                                if container.name == 'a' and container.get('href'):
                                    link_url = urljoin(URL_BASE, container['href'])
                                else:
                                    link_tag = (
                                        container.find('a', class_='btn-reveal') or
                                        container.select_one('a.btn-reveal, a.btn, a')
                                    )
                                    if link_tag and link_tag.get('href'):
                                        link_url = urljoin(URL_BASE, link_tag['href'])
                                    
                                if not link_url:
                                    continue
                                
                                # Evitar duplicados na listagem
                                if any(n['link'] == link_url for n in noticias_hoje):
                                    continue
                            
                                # Título
                                titulo = ""
                                titulo_tag = (
                                    container.select_one('.titulo, h3.titulo, .bloco-ultimas-noticia-titulo, h2, h3') or
                                    container.find('h3', class_='titulo') or
                                    container.find('h2')
                                )
                                if titulo_tag:
                                    titulo = titulo_tag.get_text(strip=True)
                            
                                if not titulo:
                                    continue
                            
                                # Descrição (resumo da página principal)
                                descricao = ""
                                desc_tag = (
                                    container.select_one('.subtitulo, p.subtitulo, .bloco-ultimas-subtitulo') or
                                    container.find('p', class_='subtitulo')
                                )
                                if desc_tag:
                                    descricao = desc_tag.get_text(strip=True)[:200]
                                else:
                                    intro_div = container.find('div', class_='intro')
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
                                img_container = (
                                    container.select_one('.imagem') or
                                    container.find('figure', class_='blog-item-small-image') or
                                    container.find('div', class_='blog-item-small-image') or
                                    container.find('div', class_='imagem') or
                                    container.find('figure')
                                )
                                img_tag = None
                                if img_container:
                                    img_tag = img_container.find('img')
                                if not img_tag:
                                    img_tag = container.find('img')
                                
                                if img_tag:
                                    src = img_tag.get('src') or img_tag.get('data-src') or img_tag.get('data-lazy-src')
                                    if src and not src.startswith('data:'):
                                        src = src.strip().replace('\n    ', '').replace('\r', '')
                                        if not src.startswith(('http://', 'https://')):
                                            if src.startswith('//'):
                                                imagem_miniatura = 'https:' + src
                                            elif src.startswith('/'):
                                                imagem_miniatura = URL_BASE + src
                                            else:
                                                imagem_miniatura = urljoin(URL_BASE, src)
                                        else:
                                            imagem_miniatura = src
                                        imagem_miniatura = encodificar_url(imagem_miniatura)
                            
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
                
                    print(f"   📊 Notícias recentes nesta página: {len(noticias_hoje)}")
                
                    # Se não encontrou notícias recentes E já viu algumas páginas, parar
                    if not encontrou_alvo and pagina >= 2:
                        print("   ⏹️  Nenhuma notícia recente, parando busca")
                        break
                
                    # Próxima página
                    proxima = None
                
                    # 1. Se estiver na Home, avançar para /noticias
                    btn_mais = soup.select_one('a.btn-mais-noticias, .botao-mais-noticias a')
                    if btn_mais and btn_mais.get('href'):
                        candidata = urljoin(URL_BASE, btn_mais['href'])
                        if candidata != url and candidata not in [URL_BASE, URL_BASE + "/"]:
                            proxima = candidata
                
                    # 2. Paginação tradicional do Joomla/K2 (ex.: /noticias?start=5)
                    if not proxima:
                        paginador = (
                            soup.find('div', class_='news-pagination') or
                            soup.find('ul', class_='pagination') or
                            soup.find('div', class_='pagination')
                        )
                        if paginador:
                            link_proximo = (
                                paginador.find('li', class_='pagination-next') or
                                paginador.select_one('li.pagination-next a, .pagination-next a, a[data-original-title="Próximo"], a[title="Próximo"], a[rel="next"]')
                            )
                            if link_proximo:
                                a_prox = link_proximo.find('a') if link_proximo.name != 'a' else link_proximo
                                if a_prox and a_prox.get('href'):
                                    proxima = urljoin(URL_BASE, a_prox['href'])
                                    print(f"   🔗 Próxima página encontrada: {proxima}")
                
                    if not proxima:
                        break
                
                    pagina += 1
                    url = proxima
                    time.sleep(1)  # Respeitar o servidor
                
                except Exception as e:
                    print(f"   ❌ Erro na página {pagina}: {e}")

                    if pagina == 1:
                        raise RuntimeError(
                            "Não foi possível acessar a primeira página de notícias. "
                            "O feed não será gerado como se não houvesse notícias."
                        ) from e

                    print("   ⚠️ Falha em página seguinte. Mantendo as notícias já coletadas.")
                    break
        
            print("-" * 60)
            print(f"📈 Busca concluída: {pagina} página(s)")
            print(f"🎯 Notícias recentes (hoje/ontem) encontradas: {len(noticias_hoje)}")
        
            # ================= 3. EXTRAIR CONTEÚDO COMPLETO =================
            print(f"\n    📥 Extraindo conteúdo completo das notícias...")
            print("-" * 60)
        
            noticias_com_conteudo = []
        
            for i, noticia in enumerate(noticias_hoje, 1):
                print(f"\n    📰 Notícia {i}/{len(noticias_hoje)}: {noticia['titulo'][:60]}...")
            
                # Aguardar entre requisições para não sobrecarregar o servidor
                if i > 1:
                    time.sleep(2)  # 2 segundos entre requisições
            
                # Acessar a página individual da notícia passando a miniatura
                conteudo_extraido = extrair_conteudo_completo(noticia['link'], HEADERS, noticia['imagem_miniatura'])
            
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
            print(f"\n    📊 Estatísticas:")
            print(f"   Total de notícias: {len(noticias_com_conteudo)}")
            print(f"   Com conteúdo completo: {com_conteudo}")
            print(f"   Apenas resumo: {len(noticias_com_conteudo) - com_conteudo}")
        
        
        # ================= 4. VERIFICAR RESULTADO =================
        if len(noticias_com_conteudo) == 0:
            print("\n📭 Nenhuma notícia encontrada para hoje/ontem")
            print("   Possíveis causas:")
            print("   1. Realmente não há notícias novas")
            print(f"   2. Data de referência: {HOJE.strftime('%d/%m/%Y')}")
            print(f"   3. Hora UTC: {utc_agora.strftime('%H:%M')}")
            print("   4. Site pode estar offline")
            
            # Mesmo sem notícias, criar um feed válido para o GitHub
            xml_vazio = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Notícias Fortaleza - Recentes</title>
<link>{URL_BASE}</link>
<description>Sem notícias recentes. Última verificação: {utc_agora.strftime("%H:%M")} UTC</description>
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
        xml_parts.append(f'<title>Notícias Fortaleza - Recentes</title>')
        xml_parts.append(f'<link>{URL_BASE}</link>')
        xml_parts.append(f'<description>{len(noticias_com_conteudo)} notícias recentes ({com_conteudo} com conteúdo completo)</description>')
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
