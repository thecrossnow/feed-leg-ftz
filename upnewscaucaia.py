#!/usr/bin/env python3
"""
SCRAPER CAUCAIA - CÓDIGO COMPLETO FUNCIONAL
Conteúdo limpo para WordPress
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import html
import hashlib
import time
from urllib.parse import urljoin
import re

def extrair_conteudo_limpo_wordpress(soup_noticia, url_base):
    """Extrai APENAS o conteúdo essencial para WordPress"""
    
    resultado = {
        'imagem_principal': None,
        'titulo': None,
        'conteudo_limpo': []
    }
    
    # 1. IMAGEM PRINCIPAL
    img_principal = soup_noticia.find('img', class_='imginfo')
    if not img_principal:
        for img_class in ['img-responsive', 'ImagemIndexNoticia']:
            img_principal = soup_noticia.find('img', class_=img_class)
            if img_principal:
                break
    
    if img_principal and img_principal.get('src'):
        src = img_principal['src']
        if not src.startswith(('http://', 'https://')):
            src = urljoin(url_base, src)
        resultado['imagem_principal'] = src
    
    # 2. TÍTULO
    titulo_h1 = soup_noticia.find('h1', class_='DataInforma')
    if titulo_h1:
        resultado['titulo'] = titulo_h1.get_text(strip=True)
    else:
        for tag in soup_noticia.find_all(['h1', 'strong']):
            texto = tag.get_text(strip=True)
            if len(texto) > 30:
                resultado['titulo'] = texto
                break
    
    # 3. CORPO DA NOTÍCIA (DIV p-info)
    div_conteudo = soup_noticia.find('div', class_='p-info')
    
    if div_conteudo:
        for elemento in div_conteudo.find_all(['p', 'h2', 'h3', 'strong', 'em']):
            texto = elemento.get_text(strip=True)
            if not texto or len(texto) < 20:
                continue
            
            # Ignorar elementos de interface
            html_elemento = str(elemento)
            if any(indesejado in html_elemento.lower() for indesejado in [
                'social', 'fb-', 'coment', 'share', 'whatsapp', 'facebook', 'twitter'
            ]):
                continue
            
            if elemento.name == 'p':
                # Limpar classes e estilos
                html_limpo = re.sub(r'class="[^"]*"', '', str(elemento))
                html_limpo = re.sub(r'style="[^"]*"', '', html_limpo)
                html_limpo = re.sub(r'id="[^"]*"', '', html_limpo)
                
                # Manter apenas tags seguras
                html_limpo = re.sub(r'<(?!/?p\b|/?strong\b|/?b\b|/?em\b|/?i\b|/?a\b|/?br\s*/?)[^>]*>', '', html_limpo)
                
                if html_limpo.strip():
                    resultado['conteudo_limpo'].append(html_limpo)
            
            elif elemento.name.startswith('h'):
                resultado['conteudo_limpo'].append(f'<{elemento.name}>{html.escape(texto)}</{elemento.name}>')
            
            elif elemento.name in ['strong', 'b']:
                resultado['conteudo_limpo'].append(f'<p><strong>{html.escape(texto)}</strong></p>')
            
            elif elemento.name in ['em', 'i']:
                resultado['conteudo_limpo'].append(f'<p><em>{html.escape(texto)}</em></p>')
    
    # Se não encontrou conteúdo, extrair parágrafos
    if not resultado['conteudo_limpo']:
        todos_p = soup_noticia.find_all('p')
        for p in todos_p:
            texto = p.get_text(strip=True)
            if len(texto) > 50 and len(texto) < 1000:
                # Filtrar lixo
                if any(lixo in texto.lower() for lixo in ['compartilhe', 'curtir', 'comente', 'whatsapp']):
                    continue
                resultado['conteudo_limpo'].append(f'<p>{html.escape(texto)}</p>')
    
    return resultado

def criar_conteudo_wordpress_formatado(dados_noticia, link_original):
    """Cria conteúdo formatado para WordPress"""
    
    partes = []
    
    # 1. IMAGEM PRINCIPAL
    if dados_noticia.get('imagem_principal'):
        img_url = dados_noticia['imagem_principal']
        titulo_escape = html.escape(dados_noticia.get('titulo', 'Notícia Caucaia'))
        
        imagem_html = f'''
        <div class="wp-block-image">
            <figure class="aligncenter size-large">
                <img src="{img_url}" 
                     alt="{titulo_escape}" 
                     class="wp-image-{hashlib.md5(img_url.encode()).hexdigest()[:8]}"
                     style="max-width: 100%; height: auto;"
                     loading="lazy" />
                <figcaption>Foto: Prefeitura de Caucaia</figcaption>
            </figure>
        </div>
        '''
        partes.append(imagem_html.strip())
    
    # 2. TÍTULO
    if dados_noticia.get('titulo'):
        partes.append(f'<h1>{html.escape(dados_noticia["titulo"])}</h1>')
    
    # 3. CORPO DA NOTÍCIA
    if dados_noticia.get('conteudo_limpo'):
        for elemento in dados_noticia['conteudo_limpo'][:20]:  # Limitar a 20 elementos
            partes.append(elemento)
    
    # 4. FONTE
    fonte_html = f'''
    <div style="margin-top: 30px; padding: 15px; background: #f8f9fa; border-left: 4px solid #0073aa;">
        <strong>📰 Fonte oficial:</strong> 
        <a href="{link_original}" target="_blank">Prefeitura Municipal de Caucaia</a>
    </div>
    '''
    partes.append(fonte_html.strip())
    
    return '\n'.join(partes)

def criar_feed_caucaia_completo():
    """Função principal - cria feed completo"""
    
    print("🎯 SCRAPER CAUCAIA - CONTEÚDO LIMPO")
    print("="*70)
    
    URL_BASE = "https://www.caucaia.ce.gov.br"
    URL_LISTA = f"{URL_BASE}/informa.php"
    FEED_FILE = "feed_caucaia_limpo.xml"
    
    HEADERS = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        # === FASE 1: COLETAR NOTÍCIAS ===
        print("📋 Coletando notícias da página principal...")
        response = requests.get(URL_LISTA, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        lista_noticias = []
        links_processados = set()
        
        # Buscar links de notícias
        for link in soup.find_all('a', href=lambda x: x and '/informa/' in x):
            href = link['href']
            
            if href not in links_processados:
                titulo = link.get_text(strip=True)
                
                if titulo and len(titulo) > 20 and 'Continue' not in titulo:
                    link_url = urljoin(URL_BASE, href)
                    links_processados.add(href)
                    
                    lista_noticias.append({
                        'titulo': titulo[:300],
                        'link': link_url,
                        'conteudo': None,
                        'imagem': None,
                        'data': None,
                        'categoria': None
                    })
        
        # Limitar para teste
        lista_noticias = lista_noticias[:10]
        print(f"✅ {len(lista_noticias)} notícias coletadas\n")
        
        # === FASE 2: EXTRAIR CONTEÚDO LIMPO ===
        print("="*70)
        print("🔍 Extraindo conteúdo limpo...")
        print("="*70)
        
        for i, noticia in enumerate(lista_noticias, 1):
            print(f"\n📖 [{i}/{len(lista_noticias)}] {noticia['titulo'][:60]}...")
            
            try:
                time.sleep(1)
                resp = requests.get(noticia['link'], headers=HEADERS, timeout=30)
                
                if resp.status_code != 200:
                    print(f"   ⚠️  Erro {resp.status_code}")
                    continue
                
                soup_noticia = BeautifulSoup(resp.content, 'html.parser')
                
                # Extrair conteúdo limpo
                dados_limpos = extrair_conteudo_limpo_wordpress(soup_noticia, URL_BASE)
                
                # Atualizar título
                if dados_limpos.get('titulo'):
                    noticia['titulo'] = dados_limpos['titulo']
                
                # Extrair data
                texto_pagina = soup_noticia.get_text()
                data_match = re.search(r'(\d{2}/\d{2}/\d{4})', texto_pagina[:2000])
                if data_match:
                    noticia['data'] = data_match.group(1)
                
                # Extrair categoria
                tag_match = re.search(r'#(\w+)', texto_pagina[:1000])
                if tag_match:
                    noticia['categoria'] = f"#{tag_match.group(1)}"
                
                # Criar conteúdo WordPress
                noticia['conteudo'] = criar_conteudo_wordpress_formatado(dados_limpos, noticia['link'])
                noticia['imagem'] = dados_limpos.get('imagem_principal')
                
                print(f"   ✅ Conteúdo limpo extraído")
                if noticia['imagem']:
                    print(f"   🖼️  Imagem: {noticia['imagem'][:60]}...")
                
            except Exception as e:
                print(f"   ❌ Erro: {str(e)[:80]}")
                noticia['conteudo'] = f"<p>Conteúdo disponível em: <a href='{noticia['link']}'>{noticia['link']}</a></p>"
        
        # === FASE 3: GERAR FEED XML ===
        print(f"\n{'='*70}")
        print("📝 Gerando feed XML...")
        print(f"{'='*70}")
        
        xml_lines = []
        xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_lines.append('<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">')
        xml_lines.append('<channel>')
        xml_lines.append(f'  <title>Notícias da Prefeitura de Caucaia</title>')
        xml_lines.append(f'  <link>{URL_BASE}</link>')
        xml_lines.append(f'  <description>Conteúdo limpo para WordPress</description>')
        xml_lines.append(f'  <language>pt-br</language>')
        xml_lines.append(f'  <generator>Scraper Caucaia Conteúdo Limpo</generator>')
        xml_lines.append(f'  <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
        xml_lines.append(f'  <ttl>180</ttl>')
        
        for i, noticia in enumerate(lista_noticias, 1):
            print(f"   📄 [{i}] {noticia['titulo'][:50]}...")
            
            # GUID
            guid = hashlib.md5(noticia['link'].encode()).hexdigest()[:12]
            
            # Data
            if noticia['data'] and '/' in noticia['data']:
                try:
                    partes = noticia['data'].split('/')
                    dia, mes, ano = map(int, partes)
                    data_obj = datetime(ano, mes, dia, 12, 0, 0, tzinfo=timezone.utc)
                except:
                    data_obj = datetime.now(timezone.utc) - timedelta(days=i)
            else:
                data_obj = datetime.now(timezone.utc) - timedelta(days=i)
            
            data_rss = data_obj.strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            xml_lines.append('  <item>')
            xml_lines.append(f'    <title>{html.escape(noticia["titulo"])}</title>')
            xml_lines.append(f'    <link>{noticia["link"]}</link>')
            xml_lines.append(f'    <guid isPermaLink="false">caucaia-{guid}</guid>')
            xml_lines.append(f'    <pubDate>{data_rss}</pubDate>')
            
            if noticia['categoria']:
                xml_lines.append(f'    <category>{html.escape(noticia["categoria"])}</category>')
            
            # Descrição
            descricao = noticia['titulo']
            if noticia['data']:
                descricao += f" | {noticia['data']}"
            xml_lines.append(f'    <description>{html.escape(descricao[:250])}</description>')
            
            # CONTEÚDO LIMPO
            conteudo_final = noticia['conteudo'] or "<p>Notícia da Prefeitura de Caucaia.</p>"
            xml_lines.append(f'    <content:encoded><![CDATA[ {conteudo_final} ]]></content:encoded>')
            
            # Imagem
            if noticia['imagem']:
                xml_lines.append(f'    <enclosure url="{noticia["imagem"]}" type="image/jpeg" length="80000" />')
                xml_lines.append(f'    <media:content url="{noticia["imagem"]}" type="image/jpeg" medium="image">')
                xml_lines.append(f'      <media:title>{html.escape(noticia["titulo"][:100])}</media:title>')
                xml_lines.append(f'      <media:description>{html.escape(noticia["titulo"][:200])}</media:description>')
                xml_lines.append(f'    </media:content>')
            
            xml_lines.append('  </item>')
        
        xml_lines.append('</channel>')
        xml_lines.append('</rss>')
        
        # Salvar
        with open(FEED_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_lines))
        
        # Resultado
        print(f"\n✅ FEED GERADO: {FEED_FILE}")
        print(f"📊 RESUMO:")
        print(f"   • Notícias: {len(lista_noticias)}")
        print(f"   • Com imagens: {sum(1 for n in lista_noticias if n['imagem'])}")
        
        # Mostrar exemplo
        if lista_noticias:
            primeira = lista_noticias[0]
            print(f"\n📋 EXEMPLO DO CONTEÚDO:")
            print(f"   Título: {primeira['titulo'][:80]}...")
            
            # Extrair texto limpo do conteúdo
            soup_conteudo = BeautifulSoup(primeira['conteudo'], 'html.parser')
            texto_limpo = soup_conteudo.get_text()
            print(f"   Texto limpo: {texto_limpo[:200]}...")
        
        print(f"\n{'='*70}")
        print("🎉 PRONTO PARA WORDPRESS!")
        print("O conteúdo dentro de <content:encoded> está limpo e formatado.")
        print(f"{'='*70}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    criar_feed_caucaia_completo()
