#!/usr/bin/env python3
"""
Script para atualizar feed RSS - VERSÃO FINAL CORRIGIDA
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os
import sys
import html
import re

def limpar_conteudo(conteudo):
    """
    Limpa o conteúdo mantendo HTML válido e escapa ]]>
    """
    # Decodificar entidades HTML
    conteudo = html.unescape(conteudo)
    
    # Remover tags problemáticas
    conteudo = re.sub(r'<updated>.*?</updated>', '', conteudo)
    
    # Escapar sequências ]]> dentro do conteúdo
    conteudo = conteudo.replace(']]>', ']]]]><![CDATA[>')
    
    # Remover atributos problemáticos
    conteudo = re.sub(r'\sstyle="[^"]*"', '', conteudo)
    conteudo = re.sub(r'\sclass="[^"]*"', '', conteudo)
    
    # Corrigir imagens
    conteudo = re.sub(r':8080', '', conteudo)
    
    return conteudo.strip()

def criar_feed_rss_valido(noticias):
    """
    Cria feed RSS 2.0 válido
    """
    # Elemento raiz
    rss = ET.Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
    rss.set("xmlns:dc", "http://purl.org/dc/elements/1.1/")
    
    # Channel
    channel = ET.SubElement(rss, "channel")
    
    # Metadados do canal
    ET.SubElement(channel, "title").text = "Câmara Municipal de Fortaleza"
    ET.SubElement(channel, "link").text = "https://www.cmfor.ce.gov.br"
    ET.SubElement(channel, "description").text = "Notícias Oficiais da Câmara Municipal de Fortaleza"
    ET.SubElement(channel, "language").text = "pt-br"
    ET.SubElement(channel, "generator").text = "GitHub Actions"
    
    # Data de build
    last_build = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    ET.SubElement(channel, "lastBuildDate").text = last_build
    
    # TTL
    ET.SubElement(channel, "ttl").text = "60"
    
    # Atom link
    atom_link = ET.SubElement(channel, "atom:link")
    atom_link.set("href", "https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")
    
    # Processar cada notícia
    for i, item in enumerate(noticias, 1):
        titulo_raw = item.get('title', {}).get('rendered', 'Sem título')
        print(f"   [{i}/{len(noticias)}] {titulo_raw[:50]}...")
        
        # Elemento item
        item_elem = ET.SubElement(channel, "item")
        
        # Título
        titulo = html.escape(titulo_raw)
        ET.SubElement(item_elem, "title").text = titulo
        
        # Link
        link = item.get('link', '').replace(':8080', '')
        ET.SubElement(item_elem, "link").text = link
        
        # GUID
        guid = ET.SubElement(item_elem, "guid")
        guid.text = link
        guid.set("isPermaLink", "true")
        
        # Data de publicação
        pub_date = item.get('date', '')
        if pub_date:
            try:
                dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                pub_date_str = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
                ET.SubElement(item_elem, "pubDate").text = pub_date_str
                # dc:date
                dc_date = ET.SubElement(item_elem, "dc:date")
                dc_date.text = dt.isoformat()
            except Exception as e:
                print(f"      ⚠️ Erro na data: {e}")
                ET.SubElement(item_elem, "pubDate").text = pub_date
        
        # Conteúdo bruto
        conteudo_raw = item.get('content', {}).get('rendered', '')
        
        # Limpar conteúdo (ESCAPA ]]>)
        conteudo_limpo = limpar_conteudo(conteudo_raw)
        
        # Criar description (texto simples, sem tags HTML)
        texto_simples = re.sub('<[^>]+>', '', conteudo_raw)
        texto_simples = html.unescape(texto_simples)
        descricao = (texto_simples[:250] + "...") if len(texto_simples) > 250 else texto_simples
        descricao = html.escape(descricao)
        
        # Description (SEM CDATA!)
        desc_elem = ET.SubElement(item_elem, "description")
        desc_elem.text = descricao
        
        # Content:encoded (COM CDATA, conteúdo escapado)
        content_elem = ET.SubElement(item_elem, "content:encoded")
        # O conteúdo já está com ]]> escapado
        content_elem.text = f"<![CDATA[{conteudo_limpo}]]>"
        
        # Autor
        try:
            author = item.get('_embedded', {}).get('author', [{}])[0].get('name', '')
            if author:
                ET.SubElement(item_elem, "author").text = author
                dc_creator = ET.SubElement(item_elem, "dc:creator")
                dc_creator.text = author
        except:
            pass
    
    return rss

def gerar_xml_final(rss_tree):
    """
    Gera XML final garantindo que ]]> esteja escapado
    """
    # Converter para string XML
    xml_str = ET.tostring(rss_tree, encoding='unicode', method='xml')
    
    # Adicionar declaração XML
    xml_final = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
    
    # Processar manualmente o CDATA
    lines = []
    in_cdata = False
    for line in xml_final.split('\n'):
        if '<content:encoded>' in line and 'CDATA' not in line:
            lines.append(line.replace('<content:encoded>', '<content:encoded><![CDATA['))
        elif '</content:encoded>' in line and ']]>' not in line:
            lines.append(line.replace('</content:encoded>', ']]></content:encoded>'))
        else:
            lines.append(line)
    
    xml_final = '\n'.join(lines)
    
    # Garantir que ]]> esteja escapado se ainda existir
    xml_final = xml_final.replace(']]>', ']]]]><![CDATA[>')
    
    # Corrigir &lt;![CDATA[ para <![CDATA[
    xml_final = xml_final.replace('&lt;![CDATA[', '<![CDATA[')
    xml_final = xml_final.replace(']]&gt;', ']]>')
    
    # Remover linhas vazias
    lines = [line for line in xml_final.split('\n') if line.strip()]
    
    return '\n'.join(lines)

def main():
    print("=" * 60)
    print("🚀 GERANDO FEED RSS 2.0 VÁLIDO")
    print("=" * 60)
    
    # Configurações
    API_URL = "https://www.cmfor.ce.gov.br:8080/wp-json/wp/v2/posts"
    FEED_FILE = "feed.xml"
    
    try:
        # 1. Buscar notícias
        print("📡 Conectando à API da Câmara...")
        params = {
            "per_page": 10,
            "orderby": "date",
            "order": "desc",
            "_embed": "true"
        }
        
        response = requests.get(API_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro na API: {response.status_code}")
            print(f"   Resposta: {response.text[:200]}")
            # Feed mínimo
            with open(FEED_FILE, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Câmara Municipal de Fortaleza</title><link>https://www.cmfor.ce.gov.br</link><description>Feed temporariamente indisponível</description></channel></rss>')
            return True
        
        noticias = response.json()
        print(f"✅ {len(noticias)} notícias encontradas")
        
        # 2. Criar feed
        print("📝 Criando feed RSS...")
        rss = criar_feed_rss_valido(noticias)
        
        # 3. Gerar XML
        print("💾 Gerando XML...")
        xml_final = gerar_xml_final(rss)
        
        # 4. Salvar
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_final)
        
        file_size = os.path.getsize(FEED_FILE)
        print(f"✅ Feed salvo: {FEED_FILE} ({file_size:,} bytes)")
        
        # 5. Verificação rápida
        print("\n🔍 Verificando CDATA...")
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            
            if ']]]]><![CDATA[>' in content:
                print("   ✅ ]]> escapado corretamente")
            else:
                print("   ℹ️ Nenhum ]]> encontrado para escapar")
            
            if '<description><![CDATA[' in content:
                print("   ❌ ERRO: CDATA no description")
            else:
                print("   ✅ Description sem CDATA")
            
            if '<content:encoded><![CDATA[' in content:
                print("   ✅ Content com CDATA")
            else:
                print("   ❌ ERRO: Content sem CDATA")
        
        print("\n📄 Primeiras linhas do feed:")
        print("-" * 60)
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            for i, line in enumerate(f.readlines()[:20], 1):
                if line.strip():
                    print(f"{i:2}: {line.rstrip()[:80]}")
        print("-" * 60)
        
        print("\n" + "=" * 60)
        print("🎉 FEED GERADO!")
        print("=" * 60)
        print(f"📊 Estatísticas:")
        print(f"   • Notícias: {len(noticias)}")
        print(f"   • Tamanho: {file_size:,} bytes")
        print(f"   • Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("=" * 60)
        print(f"🔗 Valide em:")
        print(f"   https://validator.w3.org/feed/")
        print(f"   URL: https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
