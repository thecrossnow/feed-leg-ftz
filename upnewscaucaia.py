#!/usr/bin/env python3
"""
SCRAPER CAUCAIA - CORRIGIDO PARA XML VÁLIDO
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import html
import hashlib
import time
from urllib.parse import urljoin
import re
import os

def criar_feed_caucaia_corrigido():
    """Cria feed XML válido sem erros de codificação"""
    
    print("🎯 SCRAPER CAUCAIA - XML VÁLIDO")
    print("="*70)
    
    URL_BASE = "https://www.caucaia.ce.gov.br"
    URL_LISTA = f"{URL_BASE}/informa.php"
    FEED_FILE = "feed_caucaia_correto.xml"
    
    HEADERS = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        # 1. COLETAR NOTÍCIAS
        print("📋 Coletando notícias...")
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
                        'link': link_url,
                        'titulo_original': titulo[:300]
                    })
        
        lista_noticias = lista_noticias[:10]
        print(f"✅ {len(lista_noticias)} notícias coletadas\n")
        
        # 2. EXTRAIR CONTEÚDO
        print("="*70)
        print("🔍 Extraindo conteúdo...")
        print("="*70)
        
        noticias_completas = []
        
        for i, noticia in enumerate(lista_noticias, 1):
            print(f"\n📖 [{i}/{len(lista_noticias)}] {noticia['titulo_original'][:60]}...")
            
            try:
                time.sleep(1)
                resp = requests.get(noticia['link'], headers=HEADERS, timeout=30)
                
                if resp.status_code != 200:
                    print(f"   ⚠️  Erro {resp.status_code}")
                    continue
                
                soup_noticia = BeautifulSoup(resp.content, 'html.parser')
                
                # TÍTULO
                titulo_tag = soup_noticia.find('h1', class_='DataInforma')
                titulo_final = titulo_tag.get_text(strip=True) if titulo_tag else noticia['titulo_original']
                
                # IMAGEM
                img_tag = soup_noticia.find('img', class_='imginfo') or \
                         soup_noticia.find('img', class_='img-responsive') or \
                         soup_noticia.find('img', class_='ImagemIndexNoticia')
                
                imagem_url = None
                if img_tag and img_tag.get('src'):
                    src = img_tag['src']
                    if not src.startswith(('http://', 'https://')):
                        src = urljoin(URL_BASE, src)
                    if 'p_noticia.png' not in src:
                        imagem_url = src
                
                # CONTEÚDO
                div_conteudo = soup_noticia.find('div', class_='p-info')
                conteudo_html = ""
                
                if div_conteudo:
                    # Remover scripts e estilos
                    for tag in div_conteudo.find_all(['script', 'style', 'iframe']):
                        tag.decompose()
                    
                    # Processar imagens no conteúdo
                    for img in div_conteudo.find_all('img', src=True):
                        src = img['src']
                        if not src.startswith(('http://', 'https://')):
                            src = urljoin(URL_BASE, src)
                        img['src'] = src
                        img['style'] = 'max-width: 100%; height: auto;'
                    
                    conteudo_html = str(div_conteudo)
                else:
                    # Fallback
                    todos_p = soup_noticia.find_all('p')
                    paragrafos = []
                    for p in todos_p:
                        texto = p.get_text(strip=True)
                        if len(texto) > 50 and not any(lixo in texto.lower() for lixo in ['compartilhe', 'curtir']):
                            paragrafos.append(f'<p>{html.escape(texto)}</p>')
                    
                    if paragrafos:
                        conteudo_html = ''.join(paragrafos[:8])
                
                # DATA
                texto_pagina = soup_noticia.get_text()
                data_match = re.search(r'(\d{2}/\d{2}/\d{4})', texto_pagina[:2000])
                data_str = data_match.group(1) if data_match else None
                
                noticias_completas.append({
                    'titulo': titulo_final,
                    'link': noticia['link'],
                    'imagem': imagem_url,
                    'conteudo': conteudo_html,
                    'data': data_str
                })
                
                print(f"   ✅ {titulo_final[:50]}...")
                if imagem_url:
                    print(f"   🖼️  Imagem: {imagem_url[:60]}...")
                
            except Exception as e:
                print(f"   ❌ Erro: {str(e)[:80]}")
                continue
        
        # 3. GERAR XML CORRETO
        print(f"\n{'='*70}")
        print("📝 Gerando XML válido...")
        print(f"{'='*70}")
        
        # ✅ CRÍTICO: Criar lista e depois escrever TUDO DE UMA VEZ
        xml_parts = []
        
        # ✅ XML declaration PRIMEIRO, sem espaços antes
        xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_parts.append('<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">')
        xml_parts.append('<channel>')
        xml_parts.append(f'<title>Notícias de Caucaia</title>')
        xml_parts.append(f'<link>{URL_BASE}</link>')
        xml_parts.append('<description>Notícias oficiais da Prefeitura de Caucaia</description>')
        xml_parts.append('<language>pt-br</language>')
        xml_parts.append(f'<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
        xml_parts.append('<ttl>180</ttl>')
        
        for i, noticia in enumerate(noticias_completas, 1):
            print(f"   📄 [{i}] {noticia['titulo'][:50]}...")
            
            # GUID
            guid = hashlib.md5(noticia['link'].encode()).hexdigest()[:10]
            
            # Data
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
            
            # Description (texto simples)
            desc_texto = noticia['titulo']
            if noticia['data']:
                desc_texto += f" - {noticia['data']}"
            xml_parts.append(f'<description>{html.escape(desc_texto[:250])}</description>')
            
            # ✅ CONTEÚDO COMPLETO (para WordPress)
            conteudo_final = noticia['conteudo']
            
            # Adicionar fonte
            fonte_html = f'<p><strong>Fonte:</strong> <a href="{noticia["link"]}">Prefeitura de Caucaia</a></p>'
            conteudo_final += fonte_html
            
            xml_parts.append(f'<content:encoded><![CDATA[ {conteudo_final} ]]></content:encoded>')
            
            # IMAGEM (se houver)
            if noticia['imagem']:
                xml_parts.append(f'<enclosure url="{noticia["imagem"]}" length="0" type="image/jpeg" />')
            
            xml_parts.append('</item>')
        
        xml_parts.append('</channel>')
        xml_parts.append('</rss>')
        
        # ✅ ESCREVER TUDO DE UMA VEZ (evita BOM/encoding issues)
        with open(FEED_FILE, 'w', encoding='utf-8') as f:
            # NÃO escreva nada antes do XML declaration
            f.write('\n'.join(xml_parts))
        
        # 4. VERIFICAR SE O XML É VÁLIDO
        print(f"\n✅ XML GERADO: {FEED_FILE}")
        
        # Ler e verificar
        with open(FEED_FILE, 'r', encoding='utf-8') as f:
            conteudo = f.read()
            
            # Verificar problemas comuns
            if conteudo.startswith('\ufeff'):
                print("⚠️  ATENÇÃO: Arquivo tem BOM (Byte Order Mark)")
                # Corrigir removendo BOM
                with open(FEED_FILE, 'w', encoding='utf-8-sig') as f2:
                    f2.write(conteudo.lstrip('\ufeff'))
                print("✅ BOM removido")
            
            if not conteudo.startswith('<?xml'):
                print("⚠️  ATENÇÃO: XML não começa com declaration")
                # Encontrar onde começa o XML
                xml_start = conteudo.find('<?xml')
                if xml_start > 0:
                    print(f"   XML começa na posição {xml_start}")
                    # Cortar tudo antes
                    with open(FEED_FILE, 'w', encoding='utf-8') as f2:
                        f2.write(conteudo[xml_start:])
                    print("✅ XML corrigido")
            
            # Estatísticas
            file_size = os.path.getsize(FEED_FILE)
            print(f"📊 Tamanho do arquivo: {file_size:,} bytes")
            print(f"📊 Notícias no feed: {len(noticias_completas)}")
        
        # 5. CRIAR VERSÃO SIMPLES TAMBÉM (sem content:encoded)
        FEED_SIMPLE = "feed_caucaia_simples.xml"
        xml_simple = []
        xml_simple.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_simple.append('<rss version="2.0">')
        xml_simple.append('<channel>')
        xml_simple.append(f'<title>Notícias Caucaia Simples</title>')
        xml_simple.append(f'<link>{URL_BASE}</link>')
        xml_simple.append('<description>Versão simples para testes</description>')
        xml_simple.append('<language>pt-br</language>')
        xml_simple.append(f'<lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
        
        for noticia in noticias_completas[:5]:  # Apenas 5 para teste
            guid = hashlib.md5(noticia['link'].encode()).hexdigest()[:8]
            
            xml_simple.append('<item>')
            xml_simple.append(f'<title>{html.escape(noticia["titulo"])}</title>')
            xml_simple.append(f'<link>{noticia["link"]}</link>')
            xml_simple.append(f'<guid>caucaia-{guid}</guid>')
            xml_simple.append('<description>Notícia da Prefeitura de Caucaia</description>')
            xml_simple.append('</item>')
        
        xml_simple.append('</channel>')
        xml_simple.append('</rss>')
        
        with open(FEED_SIMPLE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_simple))
        
        print(f"\n📁 Arquivos criados:")
        print(f"   1. {FEED_FILE} (completo para WordPress)")
        print(f"   2. {FEED_SIMPLE} (simples para teste)")
        
        print(f"\n{'='*70}")
        print("🔧 TESTE SEU XML:")
        print(f"1. Abra no navegador: https://thecrossnow.github.io/feed-leg-ftz/{FEED_FILE}")
        print(f"2. Valide em: https://validator.w3.org/feed/")
        print(f"3. Para WordPress, use: {FEED_FILE}")
        print(f"{'='*70}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Limpar qualquer espaço em branco no início
    import sys
    if sys.version_info >= (3, 0):
        sys.stdout.reconfigure(encoding='utf-8')
    
    criar_feed_caucaia_corrigido()
