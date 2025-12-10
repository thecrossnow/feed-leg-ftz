#!/usr/bin/env python3
"""
FEED RSS CORRETO - COM DATAS FIXAS
Usa date_gmt da API para evitar problemas de timezone
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import os
import sys
import re
import html
import hashlib
import time
import json
from pathlib import Path

def criar_feed_corrigido():
    """Cria feed RSS com datas CORRETAS da API"""
    
    print("=" * 70)
    print("🎯 GERANDO FEED COM DATAS CORRETAS")
    print("=" * 70)
    
    API_URL = "https://www.cmfor.ce.gov.br:8080/wp-json/wp/v2/posts"
    FEED_FILE = "feed.xml"
    
    # Banco de imagens temáticas
    IMAGENS_TEMATICAS = {
        'default': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/01/logo-cmfor.png',
        'transporte': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/05/transporte-1024x683.jpg',
        'educacao': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/06/escola-parlamento-1024x683.jpg',
        'saude': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/03/saude-comunidade-1024x683.jpg',
        'seguranca': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/04/guarda-municipal-1024x683.jpg',
        'cultura': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/07/cultura-eventos-1024x683.jpg',
        'esporte': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/08/esporte-comunidade-1024x683.jpg',
        'sessao': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/10/plenario-sessao-1024x683.jpg',
        'projeto': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/11/projetos-lei-1024x683.jpg',
    }
    
    try:
        # Buscar notícias
        print("📡 Buscando notícias da API...")
        response = requests.get(API_URL, params={
            "per_page": 10,
            "orderby": "date",
            "order": "desc",
            "_embed": "true"
        }, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro {response.status_code} na API")
            return False
        
        noticias = response.json()
        print(f"✅ {len(noticias)} notícias encontradas")
        
        # Criar XML
        print("📝 Criando feed XML...")
        
        xml_lines = []
        xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_lines.append('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">')
        xml_lines.append('  <channel>')
        xml_lines.append('    <title>Câmara Municipal de Fortaleza</title>')
        xml_lines.append('    <link>https://www.cmfor.ce.gov.br</link>')
        xml_lines.append('    <description>Notícias Oficiais da Câmara Municipal de Fortaleza</description>')
        xml_lines.append('    <language>pt-br</language>')
        xml_lines.append('    <generator>GitHub Actions com Datas Corrigidas</generator>')
        
        # Timestamp atual
        last_build = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        xml_lines.append(f'    <lastBuildDate>{last_build}</lastBuildDate>')
        xml_lines.append('    <ttl>30</ttl>')
        xml_lines.append('    <atom:link href="https://thecrossnow.github.io/feed-leg-ftz/feed.xml" rel="self" type="application/rss+xml" />')
        
        # Processar cada notícia
        for i, item in enumerate(noticias, 1):
            titulo_raw = item.get('title', {}).get('rendered', 'Sem título')
            print(f"\n   [{i}/{len(noticias)}] {titulo_raw[:60]}...")
            
            link = item.get('link', '').replace(':8080', '')
            
            # 🎯 CORREÇÃO CRÍTICA: Usar date_gmt (já está em UTC)
            pub_date_gmt = item.get('date_gmt', '')
            
            # Formatar data CORRETAMENTE
            pub_date_str = ''
            if pub_date_gmt:
                try:
                    # Formato da API: "2025-12-09T20:25:28" (JÁ É GMT!)
                    # Adicionar 'Z' para indicar UTC
                    if not pub_date_gmt.endswith('Z'):
                        pub_date_gmt = pub_date_gmt + 'Z'
                    
                    # Converter
                    dt = datetime.fromisoformat(pub_date_gmt.replace('Z', '+00:00'))
                    
                    # Garantir UTC
                    dt = dt.replace(tzinfo=timezone.utc)
                    
                    # Formatar para RSS (mês em inglês)
                    formatted = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
                    
                    # Garantir mês em inglês
                    meses_traduzidos = {
                        'Dez': 'Dec', 'Jan': 'Jan', 'Fev': 'Feb', 'Mar': 'Mar',
                        'Abr': 'Apr', 'Mai': 'May', 'Jun': 'Jun', 'Jul': 'Jul',
                        'Ago': 'Aug', 'Set': 'Sep', 'Out': 'Oct', 'Nov': 'Nov'
                    }
                    
                    for pt, en in meses_traduzidos.items():
                        formatted = formatted.replace(pt, en)
                    
                    pub_date_str = formatted
                    
                    print(f"      📅 Data GMT: {pub_date_gmt}")
                    print(f"      📅 RSS Format: {pub_date_str}")
                    
                except Exception as e:
                    print(f"      ⚠️  Erro na data: {e}")
                    # Fallback: usar data atual
                    pub_date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
            else:
                # Se não tiver date_gmt, usar date e converter
                pub_date = item.get('date', '')
                if pub_date:
                    try:
                        # date está em horário local (-3h), converter para UTC
                        dt_local = datetime.fromisoformat(pub_date)
                        # Adicionar 3 horas para converter para GMT
                        dt_utc = dt_local + timedelta(hours=3)
                        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                        pub_date_str = dt_utc.strftime("%a, %d %b %Y %H:%M:%S +0000")
                        print(f"      📅 Data local (+3h): {pub_date_str}")
                    except:
                        pub_date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            # Imagem (simplificado)
            imagem_url = IMAGENS_TEMATICAS['default']
            
            # Conteúdo
            conteudo_raw = item.get('content', {}).get('rendered', '')
            
            # Descrição
            texto = re.sub('<[^>]+>', '', conteudo_raw)
            texto = html.unescape(texto)
            texto = ' '.join(texto.split())
            descricao = (texto[:250] + "...") if len(texto) > 250 else texto
            descricao = html.escape(descricao)
            
            # GUID único
            guid_hash = hashlib.md5(f"{link}{pub_date_gmt}".encode()).hexdigest()
            guid_unico = f"cmfor-{guid_hash[:12]}"
            
            xml_lines.append('    <item>')
            xml_lines.append(f'      <title>{html.escape(titulo_raw)}</title>')
            xml_lines.append(f'      <link>{link}</link>')
            xml_lines.append(f'      <guid>{guid_unico}</guid>')
            
            if pub_date_str:
                xml_lines.append(f'      <pubDate>{pub_date_str}</pubDate>')
            
            xml_lines.append(f'      <enclosure url="{imagem_url}" type="image/jpeg" length="100000" />')
            
            xml_lines.append(f'      <description>{descricao}</description>')
            xml_lines.append(f'      <content:encoded><![CDATA[<p><img src="{imagem_url}" alt="{html.escape(titulo_raw)}" /></p>{conteudo_raw}]]></content:encoded>')
            xml_lines.append('    </item>')
            
            print(f"      🔗 {link.split('/')[-2]}/...")
        
        xml_lines.append('  </channel>')
        xml_lines.append('</rss>')
        
        xml_final = '\n'.join(xml_lines)
        
        # Salvar
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_final)
        
        file_size = os.path.getsize(FEED_FILE)
        print(f"\n✅ Feed salvo: {FEED_FILE} ({file_size:,} bytes)")
        
        # Verificação
        print("\n🔍 VERIFICAÇÃO DE DATAS:")
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            dates = re.findall(r'<pubDate>(.*?)</pubDate>', content)
            for i, date in enumerate(dates, 1):
                print(f"   {i}. {date}")
        
        print("\n" + "=" * 70)
        print("🎉 FEED COM DATAS CORRIGIDAS!")
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
