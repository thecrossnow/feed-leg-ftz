#!/usr/bin/env python3
# upnewsagenciabr.py - Agência Brasil via RSS Oficial para WordPress

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, date, timezone
import html
import re
from urllib.parse import urljoin, quote
import xml.etree.ElementTree as ET
from xml.dom import minidom

# ================= CONFIG =================

RSS_URL = "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml"
URL_BASE = "https://agenciabrasil.ebc.com.br"

FEED_FILE = "feed_agenciabrasil_wp.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Configurações WordPress
WP_CATEGORY = "Notícias"
WP_AUTHOR = "Agência Brasil"

# ================= DATAS =================

HOJE = date.today()
ONTEM = HOJE - timedelta(days=1)

# ================= FUNÇÕES =================

def limpar_texto(texto):
    """Limpa e formata texto para XML seguro"""
    if not texto:
        return ""
    
    texto = html.unescape(texto)
    
    # Remover múltiplos espaços e quebras de linha
    texto = re.sub(r'\s+', ' ', texto)
    
    # Codificar caracteres especiais XML (MAS NÃO para CDATA)
    # Em CDATA, só precisamos escapar ]]> 
    texto = texto.replace(']]>', ']]]]><![CDATA[>')
    
    return texto.strip()

def limpar_texto_para_elemento(texto):
    """Limpa texto para uso direto em elementos XML (sem CDATA)"""
    if not texto:
        return ""
    
    texto = html.unescape(texto)
    
    # Remover múltiplos espaços e quebras de linha
    texto = re.sub(r'\s+', ' ', texto)
    
    # Codificar caracteres especiais XML
    texto = texto.replace('&', '&amp;')
    texto = texto.replace('<', '&lt;')
    texto = texto.replace('>', '&gt;')
    texto = texto.replace('"', '&quot;')
    texto = texto.replace("'", '&apos;')
    
    # Remover caracteres de controle
    texto = ''.join(char for char in texto if char.isprintable() or char in '\n\r\t')
    
    return texto.strip()

