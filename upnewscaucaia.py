#!/usr/bin/env python3
"""
SCRAPER CAUCAIA - VERSÃO FINAL OTIMIZADA
Funcionando 100% - apenas ajustes finais
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import html
import hashlib
import time
from urllib.parse import urljoin
import re

def criar_feed_caucaia_final():
    """Versão final otimizada"""
    
    print("🎯 SCRAPER CAUCAIA - VERSÃO FINAL")
    print("="*70)
    
    URL_BASE = "https://www.caucaia.ce.gov.br"
    URL_LISTA = f"{URL_BASE}/informa.php"
    FEED_FILE = "feed_caucaia_final.xml"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        # 1. COLETAR NOTÍCIAS DA PÁGINA PRINCIPAL
        print("📋 Coletando notícias...")
        response = requests.get(URL_LISTA, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        lista_noticias = []
        links_processados = set()
        
        # Buscar links de notícias
        for link in soup.find_all('a', href=lambda x: x and '/informa/' in x):
            href = link['href']
            
            if href not in links_processados:
                # Extrair título do texto do link
                titulo = link.get_text(strip=True)
                
                # Pular links "Continue lendo..."
                if titulo and len(titulo) > 20 and 'Continue' not in titulo:
                    link_url = urljoin(URL_BASE, href)
                    links_processados.add(href)
                    
                    lista_noticias.append({
                        'titulo': titulo[:300],  # Limitar tamanho
                        'link': link_url,
                        'conteudo': None,
                        'imagem': None,
                        'data': None,
                        'categoria': None
                    })
        
        # Limitar para teste (remova esta linha para todas)
        lista_noticias = lista_noticias[:12]
        print(f"✅ {len(lista_noticias)} notícias coletadas\n")
        
        # 2. EXTRAIR CONTEÚDO DETALHADO
        print("="*70)
        print("🔍 Extraindo conteúdo detalhado...")
        print("="*70)
        
        for i, noticia in enumerate(lista_noticias, 1):
            print(f"\n📖 [{i}/{len(lista_noticias)}] {noticia['titulo'][:60]}...")
            
            try:
                time.sleep(1)  # Respeitar servidor
                resp = requests.get(noticia['link'], headers=HEADERS, timeout=30)
                
                if resp.status_code != 200:
                    print(f"   ⚠️  Erro {resp.status_code}")
                    continue
                
                soup_noticia = BeautifulSoup(resp.content, 'html.parser')
                
                # A. MELHORAR TÍTULO (se houver h1/h2 na página)
                titulo_tags = soup_noticia.find_all(['h1', 'h2', 'h3'])
                for tag in titulo_tags:
                    texto = tag.get_text(strip=True)
                    if len(texto) > 30:
                        noticia['titulo'] = texto[:250]
                        break
                
                # B. EXTRAIR DATA
                # Procurar data em vários lugares
                texto_pagina = soup_noticia.get_text()
                
                # Padrões de data
                padroes_data = [
                    r'(\d{2}/\d{2}/\d{4})',  # DD/MM/YYYY
                    r'(\d{2} de [a-zç]+ de \d{4})',  # DD de MMMM de YYYY
                    r'Publicado em[:\s]*([^\n<]+)',  # Publicado em: ...
                    r'Data[:\s]*([^\n<]+)',  # Data: ...
                ]
                
                for padrao in padroes_data:
                    match = re.search(padrao, texto_pagina[:3000], re.IGNORECASE)
                    if match:
                        noticia['data'] = match.group(1).strip()
                        break
                
                if noticia['data']:
                    print(f"   📅 Data: {noticia['data']}")
                
                # C. EXTRAIR CONTEÚDO PRINCIPAL
                # Estratégias para encontrar conteúdo
                conteudo_div = None
                
                # 1. Por ID
                for id_name in ['conteudo', 'texto', 'noticia', 'post', 'article']:
                    conteudo_div = soup_noticia.find('div', id=id_name)
                    if conteudo_div:
                        break
                
                # 2. Por classe
                if not conteudo_div:
                    for classe in ['conteudo', 'texto', 'noticia', 'post', 'article', 'entry-content']:
                        conteudo_div = soup_noticia.find('div', class_=classe)
                        if conteudo_div:
                            break
                
                # 3. Fallback: div com mais texto
                if not conteudo_div:
                    divs = soup_noticia.find_all('div')
                    if divs:
                        # Encontrar div com mais texto
                        conteudo_div = max(
                            [div for div in divs if len(div.get_text(strip=True)) > 200],
                            key=lambda x: len(x.get_text(strip=True)),
                            default=None
                        )
                
                if conteudo_div:
                    # Limpar elementos indesejados
                    for tag in conteudo_div.find_all(['script', 'style', 'iframe', 'form', 'nav', 'footer', 'header', 'aside']):
                        tag.decompose()
                    
                    # Manter estrutura HTML
                    html_conteudo = str(conteudo_div)
                    
                    # Se ainda for muito curto, adicionar mais parágrafos
                    if len(html_conteudo) < 1000:
                        all_p = soup_noticia.find_all('p')
                        if all_p:
                            html_conteudo = ''.join(str(p) for p in all_p[:15])
                    
                    noticia['conteudo'] = html_conteudo
                    print(f"   📝 Conteúdo: {len(html_conteudo):,} caracteres")
                else:
                    # Fallback: texto completo
                    texto = soup_noticia.get_text()
                    linhas = [linha.strip() for linha in texto.split('\n') if len(linha.strip()) > 50]
                    noticia['conteudo'] = ''.join(f'<p>{html.escape(linha)}</p>' for linha in linhas[:20])
                    print(f"   📝 Conteúdo (fallback): {len(noticia['conteudo']):,} caracteres")
                
                # D. TENTAR ENCONTRAR IMAGEM REAL
                # Primeiro, verificar se há imagem no conteúdo
                if conteudo_div:
                    img = conteudo_div.find('img', src=True)
                    if img:
                        src = img['src']
                        if not src.startswith(('http://', 'https://')):
                            src = urljoin(URL_BASE, src)
                        
                        # Validar que não é placeholder
                        if 'p_noticia.png' not in src and 'selo' not in src.lower():
                            noticia['imagem'] = src
                            print(f"   🖼️  Imagem real encontrada")
                
                # Se não encontrou, usar placeholder
                if not noticia['imagem']:
                    noticia['imagem'] = urljoin(URL_BASE, '/imagens/p_noticia.png')
                    print(f"   🖼️  Usando imagem padrão")
                
                # E. EXTRAIR CATEGORIA (se houver)
                # Procurar por tags/categorias
                for elem in soup_noticia.find_all(['span', 'div'], class_=lambda x: x and any(
                    word in str(x).lower() for word in ['tag', 'categoria', 'category', 'setor']
                )):
                    texto = elem.get_text(strip=True)
                    if texto and len(texto) < 30:
                        noticia['categoria'] = texto
                        break
                
                if noticia['categoria']:
                    print(f"   🏷️  Categoria: {noticia['categoria']}")
                
            except Exception as e:
                print(f"   ❌ Erro: {str(e)[:80]}")
                noticia['conteudo'] = f"<p>Erro ao carregar notícia. <a href='{noticia['link']}'>Acesse aqui</a></p>"
        
        # 3. GERAR FEED XML
        print(f"\n{'='*70}")
        print("📝 Gerando feed XML final...")
        print(f"{'='*70}")
        
        xml_lines = []
        xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_lines.append('<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">')
        xml_lines.append('<channel>')
        xml_lines.append(f'  <title>Notícias Oficiais - Prefeitura de Caucaia</title>')
        xml_lines.append(f'  <link>{URL_BASE}</link>')
        xml_lines.append(f'  <description>Notícias completas da Prefeitura Municipal de Caucaia/CE</description>')
        xml_lines.append(f'  <language>pt-br</language>')
        xml_lines.append(f'  <generator>Scraper Caucaia v4.0</generator>')
        xml_lines.append(f'  <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
        xml_lines.append(f'  <ttl>180</ttl>')
        
        # Adicionar cada notícia
        for i, noticia in enumerate(lista_noticias, 1):
            print(f"   📄 [{i}] {noticia['titulo'][:50]}...")
            
            # GUID único
            guid = hashlib.md5(f"{noticia['link']}{noticia['titulo']}".encode()).hexdigest()[:12]
            
            # Data para RSS
            if noticia['data'] and '/' in noticia['data']:
                try:
                    partes = noticia['data'].split('/')
                    if len(partes) == 3:
                        dia, mes, ano = map(int, partes)
                        # Criar datetime (assumindo meio-dia)
                        data_obj = datetime(ano, mes, dia, 12, 0, 0, tzinfo=timezone.utc)
                    else:
                        raise ValueError
                except:
                    # Fallback: datas distribuídas
                    data_obj = datetime.now(timezone.utc) - timedelta(days=i*2)
            else:
                # Datas distribuídas
                data_obj = datetime.now(timezone.utc) - timedelta(days=i*2)
            
            data_rss = data_obj.strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            xml_lines.append('  <item>')
            xml_lines.append(f'    <title>{html.escape(noticia["titulo"])}</title>')
            xml_lines.append(f'    <link>{noticia["link"]}</link>')
            xml_lines.append(f'    <guid isPermaLink="false">caucaia-{guid}</guid>')
            xml_lines.append(f'    <pubDate>{data_rss}</pubDate>')
            
            # Categoria
            if noticia['categoria']:
                xml_lines.append(f'    <category>{html.escape(noticia["categoria"])}</category>')
            
            # Descrição (resumo)
            descricao = noticia['titulo']
            if noticia['data']:
                descricao += f" | {noticia['data']}"
            xml_lines.append(f'    <description>{html.escape(descricao[:250])}</description>')
            
            # CONTEÚDO COMPLETO com imagem otimizada
            conteudo_final = noticia['conteudo']
            
            # Adicionar imagem no início (formato WordPress amigável)
            if noticia['imagem']:
                imagem_html = f'''
                <div class="wp-block-image">
                    <figure class="aligncenter size-full">
                        <img src="{noticia['imagem']}" 
                             alt="{html.escape(noticia['titulo'])}" 
                             class="wp-image-{guid}"
                             style="max-width: 100%; height: auto;"
                             loading="lazy" />
                        <figcaption>Foto: Prefeitura de Caucaia</figcaption>
                    </figure>
                </div>
                '''
                conteudo_final = imagem_html + conteudo_final
            
            # Adicionar fonte
            conteudo_final += f'''
            <div style="margin-top: 20px; padding: 10px; background: #f5f5f5; border-left: 4px solid #0066cc;">
                <strong>📰 Fonte oficial:</strong> 
                <a href="{noticia['link']}" target="_blank" rel="noopener">
                    Prefeitura Municipal de Caucaia - {noticia['data'] or "Notícia oficial"}
                </a>
            </div>
            '''
            
            xml_lines.append(f'    <content:encoded><![CDATA[ {conteudo_final} ]]></content:encoded>')
            
            # Imagem como enclosure (para WordPress)
            if noticia['imagem']:
                xml_lines.append(f'    <enclosure url="{noticia["imagem"]}" type="image/jpeg" length="80000" />')
                # Media content com metadados
                xml_lines.append(f'    <media:content url="{noticia["imagem"]}" type="image/jpeg" medium="image">')
                xml_lines.append(f'      <media:title>{html.escape(noticia["titulo"][:100])}</media:title>')
                xml_lines.append(f'      <media:description>{html.escape(noticia["titulo"][:200])}</media:description>')
                xml_lines.append(f'      <media:credit>Prefeitura de Caucaia</media:credit>')
                xml_lines.append(f'    </media:content>')
            
            xml_lines.append('  </item>')
        
        xml_lines.append('</channel>')
        xml_lines.append('</rss>')
        
        # Salvar arquivo
        with open(FEED_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_lines))
        
        # ESTATÍSTICAS
        print(f"\n✅ FEED GERADO: {FEED_FILE}")
        print(f"📊 RESUMO FINAL:")
        print(f"   • Notícias processadas: {len(lista_noticias)}")
        
        # Verificar conteúdo real
        conteudo_valido = sum(1 for n in lista_noticias if n['conteudo'] and len(n['conteudo']) > 1000)
        print(f"   • Com conteúdo válido (>1K chars): {conteudo_valido}")
        
        # Mostrar exemplo
        if lista_noticias:
            primeira = lista_noticias[0]
            print(f"\n📋 EXEMPLO DO PRIMEIRO ITEM:")
            print(f"   Título: {primeira['titulo'][:80]}...")
            print(f"   Link: {primeira['link']}")
            print(f"   Conteúdo: {len(primeira['conteudo']):,} caracteres")
            print(f"   Imagem: {primeira['imagem']}")
        
        print(f"\n{'='*70}")
        print("🚀 PRÓXIMOS PASSOS:")
        print("1. Hospedar feed_caucaia_final.xml no GitHub Pages")
        print("2. Configurar no WP RSS Aggregator:")
        print("   - Feed URL: https://seusite.github.io/feed_caucaia_final.xml")
        print("   - Content: {content:encoded}")
        print("   - Import Images: ✅ ON")
        print("   - Featured Image: ✅ ON")
        print("3. Agendar atualizações a cada 4 horas")
        print(f"{'='*70}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    criar_feed_caucaia_final()
