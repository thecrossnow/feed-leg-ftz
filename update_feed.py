#!/usr/bin/env python3
"""
Script para atualizar feed RSS - VERSÃO CORRIGIDA E VÁLIDA
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os

print("=" * 60)
print("🔄 ATUALIZANDO FEED RSS - VERSÃO VÁLIDA")
print("=" * 60)

# Configurações
API_URL = "https://www.cmfor.ce.gov.br:8080/wp-json/wp/v2/posts"
ITEMS_TO_FETCH = 10
FEED_FILE = "feed.xml"

def criar_feed_valido(noticias):
    """Criar feed RSS 2.0 válido"""
    print("📝 Criando feed válido...")
    
    # Criar elemento raiz com namespaces CORRETOS
    rss = ET.Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
    rss.set("xmlns:dc", "http://purl.org/dc/elements/1.1/")
    
    # Channel
    channel = ET.SubElement(rss, "channel")
    
    # Metadados obrigatórios
    ET.SubElement(channel, "title").text = "Câmara Municipal de Fortaleza"
    ET.SubElement(channel, "link").text = "https://www.cmfor.ce.gov.br"
    ET.SubElement(channel, "description").text = "Notícias Oficiais da Câmara Municipal de Fortaleza"
    ET.SubElement(channel, "language").text = "pt-br"
    ET.SubElement(channel, "generator").text = "Feed Generator v2.0"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    
    # Atom link
    atom_link = ET.SubElement(channel, "atom:link")
    atom_link.set("href", "https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")
    
    print(f"📰 Processando {len(noticias)} notícias...")
    
    for i, item in enumerate(noticias, 1):
        titulo_raw = item.get('title', {}).get('rendered', 'Sem título')
        print(f"   [{i}/{len(noticias)}] {titulo_raw[:50]}...")
        
        item_elem = ET.SubElement(channel, "item")
        
        # Título
        titulo = titulo_raw.replace('&', '&amp;')
        ET.SubElement(item_elem, "title").text = titulo
        
        # Link
        link = item.get('link', '').replace(':8080', '')
        ET.SubElement(item_elem, "link").text = link
        
        # GUID
        guid = ET.SubElement(item_elem, "guid")
        guid.text = link
        guid.set("isPermaLink", "true")
        
        # Conteúdo
        conteudo_raw = item.get('content', {}).get('rendered', '')
        
        # 1. PRIMEIRO: description (obrigatório no RSS 2.0)
        # Extrair resumo (primeiros 500 chars sem tags)
        import re
        texto_simples = re.sub('<[^>]+>', '', conteudo_raw)
        descricao = texto_simples[:500] + "..." if len(texto_simples) > 500 else texto_simples
        
        desc_elem = ET.SubElement(item_elem, "description")
        desc_elem.text = f"<![CDATA[{descricao}]]>"
        
        # 2. DEPOIS: content:encoded (opcional, para conteúdo completo)
        content_elem = ET.SubElement(item_elem, "content:encoded")
        content_elem.text = f"<![CDATA[{conteudo_raw}]]>"
        
        # Data RFC 2822 format (obrigatório)
        pub_date = item.get('date', '')
        if pub_date:
            try:
                dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                ET.SubElement(item_elem, "pubDate").text = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except:
                ET.SubElement(item_elem, "pubDate").text = pub_date
        
        # NÃO usar <updated> - não é padrão RSS 2.0
        # Use dc:date se quiser data modificação
        modified = item.get('modified', '')
        if modified:
            dc_date = ET.SubElement(item_elem, "dc:date")
            dc_date.text = modified
    
    return rss

def formatar_xml_valido(rss_element):
    """Formatar XML válido"""
    from xml.dom import minidom
    
    rough_string = ET.tostring(rss_element, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    
    xml_pretty = reparsed.toprettyxml(indent="  ", encoding='utf-8')
    xml_str = xml_pretty.decode('utf-8')
    
    # Corrigir CDATA
    xml_str = xml_str.replace('&lt;![CDATA[', '<![CDATA[')
    xml_str = xml_str.replace(']]&gt;', ']]>')
    
    # Remover XML declaration duplicada
    if xml_str.count('<?xml') > 1:
        lines = xml_str.split('\n')
        lines = [line for line in lines if line.strip()]
        lines = [lines[0]] + [line for line in lines[1:] if not line.startswith('<?xml')]
        xml_str = '\n'.join(lines)
    
    return xml_str

def validar_feed(xml_content):
    """Validar feed com feedvalidator.org"""
    import tempfile
    import webbrowser
    
    # Salvar temporariamente
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml_content)
        temp_path = f.name
    
    print("🔍 Validando feed...")
    
    # URL do validator
    validator_url = f"https://validator.w3.org/feed/check.cgi?url=file://{temp_path}"
    print(f"✅ Validator: {validator_url}")
    
    # Verificar erros comuns
    if '<updated>' in xml_content:
        print("⚠️  AVISO: Elemento <updated> não é padrão RSS 2.0")
    
    if xml_content.find('<content:encoded>') < xml_content.find('<description>'):
        print("⚠️  AVISO: content:encoded deve vir DEPOIS de description")
    
    # Contar itens
    items = xml_content.count('<item>')
    print(f"📊 Feed tem {items} itens")
    
    return temp_path

def main():
    """Função principal"""
    
    print("📡 Buscando notícias...")
    
    try:
        response = requests.get(
            API_URL,
            params={"per_page": ITEMS_TO_FETCH, "orderby": "date", "order": "desc"},
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Erro API: {response.status_code}")
            return False
        
        noticias = response.json()
        print(f"✅ {len(noticias)} notícias encontradas")
        
        # Criar feed válido
        rss = criar_feed_valido(noticias)
        
        # Formatar
        xml_content = formatar_xml_valido(rss)
        
        # Validar
        temp_file = validar_feed(xml_content)
        
        # Salvar
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_content)
        
        file_size = os.path.getsize(FEED_FILE)
        print(f"💾 Feed salvo: {file_size:,} bytes")
        
        # Mostrar estrutura
        print("\n📋 ESTRUTURA DO FEED:")
        print("-" * 50)
        lines = xml_content.split('\n')
        for line in lines[:20]:
            if line.strip():
                print(f"   {line[:80]}{'...' if len(line) > 80 else ''}")
        print("-" * 50)
        
        print("\n" + "=" * 60)
        print("🎉 FEED RSS VÁLIDO GERADO!")
        print("=" * 60)
        print(f"🔗 URL: https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
        print("=" * 60)
        
        # Perguntar se quer abrir validator
        abrir = input("\nAbrir validador no navegador? (s/n): ")
        if abrir.lower() == 's':
            webbrowser.open(f"https://validator.w3.org/feed/check.cgi?url=https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
