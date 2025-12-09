#!/usr/bin/env python3
"""
Script para atualizar feed RSS da Câmara de Fortaleza
Versão corrigida - XML formatado corretamente
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os

print("=" * 60)
print("🔄 ATUALIZAÇÃO DO FEED RSS - CÂMARA DE FORTALEZA")
print("=" * 60)

# Configurações
API_URL = "https://www.cmfor.ce.gov.br:8080/wp-json/wp/v2/posts"
ITEMS_TO_FETCH = 10  # Número de notícias a buscar
FEED_FILE = "feed.xml"

def buscar_noticias():
    """Buscar notícias da API da Câmara"""
    print("📡 Conectando à API da Câmara...")
    
    try:
        params = {
            "per_page": ITEMS_TO_FETCH,
            "orderby": "date",
            "order": "desc"
        }
        
        response = requests.get(API_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro na API: {response.status_code}")
            return None
        
        noticias = response.json()
        print(f"✅ {len(noticias)} notícias encontradas")
        return noticias
        
    except Exception as e:
        print(f"❌ Erro ao buscar notícias: {e}")
        return None

def limpar_texto(texto):
    """Limpar texto para XML seguro"""
    if not texto:
        return ""
    
    # Primeiro, substituir entidades HTML
    texto = texto.replace('&amp;', '&')
    texto = texto.replace('&lt;', '<')
    texto = texto.replace('&gt;', '>')
    texto = texto.replace('&quot;', '"')
    texto = texto.replace('&#8211;', '-')
    texto = texto.replace('&#8217;', "'")
    texto = texto.replace('&#8220;', '"')
    texto = texto.replace('&#8221;', '"')
    
    # Agora re-escape para XML
    texto = texto.replace('&', '&amp;')
    texto = texto.replace('<', '&lt;')
    texto = texto.replace('>', '&gt;')
    texto = texto.replace('"', '&quot;')
    texto = texto.replace("'", '&apos;')
    
    return texto

def criar_feed_rss(noticias):
    """Criar feed RSS formatado corretamente"""
    print("📝 Criando estrutura RSS...")
    
    # Criar elemento raiz
    rss = ET.Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    
    # Criar channel
    channel = ET.SubElement(rss, "channel")
    
    # Adicionar metadados do channel
    ET.SubElement(channel, "title").text = "Câmara Municipal de Fortaleza"
    ET.SubElement(channel, "link").text = "https://www.cmfor.ce.gov.br"
    ET.SubElement(channel, "description").text = "Notícias Oficiais da Câmara Municipal de Fortaleza"
    ET.SubElement(channel, "language").text = "pt-br"
    ET.SubElement(channel, "generator").text = "Feed Generator v2.0"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    # Adicionar link atom
    atom_link = ET.SubElement(channel, "atom:link")
    atom_link.set("href", "https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")
    
    print(f"📰 Processando {len(noticias)} notícias...")
    
    # Adicionar cada notícia
    for i, item in enumerate(noticias, 1):
        print(f"   [{i}/{len(noticias)}] Processando: {item.get('title', {}).get('rendered', '')[:50]}...")
        
        item_elem = ET.SubElement(channel, "item")
        
        # Título
        titulo_raw = item.get('title', {}).get('rendered', 'Sem título')
        titulo = limpar_texto(titulo_raw)
        ET.SubElement(item_elem, "title").text = titulo
        
        # Link
        link = item.get('link', '')
        ET.SubElement(item_elem, "link").text = link
        
        # GUID
        guid = ET.SubElement(item_elem, "guid")
        guid.text = link
        guid.set("isPermaLink", "true")
        
        # Descrição (conteúdo)
        conteudo_raw = item.get('content', {}).get('rendered', '')
        conteudo = limpar_texto(conteudo_raw)
        description = ET.SubElement(item_elem, "description")
        description.text = f"<![CDATA[{conteudo}]]>"
        
        # Data de publicação
        pub_date = item.get('date', '')
        if pub_date:
            ET.SubElement(item_elem, "pubDate").text = pub_date
        
        # Data de modificação
        modified = item.get('modified', '')
        if modified:
            # Adicionar como elemento personalizado
            updated = ET.SubElement(item_elem, "updated")
            updated.text = modified
    
    print("✅ Estrutura RSS criada")
    return rss

def formatar_xml(rss_element):
    """Formatar XML com indentação correta"""
    print("🎨 Formatando XML...")
    
    # Converter para string
    xml_raw = ET.tostring(rss_element, encoding='unicode', method='xml')
    
    # Adicionar declaração XML no início
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    
    # Formatar manualmente com indentação
    lines = xml_raw.split('><')
    
    formatted_lines = []
    indent_level = 0
    
    for i, line in enumerate(lines):
        if i == 0:
            line = line + '>'
        elif i == len(lines) - 1:
            line = '<' + line
        else:
            line = '<' + line + '>'
        
        # Ajustar indentação
        if line.startswith('</'):
            indent_level -= 1
        
        indent = '  ' * indent_level
        formatted_lines.append(indent + line)
        
        if not line.startswith('</') and not line.endswith('/>') and not '?>' in line:
            if not ('</' in line and line.index('</') > line.index('<')):  # Não é tag única
                indent_level += 1
        
        if line.endswith('/>'):
            indent_level -= 1
    
    xml_formatted = xml_declaration + '\n'.join(formatted_lines)
    
    # Garantir que CDATA não seja quebrado
    xml_formatted = xml_formatted.replace('&lt;![CDATA[', '<![CDATA[')
    xml_formatted = xml_formatted.replace(']]&gt;', ']]>')
    
    print("✅ XML formatado corretamente")
    return xml_formatted

def salvar_feed(xml_content):
    """Salvar feed no arquivo"""
    print(f"💾 Salvando em {FEED_FILE}...")
    
    try:
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_content)
        
        # Verificar tamanho
        file_size = os.path.getsize(FEED_FILE)
        print(f"✅ Feed salvo! Tamanho: {file_size:,} bytes")
        
        # Mostrar primeiras linhas
        print("📄 Primeiras 10 linhas do feed:")
        print("-" * 40)
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            for i in range(10):
                line = f.readline().rstrip()
                print(f"   {line}")
        print("-" * 40)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao salvar arquivo: {e}")
        return False

def main():
    """Função principal"""
    
    # 1. Buscar notícias
    noticias = buscar_noticias()
    if not noticias:
        print("❌ Não foi possível buscar notícias")
        return False
    
    # 2. Criar feed RSS
    rss_element = criar_feed_rss(noticias)
    
    # 3. Formatar XML
    xml_content = formatar_xml(rss_element)
    
    # 4. Salvar arquivo
    if not salvar_feed(xml_content):
        return False
    
    print("=" * 60)
    print("🎉 ATUALIZAÇÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 60)
    print(f"📊 Estatísticas:")
    print(f"   • Notícias processadas: {len(noticias)}")
    print(f"   • Data/hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"   • Próxima atualização: automática a cada hora")
    print("=" * 60)
    print(f"🔗 URL do feed: https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
    print(f"📱 Para testar: Abra a URL acima no navegador")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Interrompido pelo usuário")
        exit(1)
    except Exception as e:
        print(f"\n💥 ERRO INESPERADO: {e}")
        exit(1)
