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

# Categoria padrão para WordPress (pode ser alterada)
WP_CATEGORY = "Notícias"
WP_AUTHOR = "Agência Brasil"

# ================= DATAS =================

HOJE = date.today()
ONTEM = HOJE - timedelta(days=1)

# ================= FUNÇÕES =================

def limpar_texto(texto):
    """Limpa e formata texto para WordPress"""
    texto = html.unescape(texto)
    # Remove múltiplos espaços e quebras de linha
    texto = re.sub(r'\s+', ' ', texto)
    # Remove caracteres especiais problemáticos
    texto = texto.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    texto = texto.replace('"', '&quot;').replace("'", '&apos;')
    return texto.strip()

def parse_rss_date(pubdate):
    """
    Converte data RSS para formato WordPress
    Exemplo: Tue, 23 Dec 2025 14:30:00 -0300 -> 2025-12-23 14:30:00
    """
    try:
        # Formato RSS
        dt = datetime.strptime(pubdate[:25], "%a, %d %b %Y %H:%M:%S")
        # Converter para formato WordPress
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        # Se falhar, usar data atual
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def extrair_conteudo_completo(url, session):
    """Extrai conteúdo formatado para WordPress"""
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"   Erro ao acessar página: {e}")
        return None, None, None
    
    soup = BeautifulSoup(r.content, "html.parser")
    
    # 1. EXTRAIR TÍTULO DA PÁGINA (se disponível)
    page_title = ""
    title_tag = soup.find("meta", property="og:title")
    if title_tag and title_tag.get("content"):
        page_title = limpar_texto(title_tag["content"])
    
    # 2. EXTRAIR IMAGEM DESTAQUE
    featured_image = None
    
    # Primeiro tenta og:image
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        featured_image = og_image["content"]
    
    # Tenta outras fontes de imagem
    if not featured_image:
        # Procura imagem em div de destaque
        img_div = soup.find("div", class_=re.compile(r"featured|destaque|thumbnail", re.I))
        if img_div:
            img_tag = img_div.find("img")
            if img_tag and img_tag.get("src"):
                featured_image = urljoin(URL_BASE, img_tag["src"]) if not img_tag["src"].startswith('http') else img_tag["src"]
    
    if not featured_image:
        # Última tentativa: qualquer imagem razoável
        for img in soup.find_all("img", src=re.compile(r"\.(jpg|jpeg|png|webp)$", re.I)):
            src = img.get("src", "")
            if src and not any(word in src.lower() for word in ['logo', 'icon', 'avatar', 'thumb']):
                featured_image = urljoin(URL_BASE, src) if not src.startswith('http') else src
                break
    
    # 3. EXTRAIR CONTEÚDO COMPLETO (formato WordPress)
    conteudo_wp = ""
    
    # Encontrar o container principal do conteúdo
    content_selectors = [
        "article",
        ".conteudo",
        ".noticia-conteudo",
        ".materia-conteudo",
        ".texto-materia",
        "div[itemprop='articleBody']",
        ".entry-content",
        ".post-content",
        ".article-body"
    ]
    
    content_div = None
    for selector in content_selectors:
        if selector.startswith('.'):
            content_div = soup.select_one(selector)
        else:
            content_div = soup.find(selector)
        if content_div:
            break
    
    if not content_div:
        # Fallback: procurar por divs com muito texto
        all_divs = soup.find_all("div")
        for div in all_divs:
            text_length = len(div.get_text(strip=True))
            if text_length > 500:  # Div com conteúdo significativo
                content_div = div
                break
    
    if content_div:
        # Remover elementos indesejados
        for element in content_div.find_all(["script", "style", "iframe", "aside", 
                                            "nav", "header", "footer", "form"]):
            element.decompose()
        
        # Remover anúncios e elementos relacionados
        for element in content_div.find_all(class_=re.compile(
            r"ad|banner|publicidade|propaganda|ads|widget|related|share|social|comentario|comment", 
            re.I)):
            element.decompose()
        
        # Converter para formato WordPress
        for element in content_div.find_all(recursive=True):
            # Preservar parágrafos
            if element.name == 'p':
                text = element.get_text(strip=True)
                if len(text) > 10:
                    conteudo_wp += f"<p>{limpar_texto(text)}</p>\n"
            
            # Preservar cabeçalhos
            elif element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = element.get_text(strip=True)
                if text:
                    conteudo_wp += f"<{element.name}>{limpar_texto(text)}</{element.name}>\n"
            
            # Preservar listas
            elif element.name == 'ul':
                conteudo_wp += "<ul>\n"
                for li in element.find_all('li', recursive=False):
                    li_text = li.get_text(strip=True)
                    if li_text:
                        conteudo_wp += f"  <li>{limpar_texto(li_text)}</li>\n"
                conteudo_wp += "</ul>\n"
            
            # Preservar citações
            elif element.name == 'blockquote':
                text = element.get_text(strip=True)
                if text:
                    conteudo_wp += f"<blockquote>{limpar_texto(text)}</blockquote>\n"
    
    # Se não extraiu conteúdo suficiente, usar todo o texto
    if len(conteudo_wp) < 200:
        if content_div:
            texto_bruto = content_div.get_text(separator='\n', strip=True)
        else:
            texto_bruto = soup.get_text(separator='\n', strip=True)
        
        # Dividir em parágrafos
        paragraphs = [p.strip() for p in texto_bruto.split('\n') if len(p.strip()) > 30]
        conteudo_wp = "\n".join(f"<p>{limpar_texto(p)}</p>" for p in paragraphs[:20])
    
    # Adicionar imagem destacada no início do conteúdo
    if featured_image:
        conteudo_wp = f'<p><img src="{featured_image}" alt="{page_title}" class="aligncenter size-full" /></p>\n' + conteudo_wp
    
    # Adicionar link para fonte original no final
    conteudo_wp += f'\n<p><em>Fonte: <a href="{url}" rel="nofollow">{URL_BASE}</a></em></p>'
    
    return page_title, conteudo_wp, featured_image

