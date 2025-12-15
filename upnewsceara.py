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

            pubDate = pub_date_str
            title = html.unescape(post['title']['rendered'])
            link = post['link']
            
            clean_description = clean_content(post['content']['rendered'])
            
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
