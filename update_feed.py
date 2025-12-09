#!/usr/bin/env python3
"""
Script para atualizar feed RSS da Câmara de Fortaleza
Versão simplificada para GitHub Actions
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os

print("🔄 Iniciando atualização do feed RSS...")

# 1. Buscar notícias da API
API_URL = "https://www.cmfor.ce.gov.br:8080/wp-json/wp/v2/posts"

try:
    print("📡 Conectando à API da Câmara...")
    response = requests.get(API_URL, params={"per_page": 15, "orderby": "date"})
    
    if response.status_code != 200:
        print(f"❌ Erro na API: {response.status_code}")
        exit(1)
    
    noticias = response.json()
    print(f"✅ {len(noticias)} notícias encontradas")
    
except Exception as e:
    print(f"❌ Erro ao buscar notícias: {e}")
    exit(1)

# 2. Criar feed RSS
print("📝 Gerando feed RSS...")

# Criar elemento raiz RSS
rss = ET.Element("rss", version="2.0")

# Criar channel
channel = ET.SubElement(rss, "channel")

# Metadados do channel
ET.SubElement(channel, "title").text = "Câmara Municipal de Fortaleza"
ET.SubElement(channel, "link").text = "https://www.cmfor.ce.gov.br"
ET.SubElement(channel, "description").text = "Notícias Oficiais da Câmara Municipal de Fortaleza"
ET.SubElement(channel, "language").text = "pt-br"
ET.SubElement(channel, "lastBuildDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")

# Adicionar cada notícia
for item in noticias:
    item_elem = ET.SubElement(channel, "item")
    
    # Título
    titulo = item.get('title', {}).get('rendered', 'Sem título')
    # Corrigir caracteres especiais
    titulo = titulo.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    ET.SubElement(item_elem, "title").text = titulo
    
    # Link
    link = item.get('link', '')
    ET.SubElement(item_elem, "link").text = link
    
    # Conteúdo
    conteudo = item.get('content', {}).get('rendered', '')
    desc_elem = ET.SubElement(item_elem, "description")
    desc_elem.text = f"<![CDATA[{conteudo}]]>"
    
    # Data
    data = item.get('date', '')
    if data:
        ET.SubElement(item_elem, "pubDate").text = data

# 3. Converter para string XML
xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
xml_str += ET.tostring(rss, encoding='unicode', method='xml')

# 4. Salvar em arquivo
print("💾 Salvando arquivo feed.xml...")
try:
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)
    print("✅ Feed salvo com sucesso!")
    
    # Mostrar estatísticas
    print(f"📊 Estatísticas:")
    print(f"   - Notícias: {len(noticias)}")
    print(f"   - Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
except Exception as e:
    print(f"❌ Erro ao salvar arquivo: {e}")
    exit(1)

print("🎉 Atualização concluída com sucesso!")