def parse_rss_date(pubdate):
    """
    Converte data RSS para formato WordPress
    Exemplo: Tue, 23 Dec 2025 14:30:00 -0300 -> 2025-12-23 14:30:00
    """
    try:
        # Formato RSS padrão
        dt = datetime.strptime(pubdate[:25], "%a, %d %b %Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"   ⚠ Erro ao parsear data '{pubdate}': {e}")
        # Usar data atual como fallback
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def extrair_conteudo_completo(url, session):
    """Extrai conteúdo formatado para WordPress"""
    try:
        print(f"   🌐 Acessando: {url}")
        r = session.get(url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"   ❌ Erro ao acessar página: {e}")
        return None, None, None
    
    soup = BeautifulSoup(r.content, "html.parser")
    
    # 1. EXTRAIR IMAGEM DESTAQUE
    featured_image = None
    
    # Primeiro tenta og:image
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        featured_image = og_image["content"]
        print(f"   📷 Imagem do OG: {featured_image[:80]}...")
    
    # Se não encontrar, procura imagem principal no conteúdo
    if not featured_image:
        # Procura por imagens grandes no artigo
        img_tags = soup.find_all("img", src=re.compile(r'\.(jpg|jpeg|png|webp)$', re.I))
        for img in img_tags:
            src = img.get("src", "")
            if src:
                # Verifica se é uma imagem de conteúdo (não logo, ícone, etc.)
                if (not any(word in src.lower() for word in ['logo', 'icon', 'avatar', 'thumb', 'small']) 
                    and any(word in src.lower() for word in ['image', 'foto', 'photo', 'img'])):
                    featured_image = urljoin(url, src) if not src.startswith('http') else src
                    print(f"   📷 Imagem do conteúdo: {featured_image[:80]}...")
                    break
    
    # 2. EXTRAIR CONTEÚDO COMPLETO
    conteudo_html = ""
    
    # Estratégias para encontrar o conteúdo principal
    content_selectors = [
        "article",
        ".conteudo",
        ".noticia-conteudo",
        ".materia-conteudo",
        ".texto-materia",
        "div[itemprop='articleBody']",
        ".entry-content",
        ".post-content",
        ".article-body",
        ".field-name-body",
        ".content"
    ]
    
    content_div = None
    for selector in content_selectors:
        if selector.startswith('.'):
            content_div = soup.select_one(selector)
        else:
            content_div = soup.find(selector)
        if content_div:
            print(f"   ✅ Conteúdo encontrado com seletor: {selector}")
            break
    
    # Fallback: procurar por divs com muito texto
    if not content_div:
        print("   🔍 Procurando conteúdo por fallback...")
        all_divs = soup.find_all("div")
        for div in all_divs:
            text_length = len(div.get_text(strip=True))
            if text_length > 300:  # Div com conteúdo significativo
                content_div = div
                print(f"   ✅ Conteúdo encontrado por fallback ({text_length} chars)")
                break
    
    if not content_div:
        print("   ❌ Não foi possível encontrar conteúdo")
        return None, None, None
    
    # Remover elementos indesejados
    elementos_remover = ["script", "style", "iframe", "aside", "nav", 
                        "header", "footer", "form", "button", "input",
                        "select", "textarea"]
    
    for tag_name in elementos_remover:
        for element in content_div.find_all(tag_name):
            element.decompose()
    
    # Remover classes de anúncios e elementos irrelevantes
    for element in content_div.find_all(class_=re.compile(
        r"ad|banner|publicidade|propaganda|ads|widget|related|share|social|comentario|comment|meta|footer|header|navigation", 
        re.I)):
        element.decompose()
    
    # Processar o conteúdo para formato WordPress
    for element in content_div.find_all(recursive=False):
        # Parágrafos
        if element.name == 'p':
            text = element.get_text(strip=True)
            if len(text) > 20:
                conteudo_html += f"<p>{limpar_texto_para_elemento(text)}</p>\n"
        
        # Cabeçalhos
        elif element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            text = element.get_text(strip=True)
            if text and len(text) > 5:
                conteudo_html += f"<{element.name}>{limpar_texto_para_elemento(text)}</{element.name}>\n"
        
        # Listas
        elif element.name == 'ul':
            conteudo_html += "<ul>\n"
            for li in element.find_all('li', recursive=False):
                li_text = li.get_text(strip=True)
                if li_text:
                    conteudo_html += f"  <li>{limpar_texto_para_elemento(li_text)}</li>\n"
            conteudo_html += "</ul>\n"
        
        elif element.name == 'ol':
            conteudo_html += "<ol>\n"
            for li in element.find_all('li', recursive=False):
                li_text = li.get_text(strip=True)
                if li_text:
                    conteudo_html += f"  <li>{limpar_texto_para_elemento(li_text)}</li>\n"
            conteudo_html += "</ol>\n"
        
        # Citações
        elif element.name == 'blockquote':
            text = element.get_text(strip=True)
            if text:
                conteudo_html += f"<blockquote>{limpar_texto_para_elemento(text)}</blockquote>\n"
        
        # Imagens dentro do conteúdo
        elif element.name == 'img':
            src = element.get('src', '')
            alt = element.get('alt', '')
            if src:
                img_url = urljoin(url, src) if not src.startswith('http') else src
                conteudo_html += f'<p><img src="{img_url}" alt="{limpar_texto_para_elemento(alt)}" class="aligncenter" /></p>\n'
    
    # Se processou pouco conteúdo, usar extração por texto
    if len(conteudo_html) < 500:
        print("   🔍 Extraindo texto bruto...")
        texto_bruto = content_div.get_text(separator='\n', strip=True)
        paragraphs = [p.strip() for p in texto_bruto.split('\n') if len(p.strip()) > 30]
        
        if paragraphs:
            conteudo_html = "\n".join(f"<p>{limpar_texto_para_elemento(p)}</p>" for p in paragraphs[:15])
        else:
            # Último recurso: todo o texto
            texto_bruto = soup.get_text(separator='\n', strip=True)
            paragraphs = [p.strip() for p in texto_bruto.split('\n') if len(p.strip()) > 50]
            conteudo_html = "\n".join(f"<p>{limpar_texto_para_elemento(p)}</p>" for p in paragraphs[:10])
    
    # Adicionar imagem destacada no início se houver
    if featured_image and len(conteudo_html) > 0:
        # Usar o título do artigo para alt da imagem
        title_tag = soup.find("meta", property="og:title")
        alt_text = title_tag.get("content", "") if title_tag else "Imagem da notícia"
        conteudo_html = f'<p><img src="{featured_image}" alt="{limpar_texto_para_elemento(alt_text)}" class="aligncenter size-full" /></p>\n{conteudo_html}'
    
    # Adicionar link para fonte original
    fonte_link = f'<p><em>Fonte: <a href="{url}" rel="nofollow">Agência Brasil - EBC</a></em></p>'
    conteudo_html += fonte_link
    
    print(f"   ✅ Conteúdo extraído: {len(conteudo_html)} caracteres")
    return conteudo_html, featured_image

def gerar_feed_wordpress(noticias):
    """Gera feed XML no formato WordPress WXR simplificado"""
    
    # Criar estrutura XML
    rss = ET.Element("rss", {
        "version": "2.0",
        "xmlns:excerpt": "http://wordpress.org/export/1.2/excerpt/",
        "xmlns:content": "http://purl.org/rss/1.0/modules/content/",
        "xmlns:wfw": "http://wellformedweb.org/CommentAPI/",
        "xmlns:dc": "http://purl.org/dc/elements/1.1/",
        "xmlns:wp": "http://wordpress.org/export/1.2/"
    })
    
    channel = ET.SubElement(rss, "channel")
    
    # Informações do canal
    ET.SubElement(channel, "title").text = "Agência Brasil - Últimas Notícias"
    ET.SubElement(channel, "link").text = "https://agenciabrasil.ebc.com.br"
    ET.SubElement(channel, "description").text = "Notícias oficiais da Agência Brasil importadas automaticamente"
    ET.SubElement(channel, "pubDate").text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')
    ET.SubElement(channel, "language").text = "pt-BR"
    ET.SubElement(channel, "wp:wxr_version").text = "1.2"
    ET.SubElement(channel, "wp:base_site_url").text = "https://agenciabrasil.ebc.com.br"
    ET.SubElement(channel, "wp:base_blog_url").text = "https://agenciabrasil.ebc.com.br"
    
    # Autor único e simples
    author = ET.SubElement(channel, "wp:author")
    ET.SubElement(author, "wp:author_id").text = "1"
    ET.SubElement(author, "wp:author_login").text = "admin"
    ET.SubElement(author, "wp:author_email").text = "admin@example.com"
    ET.SubElement(author, "wp:author_display_name").text = WP_AUTHOR
    
    # Categoria padrão
    category = ET.SubElement(channel, "wp:category")
    ET.SubElement(category, "wp:term_id").text = "1"
    ET.SubElement(category, "wp:category_nicename").text = WP_CATEGORY.lower().replace(" ", "-")
    ET.SubElement(category, "wp:category_parent").text = ""
    ET.SubElement(category, "wp:cat_name").text = WP_CATEGORY
    
    # Adicionar cada notícia como POST
    post_id = 1000
    
    for i, noticia in enumerate(noticias, 1):
        item = ET.SubElement(channel, "item")
        
        # Título (usar limpeza para XML seguro)
        titulo_limpo = limpar_texto_para_elemento(noticia["title"])
        ET.SubElement(item, "title").text = titulo_limpo
        
        # Link
        ET.SubElement(item, "link").text = noticia["link"]
        
        # Datas
        pub_date = ET.SubElement(item, "pubDate")
        pub_date.text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
        
        # Creator (sem CDATA desnecessário)
        ET.SubElement(item, "dc:creator").text = WP_AUTHOR
        
        # GUID único
        guid = ET.SubElement(item, "guid", isPermaLink="false")
        guid.text = f"{noticia['link']}#{post_id}"
        
        # Descrição (excerpt) - SEM CDATA
        description = ET.SubElement(item, "description")
        description.text = noticia["excerpt"]
        
        # Conteúdo completo - SEM CDATA, já está limpo
        content = ET.SubElement(item, "content:encoded")
        content.text = noticia["content"]
        
        # Excerpt - SEM CDATA
        excerpt = ET.SubElement(item, "excerpt:encoded")
        excerpt.text = noticia["excerpt"]
        
        # Metadados WordPress
        ET.SubElement(item, "wp:post_id").text = str(post_id)
        
        # Usar a data da notícia
        post_date_str = noticia.get("post_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ET.SubElement(item, "wp:post_date").text = post_date_str
        ET.SubElement(item, "wp:post_date_gmt").text = post_date_str
        ET.SubElement(item, "wp:post_modified").text = post_date_str
        ET.SubElement(item, "wp:post_modified_gmt").text = post_date_str
        
        # Status e configurações
        ET.SubElement(item, "wp:comment_status").text = "closed"
        ET.SubElement(item, "wp:ping_status").text = "closed"
        ET.SubElement(item, "wp:status").text = "publish"
        ET.SubElement(item, "wp:post_type").text = "post"
        ET.SubElement(item, "wp:post_password").text = ""
        ET.SubElement(item, "wp:is_sticky").text = "0"
        ET.SubElement(item, "wp:menu_order").text = "0"
        ET.SubElement(item, "wp:post_parent").text = "0"
        
        # Categoria - SEM CDATA
        category_elem = ET.SubElement(item, "category", 
                                    domain="category", 
                                    nicename=WP_CATEGORY.lower().replace(" ", "-"))
        category_elem.text = WP_CATEGORY
        
        # Tags padrão - SEM CDATA
        tags = ["Brasil", "Notícias", "Agência Brasil", "EBC"]
        for tag in tags:
            tag_elem = ET.SubElement(item, "category", 
                                   domain="post_tag", 
                                   nicename=tag.lower().replace(" ", "-"))
            tag_elem.text = tag
        
        # Imagem destacada como metadado
        if noticia.get("featured_image"):
            postmeta = ET.SubElement(item, "wp:postmeta")
            ET.SubElement(postmeta, "wp:meta_key").text = "_thumbnail_ext_url"
            ET.SubElement(postmeta, "wp:meta_value").text = noticia["featured_image"]
        
        post_id += 1
    
    # Converter para string XML formatada
    xml_str = ET.tostring(rss, encoding='unicode', method='xml')
    
    # Substituir possíveis entidades problemáticas
    xml_str = xml_str.replace('&amp;amp;', '&amp;')
    xml_str = xml_str.replace('&amp;lt;', '&lt;')
    xml_str = xml_str.replace('&amp;gt;', '&gt;')
    xml_str = xml_str.replace('&amp;quot;', '&quot;')
    xml_str = xml_str.replace('&amp;apos;', '&apos;')
    
    # Formatar com minidom para melhor legibilidade
    dom = minidom.parseString(xml_str)
    formatted_xml = dom.toprettyxml(indent="  ")
    
    # Remover a declaração XML duplicada
    lines = formatted_xml.split('\n')
    if lines[0].startswith('<?xml'):
        lines = lines[1:]
    
    # Adicionar declaração XML com encoding UTF-8
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    
    return xml_declaration + '\n'.join(lines)

# ================= CRAWLER =================

def extrair_agencia_brasil():
    print(f"📰 Buscando Agência Brasil | Datas aceitas: {HOJE} e {ONTEM}")
    print("=" * 60)

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        print("🌐 Conectando ao feed RSS...")
        r = session.get(RSS_URL, timeout=30)
        r.raise_for_status()
        print("✅ Feed RSS carregado com sucesso")
    except requests.RequestException as e:
        print(f"❌ Erro ao acessar RSS: {e}")
        return

    soup = BeautifulSoup(r.content, "xml")
    items = soup.find_all("item")
    
    print(f"📋 Encontradas {len(items)} notícias no feed RSS")
    
    noticias = []
    noticias_processadas = 0
    
    for i, item in enumerate(items, 1):
        titulo = item.title.get_text(strip=True) if item.title else "Sem título"
        link = item.link.get_text(strip=True) if item.link else None
        pubdate = item.pubDate.get_text(strip=True) if item.pubDate else ""
        
        if not link:
            continue
        
        # Verificar data da notícia
        data_noticia_str = parse_rss_date(pubdate)
        try:
            data_noticia = datetime.strptime(data_noticia_str[:10], "%Y-%m-%d").date()
        except:
            data_noticia = HOJE
        
        # Filtrar por data
        if data_noticia not in (HOJE, ONTEM):
            continue
        
        print(f"\n[{i}] 📰 Processando: {titulo[:70]}...")
        print(f"   📅 Data: {data_noticia_str}")
        print(f"   🔗 URL: {link}")
        
        # Extrair conteúdo completo
        conteudo_wp, featured_image = extrair_conteudo_completo(link, session)
        
        if not conteudo_wp or len(conteudo_wp) < 200:
            print(f"   ⚠ Conteúdo insuficiente ou não encontrado")
            continue
        
        # Criar excerpt (primeiros 150 caracteres limpos)
        excerpt_text = re.sub(r'<[^>]+>', '', conteudo_wp)
        excerpt = excerpt_text[:150] + "..." if len(excerpt_text) > 150 else excerpt_text
        
        # Limpar excerpt também
        excerpt = limpar_texto_para_elemento(excerpt)
        
        noticias.append({
            "title": titulo,
            "link": link,
            "content": conteudo_wp,
            "excerpt": excerpt,
            "featured_image": featured_image,
            "post_date": data_noticia_str
        })
        
        noticias_processadas += 1
        print(f"   ✅ Adicionada | Imagem: {'✅' if featured_image else '❌'} | Texto: {len(conteudo_wp)} chars")

    # Gerar feed WordPress
    if noticias:
        print(f"\n📊 Gerando feed WordPress com {len(noticias)} notícias...")
        xml_content = gerar_feed_wordpress(noticias)
        
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_content)
        
        print(f"\n" + "=" * 60)
        print(f"✅ FEED WORDPRESS GERADO COM SUCESSO!")
        print(f"📁 Arquivo: {FEED_FILE}")
        print(f"📰 Notícias processadas: {len(noticias)}")
        print(f"📊 Tamanho do arquivo: {len(xml_content) // 1024} KB")
        
        # Verificar se há CDATA no arquivo gerado
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            cdata_count = content.count("<![CDATA[")
            if cdata_count > 0:
                print(f"⚠️  Aviso: Encontrados {cdata_count} blocos CDATA no arquivo")
            else:
                print(f"✅ Nenhum bloco CDATA encontrado - Formato correto")
        
        print("\n🎯 PARA IMPORTAR NO WORDPRESS:")
        print("1. Acesse WordPress Admin → Ferramentas → Importar")
        print("2. Instale/Execute o importador 'WordPress'")
        print("3. Faça upload do arquivo XML")
        print("4. Atribua os autores conforme necessário")
        print("5. MARQUE a opção 'Baixar e importar arquivos em anexo'")
        print("=" * 60)
        
        # Salvar também um resumo
        with open("resumo_importacao.txt", "w", encoding="utf-8") as f:
            f.write(f"Feed Agência Brasil - {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
            f.write(f"Total de notícias: {len(noticias)}\n\n")
            for n in noticias:
                f.write(f"- {n['title']}\n")
                f.write(f"  Imagem: {n.get('featured_image', 'Não')}\n\n")
    else:
        print(f"\n⚠ Nenhuma notícia encontrada para as datas filtradas ({HOJE} e {ONTEM})")

# ================= MAIN =================

if __name__ == "__main__":
    # Verificar dependências
    try:
        from lxml import etree
        print("✅ lxml está instalado")
    except ImportError:
        print("⚠ ATENÇÃO: lxml não está instalado.")
        print("Execute: pip install lxml")
        print("Usando parser nativo...")
    
    print("\n" + "=" * 60)
    print("🔧 AGÊNCIA BRASIL RSS PARA WORDPRESS")
    print("=" * 60)
    
    extrair_agencia_brasil()
