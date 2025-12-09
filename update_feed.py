#!/usr/bin/env python3
"""
FEED RSS 2.0 - VERSÃO CORRIGIDA
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os
import sys
import re
import html

def criar_feed_corrigido():
    """Cria feed RSS com namespace correto"""
    
    print("=" * 70)
    print("🚀 GERANDO FEED RSS CORRIGIDO")
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
        # DECLARAR namespace content CORRETAMENTE
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
            
            # Descrição
            conteudo_raw = item.get('content', {}).get('rendered', '')
            
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
            
            # 4. ESCAPAR ]]> dividindo o CDATA (IMPORTANTE!)
            if ']]>' in conteudo_limpo:
                conteudo_limpo = conteudo_limpo.replace(']]>', ']]]]><![CDATA[>')
            
            # 5. Escapar & que não seja parte de entity
            conteudo_limpo = re.sub(r'&(?!(?:[a-zA-Z]+|#\d+);)', '&amp;', conteudo_limpo)
            
            # Adicionar item ao XML
            xml_lines.append('    <item>')
            xml_lines.append(f'      <title>{html.escape(titulo_raw)}</title>')
            xml_lines.append(f'      <link>{link}</link>')
            xml_lines.append(f'      <guid>{link}</guid>')
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
            
            # Verificar namespaces
            if 'xmlns:content=' in content:
                print("   ✅ Namespace content declarado")
            else:
                print("   ❌ Namespace content NÃO declarado")
            
            if 'xmlns:atom=' in content:
                print("   ✅ Namespace atom declarado")
            else:
                print("   ❌ Namespace atom NÃO declarado")
            
            # Verificar CDATA
            cdata_open = content.count('<![CDATA[')
            cdata_close = content.count(']]>')
            
            print(f"   ✅ CDATA abertos: {cdata_open}")
            print(f"   ✅ CDATA fechados: {cdata_close}")
            print(f"   ✅ Balanceado: {cdata_open == cdata_close}")
        
        print("\n" + "=" * 70)
        print("🎉 FEED GERADO!")
        print("=" * 70)
        print("📋 Para validar:")
        print("   https://validator.w3.org/feed/check.cgi?url=https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = criar_feed_corrigido()
    sys.exit(0 if success else 1)
