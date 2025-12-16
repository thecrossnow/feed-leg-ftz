import urllib.request
import json
import re
import html
import ssl
from datetime import datetime
# Bypass SSL verify for simple scripts if certificates are an issue on some envs
ssl._create_default_https_context = ssl._create_unverified_context
API_URL = "https://www.ceara.gov.br/wp-json/wp/v2/posts?per_page=30&_embed"
def clean_content(html_content):
    if not html_content:
        return ""
    
    # Replace <p> and <br> with newlines
    text = re.sub(r'</p>', '\n\n', html_content)
    text = re.sub(r'<br\s*/?>', '\n', text)
    
    # Remove subtitles (h1-h6) and specific classes
    text = re.sub(r'<h[1-6][^>]*?class=["\'].*?subtitulo.*?["\'][^>]*?>.*?</h3>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<h[1-6][^>]*>.*?</h[1-6]>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<span[^>]*?class=["\'].*?hashtag.*?["\'][^>]*?>.*?</span>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<p[^>]*?class=["\'].*?data.*?["\'][^>]*?>.*?</p>', '', text, flags=re.IGNORECASE | re.DOTALL)
    # Remove formatted date lines (15 de dezembro de 2025 – 15:19)
    text = re.sub(r'\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4}\s*.\s*\d{2}:\d{2}', '', text, flags=re.IGNORECASE)
    # Remove lines containing hashtag links (anchors pointing to /tag/)
    text = re.sub(r'<a[^>]+href=["\'].*?/tag/.*?["\'][^>]*>.*?</a>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'#\s*<a.*?>.*?</a>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'(?m)^.*?#.*$', '', text) # Remove lines with remaining hashtags
    # Remove all other HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode HTML entities
    text = html.unescape(text)
    
    return text.strip()
def generate_rss():
    print("Fetching news from API...")
    try:
        req = urllib.request.Request(API_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = response.read()
            posts = json.loads(data)
            
        rss = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
  <title>Notícias Ceará - Extração Limpa</title>
  <link>https://www.ceara.gov.br</link>
  <description>Feed RSS gerado via API</description>
"""
        for post in posts:
            pub_date_str = post['date']
            post_date = pub_date_str.split('T')[0]
            today = datetime.now().strftime('%Y-%m-%d')
            if post_date != today:
                continue
            # Category Filtering
            excluded_slugs = ["seguranca-publica", "aviso-de-pauta", "sspds", "policia-civil", "policia-militar", "corpo-de-bombeiros", "pefoce"]
            excluded_names = ["Segurança Pública", "Aviso de Pauta", "SSPDS", "Polícia", "Bombeiros", "Pefoce"]
            
            is_security = False
            if "_embedded" in post and "wp:term" in post["_embedded"]:
                categories = post["_embedded"]["wp:term"][0]
                for cat in categories:
                    if any(slug in cat["slug"] for slug in excluded_slugs) or any(name in cat["name"] for name in excluded_names):
                        is_security = True
                        break
            if is_security:
                continue
            # Keyword Filtering
            security_keywords = ["prisão", "preso", "delegacia", "homicídio", "homicidio", "assassinato", "tráfico", "trafico", "drogas", "aprem", "armas", "polícia", "policia", "criminoso", "crime", "suspeito", "captura", "foragido"]
            title_lower = html.unescape(post['title']['rendered']).lower()
            content_lower = clean_content(post['content']['rendered']).lower()
            
            if any(keyword in title_lower for keyword in security_keywords) or any(keyword in content_lower for keyword in security_keywords):
                continue
            pubDate = pub_date_str
            title = html.unescape(post['title']['rendered'])
            link = post['link']
            
            clean_description = clean_content(post['content']['rendered'])
            
            # Additional regex cleaning for dates/authors
            clean_description = re.sub(r'(?m)^.*?\d{1,2}\s+de\s+[A-Za-zç]+\s+de\s+\d{4}.*?$', '', clean_description)
            clean_description = re.sub(r'(?m)^.*?[\d]{1,2}:[\d]{2}.*?$', '', clean_description)
            clean_description = re.sub(r'(?m)^.*?(Ascom|Texto|Fotos|Foto:|Texto:|Fonte:).*?$', '', clean_description)
            clean_description = re.sub(r'(?m)^.*?#.*$', '', clean_description) # Hashtags
            clean_description = re.sub(r'(?m)^[\s\-–_]*$', '', clean_description) # Separators
            clean_description = re.sub(r'(?m)^.*?[\-\–\—]\s*Texto.*?$', '', clean_description)
            clean_description = re.sub(r'(?m)^.*?(Eliazio Jerhy|Carlos Ghaja|Thiago Gaspar).*?$', '', clean_description)
            # Remove empty lines
            lines = [line.strip() for line in clean_description.split('\n') if len(line.strip()) > 5]
            clean_description = '\n\n'.join(lines)
            
            clean_description = clean_description.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
            title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
            image_url = ""
            if "_embedded" in post and "wp:featuredmedia" in post["_embedded"] and post["_embedded"]["wp:featuredmedia"]:
                media = post["_embedded"]["wp:featuredmedia"][0]
                if "source_url" in media:
                    image_url = media["source_url"]
            if not image_url:
                continue
            # Usando GUID ao invés de LINK para impedir o plugin de raspar a fonte original
            rss += f"""
  <item>
    <title>{title}</title>
    <guid>{link}</guid>
    <pubDate>{pubDate}</pubDate>
    <description><![CDATA[{clean_description}]]></description>
    <content:encoded><![CDATA[{clean_description}]]></content:encoded>
    <enclosure url="{image_url}" type="image/jpeg" />
  </item>"""
        rss += """
</channel>
</rss>"""
        with open('feed_ceara_news.xml', 'w', encoding='utf-8') as f:
            f.write(rss)
            
        print("RSS Feed generated successfully: feed_ceara_news.xml")
    except Exception as e:
        print(f"Error extracting news: {e}")
if __name__ == "__main__":
    generate_rss()
