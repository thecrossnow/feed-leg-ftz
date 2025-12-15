import urllib.request
import json
import re
import html
import ssl

# Bypass SSL verify for simple scripts if certificates are an issue on some envs
ssl._create_default_https_context = ssl._create_unverified_context

API_URL = "https://www.ceara.gov.br/wp-json/wp/v2/posts?per_page=10&_embed"

def clean_content(html_content):
    if not html_content:
        return ""
    
    # Replace <p> and <br> with newlines
    text = re.sub(r'</p>', '\n\n', html_content)
    text = re.sub(r'<br\s*/?>', '\n', text)
    
    # Remove subtitles (h1, h2, h3, h4, etc.)
    text = re.sub(r'<h[1-6][^>]*>.*?</h[1-6]>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
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
<rss version="2.0">
<channel>
  <title>Notícias Ceará - Extração Limpa</title>
  <link>https://www.ceara.gov.br</link>
  <description>Feed RSS gerado via API</description>
"""

        for post in posts:
            pub_date_str = post['date']
            # Get just the YYYY-MM-DD part
            post_date = pub_date_str.split('T')[0]
            
            # Get today's date in YYYY-MM-DD
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')

            # Filter: only process if post date matches today
            if post_date != today:
                continue

            # Category Filtering
            is_security = False
            if "_embedded" in post and "wp:term" in post["_embedded"]:
                # terms[0] usually contains categories
                categories = post["_embedded"]["wp:term"][0]
                for cat in categories:
                    if "Segurança Pública" in cat["name"] or "seguranca-publica" in cat["slug"]:
                        is_security = True
                        break
                    if "Aviso de Pauta" in cat["name"] or "aviso-de-pauta" in cat["slug"]:
                        is_security = True
                        break
            
            if is_security:
                continue

            pubDate = pub_date_str
            title = html.unescape(post['title']['rendered'])
            link = post['link']
            
            clean_description = clean_content(post['content']['rendered'])
            
            # 1. Remove date/time lines - padrão mais flexível
            # Aceita: "15 de dezembro de2025-13:49" ou "15 de dezembro de 2025-13:49"
            clean_description = re.sub(r'(?m)^\s*\d{1,2}\s+de\s+\w+\s+de\s?\d{4}.*?$', '', clean_description)
            
            # 2. Remove authorship lines - padrão mais amplo
            # Remove linhas com Ascom, Ascom Casa Civil, ou combinações com texto/foto
            # Also catch "Texto: Name", "Foto: Name", and alone standing names often seen at start/end
            clean_description = re.sub(r'(?m)^.*?(Ascom|Texto|Fotos|Foto:|Texto:).*?$', '', clean_description)
            
            # 3. Remove hashtags - remove completamente linhas que começam com #
            clean_description = re.sub(r'(?m)^\s*#.*?$', '', clean_description)
            
            # Remove hashtags anywhere in text
            clean_description = re.sub(r'#\w+', '', clean_description)
            
            # 4. Remove tags HTML que podem ter escapado
            clean_description = re.sub(r'&[a-z]+;', '', clean_description)
            
            # 5. Remove linhas que contêm apenas hífens, traços ou são vazias
            clean_description = re.sub(r'(?m)^[\s\-–_]*$', '', clean_description)
            clean_description = re.sub(r'(?m)^.*?[\-\–\—]\s*Texto.*?$', '', clean_description)
            
            # 6. Remove autoria específica que aparece na imagem
            clean_description = re.sub(r'(?m)^.*?(Eliazio Jerhy|Carlos Ghaja|Thiago Gaspar).*?$', '', clean_description)

            # 7. Remove empty or very short lines (often artifacts)
            # Remove lines with less than 3 chars
            lines = [line for line in clean_description.split('\n') if len(line.strip()) > 2]
            clean_description = '\n\n'.join(lines)
            
            # Clean up extra newlines
            clean_description = re.sub(r'\n{3,}', '\n\n', clean_description)
            clean_description = clean_description.strip()
            
            # Escape XML special chars in content
            clean_description = clean_description.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
            title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")

            image_url = ""
            # Check for featured media
            if "_embedded" in post and "wp:featuredmedia" in post["_embedded"] and post["_embedded"]["wp:featuredmedia"]:
                media = post["_embedded"]["wp:featuredmedia"][0]
                if "source_url" in media:
                    image_url = media["source_url"]

            rss += f"""
  <item>
    <title>{title}</title>
    <link>{link}</link>
    <pubDate>{pubDate}</pubDate>
    <description><![CDATA[{clean_description}]]></description>
    {f'<enclosure url="{image_url}" type="image/jpeg" />' if image_url else ''}
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
