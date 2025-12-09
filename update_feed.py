#!/usr/bin/env python3
"""
Script final para feed RSS - VERSÃO ULTIMATE
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os
import sys
import re

def limpar_conteudo_ultra_seguro(conteudo):
    """
    Limpa conteúdo garantindo NENHUM ]]> no resultado
    """
    # Remover qualquer ]]> que possa existir
    conteudo = re.sub(r'\]\]\s*>', '', conteudo)
    
    # Remover tags problemáticas
    conteudo = re.sub(r'<updated>.*?</updated>', '', conteudo)
    
    # Decodificar entidades HTML (mas manter < > & escapados)
    from html import unescape
    conteudo = unescape(conteudo)
    
    # AGORA escapar para XML
    conteudo = conteudo.replace('&', '&amp;')
    conteudo = conteudo.replace('<', '&lt;')
    conteudo = conteudo.replace('>', '&gt;')
    conteudo = conteudo.replace('"', '&quot;')
    
    # Remover porta :8080
    conteudo = re.sub(r':8080', '', conteudo)
    
    return conteudo.strip()

def main():
    print("=" * 60)
    print("🚀 GERANDO FEED RSS ULTIMATE")
    print("=" * 60)
    
    API_URL = "https://www.cmfor.ce.gov.br:8080/wp-json/wp/v2/posts"
    FEED_FILE = "feed.xml"
    
    try:
        # Buscar notícias
        print("📡 Conectando à API...")
        response = requests.get(API_URL, params={
            "per_page": 10,
            "orderby": "date",
            "order": "desc"
        }, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro {response.status_code}")
            # Feed mínimo válido
            with open(FEED_FILE, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Câmara Municipal de Fortaleza</title><link>https://www.cmfor.ce.gov.br</link><description>Feed em manutenção</description></channel></rss>')
            return True
        
        noticias = response.json()
        print(f"✅ {len(noticias)} notícias")
        
        # Criar XML
        rss = ET.Element("rss")
        rss.set("version", "2.0")
        rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
        rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
        
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = "Câmara Municipal de Fortaleza"
        ET.SubElement(channel, "link").text = "https://www.cmfor.ce.gov.br"
        ET.SubElement(channel, "description").text = "Notícias Oficiais da Câmara Municipal de Fortaleza"
        ET.SubElement(channel, "language").text = "pt-br"
        ET.SubElement(channel, "generator").text = "GitHub Actions"
        ET.SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        ET.SubElement(channel, "ttl").text = "60"
        
        atom_link = ET.SubElement(channel, "atom:link")
        atom_link.set("href", "https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
        atom_link.set("rel", "self")
        atom_link.set("type", "application/rss+xml")
        
        # Processar notícias
        for item in noticias:
            item_elem = ET.SubElement(channel, "item")
            
            titulo = item.get('title', {}).get('rendered', 'Sem título')
            ET.SubElement(item_elem, "title").text = titulo
            
            link = item.get('link', '').replace(':8080', '')
            ET.SubElement(item_elem, "link").text = link
            
            guid = ET.SubElement(item_elem, "guid")
            guid.text = link
            guid.set("isPermaLink", "true")
            
            # Data
            pub_date = item.get('date', '')
            if pub_date:
                try:
                    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    ET.SubElement(item_elem, "pubDate").text = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
                except:
                    ET.SubElement(item_elem, "pubDate").text = pub_date
            
            # Description simples
            conteudo_raw = item.get('content', {}).get('rendered', '')
            texto_simples = re.sub('<[^>]+>', '', conteudo_raw)
            descricao = (texto_simples[:250] + "...") if len(texto_simples) > 250 else texto_simples
            ET.SubElement(item_elem, "description").text = descricao
            
            # Content:encoded limpo
            conteudo_limpo = limpar_conteudo_ultra_seguro(conteudo_raw)
            content_elem = ET.SubElement(item_elem, "content:encoded")
            content_elem.text = conteudo_limpo
        
        # Gerar XML
        xml_str = ET.tostring(rss, encoding='unicode', method='xml')
        xml_final = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
        
        # VERIFICAÇÃO FINAL: Garantir NENHUM ]]>
        if ']]>' in xml_final:
            print("⚠️  ALERTA: Encontrado ]]>, removendo...")
            xml_final = xml_final.replace(']]>', '')
        
        # Salvar
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_final)
        
        print(f"✅ Feed salvo: {FEED_FILE}")
        
        # Teste final
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            if ']]>' in content:
                print("❌ ERRO CRÍTICO: Ainda tem ]]> no arquivo!")
                # Forçar remoção
                content = content.replace(']]>', '')
                with open(FEED_FILE, "w", encoding="utf-8") as f2:
                    f2.write(content)
            else:
                print("✅ VERIFICADO: Nenhum ]]> no arquivo final")
        
        print("\n" + "=" * 60)
        print("🎉 FEED PRONTO!")
        print("=" * 60)
        print("🔗 Valide em: https://validator.w3.org/feed/")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
