#!/usr/bin/env python3
"""
SCRAPER CAUCAIA - WORDPRESS COM IMAGENS DESTACADAS
Mantém estrutura original, otimiza para WordPress
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

def extrair_imagem_destacada(soup_noticia, url_base):
    """Extrai a imagem principal para ser destacada no WordPress"""
    
    # Prioridade 1: Imagem da notícia (classe 'imginfo' ou similar)
    img_principal = soup_noticia.find('img', class_='imginfo')
    if not img_principal:
        img_principal = soup_noticia.find('img', class_='img-responsive')
    if not img_principal:
        img_principal = soup_noticia.find('img', class_='ImagemIndexNoticia')
    
    # Prioridade 2: Primeira imagem no conteúdo
    if not img_principal:
        div_conteudo = soup_noticia.find('div', class_='p-info')
        if div_conteudo:
            img_principal = div_conteudo.find('img', src=True)
    
    # Prioridade 3: Qualquer imagem que não seja logo/placeholder
    if not img_principal:
        for img in soup_noticia.find_all('img', src=True):
            src = img['src'].lower()
            if any(termo in src for termo in ['noticia', 'foto', 'imagem', '.jpg', '.jpeg', '.png']):
                if not any(termo in src for termo in ['logo', 'selo', 'banner', 'placeholder']):
                    img_principal = img
                    break
    
    if img_principal and img_principal.get('src'):
        src = img_principal['src']
        if not src.startswith(('http://', 'https://')):
            src = urljoin(url_base, src)
        
        # Verificar se é imagem padrão do site
        if 'p_noticia.png' in src:
            return None  # Não usar placeholder como destacada
        return src
    
    return None

def extrair_conteudo_completo(soup_noticia, url_base):
    """Extrai conteúdo completo com imagens embutidas"""
    
    resultado = {
        'titulo': '',
        'imagem_destacada': None,
        'conteudo_html': '',
        'imagens_embutidas': []
    }
    
    # 1. TÍTULO
    titulo_tag = soup_noticia.find('h1', class_='DataInforma')
    if titulo_tag:
        resultado['titulo'] = titulo_tag.get_text(strip=True)
    else:
        for tag in soup_noticia.find_all(['h1', 'h2', 'strong']):
            texto = tag.get_text(strip=True)
            if len(texto) > 30 and len(texto) < 200:
                resultado['titulo'] = texto
                break
    
    # 2. IMAGEM DESTACADA
    resultado['imagem_destacada'] = extrair_imagem_destacada(soup_noticia, url_base)
    
    # 3. CONTEÚDO PRINCIPAL
    div_conteudo = soup_noticia.find('div', class_='p-info')
    
    if div_conteudo:
        # Fazer cópia para não modificar o original
        conteudo_copy = BeautifulSoup(str(div_conteudo), 'html.parser')
        
        # Remover elementos indesejados
        for tag in conteudo_copy.find_all(['script', 'style', 'iframe', 'form']):
            tag.decompose()
        
        # Processar imagens no conteúdo
        for img in conteudo_copy.find_all('img', src=True):
            src = img['src']
            if not src.startswith(('http://', 'https://')):
                src = urljoin(url_base, src)
            
            # Adicionar à lista de imagens embutidas
            if src not in resultado['imagens_embutidas']:
                resultado['imagens_embutidas'].append(src)
            
            # Otimizar atributos da imagem
            img['style'] = 'max-width: 100%; height: auto;'
            img['loading'] = 'lazy'
            if not img.get('alt'):
                img['alt'] = resultado['titulo'][:100]
        
        resultado['conteudo_html'] = str(conteudo_copy)
    else:
        # Fallback: parágrafos principais
        todos_p = soup_noticia.find_all('p')
        conteudo_parts = []
        for p in todos_p:
            texto = p.get_text(strip=True)
            if len(texto) > 50 and not any(lixo in texto.lower() for lixo in ['compartilhe', 'curtir']):
                conteudo_parts.append(f'<p>{html.escape(texto)}</p>')
        
        if conteudo_parts:
            resultado['conteudo_html'] = ''.join(conteudo_parts[:10])
    
    return resultado

def criar_feed_caucaia_wordpress():
    """Cria feed otimizado para WordPress com imagens destacadas"""
    
    print("🎯 SCRAPER CAUCAIA - WORDPRESS COM IMAGENS")
    print("="*70)
    
    URL_BASE = "https://www.caucaia.ce.gov.br"
    URL_LISTA = f"{URL_BASE}/informa.php"
    FEED_FILE = "feed_caucaia_wp_completo.xml"
    
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
        
        # Limitar
        lista_noticias = lista_noticias[:15]
        print(f"✅ {len(lista_noticias)} notícias coletadas\n")
        
        # 2. EXTRAIR CONTEÚDO COMPLETO
        print("="*70)
        print("🔍 Extraindo conteúdo completo...")
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
                
                # Extrair dados completos
                dados = extrair_conteudo_completo(soup_noticia, URL_BASE)
                
                # Usar título extraído ou o original
                titulo_final = dados['titulo'] if dados['titulo'] else noticia['titulo_original']
                
                # Extrair data
                texto_pagina = soup_noticia.get_text()
                data_match = re.search(r'(\d{2}/\d{2}/\d{4})', texto_pagina[:2000])
                data_str = data_match.group(1) if data_match else None
                
                # Extrair categoria
                categoria = None
                for elem in soup_noticia.find_all(['span', 'div'], class_=lambda x: x and any(
                    word in str(x).lower() for word in ['tag', 'categoria', 'category', 'setor']
                )):
                    texto = elem.get_text(strip=True)
                    if texto and len(texto) < 30:
                        categoria = texto
                        break
                
                noticias_completas.append({
                    'titulo': titulo_final,
                    'link': noticia['link'],
                    'imagem_destacada': dados['imagem_destacada'],
                    'conteudo': dados['conteudo_html'],
                    'imagens_embutidas': dados['imagens_embutidas'],
                    'data': data_str,
                    'categoria': categoria
                })
                
                print(f"   ✅ Título: {titulo_final[:50]}...")
                if dados['imagem_destacada']:
                    print(f"   🖼️  Imagem destacada encontrada")
                print(f"   📝 Conteúdo: {len(dados['conteudo_html']):,} caracteres")
                
            except Exception as e:
                print(f"   ❌ Erro: {str(e)[:80]}")
                continue
        
        # 3. GERAR FEED PARA WORDPRESS
        print(f"\n{'='*70}")
        print("📝 Gerando feed WordPress completo...")
        print(f"{'='*70}")
        
        xml_lines = []
        xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_lines.append('<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:wp="http://wordpress.org/export/1.2/">')
        xml_lines.append('<channel>')
        xml_lines.append(f'  <title>Notícias de Caucaia - Completo</title>')
        xml_lines.append(f'  <link>{URL_BASE}</link>')
        xml_lines.append(f'  <description>Notícias com imagens destacadas e conteúdo completo</description>')
        xml_lines.append(f'  <language>pt-br</language>')
        xml_lines.append(f'  <wp:wxr_version>1.2</wp:wxr_version>')
        xml_lines.append(f'  <generator>Caucaia WP Importer</generator>')
        xml_lines.append(f'  <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
        xml_lines.append(f'  <ttl>180</ttl>')
        
        for i, noticia in enumerate(noticias_completas, 1):
            print(f"   📄 [{i}] {noticia['titulo'][:50]}...")
            
            # GUID único
            guid = hashlib.md5(noticia['link'].encode()).hexdigest()[:12]
            
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
            
            xml_lines.append('  <item>')
            xml_lines.append(f'    <title>{html.escape(noticia["titulo"])}</title>')
            xml_lines.append(f'    <link>{noticia["link"]}</link>')
            xml_lines.append(f'    <guid isPermaLink="false">caucaia-{guid}</guid>')
            xml_lines.append(f'    <pubDate>{data_rss}</pubDate>')
            
            if noticia['categoria']:
                xml_lines.append(f'    <category><![CDATA[{noticia["categoria"]}]]></category>')
            
            # Description (resumo)
            descricao_resumo = noticia['titulo']
            if noticia['data']:
                descricao_resumo += f" | {noticia['data']}"
            xml_lines.append(f'    <description><![CDATA[{html.escape(descricao_resumo)}]]></description>')
            
            # ✅ CONTEÚDO COMPLETO PARA WORDPRESS
            conteudo_final = noticia['conteudo']
            
            # Adicionar fonte no final
            fonte_html = f'''
            <div style="margin-top: 30px; padding: 15px; background: #f8f9fa; border-left: 4px solid #0073aa;">
                <strong>📰 Fonte oficial:</strong> 
                <a href="{noticia['link']}" target="_blank">Prefeitura Municipal de Caucaia</a>
                {f" | {noticia['data']}" if noticia['data'] else ""}
            </div>
            '''
            conteudo_final += fonte_html
            
            xml_lines.append(f'    <content:encoded><![CDATA[ {conteudo_final} ]]></content:encoded>')
            
            # ✅ IMAGEM DESTACADA (para WordPress)
            if noticia['imagem_destacada']:
                # Método 1: enclosure (para alguns importadores)
                xml_lines.append(f'    <enclosure url="{noticia["imagem_destacada"]}" type="image/jpeg" length="0" />')
                
                # Método 2: media:content (padrão RSS)
                xml_lines.append(f'    <media:content url="{noticia["imagem_destacada"]}" type="image/jpeg" medium="image">')
                xml_lines.append(f'      <media:title>{html.escape(noticia["titulo"][:100])}</media:title>')
                xml_lines.append(f'      <media:description>Imagem destacada: {html.escape(noticia["titulo"][:150])}</media:description>')
                xml_lines.append(f'      <media:credit>Prefeitura de Caucaia</media:credit>')
                xml_lines.append(f'    </media:content>')
                
                # Método 3: Meta WordPress (para WXR import)
                xml_lines.append(f'    <wp:postmeta>')
                xml_lines.append(f'      <wp:meta_key>_thumbnail_id</wp:meta_key>')
                xml_lines.append(f'      <wp:meta_value><![CDATA[external_{guid}]]></wp:meta_value>')
                xml_lines.append(f'    </wp:postmeta>')
                
                # Imagem como attachment (formato WXR)
                xml_lines.append(f'    <wp:attachment_url>{noticia["imagem_destacada"]}</wp:attachment_url>')
            
            # Imagens embutidas no conteúdo
            for img_url in noticia['imagens_embutidas'][:5]:  # Limitar a 5 imagens
                xml_lines.append(f'    <media:content url="{img_url}" type="image/jpeg" medium="image" />')
            
            xml_lines.append('  </item>')
        
        xml_lines.append('</channel>')
        xml_lines.append('</rss>')
        
        # Salvar arquivo
        with open(FEED_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_lines))
        
        # 4. RELATÓRIO
        print(f"\n✅ FEED GERADO: {FEED_FILE}")
        print(f"📊 RESUMO:")
        print(f"   • Notícias processadas: {len(noticias_completas)}")
        print(f"   • Com imagem destacada: {sum(1 for n in noticias_completas if n['imagem_destacada'])}")
        print(f"   • Com imagens no conteúdo: {sum(1 for n in noticias_completas if n['imagens_embutidas'])}")
        
        if noticias_completas:
            primeira = noticias_completas[0]
            print(f"\n📋 EXEMPLO:")
            print(f"   Título: {primeira['titulo'][:80]}")
            print(f"   Imagem destacada: {primeira['imagem_destacada']}")
            print(f"   Imagens no conteúdo: {len(primeira['imagens_embutidas'])}")
        
        print(f"\n{'='*70}")
        print("🚀 COMO IMPORTAR NO WORDPRESS:")
        print("1. Instale o plugin 'WP RSS Aggregator'")
        print("2. Adicione o feed: https://seusite.github.io/feed_caucaia_wp_completo.xml")
        print("3. Configure:")
        print("   - Content Source: content:encoded")
        print("   - Featured Images: ON")
        print("   - Import Images: ON")
        print("4. O plugin irá:")
        print("   • Criar posts com conteúdo completo")
        print("   • Baixar imagem destacada automaticamente")
        print("   • Inserir imagens no conteúdo")
        print(f"{'='*70}")
        
        # Criar também um arquivo de configuração simples
        config_content = f"""# CONFIGURAÇÃO WORDPRESS RSS AGGREGATOR
Feed URL: https://thecrossnow.github.io/feed-leg-ftz/feed_caucaia_wp_completo.xml

Configurações recomendadas:
1. General:
   - Feed Name: Notícias Caucaia
   - Limit: 10 items
   - Update interval: 2 hours

2. Content:
   - Use content:encoded
   - Import images: ✅ Yes
   - Set first image as featured: ✅ Yes

3. Featured Image:
   - Import as featured image: ✅ Yes
   - Use enclosure/media:content

4. Taxonomies:
   - Import categories: ✅ Yes

Última geração: {datetime.now().strftime('%d/%m/%Y %H:%M')}
Total de itens: {len(noticias_completas)}
"""
        
        with open('wp_config.txt', 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    criar_feed_caucaia_wordpress()
