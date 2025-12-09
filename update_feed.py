#!/usr/bin/env python3
"""
Script para atualizar feed RSS - VERSÃO CORRIGIDA PARA RSS 2.0 VÁLIDO
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os
import sys
import html
import re

def limpar_conteudo_wordpress(conteudo):
    """
    Limpa o conteúdo para compatibilidade com WordPress
    """
    # Remover scripts e estyles
    conteudo = re.sub(r'<script[^>]*>.*?</script>', '', conteudo, flags=re.DOTALL)
    conteudo = re.sub(r'<style[^>]*>.*?</style>', '', conteudo, flags=re.DOTALL)
    
    # Remover elementos não suportados no RSS
    conteudo = re.sub(r'<updated>.*?</updated>', '', conteudo)  # REMOVER <updated>
    conteudo = re.sub(r'<dc:creator>.*?</dc:creator>', '', conteudo)
    
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
    
    # Channel
    channel = ET.SubElement(rss, "channel")
    
    # Metadados do canal
    ET.SubElement(channel, "title").text = "Câmara Municipal de Fortaleza"
    ET.SubElement(channel, "link").text = "https://www.cmfor.ce.gov.br"
    ET.SubElement(channel, "description").text = "Notícias Oficiais da Câmara Municipal de Fortaleza"
    ET.SubElement(channel, "language").text = "pt-br"
    ET.SubElement(channel, "generator").text = "GitHub Actions"
    
    # Data de build (correta para RSS 2.0)
    last_build = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    ET.SubElement(channel, "lastBuildDate").text = last_build
    
    # Atom link (self)
    atom_link = ET.SubElement(channel, "atom:link")
    atom_link.set("href", "https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")
    
    # TTL (Time To Live) - 60 minutos
    ET.SubElement(channel, "ttl").text = "60"
    
    # Processar cada notícia
    for i, item in enumerate(noticias, 1):
        titulo_raw = item.get('title', {}).get('rendered', 'Sem título')
        print(f"   [{i}/{len(noticias)}] {titulo_raw[:50]}...")
        
        # Elemento item
        item_elem = ET.SubElement(channel, "item")
        
        # Título (escapar HTML)
        titulo = html.escape(titulo_raw)
        ET.SubElement(item_elem, "title").text = titulo
        
        # Link (remover porta 8080 se existir)
        link = item.get('link', '').replace(':8080', '')
        ET.SubElement(item_elem, "link").text = link
        
        # GUID (usar link como GUID permanente)
        guid = ET.SubElement(item_elem, "guid")
        guid.text = link
        guid.set("isPermaLink", "true")
        
        # Data de publicação (formato correto RSS)
        pub_date = item.get('date', '')
        if pub_date:
            try:
                dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                ET.SubElement(item_elem, "pubDate").text = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except:
                ET.SubElement(item_elem, "pubDate").text = pub_date
        
        # Conteúdo bruto da API
        conteudo_raw = item.get('content', {}).get('rendered', '')
        
        # Limpar conteúdo
        conteudo_limpo = limpar_conteudo_wordpress(conteudo_raw)
        
        # Criar description (resumo - DEVE vir PRIMEIRO)
        texto_simples = re.sub('<[^>]+>', '', conteudo_raw)
        descricao = (texto_simples[:250] + "...") if len(texto_simples) > 250 else texto_simples
        descricao = html.escape(descricao)
        
        # Elemento description (OBRIGATÓRIO no RSS 2.0)
        desc_elem = ET.SubElement(item_elem, "description")
        desc_elem.text = descricao
        
        # Elemento content:encoded (conteúdo completo)
        content_elem = ET.SubElement(item_elem, "content:encoded")
        content_elem.text = f"<![CDATA[{conteudo_limpo}]]>"
        
        # Autor (se disponível)
        author = item.get('_embedded', {}).get('author', [{}])[0].get('name', '')
        if author:
            ET.SubElement(item_elem, "author").text = author
        
        # Categorias (se disponíveis)
        categories = item.get('_embedded', {}).get('wp:term', [[]])[0]
        for category in categories[:3]:  # Máximo 3 categorias
            cat_name = category.get('name', '')
            if cat_name:
                cat_elem = ET.SubElement(item_elem, "category")
                cat_elem.text = cat_name
    
    return rss

def formatar_xml_com_cdata(xml_tree):
    """
    Formata XML mantendo CDATA corretamente
    """
    xml_str = ET.tostring(xml_tree, encoding='unicode', method='xml')
    
    # Declaração XML
    xml_final = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
    
    # Corrigir CDATA (o ET não suporta nativamente)
    xml_final = xml_final.replace('&lt;![CDATA[', '<![CDATA[')
    xml_final = xml_final.replace(']]&gt;', ']]>')
    
    # Formatar com indentação
    import xml.dom.minidom
    
    try:
        # Parse o XML já com CDATA corrigido
        dom = xml.dom.minidom.parseString(xml_final)
        xml_final = dom.toprettyxml(indent="  ")
        
        # Remover a primeira linha (já temos declaração)
        lines = xml_final.split('\n')
        xml_final = '\n'.join(lines[1:])  # Remove linha duplicada
        
        # Remover linhas vazias excessivas
        lines = [line for line in xml_final.split('\n') if line.strip()]
        xml_final = '\n'.join(lines)
    except:
        # Fallback simples
        pass
    
    return xml_final

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
            "_embed": "true"  # Para pegar autor e categorias
        }
        
        response = requests.get(API_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro na API: {response.status_code}")
            print(f"   Resposta: {response.text[:200]}")
            sys.exit(1)
        
        noticias = response.json()
        print(f"✅ {len(noticias)} notícias encontradas")
        
        # 2. Criar feed RSS válido
        print("📝 Criando feed RSS 2.0 válido...")
        rss = criar_feed_rss_valido(noticias)
        
        # 3. Formatar e salvar XML
        print("💾 Formatando e salvando XML...")
        xml_final = formatar_xml_com_cdata(rss)
        
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_final)
        
        # 4. Verificar arquivo
        file_size = os.path.getsize(FEED_FILE)
        print(f"✅ Feed salvo: {FEED_FILE} ({file_size:,} bytes)")
        
        # 5. Validar estrutura básica
        print("\n🔍 Validando estrutura básica...")
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            
            # Verificar elementos obrigatórios
            checks = {
                "<rss version=\"2.0\">": content.count('<rss version="2.0">') > 0,
                "<channel>": content.count('<channel>') > 0,
                "<title>": content.count('<title>') >= 2,
                "<item>": content.count('<item>') == len(noticias),
                "<description>": content.count('<description>') >= len(noticias) + 1,
            }
            
            for check, result in checks.items():
                status = "✅" if result else "❌"
                print(f"   {status} {check}")
        
        print("\n📄 Preview do feed:")
        print("-" * 50)
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[:20]
            for i, line in enumerate(lines[:20], 1):
                if line.strip():
                    clean_line = line.rstrip().replace('\t', '  ')
                    print(f"   {clean_line[:80]}{'...' if len(clean_line) > 80 else ''}")
        print("-" * 50)
        
        print("\n" + "=" * 60)
        print("🎉 FEED RSS 2.0 VÁLIDO GERADO!")
        print("=" * 60)
        print(f"📊 Estatísticas:")
        print(f"   • Notícias processadas: {len(noticias)}")
        print(f"   • Tamanho do arquivo: {file_size:,} bytes")
        print(f"   • Data/hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("=" * 60)
        print(f"🔗 URL para validação:")
        print(f"   https://validator.w3.org/feed/check.cgi?url=https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
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
