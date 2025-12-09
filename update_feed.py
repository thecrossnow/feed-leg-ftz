#!/usr/bin/env python3
"""
Script para atualizar feed RSS - VERSÃO FINAL FUNCIONAL
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os

print("=" * 60)
print("🔄 ATUALIZAÇÃO DO FEED RSS - VERSÃO CORRIGIDA")
print("=" * 60)

# Configurações
API_URL = "https://www.cmfor.ce.gov.br:8080/wp-json/wp/v2/posts"
ITEMS_TO_FETCH = 10
FEED_FILE = "feed.xml"

def corrigir_link(link_original):
    """Corrigir links removendo porta 8080"""
    if not link_original:
        return ""
    
    # SIMPLES: apenas remover :8080
    link = link_original.replace(':8080', '')
    return link

def processar_conteudo(conteudo_html):
    """Processar conteúdo HTML - VERSÃO SIMPLIFICADA E CORRETA"""
    if not conteudo_html:
        return ""
    
    # A API já retorna HTML escapado corretamente
    # Exemplo: &lt;p class=&quot;has-medium-font-size&quot;&gt;
    # Isso já está PRONTO para XML!
    
    # ÚNICAS correções necessárias:
    
    # 1. Remover porta :8080 das URLs de imagem
    conteudo_html = conteudo_html.replace(':8080', '')
    
    # 2. Escapar fim de CDATA (importante!)
    conteudo_html = conteudo_html.replace(']]>', ']]&gt;')
    
    # 3. Remover caracteres de controle inválidos
    # (opcional, mas recomendado)
    import re
    conteudo_html = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', conteudo_html)
    
    return conteudo_html

def criar_feed_rss(noticias):
    """Criar feed RSS"""
    print("📝 Criando estrutura RSS...")
    
    # Criar elemento raiz
    rss = ET.Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
    
    # Criar channel
    channel = ET.SubElement(rss, "channel")
    
    # Metadados
    ET.SubElement(channel, "title").text = "Câmara Municipal de Fortaleza"
    ET.SubElement(channel, "link").text = "https://www.cmfor.ce.gov.br"
    ET.SubElement(channel, "description").text = "Notícias Oficiais da Câmara Municipal de Fortaleza"
    ET.SubElement(channel, "language").text = "pt-br"
    ET.SubElement(channel, "generator").text = "Feed Generator v2.0"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    
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
        
        # Título (escapar apenas & para XML)
        titulo = titulo_raw.replace('&', '&amp;')
        ET.SubElement(item_elem, "title").text = titulo
        
        # Link (corrigir)
        link_original = item.get('link', '')
        link_corrigido = corrigir_link(link_original)
        ET.SubElement(item_elem, "link").text = link_corrigido
        
        # GUID
        guid = ET.SubElement(item_elem, "guid")
        guid.text = link_corrigido
        guid.set("isPermaLink", "true")
        
        # Conteúdo completo (content:encoded)
        conteudo_raw = item.get('content', {}).get('rendered', '')
        conteudo_processado = processar_conteudo(conteudo_raw)
        
        content_elem = ET.SubElement(item_elem, "content:encoded")
        content_elem.text = f"<![CDATA[{conteudo_processado}]]>"
        
        # Descrição curta (description) - opcional
        if conteudo_raw:
            # Pegar primeiro parágrafo como descrição
            import re
            primeiro_paragrafo = re.search(r'&lt;p.*?&gt;(.*?)&lt;/p&gt;', conteudo_raw)
            if primeiro_paragrafo:
                descricao = primeiro_paragrafo.group(1)[:200] + "..."
            else:
                descricao = conteudo_raw[:200] + "..."
            
            desc_elem = ET.SubElement(item_elem, "description")
            desc_elem.text = f"<![CDATA[{descricao}]]>"
        
        # Data
        pub_date = item.get('date', '')
        if pub_date:
            try:
                # Converter formato ISO para RFC 822
                dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                ET.SubElement(item_elem, "pubDate").text = dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
            except:
                ET.SubElement(item_elem, "pubDate").text = pub_date
        
        # Data de modificação
        modified = item.get('modified', '')
        if modified:
            updated = ET.SubElement(item_elem, "updated")
            updated.text = modified
    
    return rss

def salvar_xml(rss_element):
    """Salvar XML formatado"""
    print(f"💾 Salvando em {FEED_FILE}...")
    
    # Converter para string XML
    from xml.dom import minidom
    
    rough_string = ET.tostring(rss_element, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    
    # Formatar bonito
    xml_pretty = reparsed.toprettyxml(indent="  ", encoding='utf-8')
    
    # Decodificar e corrigir CDATA
    xml_str = xml_pretty.decode('utf-8')
    xml_str = xml_str.replace('&lt;![CDATA[', '<![CDATA[')
    xml_str = xml_str.replace(']]&gt;', ']]>')
    
    # Salvar
    with open(FEED_FILE, "w", encoding="utf-8") as f:
        f.write(xml_str)
    
    print(f"✅ Feed salvo! Tamanho: {len(xml_str):,} bytes")
    return True

def main():
    """Função principal"""
    
    print("📡 Buscando notícias da API...")
    
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
        
        # Criar feed
        rss = criar_feed_rss(noticias)
        
        # Salvar
        if salvar_xml(rss):
            print("\n" + "="*60)
            print("🎉 FEED GERADO COM SUCESSO!")
            print("="*60)
            
            # Mostrar exemplo
            print("\n📄 EXEMPLO DO PRIMEIRO ITEM:")
            print("-"*50)
            with open(FEED_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
                # Encontrar primeiro <content:encoded>
                in_content = False
                content_lines = []
                for line in lines:
                    if '<content:encoded>' in line:
                        in_content = True
                    if in_content:
                        content_lines.append(line.rstrip())
                        if ']]>' in line:
                            break
                
                # Mostrar apenas algumas linhas do conteúdo
                for line in content_lines[:10]:
                    if len(line) > 100:
                        print(f"   {line[:100]}...")
                    else:
                        print(f"   {line}")
            
            print("-"*50)
            print("🔗 URL do feed: https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
            print("="*60)
            
            return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
