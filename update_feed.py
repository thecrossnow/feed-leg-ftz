#!/usr/bin/env python3
"""
FEED RSS 2.0 - VERSÃO FINAL COM GARANTIA DE IMAGENS
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os
import sys
import re
import html
import hashlib

class FeedOtimizado:
    def __init__(self):
        self.api_url = "https://www.cmfor.ce.gov.br:8080/wp-json/wp/v2/posts"
        self.feed_file = "feed.xml"
        self.imagem_padrao = "https://www.cmfor.ce.gov.br/wp-content/uploads/2024/01/logo-cmfor.png"
    
    def garantir_html_valido(self, html_content):
        """Garante HTML válido dentro do CDATA"""
        # Remover qualquer CDATA interno
        html_content = html_content.replace('<![CDATA[', '').replace(']]>', '')
        
        # Decodificar HTML entities
        html_content = html.unescape(html_content)
        
        # Remover elementos problemáticos
        html_content = re.sub(r'<updated>.*?</updated>', '', html_content, flags=re.DOTALL)
        
        # Remover porta 8080
        html_content = html_content.replace(':8080', '')
        
        # Corrigir aspas curvas para retas (comum em Word)
        html_content = html_content.replace('"', '"').replace('"', '"')
        
        # Escapar apenas & que não seja parte de entity
        html_content = re.sub(r'&(?!(?:[a-zA-Z]+|#\d+);)', '&amp;', html_content)
        
        # Garantir URLs absolutas
        def completar_url(match):
            url = match.group(1)
            if url.startswith('/'):
                return f'href="https://www.cmfor.ce.gov.br{url}"'
            return match.group(0)
        
        html_content = re.sub(r'href="/([^"]+)"', completar_url, html_content)
        
        # Garantir que listas tenham formatação correta
        if '<ul>' in html_content and '<li>' not in html_content:
            # Converter para parágrafos se não tiver formatação de lista
            html_content = html_content.replace('<ul>', '<p>• ').replace('</ul>', '</p>')
        
        return html_content.strip()
    
    def encontrar_imagem_noticia(self, conteudo, titulo):
        """Encontra a melhor imagem para a notícia"""
        # Padrões de busca
        padroes = [
            r'<figure[^>]*>.*?<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|gif|webp))"',
            r'<img[^>]+src="([^"]+wp-content/uploads[^"]+\.(?:jpg|jpeg|png|gif))"',
            r'background-image:\s*url\([\'"]?([^\'"\)]+\.(?:jpg|jpeg|png))',
            r'<img[^>]+src="([^"]+/202[0-9]/[0-9]{2}/[^"]+\.(?:jpg|jpeg|png))"',
        ]
        
        for padrao in padroes:
            match = re.search(padrao, conteudo, re.IGNORECASE | re.DOTALL)
            if match:
                img_url = match.group(1)
                if img_url and 'logo' not in img_url.lower():
                    if img_url.startswith('/'):
                        img_url = f"https://www.cmfor.ce.gov.br{img_url}"
                    img_url = img_url.replace(':8080', '')
                    return img_url
        
        # Se não encontrar, usar imagem padrão baseada no tema
        palavras_chave = {
            'transporte|motocicleta|uber|99|app': 'transporte.jpg',
            'educação|escola|professor|aluno': 'educacao.jpg',
            'saúde|hospital|médico|enfermeiro': 'saude.jpg',
            'segurança|polícia|guarda|violência': 'seguranca.jpg',
        }
        
        titulo_lower = titulo.lower()
        for palavras, imagem in palavras_chave.items():
            if any(palavra in titulo_lower for palavra in palavras.split('|')):
                return f"https://www.cmfor.ce.gov.br/wp-content/uploads/2024/01/{imagem}"
        
        return self.imagem_padrao
    
    def criar_feed_otimizado(self, noticias):
        """Cria feed com garantia de conteúdo e imagens"""
        rss = ET.Element("rss")
        rss.set("version", "2.0")
        rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
        rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
        rss.set("xmlns:media", "http://search.yahoo.com/mrss/")
        
        channel = ET.SubElement(rss, "channel")
        
        # Cabeçalho
        ET.SubElement(channel, "title").text = "Câmara Municipal de Fortaleza"
        ET.SubElement(channel, "link").text = "https://www.cmfor.ce.gov.br"
        ET.SubElement(channel, "description").text = "Notícias Oficiais da Câmara Municipal de Fortaleza"
        ET.SubElement(channel, "language").text = "pt-br"
        ET.SubElement(channel, "generator").text = "GitHub Actions Feed Otimizado"
        ET.SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        ET.SubElement(channel, "ttl").text = "60"
        
        atom_link = ET.SubElement(channel, "atom:link")
        atom_link.set("href", "https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
        atom_link.set("rel", "self")
        atom_link.set("type", "application/rss+xml")
        
        # Processar notícias
        for i, item in enumerate(noticias, 1):
            titulo_raw = item.get('title', {}).get('rendered', 'Sem título')
            print(f"   [{i}/{len(noticias)}] {titulo_raw[:70]}...")
            
            item_elem = ET.SubElement(channel, "item")
            
            # Elementos básicos
            ET.SubElement(item_elem, "title").text = html.escape(titulo_raw)
            
            link = item.get('link', '').replace(':8080', '')
            ET.SubElement(item_elem, "link").text = link
            
            # GUID único
            guid_hash = hashlib.md5(f"{link}{datetime.now().strftime('%Y%m%d%H')}".encode()).hexdigest()
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
            
            # Conteúdo
            conteudo_raw = item.get('content', {}).get('rendered', '')
            
            # Description
            texto_simples = re.sub('<[^>]+>', '', conteudo_raw)
            texto_simples = html.unescape(texto_simples)
            descricao = (texto_simples[:300] + "...") if len(texto_simples) > 300 else texto_simples
            ET.SubElement(item_elem, "description").text = html.escape(descricao)
            
            # Content:encoded - HTML otimizado
            conteudo_limpo = self.garantir_html_valido(conteudo_raw)
            content_elem = ET.SubElement(item_elem, "content:encoded")
            content_elem.text = f"<![CDATA[{conteudo_limpo}]]>"
            
            # Imagem (CRÍTICO para WordPress)
            imagem_url = self.encontrar_imagem_noticia(conteudo_raw, titulo_raw)
            
            # Adicionar como enclosure (WordPress reconhece)
            enclosure = ET.SubElement(item_elem, "enclosure")
            enclosure.set("url", imagem_url)
            enclosure.set("type", "image/jpeg")
            enclosure.set("length", "50000")
            
            # Adicionar como media:content
            media_content = ET.SubElement(item_elem, "media:content")
            media_content.set("url", imagem_url)
            media_content.set("medium", "image")
            media_content.set("type", "image/jpeg")
            
            media_title = ET.SubElement(media_content, "media:title")
            media_title.set("type", "plain")
            media_title.text = html.escape(titulo_raw[:100])
            
            media_description = ET.SubElement(media_content, "media:description")
            media_description.set("type", "plain")
            media_description.text = html.escape(descricao[:200])
            
            if 'logo-cmfor' in imagem_url:
                print(f"      ⚠️  Usando imagem padrão")
            else:
                print(f"      📷 Imagem: {imagem_url.split('/')[-1]}")
        
        return rss
    
    def executar(self):
        """Executa geração do feed"""
        print("=" * 70)
        print("🚀 FEED RSS COM GARANTIA DE IMAGENS")
        print("=" * 70)
        
        try:
            # Buscar notícias
            print("📡 Conectando à API...")
            response = requests.get(self.api_url, params={
                "per_page": 10,
                "orderby": "date",
                "order": "desc"
            }, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Erro {response.status_code}")
                return False
            
            noticias = response.json()
            print(f"✅ {len(noticias)} notícias")
            
            # Criar feed
            print("📝 Processando...")
            rss_tree = self.criar_feed_otimizado(noticias)
            
            # Gerar XML
            xml_str = ET.tostring(rss_tree, encoding='unicode', method='xml')
            xml_final = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
            
            # Corrigir CDATA
            xml_final = xml_final.replace('&lt;![CDATA[', '<![CDATA[')
            xml_final = xml_final.replace(']]&gt;', ']]>')
            
            # Formatar
            try:
                import xml.dom.minidom
                dom = xml.dom.minidom.parseString(xml_final)
                xml_final = dom.toprettyxml(indent="  ")
                lines = xml_final.split('\n')
                xml_final = '\n'.join(lines[1:])
            except:
                pass
            
            # Salvar
            with open(self.feed_file, "w", encoding="utf-8") as f:
                f.write(xml_final)
            
            # Verificação
            print("\n🔍 Verificação:")
            with open(self.feed_file, "r", encoding="utf-8") as f:
                content = f.read()
                imagens = len(re.findall(r'<enclosure[^>]+url="[^"]+"', content))
                print(f"   📷 Notícias com imagens: {imagens}/10")
                print(f"   ✅ CDATA correto: {'<![CDATA[' in content}")
                print(f"   ✅ Sem <updated>: {'<updated>' not in content}")
            
            print("\n" + "=" * 70)
            print("🎉 FEED GERADO COM SUCESSO!")
            print("=" * 70)
            print("⚙️  Dica para WordPress:")
            print("   • No WP Automatic, use: 'Get full content: YES'")
            print("   • 'Download images: YES'")
            print("   • 'First image as featured: YES'")
            print("=" * 70)
            
            return True
            
        except Exception as e:
            print(f"❌ Erro: {e}")
            return False

if __name__ == "__main__":
    feed = FeedOtimizado()
    success = feed.executar()
    sys.exit(0 if success else 1)
