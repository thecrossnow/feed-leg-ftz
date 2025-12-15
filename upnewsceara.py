import urllib.request
import json
import re
import html
import ssl

# Bypass SSL verify for simple scripts if certificates are an issue on some envs
ssl._create_default_https_context = ssl._create_unverified_context

API_URL = "https://www.ceara.gov.br/wp-json/wp/v2/posts?per_page=30&_embed"

def clean_content(html_content):
    if not html_content:
        return ""
    
    # Replace <p> and <br> with newlines
    text = re.sub(r'</p>', '\n\n', html_content)
    text = re.sub(r'<br\s*/?>', '\n', text)
    
    # Remove specific subtitles with classes "subtitulo" or similar which container the unwanted date/hashtags
    # Using more flexible pattern to catch attributes in any order or spacing
    text = re.sub(r'<h3[^>]*?class=["\'].*?subtitulo.*?["\'][^>]*?>.*?</h3>', '', text, flags=re.IGNORECASE | re.DOTALL)

    # Also removing generic h1-h6 tags
    text = re.sub(r'<h[1-6][^>]*>.*?</h[1-6]>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove spans with class "hashtag" - flexible matching
    text = re.sub(r'<span[^>]*?class=["\'].*?hashtag.*?["\'][^>]*?>.*?</span>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Also explicitly remove the container div/p if they might be wrapping it
    text = re.sub(r'<p[^>]*?class=["\'].*?data.*?["\'][^>]*?>.*?</p>', '', text, flags=re.IGNORECASE | re.DOTALL)

    # Remove formatted date lines that might be outside tags (15 de dezembro de 2025 – 15:19)
    # This specific regex targets the format user showed: 15 de dezembro de 2025 \u2013 15:19
    text = re.sub(r'\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4}\s*.\s*\d{2}:\d{2}', '', text, flags=re.IGNORECASE)

    # Remove lines containing hashtag links (anchors pointing to /tag/)
    text = re.sub(r'<a[^>]+href=["\'].*?/tag/.*?["\'][^>]*>.*?</a>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Final sweep for any remaining hashtags text
    text = re.sub(r'#\s*<a.*?>.*?</a>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
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

            # Category Filtering (slugs and names)
            excluded_slugs = ["seguranca-publica", "aviso-de-pauta", "sspds", "policia-civil", "policia-militar", "corpo-de-bombeiros", "pefoce"]
            excluded_names = ["Segurança Pública", "Aviso de Pauta", "SSPDS", "Polícia", "Bombeiros", "Pefoce"]
            
            is_security = False
            if "_embedded" in post and "wp:term" in post["_embedded"]:
                # terms[0] usually contains categories
                categories = post["_embedded"]["wp:term"][0]
                for cat in categories:
                    if any(slug in cat["slug"] for slug in excluded_slugs) or any(name in cat["name"] for name in excluded_names):
                        is_security = True
                        break
            
            if is_security:
                continue

            # Content & Title Keyword Filtering
            # Stopwords that indicate security news
            security_keywords = ["prisão", "preso", "delegacia", "homicídio", "homicidio", "assassinato", "tráfico", "trafico", "drogas", "aprem", "armas", "polícia", "policia", "criminoso", "crime", "suspeito", "captura", "foragido"]
            
            title_lower = html.unescape(post['title']['rendered']).lower()
            content_lower = clean_content(post['content']['rendered']).lower()
            
            if any(keyword in title_lower for keyword in security_keywords) or any(keyword in content_lower for keyword in security_keywords):
                continue

            pubDate = pub_date_str
            title = html.unescape(post['title']['rendered'])
            link = post['link']
            
            clean_description = clean_content(post['content']['rendered'])
            
            # 1. Remove date/time lines - Broadest pattern
            # Matches lines having "digit + de + word + de + digit", regardless of what else is on the line
            clean_description = re.sub(r'(?m)^.*?\d{1,2}\s+de\s+[A-Za-zç]+\s+de\s+\d{4}.*?$', '', clean_description)
            clean_description = re.sub(r'(?m)^.*?[\d]{1,2}:[\d]{2}.*?$', '', clean_description) 
            
            # 2. Remove authorship lines - Broadest pattern
            clean_description = re.sub(r'(?m)^.*?(Ascom|Texto|Fotos|Foto:|Texto:|Fonte:).*?$', '', clean_description)
            
            # 3. Remove hashtags - Aggressive
            # Remove ANY line that contains a hash char #
            clean_description = re.sub(r'(?m)^.*?#.*$', '', clean_description)
            
            # Just to be sure, remove any remaining #hashtag strings that might be inline
            clean_description = re.sub(r'#\S+', '', clean_description)
            
            # 4. Remove tags HTML
            clean_description = re.sub(r'&[a-z]+;', '', clean_description)
            
            # 5. Remove lines that are just separators or emptyish
            clean_description = re.sub(r'(?m)^[\s\-–_]*$', '', clean_description)
            clean_description = re.sub(r'(?m)^.*?[\-\–\—]\s*Texto.*?$', '', clean_description)
            
            # 6. Specific names
            clean_description = re.sub(r'(?m)^.*?(Eliazio Jerhy|Carlos Ghaja|Thiago Gaspar).*?$', '', clean_description)

            # 7. Remove empty or very short lines
            lines = [line.strip() for line in clean_description.split('\n') if len(line.strip()) > 5] # Increased limit to 5 to catch "CEE." etc
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

            if not image_url:
                continue

            rss += f"""
  <item>
    <title>{title}</title>
    <link>{link}</link>
    <pubDate>{pubDate}</pubDate>
    <description><![CDATA[{clean_description}]]></description>
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
