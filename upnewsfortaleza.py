#!/usr/bin/env python3
# upnewsfortaleza.py - VERSÃO COM CONTEÚDO COMPLETO E FORMATAÇÃO ORIGINAL

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

def criar_feed_fortaleza_completo():
    """
    Extrai conteúdo COMPLETO com formatação original
    """
    
    print("🚀 upnewsfortaleza.py - CONTEÚDO COMPLETO COM FORMATAÇÃO")
    print("=" * 60)
    
    # ================= CONFIGURAÇÃO =================
    URL_BASE = "https://www.fortaleza.ce.gov.br"
    URL_LISTA = f"{URL_BASE}/noticias"
    FEED_FILE = "feed_fortaleza_hoje.xml"
    
    # Data UTC → Brasília
    utc_agora = datetime.now(timezone.utc)
    if utc_agora.hour >= 21:
        HOJE_REF = (utc_agora + timedelta(hours=3)).date()
    else:
        HOJE_REF = (utc_agora + timedelta(hours=3)).date()
    
    print(f"📅 Data de referência: {HOJE_REF.strftime('%d/%m/%Y')}")
    print("-" * 60)
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9'
    }
    
    MESES_PT = {
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
        'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
        'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
    }
    
    def extrair_data(texto):
        """Extrai data do texto em português"""
        try:
            texto = texto.lower()
            for mes_pt, mes_num in MESES_PT.items():
                if mes_pt in texto:
                    dia_match = re.search(r'(\d{1,2})', texto)
                    ano_match = re.search(r'(\d{4})', texto)
                    if dia_match:
                        dia = int(dia_match.group(1))
                        ano = int(ano_match.group(1)) if ano_match else HOJE_REF.year
                        return date(ano, mes_num, dia)
        except:
            pass
        return None
    
    try:
        # ================= 1. COLETAR LISTAGEM =================
        print("🔍 Coletando notícias...")
        
        lista_noticias = []
        pagina = 1
        url = URL_LISTA
        
        while url and pagina <= 5:
            print(f"📄 Página {pagina}")
            
            try:
                response = requests.get(url, headers=HEADERS, timeout=15)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                containers = soup.find_all('div', class_='blog-post-item')
                
                for container in containers:
                    try:
                        # Data
                        data_div = container.find('div', class_='blog-time')
                        if not data_div:
                            continue
                            
                        span_data = data_div.find('span', class_='font-lato')
                        if not span_data:
                            continue
                            
                        data_texto = span_data.get_text(strip=True)
                        data_noticia = extrair_data(data_texto)
                        
                        if not data_noticia or data_noticia != HOJE_REF:
                            continue
                        
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
                        
                        # Hora
                        hora = "00:00"
                        hora_match = re.search(r'(\d{1,2}:\d{2})', data_texto)
                        if hora_match:
                            hora = hora_match.group(1)
                        
                        # Imagem destacada
                        imagem_destaque = None
                        img_tag = container.find('figure', class_='blog-item-small-image')
                        if img_tag:
                            img = img_tag.find('img')
                            if img and img.get('src'):
                                src = img['src']
                                if not src.startswith(('http://', 'https://')):
                                    imagem_destaque = urljoin(URL_BASE, src)
                                else:
                                    imagem_destaque = src
                        
                        lista_noticias.append({
                            'titulo': titulo,
                            'link': link_url,
                            'data_texto': data_texto,
                            'imagem_destaque': imagem_destaque,
                            'hora': hora
                        })
                        
                        print(f"    ✅ [{hora}] {titulo[:60]}...")
                    
                    except:
                        continue
                
                # Próxima página
                paginador = soup.find('div', class_='news-pagination')
                proxima = None
                
                if paginador:
                    link_proximo = paginador.find('a', string=lambda t: t and 'próximo' in str(t).lower())
                    if link_proximo and link_proximo.get('href'):
                        proxima = urljoin(URL_BASE, link_proximo['href'])
                
                if not proxima:
                    break
                
                pagina += 1
                url = proxima
                time.sleep(1)
                
            except:
                break
        
        if not lista_noticias:
            print("📭 Nenhuma notícia hoje")
            return True
        
        # ================= 2. EXTRAIR CONTEÚDO COMPLETO =================
        print(f"\n📥 Extraindo conteúdo completo...")
        
        noticias_completas = []
        
        for i, noticia in enumerate(lista_noticias, 1):
            print(f"🔗 ({i}/{len(lista_noticias)}) {noticia['link'][:70]}...")
            
            try:
                time.sleep(2)
                
                response = requests.get(noticia['link'], headers=HEADERS, timeout=20)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # ================= CONTEÚDO COM FORMATAÇÃO ORIGINAL =================
                # Estratégias para encontrar o conteúdo principal
                conteudo_div = None
                
                # Tentar diferentes seletores comuns
                seletores = [
                    ('div', {'class': 'item-page'}),
                    ('div', {'itemprop': 'articleBody'}),
                    ('article', {}),
                    ('div', {'class': 'blog-item-small-content'}),
                    ('div', {'id': 'content'}),
                    ('div', {'id': 'conteudo'}),
                    ('div', {'class': 'content'}),
                    ('div', {'class': 'conteudo'})
                ]
                
                for tag_name, attrs in seletores:
                    conteudo_div = soup.find(tag_name, attrs)
                    if conteudo_div:
                        print(f"    ✅ Encontrado: {tag_name} {attrs}")
                        break
                
                if not conteudo_div:
                    # Fallback: procurar div com muito texto
                    divs = soup.find_all('div')
                    for div in divs:
                        texto = div.get_text(strip=True)
                        if len(texto) > 500 and 'script' not in str(div).lower():
                            conteudo_div = div
                            print(f"    ✅ Fallback: div com {len(texto)} caracteres")
                            break
                
                if not conteudo_div:
                    noticia['conteudo'] = f'<p>{noticia["titulo"]}</p>'
                    noticias_completas.append(noticia)
                    continue
                
                # ================= LIMPAR E MANTER FORMATAÇÃO =================
                # 1. Remover elementos completamente indesejados
                elementos_remover = ['script', 'style', 'iframe', 'nav', 'aside', 
                                    'header', 'footer', 'form', 'button']
                
                for tag in conteudo_div.find_all(elementos_remover):
                    tag.decompose()
                
                # 2. Remover elementos de compartilhamento, comentários, etc
                for tag in conteudo_div.find_all(True):
                    classes = tag.get('class', [])
                    id_tag = tag.get('id', '')
                    texto_classe = ' '.join(classes).lower()
                    
                    # Remover elementos comuns de redes sociais, banners, etc
                    palavras_remover = ['social', 'share', 'comentario', 'comment',
                                       'banner', 'advertisement', 'ad', 'publicidade',
                                       'newsletter', 'related', 'recomendado', 'sidebar']
                    
                    if any(palavra in texto_classe for palavra in palavras_remover) or \
                       any(palavra in id_tag.lower() for palavra in palavras_remover):
                        tag.decompose()
                
                # 3. CORREÇÃO DE URLS para imagens e links
                # 3.1 Imagens: corrigir URLs relativas e adicionar atributos
                for img in conteudo_div.find_all('img'):
                    src = img.get('src')
                    if src:
                        # Corrigir URL se for relativa
                        if not src.startswith(('http://', 'https://', 'data:')):
                            if src.startswith('/'):
                                img['src'] = urljoin(URL_BASE, src)
                            else:
                                img['src'] = urljoin(noticia['link'], src)
                        
                        # Adicionar atributos para responsividade
                        img['style'] = 'max-width: 100%; height: auto;'
                        
                        # Garantir alt text
                        if not img.get('alt'):
                            img['alt'] = noticia['titulo'][:100]
                
                # 3.2 Links: corrigir URLs relativas
                for a in conteudo_div.find_all('a'):
                    href = a.get('href')
                    if href and not href.startswith(('http://', 'https://', '#')):
                        if href.startswith('/'):
                            a['href'] = urljoin(URL_BASE, href)
                        else:
                            a['href'] = urljoin(noticia['link'], href)
                
                # 4. LIMPAR ATRIBUTOS, MAS MANTER TAGS ESTRUTURAIS
                # Tags que queremos manter com atributos mínimos
                tags_estruturais = {
                    'a': ['href'],
                    'img': ['src', 'alt', 'style'],
                    'table': [],
                    'tr': [],
                    'td': ['colspan', 'rowspan'],
                    'th': [],
                    'iframe': ['src', 'width', 'height']
                }
                
                for tag in conteudo_div.find_all(True):
                    tag_name = tag.name
                    
                    if tag_name in tags_estruturais:
                        # Manter apenas atributos permitidos
                        attrs_permitidos = tags_estruturais[tag_name]
                        novos_atributos = {}
                        
                        for attr in attrs_permitidos:
                            if tag.get(attr):
                                novos_atributos[attr] = tag[attr]
                        
                        tag.attrs = novos_atributos
                    else:
                        # Para outras tags, remover todos atributos exceto alguns básicos
                        if tag_name in ['div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                       'ul', 'ol', 'li', 'strong', 'em', 'b', 'i', 'u', 'br',
                                       'blockquote', 'pre', 'code']:
                            # Manter apenas estilo se existir
                            if tag.get('style'):
                                tag.attrs = {'style': tag['style']}
                            else:
                                tag.attrs = {}
                        else:
                            # Para tags não reconhecidas, manter conteúdo mas remover tag
                            tag.unwrap()
                
                # 5. ADICIONAR IMAGEM DESTACADA NO INÍCIO (se existir)
                conteudo_final = ""
                
                if noticia['imagem_destaque']:
                    img_html = f'''
                    <div style="margin-bottom: 25px; text-align: center;">
                        <img src="{noticia['imagem_destaque']}" 
                             alt="{html.escape(noticia['titulo'][:100])}"
                             style="max-width: 100%; height: auto; border-radius: 8px;">
                    </div>
                    '''
                    conteudo_final += img_html
                
                # 6. ADICIONAR TÍTULO E DATA
                cabecalho = f'''
                <div style="margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #eee;">
                    <h1 style="margin: 0 0 10px 0; color: #333; font-size: 24px;">
                        {html.escape(noticia['titulo'])}
                    </h1>
                    <div style="color: #666; font-size: 14px;">
                        <strong>Publicado em:</strong> {noticia['data_texto']}
                    </div>
                </div>
                '''
                conteudo_final += cabecalho
                
                # 7. ADICIONAR CONTEÚDO EXTRAÍDO
                conteudo_final += str(conteudo_div)
                
                # 8. ADICIONAR RODAPÉ COM FONTE
                rodape = f'''
                <div style="margin-top: 30px; padding: 15px; background: #f5f5f5; 
                     border-left: 3px solid #0073aa; font-size: 14px;">
                    <p style="margin: 0;">
                        <strong>Fonte:</strong> Prefeitura de Fortaleza<br>
                        <strong>Link original:</strong> 
                        <a href="{noticia['link']}" target="_blank">{noticia['link']}</a>
                    </p>
                </div>
                '''
                conteudo_final += rodape
                
                # 9. LIMPAR FORMATAÇÃO EXCESSIVA
                conteudo_final = re.sub(r'\n\s*\n\s*\n+', '\n\n', conteudo_final)
                conteudo_final = re.sub(r'<p>\s*</p>', '', conteudo_final)
                conteudo_final = re.sub(r'<div>\s*</div>', '', conteudo_final)
                
                noticia['conteudo'] = conteudo_final
                noticia['tamanho'] = len(conteudo_final)
                noticias_completas.append(noticia)
                
                print(f"    ✅ Conteúdo: {len(conteudo_final):,} caracteres")
                
            except Exception as e:
                print(f"    ❌ Erro: {str(e)[:50]}")
                continue
        
        # ================= 3. GERAR XML =================
        print(f"\n📄 Gerando XML com formatação original...")
        
        # Ordenar por hora
        noticias_completas.sort(key=lambda x: x['hora'], reverse=True)
        
        xml_parts = []
        
        xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_parts.append('<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">')
        xml_parts.append('<channel>')
        xml_parts.append(f'<title>Notícias Fortaleza - {HOJE_REF.strftime("%d/%m/%Y")}</title>')
        xml_parts.append(f'<link>{URL_BASE}</link>')
        xml_parts.append(f'<description>Notícias completas com formatação original - {len(noticias_completas)} notícias</description>')
        xml_parts.append('<language>pt-br</language>')
        xml_parts.append(f'<lastBuildDate>{utc_agora.strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
        xml_parts.append('<ttl>60</ttl>')
        
        for noticia in noticias_completas:
            guid = hashlib.md5(noticia['link'].encode()).hexdigest()[:12]
            
            # Data RSS
            try:
                hora_partes = noticia['hora'].split(':')
                hora = int(hora_partes[0]) if hora_partes else 12
                minuto = int(hora_partes[1]) if len(hora_partes) > 1 else 0
                data_rss = datetime(HOJE_REF.year, HOJE_REF.month, HOJE_REF.day, 
                                  hora, minuto, 0, tzinfo=timezone.utc)
                pub_date = data_rss.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except:
                pub_date = utc_agora.strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            xml_parts.append('<item>')
            xml_parts.append(f'<title>{html.escape(noticia["titulo"])}</title>')
            xml_parts.append(f'<link>{noticia["link"]}</link>')
            xml_parts.append(f'<guid isPermaLink="false">ftz-{guid}</guid>')
            xml_parts.append(f'<pubDate>{pub_date}</pubDate>')
            xml_parts.append(f'<description>{html.escape(noticia["titulo"][:150])} - {noticia["data_texto"]}</description>')
            
            # AQUI: conteúdo completo com formatação original
            xml_parts.append(f'<content:encoded><![CDATA[ {noticia["conteudo"]} ]]></content:encoded>')
            
            if noticia.get('imagem_destaque'):
                xml_parts.append(f'<enclosure url="{noticia["imagem_destaque"]}" type="image/jpeg" />')
                xml_parts.append(f'<media:content url="{noticia["imagem_destaque"]}" type="image/jpeg" medium="image">')
                xml_parts.append(f'<media:title>{html.escape(noticia["titulo"][:100])}</media:title>')
                xml_parts.append('</media:content>')
            
            xml_parts.append('</item>')
        
        xml_parts.append('</channel>')
        xml_parts.append('</rss>')
        
        # ================= 4. SALVAR =================
        with open(FEED_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_parts))
        
        # ================= 5. RELATÓRIO =================
        print("-" * 60)
        print(f"✅ FEED GERADO!")
        print(f"📊 Notícias: {len(noticias_completas)}")
        print(f"📏 Tamanho total: {sum(n.get('tamanho', 0) for n in noticias_completas):,} caracteres")
        print(f"📁 Arquivo: {FEED_FILE}")
        
        if noticias_completas:
            print(f"\n📋 EXEMPLO DE CONTEÚDO:")
            primeira = noticias_completas[0]
            # Mostrar preview do conteúdo HTML
            preview = primeira['conteudo'][:500].replace('\n', ' ')
            print(f"  {preview}...")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return False

if __name__ == "__main__":
    sucesso = criar_feed_fortaleza_completo()
    sys.exit(0 if sucesso else 1)
