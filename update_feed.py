#!/usr/bin/env python3
"""
FEED RSS 2.0 COM IMAGEM DESTACADA
Extrai a primeira imagem do conteúdo para usar como destacada
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os
import sys
import re
import html

def criar_feed_com_imagem_destacada():
    """Cria feed RSS com extração de imagem destacada"""
    
    print("=" * 70)
    print("🚀 GERANDO FEED RSS COM IMAGEM DESTACADA")
    print("=" * 70)
    
    API_URL = "https://www.cmfor.ce.gov.br:8080/wp-json/wp/v2/posts"
    FEED_FILE = "feed.xml"
    
    try:
        # Buscar notícias
        print("📡 Buscando notícias...")
        response = requests.get(API_URL, params={
            "per_page": 10,
            "orderby": "date",
            "order": "desc"
        }, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro {response.status_code}")
            return False
        
        noticias = response.json()
        print(f"✅ {len(noticias)} notícias encontradas")
        
        # Criar XML manualmente
        print("📝 Criando feed...")
        
        xml_lines = []
        xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_lines.append('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">')
        xml_lines.append('  <channel>')
        xml_lines.append('    <title>Câmara Municipal de Fortaleza</title>')
        xml_lines.append('    <link>https://www.cmfor.ce.gov.br</link>')
        xml_lines.append('    <description>Notícias Oficiais da Câmara Municipal de Fortaleza</description>')
        xml_lines.append('    <language>pt-br</language>')
        xml_lines.append('    <generator>GitHub Actions</generator>')
        
        last_build = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        xml_lines.append(f'    <lastBuildDate>{last_build}</lastBuildDate>')
        xml_lines.append('    <ttl>60</ttl>')
        xml_lines.append('    <atom:link href="https://thecrossnow.github.io/feed-leg-ftz/feed.xml" rel="self" type="application/rss+xml" />')
        
        # Processar cada notícia
        for i, item in enumerate(noticias, 1):
            titulo_raw = item.get('title', {}).get('rendered', 'Sem título')
            print(f"   [{i}/{len(noticias)}] {titulo_raw[:60]}...")
            
            link = item.get('link', '').replace(':8080', '')
            
            # Data
            pub_date_str = ''
            pub_date = item.get('date', '')
            if pub_date:
                try:
                    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    pub_date_str = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
                except:
                    pub_date_str = pub_date
            
            # Conteúdo
            conteudo_raw = item.get('content', {}).get('rendered', '')
            
            # ====================================================
            # EXTRAIR IMAGEM DESTACADA (PRIMEIRA IMAGEM DO CONTEÚDO)
            # ====================================================
            imagem_destacada = None
            imagem_destacada_url = None
            
            # Função para extrair a primeira imagem
            def extrair_primeira_imagem(html_content):
                """Extrai a URL da primeira imagem do HTML"""
                # Padrões para buscar imagens
                padroes = [
                    r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|gif|webp))"[^>]*>',
                    r'<figure[^>]*>.*?<img[^>]+src="([^"]+)"',
                    r'src="([^"]+wp-content/uploads[^"]+\.(?:jpg|jpeg|png|gif))"',
                ]
                
                for padrao in padroes:
                    match = re.search(padrao, html_content, re.IGNORECASE | re.DOTALL)
                    if match:
                        img_url = match.group(1)
                        if img_url:
                            # Corrigir aspas curvas
                            img_url = img_url.replace('"', '"').replace('"', '"')
                            # Garantir URL completa
                            if img_url.startswith('/'):
                                img_url = f"https://www.cmfor.ce.gov.br{img_url}"
                            # Remover porta 8080
                            img_url = img_url.replace(':8080', '')
                            # Corrigir × para x
                            img_url = img_url.replace('×', 'x')
                            return img_url
                return None
            
            # Extrair imagem
            imagem_destacada_url = extrair_primeira_imagem(conteudo_raw)
            
            if imagem_destacada_url:
                print(f"      📸 Imagem destacada encontrada!")
                imagem_destacada = f'    <enclosure url="{imagem_destacada_url}" type="image/jpeg" length="50000" />'
            else:
                print(f"      ⚠️  Nenhuma imagem encontrada no conteúdo")
                # Usar imagem padrão da Câmara
                imagem_destacada_url = "https://www.cmfor.ce.gov.br/wp-content/uploads/2024/01/logo-cmfor.png"
                imagem_destacada = f'    <enclosure url="{imagem_destacada_url}" type="image/jpeg" length="50000" />'
            
            # Criar descrição simples
            texto = re.sub('<[^>]+>', '', conteudo_raw)
            texto = html.unescape(texto)
            texto = ' '.join(texto.split())
            descricao = (texto[:250] + "...") if len(texto) > 250 else texto
            descricao = html.escape(descricao)
            
            # Preparar conteúdo para CDATA
            conteudo_limpo = conteudo_raw
            
            # 1. Remover <updated> tags
            conteudo_limpo = re.sub(r'<updated>.*?</updated>', '', conteudo_limpo, flags=re.DOTALL)
            
            # 2. Remover porta 8080
            conteudo_limpo = conteudo_limpo.replace(':8080', '')
            
            # 3. Corrigir aspas curvas
            conteudo_limpo = conteudo_limpo.replace('"', '"').replace('"', '"')
            
            # 4. ESCAPAR ]]> dividindo o CDATA
            if ']]>' in conteudo_limpo:
                conteudo_limpo = conteudo_limpo.replace(']]>', ']]]]><![CDATA[>')
            
            # 5. Escapar & que não seja parte de entity
            conteudo_limpo = re.sub(r'&(?!(?:[a-zA-Z]+|#\d+);)', '&amp;', conteudo_limpo)
            
            # Adicionar item ao XML
            xml_lines.append('    <item>')
            xml_lines.append(f'      <title>{html.escape(titulo_raw)}</title>')
            xml_lines.append(f'      <link>{link}</link>')
            xml_lines.append(f'      <guid>{link}</guid>')
            
            # ADICIONAR ENCLOSURE (IMAGEM DESTACADA)
            xml_lines.append(imagem_destacada)
            
            if pub_date_str:
                xml_lines.append(f'      <pubDate>{pub_date_str}</pubDate>')
            
            xml_lines.append(f'      <description>{descricao}</description>')
            xml_lines.append(f'      <content:encoded><![CDATA[{conteudo_limpo}]]></content:encoded>')
            xml_lines.append('    </item>')
        
        xml_lines.append('  </channel>')
        xml_lines.append('</rss>')
        
        xml_final = '\n'.join(xml_lines)
        
        # Verificação final
        if ']]>' in xml_final and '<![CDATA[' not in xml_final:
            print("⚠️  Corrigindo ]]> residual...")
            xml_final = xml_final.replace(']]>', '')
        
        # Salvar
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_final)
        
        file_size = os.path.getsize(FEED_FILE)
        print(f"✅ Feed salvo: {FEED_FILE} ({file_size:,} bytes)")
        
        # Validação básica
        print("\n🔍 Verificação:")
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            
            # Contar imagens destacadas
            enclosures = content.count('<enclosure')
            imagens_conteudo = len(re.findall(r'<img[^>]+src="[^"]+"', content))
            
            print(f"   📸 Imagens destacadas (enclosure): {enclosures}/10")
            print(f"   🖼️  Imagens no conteúdo: {imagens_conteudo}")
            
            # Verificar namespaces
            if 'xmlns:content=' in content:
                print("   ✅ Namespace content declarado")
            else:
                print("   ❌ Namespace content NÃO declarado")
        
        print("\n" + "=" * 70)
        print("🎉 FEED COM IMAGEM DESTACADA GERADO!")
        print("=" * 70)
        print("⚙️  Configuração WordPress IMPORTANTE:")
        print("   No WP Automatic, configure:")
        print("   1. 'First image as featured: YES'")
        print("   2. 'Download images: YES'")
        print("   3. 'Get full content: YES'")
        print("=" * 70)
        print("📋 O WordPress usará a primeira imagem como destacada!")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = criar_feed_com_imagem_destacada()
    sys.exit(0 if success else 1)
