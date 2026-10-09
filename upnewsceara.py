import urllib.request
import urllib.error
import json
import re
import html
import ssl
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ============================================================
# CONFIGURAÇÕES
# ============================================================

API_BASE = "https://www.ce.gov.br/wp-json/wp/v2/posts"
PER_PAGE = 100
MAX_PAGES = 5

# O runner do GitHub Actions roda em UTC. Usamos o fuso de Fortaleza
# para decidir o que é "hoje" e "ontem".
TZ = ZoneInfo("America/Fortaleza")

# Quantos dias considerar: 1 = hoje + ontem
DAYS_BACK = 1

OUTPUT_FILE = "feed_ceara_news.xml"

# Desabilita verificação SSL caso o ambiente apresente problemas
ssl._create_default_https_context = ssl._create_unverified_context


# ============================================================
# LIMPEZA DO CONTEÚDO
# ============================================================

def clean_content(html_content):
    if not html_content:
        return ""

    text = html_content

    # Remove scripts e styles
    text = re.sub(
        r"<script[^>]*>.*?</script>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    text = re.sub(
        r"<style[^>]*>.*?</style>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Parágrafos e quebras de linha
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # Remove títulos/subtítulos HTML
    text = re.sub(
        r"<h[1-6][^>]*>.*?</h[1-6]>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Remove spans de hashtag
    text = re.sub(
        r'<span[^>]*class=["\'][^"\']*hashtag[^"\']*["\'][^>]*>.*?</span>',
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Remove parágrafos com classes relacionadas a dados/metadados
    text = re.sub(
        r'<p[^>]*class=["\'][^"\']*data[^"\']*["\'][^>]*>.*?</p>',
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Remove links para tags do WordPress
    text = re.sub(
        r'<a[^>]+href=["\'][^"\']*/tag/[^"\']*["\'][^>]*>.*?</a>',
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Remove hashtags que ainda existirem
    text = re.sub(
        r"(?m)^.*?#.*$",
        "",
        text
    )

    # Remove imagens
    text = re.sub(
        r"<figure[^>]*>.*?</figure>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    text = re.sub(
        r"<img[^>]*>",
        "",
        text,
        flags=re.IGNORECASE
    )

    # Remove todas as outras tags HTML
    text = re.sub(r"<[^>]+>", "", text)

    # Decodifica entidades HTML
    text = html.unescape(text)

    # Normaliza espaços
    text = re.sub(r"[ \t]+", " ", text)

    # Normaliza excesso de quebras de linha
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


# ============================================================
# BUSCA DA IMAGEM
# ============================================================

def get_image_url(post):
    """
    Tenta encontrar a imagem destacada usando _embedded.
    Caso não encontre, tenta buscar diretamente pela API de mídia.
    """

    # --------------------------------------------------------
    # 1. Tenta _embedded
    # --------------------------------------------------------

    embedded = post.get("_embedded", {})

    featured_media = embedded.get("wp:featuredmedia", [])

    if featured_media:
        media = featured_media[0]

        source_url = media.get("source_url")

        if source_url:
            return source_url

        # Alguns retornos podem ter source_url dentro de media_details
        if media.get("media_details", {}).get("sizes"):
            sizes = media["media_details"]["sizes"]

            for size_name in ["large", "medium_large", "full"]:
                if size_name in sizes:
                    url = sizes[size_name].get("source_url")
                    if url:
                        return url

    # --------------------------------------------------------
    # 2. Usa featured_media diretamente
    # --------------------------------------------------------

    media_id = post.get("featured_media")

    if not media_id:
        return ""

    media_api = (
        f"https://www.ce.gov.br/wp-json/wp/v2/media/{media_id}"
    )

    try:
        req = urllib.request.Request(
            media_api,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            media_data = json.loads(response.read())

        source_url = media_data.get("source_url")

        if source_url:
            return source_url

    except Exception as e:
        print(
            f"   Não foi possível buscar mídia {media_id}: {e}"
        )

    return ""


# ============================================================
# FILTROS
# ============================================================

EXCLUDED_SLUGS = [
    "seguranca-publica",
    "aviso-de-pauta",
    "sspds",
    "policia-civil",
    "policia-militar",
    "corpo-de-bombeiros",
    "pefoce"
]

EXCLUDED_NAMES = [
    "Segurança Pública",
    "Aviso de Pauta",
    "SSPDS",
    "Polícia",
    "Bombeiros",
    "Pefoce"
]

SECURITY_KEYWORDS = [
    "prisão",
    "preso",
    "delegacia",
    "homicídio",
    "homicidio",
    "assassinato",
    "tráfico",
    "trafico",
    "drogas",
    "armas",
    "polícia",
    "policia",
    "criminoso",
    "crime",
    "suspeito",
    "captura",
    "foragido"
]


def is_security_category(post):
    embedded = post.get("_embedded", {})

    terms = embedded.get("wp:term", [])

    if not terms:
        return False

    for taxonomy_group in terms:

        if not isinstance(taxonomy_group, list):
            continue

        for category in taxonomy_group:

            slug = str(category.get("slug", "")).lower()
            name = str(category.get("name", "")).lower()

            for excluded in EXCLUDED_SLUGS:
                if excluded.lower() in slug:
                    return True

            for excluded in EXCLUDED_NAMES:
                if excluded.lower() in name:
                    return True

    return False


def contains_security_keyword(title, content):
    combined = f"{title} {content}".lower()

    return any(
        keyword.lower() in combined
        for keyword in SECURITY_KEYWORDS
    )


# ============================================================
# GERAÇÃO DO RSS
# ============================================================

def generate_rss():

    print("=" * 70)
    print("INICIANDO EXTRAÇÃO DO CEARÁ.GOV.BR")
    print("=" * 70)

    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")
    valid_dates = {
        (now - timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(DAYS_BACK + 1)
    }
    after = (now - timedelta(days=DAYS_BACK + 1)).strftime("%Y-%m-%dT00:00:00")

    print(f"Agora (Fortaleza): {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Datas consideradas: {sorted(valid_dates)}")
    print()

    try:

        # ----------------------------------------------------
        # CONSULTA API
        # ----------------------------------------------------

        posts = []

        for page in range(1, MAX_PAGES + 1):

            url = (
                f"{API_BASE}?per_page={PER_PAGE}&page={page}"
                f"&after={after}&orderby=date&order=desc&_embed"
            )

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            print(f"Consultando API (página {page})...")

            try:
                with urllib.request.urlopen(req, timeout=60) as response:
                    status = response.status
                    page_posts = json.loads(response.read())
            except urllib.error.HTTPError as e:
                # WordPress devolve 400 quando a página passa do total
                if e.code == 400 and page > 1:
                    break
                raise

            print(f"HTTP Status: {status} - {len(page_posts)} posts")

            posts.extend(page_posts)

            if len(page_posts) < PER_PAGE:
                break

        print(f"Posts recebidos da API: {len(posts)}")
        print()

        # ----------------------------------------------------
        # ESTATÍSTICAS
        # ----------------------------------------------------

        total_today = 0
        excluded_category = 0
        excluded_keyword = 0
        without_image = 0
        included = 0

        rss_items = []

        # ----------------------------------------------------
        # PROCESSA POSTS
        # ----------------------------------------------------

        for index, post in enumerate(posts, start=1):

            post_id = post.get("id")

            title = html.unescape(
                post.get("title", {}).get("rendered", "")
            ).strip()

            pub_date = post.get("date", "")

            print(
                f"[{index}/{len(posts)}] "
                f"ID {post_id} - {title}"
            )

            # ------------------------------------------------
            # DATA
            # ------------------------------------------------

            post_date = pub_date.split("T")[0]

            if post_date not in valid_dates:

                print(
                    f"   -> Ignorada: data {post_date} fora da janela"
                )

                continue

            total_today += 1

            print("   -> Dentro da janela (hoje/ontem)")

            # ------------------------------------------------
            # CATEGORIA
            # ------------------------------------------------

            if is_security_category(post):

                excluded_category += 1

                print(
                    "   -> Ignorada: categoria de segurança"
                )

                continue

            # ------------------------------------------------
            # CONTEÚDO
            # ------------------------------------------------

            raw_content = post.get(
                "content", {}
            ).get(
                "rendered",
                ""
            )

            clean_description = clean_content(
                raw_content
            )

            # ------------------------------------------------
            # PALAVRAS-CHAVE
            # ------------------------------------------------

            if contains_security_keyword(
                title,
                clean_description
            ):

                excluded_keyword += 1

                print(
                    "   -> Ignorada: palavra-chave de segurança"
                )

                continue

            # ------------------------------------------------
            # IMAGEM
            # ------------------------------------------------

            image_url = get_image_url(post)

            if not image_url:

                without_image += 1

                print(
                    "   -> Ignorada: sem imagem destacada"
                )

                continue

            print(
                f"   -> Imagem: {image_url}"
            )

            # ------------------------------------------------
            # LIMPEZA EXTRA
            # ------------------------------------------------

            clean_description = re.sub(
                r"(?mi)^.*?\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4}.*?$",
                "",
                clean_description
            )

            clean_description = re.sub(
                r"(?mi)^.*?\d{1,2}:\d{2}.*?$",
                "",
                clean_description
            )

            clean_description = re.sub(
                r"(?mi)^.*?(Ascom|Texto|Fotos|Foto:|Fonte:).*?$",
                "",
                clean_description
            )

            clean_description = re.sub(
                r"(?mi)^.*?#.*$",
                "",
                clean_description
            )

            clean_description = re.sub(
                r"(?m)^[\s\-–—_]*$",
                "",
                clean_description
            )

            clean_description = re.sub(
                r"\n\s*\n\s*\n+",
                "\n\n",
                clean_description
            )

            lines = []

            for line in clean_description.split("\n"):

                line = line.strip()

                if len(line) > 5:
                    lines.append(line)

            clean_description = "\n\n".join(lines).strip()

            # ------------------------------------------------
            # LINK
            # ------------------------------------------------

            link = post.get("link", "")

            # ------------------------------------------------
            # ESCAPE XML
            # ------------------------------------------------

            safe_title = html.escape(
                title,
                quote=True
            )

            safe_description = html.escape(
                clean_description,
                quote=False
            )

            safe_image_url = html.escape(
                image_url,
                quote=True
            )

            # ------------------------------------------------
            # ITEM RSS
            # ------------------------------------------------

            item = f"""
  <item>
    <title>{safe_title}</title>
    <guid isPermaLink="false">{post_id}</guid>
    <link>{html.escape(link, quote=True)}</link>
    <pubDate>{pub_date}</pubDate>
    <description><![CDATA[{clean_description}]]></description>
    <content:encoded><![CDATA[{clean_description}]]></content:encoded>
    <enclosure url="{safe_image_url}" type="image/jpeg" />
  </item>
"""

            rss_items.append(item)

            included += 1

            print(
                "   -> INCLUÍDA NO RSS"
            )

        # ----------------------------------------------------
        # MONTA RSS
        # ----------------------------------------------------

        rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">

<channel>

  <title>Notícias Ceará - Extração Limpa</title>

  <link>https://www.ce.gov.br</link>

  <description>
    Feed RSS gerado via API do Ceará.gov.br
  </description>

  <language>pt-BR</language>

  <lastBuildDate>{now.strftime("%a, %d %b %Y %H:%M:%S -0300")}</lastBuildDate>

{''.join(rss_items)}

</channel>

</rss>
"""

        # ----------------------------------------------------
        # GRAVA ARQUIVO
        # ----------------------------------------------------

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(rss)

        # ----------------------------------------------------
        # RESUMO
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("EXTRAÇÃO FINALIZADA")
        print("=" * 70)

        print(
            f"Posts recebidos:       {len(posts)}"
        )

        print(
            f"Posts na janela:       {total_today}"
        )

        print(
            f"Excluídos por categoria: {excluded_category}"
        )

        print(
            f"Excluídos por palavras:  {excluded_keyword}"
        )

        print(
            f"Sem imagem:             {without_image}"
        )

        print(
            f"Incluídos no RSS:       {included}"
        )

        print()
        print(
            f"Arquivo gerado: {OUTPUT_FILE}"
        )

        # ----------------------------------------------------
        # VERIFICAÇÃO DO ARQUIVO
        # ----------------------------------------------------

        with open(
            OUTPUT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            generated = f.read()

        print(
            f"Tamanho do XML: {len(generated)} bytes"
        )

        print(
            f"Itens <item>: {generated.count('<item>')}"
        )

        print("=" * 70)

    except urllib.error.HTTPError as e:

        print(
            f"ERRO HTTP: {e.code} - {e.reason}"
        )

        raise

    except urllib.error.URLError as e:

        print(
            f"ERRO DE CONEXÃO: {e.reason}"
        )

        raise

    except json.JSONDecodeError as e:

        print(
            f"ERRO AO INTERPRETAR JSON: {e}"
        )

        raise

    except Exception as e:

        print(
            f"ERRO INESPERADO: {type(e).__name__}: {e}"
        )

        raise


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    generate_rss()