def gerar_feed_wordpress(noticias):
    """Gera feed XML no formato WordPress WXR"""
    
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
    ET.SubElement(channel, "link").text = URL_BASE
    ET.SubElement(channel, "description").text = "Notícias oficiais da Agência Brasil importadas automaticamente"
    ET.SubElement(channel, "pubDate").text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')
    ET.SubElement(channel, "language").text = "pt-BR"
    ET.SubElement(channel, "wp:wxr_version").text = "1.2"
    ET.SubElement(channel, "wp:base_site_url").text = URL_BASE
    ET.SubElement(channel, "wp:base_blog_url").text = URL_BASE
    
    # Adicionar autor
    author = ET.SubElement(channel, "wp:author")
    ET.SubElement(author, "wp:author_id").text = "1"
    ET.SubElement(author, "wp:author_login").text = WP_AUTHOR.lower().replace(" ", "_")
    ET.SubElement(author, "wp:author_email").text = "noticias@agenciabrasil.com.br"
    ET.SubElement(author, "wp:author_display_name").text = WP_AUTHOR
    ET.SubElement(author, "wp:author_first_name").text = "Agência"
    ET.SubElement(author, "wp:author_last_name").text = "Brasil"
    
    # Adicionar categoria
    category = ET.SubElement(channel, "wp:category")
    ET.SubElement(category, "wp:term_id").text = "1"
    ET.SubElement(category, "wp:category_nicename").text = WP_CATEGORY.lower().replace(" ", "-")
    ET.SubElement(category, "wp:category_parent").text = ""
    cat_name = ET.SubElement(category, "wp:cat_name")
    cat_name.text = WP_CATEGORY
    
    # Adicionar cada notícia
    for i, noticia in enumerate(noticias, 1):
        item = ET.SubElement(channel, "item")
        
        ET.SubElement(item, "title").text = noticia["title"]
        ET.SubElement(item, "link").text = noticia["link"]
        
        # Data de publicação
        pub_date = ET.SubElement(item, "pubDate")
        pub_date.text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
        
        # Creator
        ET.SubElement(item, "dc:creator").text = f"<![CDATA[{WP_AUTHOR}]]>"
        
        # GUID
        guid = ET.SubElement(item, "guid", isPermaLink="false")
        guid.text = noticia["link"]
        
        # Descrição (excerpt)
        description = ET.SubElement(item, "description")
        description.text = f"<![CDATA[{noticia['excerpt']}]]>"
        
        # Conteúdo completo
        content = ET.SubElement(item, "content:encoded")
        content.text = f"<![CDATA[{noticia['content']}]]>"
        
        # Excerpt
        excerpt = ET.SubElement(item, "excerpt:encoded")
        excerpt.text = f"<![CDATA[{noticia['excerpt']}]]>"
        
        # Post ID
        ET.SubElement(item, "wp:post_id").text = str(1000 + i)
        
        # Data do post
        ET.SubElement(item, "wp:post_date").text = noticia["post_date"]
        ET.SubElement(item, "wp:post_date_gmt").text = noticia["post_date_gmt"]
        ET.SubElement(item, "wp:post_modified").text = noticia["post_date"]
        ET.SubElement(item, "wp:post_modified_gmt").text = noticia["post_date_gmt"]
        
        # Status e tipo
        ET.SubElement(item, "wp:comment_status").text = "closed"
        ET.SubElement(item, "wp:ping_status").text = "closed"
        ET.SubElement(item, "wp:status").text = "publish"
        ET.SubElement(item, "wp:post_type").text = "post"
        
        # Categoria
        category_elem = ET.SubElement(item, "category", domain="category", nicename=WP_CATEGORY.lower().replace(" ", "-"))
        category_elem.text = f"<![CDATA[{WP_CATEGORY}]]>"
        
        # Tags (se houver)
        if "tags" in noticia:
            for tag in noticia["tags"]:
                tag_elem = ET.SubElement(item, "category", domain="post_tag", nicename=tag.lower().replace(" ", "-"))
                tag_elem.text = f"<![CDATA[{tag}]]>"
        
        # Imagem destacada
        if noticia["featured_image"]:
            attachment_item = ET.SubElement(channel, "item")
            ET.SubElement(attachment_item, "title").text = f"Imagem: {noticia['title']}"
            ET.SubElement(attachment_item, "link").text = noticia["featured_image"]
            
            guid_att = ET.SubElement(attachment_item, "guid", isPermaLink="false")
            guid_att.text = noticia["featured_image"]
            
            ET.SubElement(attachment_item, "pubDate").text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
            ET.SubElement(attachment_item, "description").text = ""
            
            content_att = ET.SubElement(attachment_item, "content:encoded")
            content_att.text = ""
            
            ET.SubElement(attachment_item, "excerpt:encoded").text = ""
            ET.SubElement(attachment_item, "wp:post_id").text = str(2000 + i)
            ET.SubElement(attachment_item, "wp:post_date").text = noticia["post_date"]
            ET.SubElement(attachment_item, "wp:post_date_gmt").text = noticia["post_date_gmt"]
            ET.SubElement(attachment_item, "wp:comment_status").text = "closed"
            ET.SubElement(attachment_item, "wp:ping_status").text = "closed"
            ET.SubElement(attachment_item, "wp:status").text = "inherit"
            ET.SubElement(attachment_item, "wp:post_type").text = "attachment"
            ET.SubElement(attachment_item, "wp:post_parent").text = str(1000 + i)
            ET.SubElement(attachment_item, "wp:postmeta").text = ""
            
            # Meta da imagem
            meta = ET.SubElement(attachment_item, "wp:postmeta")
            ET.SubElement(meta, "wp:meta_key").text = "_wp_attached_file"
            ET.SubElement(meta, "wp:meta_value").text = noticia["featured_image"].split("/")[-1]
    
    # Converter para string XML formatada
    xml_str = ET.tostring(rss, encoding='unicode', method='xml')
    
    # Adicionar declaração XML
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    
    # Formatar com minidom para melhor legibilidade
    dom = minidom.parseString(xml_str)
    formatted_xml = dom.toprettyxml(indent="  ")
    
    # Remover a declaração XML duplicada
    lines = formatted_xml.split('\n')
    if lines[0].startswith('<?xml'):
        lines = lines[1:]
    
    return xml_declaration + '\n'.join(lines)

