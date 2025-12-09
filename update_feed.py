#!/usr/bin/env python3
"""
FEED RSS 2.0 - VERSÃO COM GUID ÚNICO
Força WP Automatic a ver como notícias novas
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os
import sys
import re
import html
import hashlib
import time

def criar_feed_com_guid_unico():
    """Cria feed RSS com GUID único para forçar novas importações"""
    
    print("=" * 70)
    print("🚀 GERANDO FEED COM GUID ÚNICO")
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
        
        # ADICIONAR TIMESTAMP para forçar cache novo
        timestamp = int(time.time())
        xml_lines.append(f'    <!-- Feed gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")} -->')
        xml_lines.append(f'    <!-- Timestamp: {timestamp} -->')
        
        last_build = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        xml_lines.append(f'    <lastBuildDate>{last_build}</lastBuildDate>')
        xml_lines.append('    <ttl>5</ttl>')  # TTL curto para atualizações frequentes
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
            # GUID ÚNICO - IMPEDE WP AUTOMATIC DE IGNORAR
            # ====================================================
            # Criar GUID único baseado em título + data + timestamp
            guid_base = f"{titulo_raw}{pub_date}{timestamp}"
            guid_hash = hashlib.md5(guid_base.encode()).hexdigest()
            guid_unico = f"cmfor-{guid_hash}"
            
            print(f"      🔑 GUID único: {guid_unico[:20]}...")
            
            # Extrair primeira imagem
            imagem_destacada_url = None
            def extrair_primeira_imagem(html_content):
                padroes = [
                    r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|gif|webp))"[^>]*>',
                    r'<figure[^>]*>.*?<img[^>]+src="([^"]+)"',
                ]
                
                for padrao in padroes:
                    match = re.search(padrao, html_content, re.IGNORECASE | re.DOTALL)
                    if match:
                        img_url = match.group(1)
                        if img_url:
                            img_url = img_url.replace('"', '"').replace('"', '"')
                            if img_url.startswith('/'):
                                img_url = f"https://www.cmfor.ce.gov.br{img_url}"
                            img_url = img_url.replace(':8080', '').replace('×', 'x')
                            return img_url
                return None
            
            imagem_destacada_url = extrair_primeira_imagem(conteudo_raw)
            
            if imagem_destacada_url:
                print(f"      📸 Imagem encontrada")
                imagem_tag = f'    <enclosure url="{imagem_destacada_url}" type="image/jpeg" length="50000" />'
            else:
                print(f"      ⚠️  Usando imagem padrão")
                imagem_destacada_url = "https://www.cmfor.ce.gov.br/wp-content/uploads/2024/01/logo-cmfor.png"
                imagem_tag = f'    <enclosure url="{imagem_destacada_url}" type="image/jpeg" length="50000" />'
            
            # Criar descrição
            texto = re.sub('<[^>]+>', '', conteudo_raw)
            texto = html.unescape(texto)
            texto = ' '.join(texto.split())
            descricao = (texto[:250] + "...") if len(texto) > 250 else texto
            descricao = html.escape(descricao)
            
            # Preparar conteúdo para CDATA
            conteudo_limpo = conteudo_raw
            conteudo_limpo = re.sub(r'<updated>.*?</updated>', '', conteudo_limpo, flags=re.DOTALL)
            conteudo_limpo = conteudo_limpo.replace(':8080', '')
            conteudo_limpo = conteudo_limpo.replace('"', '"').replace('"', '"')
            
            if ']]>' in conteudo_limpo:
                conteudo_limpo = conteudo_limpo.replace(']]>', ']]]]><![CDATA[>')
            
            conteudo_limpo = re.sub(r'&(?!(?:[a-zA-Z]+|#\d+);)', '&amp;', conteudo_limpo)
            
            # Adicionar item ao XML
            xml_lines.append('    <item>')
            xml_lines.append(f'      <title>{html.escape(titulo_raw)}</title>')
            xml_lines.append(f'      <link>{link}</link>')
            
            # GUID ÚNICO (não o link)
            xml_lines.append(f'      <guid>{guid_unico}</guid>')
            
            # Enclosure para imagem destacada
            xml_lines.append(imagem_tag)
            
            if pub_date_str:
                xml_lines.append(f'      <pubDate>{pub_date_str}</pubDate>')
            
            xml_lines.append(f'      <description>{descricao}</description>')
            xml_lines.append(f'      <content:encoded><![CDATA[{conteudo_limpo}]]></content:encoded>')
            xml_lines.append('    </item>')
        
        xml_lines.append('  </channel>')
        xml_lines.append('</rss>')
        
        xml_final = '\n'.join(xml_lines)
        
        # Limpar ]]> residual
        if ']]>' in xml_final and '<![CDATA[' not in xml_final:
            xml_final = xml_final.replace(']]>', '')
        
        # Salvar
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_final)
        
        file_size = os.path.getsize(FEED_FILE)
        print(f"✅ Feed salvo: {FEED_FILE} ({file_size:,} bytes)")
        
        # Verificação
        print("\n🔍 Verificação:")
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            guids_unicos = len(re.findall(r'<guid>cmfor-[a-f0-9]{32}</guid>', content))
            print(f"   🔑 GUIDs únicos: {guids_unicos}/10")
            print(f"   📸 Enclosures: {content.count('<enclosure')}/10")
        
        print("\n" + "=" * 70)
        print("🎉 FEED COM GUID ÚNICO GERADO!")
        print("=" * 70)
        print("🔄 AGORA VAI FUNCIONAR!")
        print("O WP Automatic verá como notícias NOVAS porque:")
        print("1. GUIDs são diferentes a cada execução")
        print("2. TTL curto (5 minutos)")
        print("3. Timestamp no feed")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = criar_feed_com_guid_unico()
    sys.exit(0 if success else 1)
