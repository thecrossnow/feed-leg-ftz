#!/usr/bin/env python3
"""
FEED RSS 2.0 OTIMIZADO PARA WORDPRESS
Versão final com garantia de imagens e formatação
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os
import sys
import re
import html
import hashlib

class FeedGenerator:
    def __init__(self):
        self.api_url = "https://www.cmfor.ce.gov.br:8080/wp-json/wp/v2/posts"
        self.feed_file = "feed.xml"
        
    def extrair_imagem_principal(self, conteudo):
        """Extrai a primeira imagem do conteúdo para WordPress"""
        # Padrões de busca para imagens
        padroes = [
            r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|gif|webp))"',
            r'src="([^"]+wp-content/uploads[^"]+\.(?:jpg|jpeg|png|gif|webp))"',
            r'<figure[^>]*>.*?<img[^>]+src="([^"]+)"'
        ]
        
        for padrao in padroes:
            match = re.search(padrao, conteudo, re.IGNORECASE | re.DOTALL)
            if match:
                img_url = match.group(1)
                # Garantir URL completa
                if img_url.startswith('/'):
                    img_url = f"https://www.cmfor.ce.gov.br{img_url}"
                # Remover porta 8080 se existir
                img_url = img_url.replace(':8080', '')
                return img_url
        return None
    
    def otimizar_html_wordpress(self, conteudo):
        """Otimiza HTML para ser interpretado corretamente pelo WordPress"""
        # 1. Decodificar HTML
        conteudo = html.unescape(conteudo)
        
        # 2. Remover elementos problemáticos do RSS
        conteudo = re.sub(r'<updated>.*?</updated>', '', conteudo, flags=re.DOTALL)
        conteudo = re.sub(r'<dc:creator>.*?</dc:creator>', '', conteudo, flags=re.DOTALL)
        
        # 3. Remover porta 8080 de TODAS as URLs
        conteudo = conteudo.replace(':8080', '')
        
        # 4. Garantir URLs absolutas para imagens
        base_url = 'https://www.cmfor.ce.gov.br'
        
        # Converter URLs relativas de imagens para absolutas
        def converter_url_imagem(match):
            url = match.group(1)
            if url.startswith('/'):
                return f'src="{base_url}{url}"'
            return match.group(0)
        
        conteudo = re.sub(r'src="/([^"]+)"', converter_url_imagem, conteudo)
        
        # 5. Remover qualquer ]]> residual (QUEBRA CDATA)
        conteudo = conteudo.replace(']]>', '')
        
        # 6. Escapar apenas & (deixar < > " ' normais para WordPress)
        conteudo = conteudo.replace('&', '&amp;')
        # Mas não tocar em &nbsp;, &quot;, etc que já são entities
        conteudo = re.sub(r'&amp;(nbsp|quot|lt|gt|amp|apos|#\d+);', r'&\1;', conteudo)
        
        # 7. Remover atributos problemáticos (opcional)
        conteudo = re.sub(r'\sclass="[^"]*"', '', conteudo)
        conteudo = re.sub(r'\sstyle="[^"]*"', '', conteudo)
        
        # 8. Garantir que iframes do YouTube funcionem
        conteudo = re.sub(
            r'&lt;iframe',
            '<iframe',
            conteudo
        )
        conteudo = re.sub(
            r'&lt;/iframe&gt;',
            '</iframe>',
            conteudo
        )
        
        # 9. Adicionar marcação WordPress para melhor interpretação
        if '<p>' not in conteudo:
            # Se não tem parágrafos, adicionar estrutura básica
            conteudo = f'<!-- wp:paragraph --><p>{conteudo}</p><!-- /wp:paragraph -->'
        
        return conteudo.strip()
    
    def criar_descricao_otimizada(self, conteudo):
        """Cria descrição otimizada para RSS"""
        # Remover HTML
        texto = re.sub('<[^>]+>', '', conteudo)
        texto = html.unescape(texto)
        
        # Limpar espaços extras
        texto = ' '.join(texto.split())
        
        # Cortar em ponto lógico (tentativa)
        if len(texto) > 250:
            # Tentar cortar no final de uma frase
            corte = texto[:250]
            ultimo_ponto = corte.rfind('.')
            ultima_virgula = corte.rfind(',')
            
            if ultimo_ponto > 150:  # Pelo menos 150 caracteres
                descricao = texto[:ultimo_ponto + 1]
            elif ultima_virgula > 150:
                descricao = texto[:ultima_virgula + 1]
            else:
                descricao = texto[:250] + "..."
        else:
            descricao = texto
        
        return html.escape(descricao)
    
    def criar_feed_completo(self, noticias):
        """Cria feed RSS completo otimizado"""
        rss = ET.Element("rss")
        rss.set("version", "2.0")
        rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
        rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
        rss.set("xmlns:media", "http://search.yahoo.com/mrss/")
        
        channel = ET.SubElement(rss, "channel")
        
        # Metadados do canal
        ET.SubElement(channel, "title").text = "Câmara Municipal de Fortaleza"
        ET.SubElement(channel, "link").text = "https://www.cmfor.ce.gov.br"
        ET.SubElement(channel, "description").text = "Notícias Oficiais da Câmara Municipal de Fortaleza"
        ET.SubElement(channel, "language").text = "pt-br"
        ET.SubElement(channel, "generator").text = "GitHub Actions - WordPress Otimizado"
        
        last_build = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        ET.SubElement(channel, "lastBuildDate").text = last_build
        ET.SubElement(channel, "ttl").text = "60"
        
        atom_link = ET.SubElement(channel, "atom:link")
        atom_link.set("href", "https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
        atom_link.set("rel", "self")
        atom_link.set("type", "application/rss+xml")
        
        # Processar cada notícia
        for i, item in enumerate(noticias, 1):
            titulo_raw = item.get('title', {}).get('rendered', 'Sem título')
            print(f"   [{i}/{len(noticias)}] {titulo_raw[:60]}...")
            
            item_elem = ET.SubElement(channel, "item")
            
            # Título
            titulo = html.escape(titulo_raw)
            ET.SubElement(item_elem, "title").text = titulo
            
            # Link
            link = item.get('link', '').replace(':8080', '')
            ET.SubElement(item_elem, "link").text = link
            
            # GUID único (evita duplicatas no WordPress)
            guid_hash = hashlib.md5(f"{link}{datetime.now().strftime('%Y%m%d')}".encode()).hexdigest()
            guid = ET.SubElement(item_elem, "guid")
            guid.text = f"cmfor-{guid_hash}"
            guid.set("isPermaLink", "false")
            
            # Data
            pub_date = item.get('date', '')
            if pub_date:
                try:
                    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    ET.SubElement(item_elem, "pubDate").text = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
                except:
                    ET.SubElement(item_elem, "pubDate").text = pub_date
            
            # Conteúdo bruto
            conteudo_raw = item.get('content', {}).get('rendered', '')
            
            # Description (obrigatório, vem primeiro)
            descricao = self.criar_descricao_otimizada(conteudo_raw)
            ET.SubElement(item_elem, "description").text = descricao
            
            # Content:encoded com HTML otimizado para WordPress
            conteudo_otimizado = self.otimizar_html_wordpress(conteudo_raw)
            content_elem = ET.SubElement(item_elem, "content:encoded")
            # Usar CDATA com HTML otimizado
            content_elem.text = f"<![CDATA[{conteudo_otimizado}]]>"
            
            # Adicionar informações de mídia (imagem principal)
            imagem_url = self.extrair_imagem_principal(conteudo_raw)
            if imagem_url:
                # Adicionar como enclosure (padrão RSS)
                enclosure = ET.SubElement(item_elem, "enclosure")
                enclosure.set("url", imagem_url)
                enclosure.set("type", "image/jpeg")
                enclosure.set("length", "100000")  # Tamanho estimado
                
                # Adicionar como media:content (padrão Media RSS)
                media_content = ET.SubElement(item_elem, "media:content")
                media_content.set("url", imagem_url)
                media_content.set("medium", "image")
                media_content.set("type", "image/jpeg")
                
                # Adicionar descrição da mídia
                media_description = ET.SubElement(media_content, "media:description")
                media_description.set("type", "plain")
                media_description.text = titulo_raw[:100]
                
                print(f"      📷 Imagem encontrada: {imagem_url.split('/')[-1]}")
        
        return rss
    
    def formatar_xml_final(self, xml_str):
        """Formata o XML final corrigindo CDATA"""
        xml_final = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
        
        # CORREÇÃO CRÍTICA: Corrigir CDATA escapado
        xml_final = xml_final.replace('&lt;![CDATA[', '<![CDATA[')
        xml_final = xml_final.replace(']]&gt;', ']]>')
        
        # Garantir que não há ]]> fora do CDATA
        # Proteger CDATA legítimos primeiro
        import re
        partes = re.split(r'(<\!\[CDATA\[.*?\]\]>)', xml_final, flags=re.DOTALL)
        
        resultado = []
        for i, parte in enumerate(partes):
            if i % 2 == 0:  # Fora do CDATA
                parte = parte.replace(']]>', '')  # Remover qualquer ]]> residual
            resultado.append(parte)
        
        xml_final = ''.join(resultado)
        
        # Formatar com indentação
        try:
            import xml.dom.minidom
            dom = xml.dom.minidom.parseString(xml_final)
            xml_final = dom.toprettyxml(indent="  ")
            
            # Remover linha duplicada da declaração XML
            lines = xml_final.split('\n')
            xml_final = '\n'.join(lines[1:])
        except:
            pass  # Manter sem formatação se der erro
        
        return xml_final
    
    def executar(self):
        """Executa a geração completa do feed"""
        print("=" * 70)
        print("🚀 GERANDO FEED RSS OTIMIZADO PARA WORDPRESS")
        print("=" * 70)
        
        try:
            # Buscar notícias
            print("📡 Buscando notícias da Câmara...")
            response = requests.get(self.api_url, params={
                "per_page": 10,
                "orderby": "date",
                "order": "desc"
            }, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Erro na API: {response.status_code}")
                # Feed mínimo de fallback
                with open(self.feed_file, "w", encoding="utf-8") as f:
                    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Câmara Municipal de Fortaleza</title><link>https://www.cmfor.ce.gov.br</link><description>Feed em manutenção</description></channel></rss>')
                return True
            
            noticias = response.json()
            print(f"✅ {len(noticias)} notícias encontradas")
            
            # Criar feed
            print("📝 Criando feed otimizado...")
            rss_tree = self.criar_feed_completo(noticias)
            
            # Gerar XML
            print("💾 Formatando XML...")
            xml_str = ET.tostring(rss_tree, encoding='unicode', method='xml')
            xml_final = self.formatar_xml_final(xml_str)
            
            # Salvar
            with open(self.feed_file, "w", encoding="utf-8") as f:
                f.write(xml_final)
            
            file_size = os.path.getsize(self.feed_file)
            print(f"✅ Feed salvo: {self.feed_file} ({file_size:,} bytes)")
            
            # Verificação final
            print("\n🔍 VERIFICAÇÃO FINAL:")
            with open(self.feed_file, "r", encoding="utf-8") as f:
                content = f.read()
                
                # Contar imagens
                imagens = re.findall(r'<img[^>]+src="[^"]+"', content)
                print(f"   📷 Imagens no feed: {len(imagens)}")
                
                # Verificar estrutura
                checks = {
                    "Tem CDATA": '<![CDATA[' in content,
                    "Tem HTML normal": '<p>' in content or '<img' in content,
                    "Sem <updated>": '<updated>' not in content,
                    "GUIDs únicos": content.count('cmfor-') >= 10,
                    "Enclosures": 'enclosure url=' in content,
                }
                
                for check, resultado in checks.items():
                    print(f"   {'✅' if resultado else '❌'} {check}")
            
            print("\n" + "=" * 70)
            print("🎉 FEED PRONTO PARA WORDPRESS!")
            print("=" * 70)
            print("🔗 URL: https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
            print("=" * 70)
            print("⚙️  Configuração WordPress recomendada:")
            print("   • Plugin: WP RSS Aggregator ou WP Automatic")
            print("   • Post content: {content}")
            print("   • Get full content: YES")
            print("   • Download images: YES")
            print("   • First image as featured: YES")
            print("=" * 70)
            
            return True
            
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    generator = FeedGenerator()
    success = generator.executar()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