# ================= CRAWLER =================

def extrair_agencia_brasil():
    print(f"📰 Buscando Agência Brasil | Datas aceitas: {HOJE} e {ONTEM}")
    print("=" * 60)

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        r = session.get(RSS_URL, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Erro ao acessar RSS: {e}")
        return

    soup = BeautifulSoup(r.content, "xml")
    items = soup.find_all("item")
    noticias = []

    print(f"📋 Encontradas {len(items)} notícias no feed RSS")
    
    for i, item in enumerate(items, 1):
        titulo = item.title.get_text(strip=True) if item.title else "Sem título"
        link = item.link.get_text(strip=True) if item.link else None
        pubdate = item.pubDate.get_text(strip=True) if item.pubDate else ""
        
        if not link:
            continue
            
        # Verificar data
        data_noticia_str = parse_rss_date(pubdate)
        data_noticia = datetime.strptime(data_noticia_str[:10], "%Y-%m-%d").date()
        
        if data_noticia not in (HOJE, ONTEM):
            continue

        print(f"\n[{i}] Processando: {titulo[:70]}...")
        print(f"   🔗 {link}")

        # Extrair conteúdo completo
        page_title, conteudo_wp, featured_image = extrair_conteudo_completo(link, session)

        if not conteudo_wp or len(conteudo_wp) < 200:
            print(f"   ⚠ Conteúdo insuficiente ({len(conteudo_wp) if conteudo_wp else 0} caracteres)")
            continue

        # Criar excerpt (primeiros 200 caracteres)
        excerpt = re.sub(r'<[^>]+>', '', conteudo_wp)[:200] + "..."
        
        # Datas para WordPress
        now = datetime.now()
        post_date = now.strftime("%Y-%m-%d %H:%M:%S")
        post_date_gmt = now.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        noticias.append({
            "title": titulo,
            "link": link,
            "content": conteudo_wp,
            "excerpt": excerpt,
            "featured_image": featured_image,
            "post_date": post_date,
            "post_date_gmt": post_date_gmt,
            "tags": ["Brasil", "Notícias", "Agência Brasil"]
        })

        print(f"   ✅ OK | Imagem: {'✅' if featured_image else '❌'} | Texto: {len(conteudo_wp)} chars")

    # Gerar feed WordPress
    if noticias:
        xml_content = gerar_feed_wordpress(noticias)
        
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_content)
        
        print(f"\n" + "=" * 60)
        print(f"✅ FEED WORDPRESS GERADO COM SUCESSO!")
        print(f"📁 Arquivo: {FEED_FILE}")
        print(f"📰 Notícias processadas: {len(noticias)}")
        print(f"📊 Tamanho do arquivo: {len(xml_content) // 1024} KB")
        print("\n🎯 PARA IMPORTAR NO WORDPRESS:")
        print("1. Acesse o WordPress Admin")
        print("2. Vá em Ferramentas → Importar")
        print("3. Escolha 'WordPress'")
        print("4. Faça upload do arquivo XML")
        print("5. Atribua os autores conforme necessário")
        print("=" * 60)
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
        print("O código funcionará, mas pode ser mais lento...")
    
    print("\n" + "=" * 60)
    print("🔧 AGÊNCIA BRASIL RSS PARA WORDPRESS")
    print("=" * 60)
    
    extrair_agencia_brasil()
