#!/usr/bin/env python3
"""
Script para atualizar feed RSS - VERSÃO PARA GITHUB ACTIONS
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os
import sys
import html

def main():
    print("=" * 60)
    print("🚀 GERANDO FEED RSS - GITHUB ACTIONS")
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
            "order": "desc"
        }
        
        response = requests.get(API_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro na API: {response.status_code}")
            print(f"   Resposta: {response.text[:200]}")
            sys.exit(1)
        
        noticias = response.json()
        print(f"✅ {len(noticias)} notícias encontradas")
        
        # 2. Criar feed RSS
        print("📝 Criando estrutura RSS...")
        
        # Elemento raiz
        rss = ET.Element("rss")
        rss.set("version", "2.0")
        rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
        rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
        
        # Channel
        channel = ET.SubElement(rss, "channel")
        
        # Metadados
        ET.SubElement(channel, "title").text = "Câmara Municipal de Fortaleza"
        ET.SubElement(channel, "link").text = "https://www.cmfor.ce.gov.br"
        ET.SubElement(channel, "description").text = "Notícias Oficiais da Câmara Municipal de Fortaleza"
        ET.SubElement(channel, "language").text = "pt-br"
        ET.SubElement(channel, "generator").text = "GitHub Actions"
        ET.SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        
        # Atom link
        atom_link = ET.SubElement(channel, "atom:link")
        atom_link.set("href", "https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
        atom_link.set("rel", "self")
        atom_link.set("type", "application/rss+xml")
        
        # 3. Processar cada notícia
        print(f"📰 Processando {len(noticias)} notícias...")
        
        for i, item in enumerate(noticias, 1):
            titulo_raw = item.get('title', {}).get('rendered', 'Sem título')
            print(f"   [{i}/{len(noticias)}] {titulo_raw[:50]}...")
            
            item_elem = ET.SubElement(channel, "item")
            
            # Título
            titulo = html.escape(titulo_raw)
            ET.SubElement(item_elem, "title").text = titulo
            
            # Link (remover porta 8080)
            link = item.get('link', '').replace(':8080', '')
            ET.SubElement(item_elem, "link").text = link
            
            # GUID
            guid = ET.SubElement(item_elem, "guid")
            guid.text = link
            guid.set("isPermaLink", "true")
            
            # Conteúdo
            conteudo_raw = item.get('content', {}).get('rendered', '')
            
            # Criar resumo para description
            import re
            texto_simples = re.sub('<[^>]+>', '', conteudo_raw)
            descricao = texto_simples[:500] + "..." if len(texto_simples) > 500 else texto_simples
            
            # Description (PRIMEIRO - obrigatório no RSS 2.0)
            desc_elem = ET.SubElement(item_elem, "description")
            desc_elem.text = f"<![CDATA[{descricao}]]>"
            
            # Content:encoded (DEPOIS - conteúdo completo)
            content_elem = ET.SubElement(item_elem, "content:encoded")
            content_elem.text = f"<![CDATA[{conteudo_raw}]]>"
            
            # Data de publicação
            pub_date = item.get('date', '')
            if pub_date:
                try:
                    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    ET.SubElement(item_elem, "pubDate").text = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
                except:
                    ET.SubElement(item_elem, "pubDate").text = pub_date
        
        # 4. Converter para XML
        print("💾 Convertendo para XML...")
        
        # Converter para string
        xml_str = ET.tostring(rss, encoding='unicode', method='xml')
        
        # Adicionar declaração XML
        xml_final = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
        
        # Corrigir CDATA
        xml_final = xml_final.replace('&lt;![CDATA[', '<![CDATA[')
        xml_final = xml_final.replace(']]&gt;', ']]>')
        
        # Remover linhas vazias
        lines = [line for line in xml_final.split('\n') if line.strip()]
        xml_final = '\n'.join(lines)
        
        # 5. Salvar arquivo
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_final)
        
        file_size = os.path.getsize(FEED_FILE)
        print(f"✅ Feed salvo: {FEED_FILE} ({file_size:,} bytes)")
        
        # 6. Mostrar preview
        print("\n📄 Preview do feed:")
        print("-" * 50)
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[:15]
            for line in lines:
                if line.strip():
                    print(f"   {line[:80].rstrip()}{'...' if len(line) > 80 else ''}")
        print("-" * 50)
        
        print("\n" + "=" * 60)
        print("🎉 FEED GERADO COM SUCESSO!")
        print("=" * 60)
        print(f"📊 Estatísticas:")
        print(f"   • Notícias processadas: {len(noticias)}")
        print(f"   • Data/hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"   • Arquivo: {FEED_FILE}")
        print("=" * 60)
        print(f"🔗 URL do feed: https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
        print("=" * 60)
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
