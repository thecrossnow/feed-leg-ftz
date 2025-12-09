#!/usr/bin/env python3
"""
Script para atualizar feed RSS - VERSÃO SIMPLIFICADA E FUNCIONAL
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os
import sys
import html
import re

def limpar_conteudo_para_rss(conteudo):
    """
    Limpa o conteúdo para RSS sem usar CDATA problemático
    """
    # Decodificar HTML entities
    conteudo = html.unescape(conteudo)
    
    # Remover elementos problemáticos
    conteudo = re.sub(r'<updated>.*?</updated>', '', conteudo)
    conteudo = re.sub(r'<dc:creator>.*?</dc:creator>', '', conteudo)
    
    # Escapar caracteres XML especiais
    conteudo = conteudo.replace('&', '&amp;')
    conteudo = conteudo.replace('<', '&lt;')
    conteudo = conteudo.replace('>', '&gt;')
    conteudo = conteudo.replace('"', '&quot;')
    conteudo = conteudo.replace("'", '&apos;')
    
    # IMPORTANTE: Remover qualquer ]]> que possa existir
    conteudo = conteudo.replace(']]>', '')
    
    # Remover porta :8080 das URLs
    conteudo = re.sub(r':8080', '', conteudo)
    
    return conteudo.strip()

def criar_feed_rss_simples(noticias):
    """
    Cria feed RSS 2.0 válido sem problemas de CDATA
    """
    # Elemento raiz
    rss = ET.Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
    
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
                ET.SubElement(item_elem, "pubDate").text = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except:
                ET.SubElement(item_elem, "pubDate").text = pub_date
        
        # Conteúdo bruto
        conteudo_raw = item.get('content', {}).get('rendered', '')
        
        # Criar description (texto simples)
        texto_simples = re.sub('<[^>]+>', '', conteudo_raw)
        texto_simples = html.unescape(texto_simples)
        descricao = (texto_simples[:250] + "...") if len(texto_simples) > 250 else texto_simples
        descricao = html.escape(descricao)
        
        # Description (texto simples, sem HTML)
        ET.SubElement(item_elem, "description").text = descricao
        
        # Content:encoded (HTML escapado, SEM CDATA)
        conteudo_limpo = limpar_conteudo_para_rss(conteudo_raw)
        content_elem = ET.SubElement(item_elem, "content:encoded")
        content_elem.text = conteudo_limpo  # Já está escapado, não precisa de CDATA
    
    return rss

def gerar_xml_com_indentacao(rss_tree):
    """
    Gera XML bem formatado
    """
    # Converter para string
    xml_str = ET.tostring(rss_tree, encoding='unicode', method='xml')
    
    # Adicionar declaração XML
    xml_final = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
    
    # Formatar com indentação
    import xml.dom.minidom
    
    try:
        dom = xml.dom.minidom.parseString(xml_final)
        xml_final = dom.toprettyxml(indent="  ")
        
        # Remover linha em branco extra após declaração XML
        lines = xml_final.split('\n')
        xml_final = '\n'.join(lines[1:])  # Pular primeira linha duplicada
    except:
        # Fallback simples
        pass
    
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
            "order": "desc"
        }
        
        response = requests.get(API_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro na API: {response.status_code}")
            # Criar feed mínimo
            with open(FEED_FILE, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Câmara Municipal de Fortaleza</title><link>https://www.cmfor.ce.gov.br</link><description>Feed temporariamente indisponível</description></channel></rss>')
            return True
        
        noticias = response.json()
        print(f"✅ {len(noticias)} notícias encontradas")
        
        # 2. Criar feed
        print("📝 Criando feed RSS...")
        rss = criar_feed_rss_simples(noticias)
        
        # 3. Gerar XML
        print("💾 Gerando XML...")
        xml_final = gerar_xml_com_indentacao(rss)
        
        # 4. Verificar se não há ]]> no XML
        if ']]>' in xml_final:
            print("⚠️  Aviso: Encontrado ]]> no XML, removendo...")
            xml_final = xml_final.replace(']]>', '')
        
        # 5. Salvar
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_final)
        
        file_size = os.path.getsize(FEED_FILE)
        print(f"✅ Feed salvo: {FEED_FILE} ({file_size:,} bytes)")
        
        # 6. Verificação
        print("\n🔍 Verificando estrutura...")
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            
            checks = {
                "Declaração XML": '<?xml' in content,
                "RSS 2.0": 'version="2.0"' in content,
                "Channel": "<channel>" in content,
                "Itens": content.count("<item>") == len(noticias),
                "Sem ]]>": ']]>' not in content,
                "Sem CDATA": '<![CDATA[' not in content,
                "Com content:encoded": '<content:encoded>' in content,
            }
            
            for check, result in checks.items():
                status = "✅" if result else "❌"
                print(f"   {status} {check}")
        
        print("\n📄 Primeiras linhas:")
        print("-" * 60)
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[:15]
            for i, line in enumerate(lines, 1):
                if line.strip():
                    clean_line = line.rstrip()
                    print(f"{i:2}: {clean_line[:80]}")
        print("-" * 60)
        
        print("\n" + "=" * 60)
        print("🎉 FEED GERADO COM SUCESSO!")
        print("=" * 60)
        print(f"📊 Estatísticas:")
        print(f"   • Notícias: {len(noticias)}")
        print(f"   • Tamanho: {file_size:,} bytes")
        print(f"   • Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("=" * 60)
        print("✅ Este feed NÃO usa CDATA, evitando problemas de validação")
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
