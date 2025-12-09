#!/usr/bin/env python3
"""
FEED RSS 2.0 - VERSÃO COM IMAGENS GARANTIDAS
Garante imagem destacada para todas as notícias
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

def criar_feed_com_imagens_garantidas():
    """Cria feed RSS com imagens destacadas garantidas"""
    
    print("=" * 70)
    print("🚀 GERANDO FEED COM IMAGENS DESTACADAS")
    print("=" * 70)
    
    API_URL = "https://www.cmfor.ce.gov.br:8080/wp-json/wp/v2/posts"
    FEED_FILE = "feed.xml"
    
    # Banco de imagens temáticas da Câmara
    IMAGENS_TEMATICAS = {
        'default': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/01/logo-cmfor.png',
        'transporte': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/05/transporte-1024x683.jpg',
        'educacao': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/06/escola-parlamento-1024x683.jpg',
        'saude': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/03/saude-comunidade-1024x683.jpg',
        'seguranca': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/04/guarda-municipal-1024x683.jpg',
        'cultura': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/07/cultura-eventos-1024x683.jpg',
        'esporte': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/08/esporte-comunidade-1024x683.jpg',
        'meioambiente': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/09/sustentabilidade-1024x683.jpg',
        'sessao': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/10/plenario-sessao-1024x683.jpg',
        'projeto': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/11/projetos-lei-1024x683.jpg',
    }
    
    try:
        # Buscar notícias
        print("📡 Buscando notícias...")
        response = requests.get(API_URL, params={
            "per_page": 10,
            "orderby": "date",
            "order": "desc",
            "_embed": "true"  # Para tentar pegar featured media
        }, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro {response.status_code}")
            return False
        
        noticias = response.json()
        print(f"✅ {len(noticias)} notícias encontradas")
        
        # Criar XML manualmente
        print("📝 Criando feed com imagens...")
        
        xml_lines = []
        xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_lines.append('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">')
        xml_lines.append('  <channel>')
        xml_lines.append('    <title>Câmara Municipal de Fortaleza</title>')
        xml_lines.append('    <link>https://www.cmfor.ce.gov.br</link>')
        xml_lines.append('    <description>Notícias Oficiais da Câmara Municipal de Fortaleza</description>')
        xml_lines.append('    <language>pt-br</language>')
        xml_lines.append('    <generator>GitHub Actions com Imagens</generator>')
        
        timestamp = int(time.time())
        last_build = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        xml_lines.append(f'    <lastBuildDate>{last_build}</lastBuildDate>')
        xml_lines.append('    <ttl>30</ttl>')
        xml_lines.append('    <atom:link href="https://thecrossnow.github.io/feed-leg-ftz/feed.xml" rel="self" type="application/rss+xml" />')
        
        # Processar cada notícia
        for i, item in enumerate(noticias, 1):
            titulo_raw = item.get('title', {}).get('rendered', 'Sem título')
            print(f"\n   [{i}/{len(noticias)}] {titulo_raw[:70]}...")
            
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
            # 1. TENTAR PEGAR IMAGEM DESTACADA DA API
            # ====================================================
            imagem_url = None
            featured_media = item.get('featured_media', 0)
            
            if featured_media and '_embedded' in item and 'wp:featuredmedia' in item['_embedded']:
                try:
                    media_data = item['_embedded']['wp:featuredmedia'][0]
                    if 'source_url' in media_data:
                        imagem_url = media_data['source_url']
                        print(f"      ✅ Imagem destacada da API")
                except:
                    pass
            
            # ====================================================
            # 2. SE NÃO TIVER, EXTRAIR DO CONTEÚDO
            # ====================================================
            if not imagem_url:
                def extrair_imagem_do_conteudo(html_content):
                    """Extrai todas as imagens do conteúdo"""
                    # Corrigir aspas primeiro
                    html_content = html_content.replace('"', '"').replace('"', '"')
                    
                    # Buscar todas as imagens
                    padroes = [
                        r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|gif|webp))"[^>]*>',
                        r'<figure[^>]*>.*?<img[^>]+src="([^"]+)"',
                        r'src="([^"]+wp-content/uploads[^"]+\.(?:jpg|jpeg|png))"',
                    ]
                    
                    imagens = []
                    for padrao in padroes:
                        matches = re.findall(padrao, html_content, re.IGNORECASE | re.DOTALL)
                        for img in matches:
                            if img and 'logo' not in img.lower() and 'icon' not in img.lower():
                                if img.startswith('/'):
                                    img = f"https://www.cmfor.ce.gov.br{img}"
                                img = img.replace(':8080', '').replace('×', 'x')
                                imagens.append(img)
                    
                    return imagens
                
                todas_imagens = extrair_imagem_do_conteudo(conteudo_raw)
                if todas_imagens:
                    imagem_url = todas_imagens[0]  # Pega a primeira imagem
                    print(f"      ✅ {len(todas_imagens)} imagem(ns) no conteúdo")
            
            # ====================================================
            # 3. SE AINDA NÃO TIVER, USAR IMAGEM TEMÁTICA
            # ====================================================
            if not imagem_url:
                titulo_lower = titulo_raw.lower()
                conteudo_lower = conteudo_raw.lower()
                
                # Determinar tema da notícia
                if any(p in titulo_lower or p in conteudo_lower for p in ['transporte', 'uber', '99', 'motocicleta', 'ônibus']):
                    imagem_url = IMAGENS_TEMATICAS['transporte']
                elif any(p in titulo_lower or p in conteudo_lower for p in ['educação', 'escola', 'professor', 'aluno']):
                    imagem_url = IMAGENS_TEMATICAS['educacao']
                elif any(p in titulo_lower or p in conteudo_lower for p in ['saúde', 'hospital', 'médico', 'vacina']):
                    imagem_url = IMAGENS_TEMATICAS['saude']
                elif any(p in titulo_lower or p in conteudo_lower for p in ['sessão', 'plenário', 'vereador', 'votação']):
                    imagem_url = IMAGENS_TEMATICAS['sessao']
                elif any(p in titulo_lower or p in conteudo_lower for p in ['projeto', 'lei', 'regulamenta', 'aprova']):
                    imagem_url = IMAGENS_TEMATICAS['projeto']
                elif any(p in titulo_lower or p in conteudo_lower for p in ['cultura', 'evento', 'música', 'teatro']):
                    imagem_url = IMAGENS_TEMATICAS['cultura']
                elif any(p in titulo_lower or p in conteudo_lower for p in ['esporte', 'arena', 'atleta', 'jogo']):
                    imagem_url = IMAGENS_TEMATICAS['esporte']
                else:
                    imagem_url = IMAGENS_TEMATICAS['default']
                
                print(f"      🎨 Usando imagem temática")
            
            # ====================================================
            # 4. PREPARAR CONTEÚDO
            # ====================================================
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
            
            # ====================================================
            # 5. ADICIONAR AO XML COM MÚLTIPLOS FORMATOS DE IMAGEM
            # ====================================================
            # GUID único
            guid_hash = hashlib.md5(f"{link}{timestamp}".encode()).hexdigest()
            guid_unico = f"cmfor-img-{guid_hash}"
            
            xml_lines.append('    <item>')
            xml_lines.append(f'      <title>{html.escape(titulo_raw)}</title>')
            xml_lines.append(f'      <link>{link}</link>')
            xml_lines.append(f'      <guid>{guid_unico}</guid>')
            
            # FORMATO 1: enclosure (WordPress reconhece como imagem destacada)
            xml_lines.append(f'      <enclosure url="{imagem_url}" type="image/jpeg" length="100000" />')
            
            # FORMATO 2: media:content (padrão Media RSS)
            xml_lines.append(f'      <media:content url="{imagem_url}" medium="image" type="image/jpeg">')
            xml_lines.append(f'        <media:title type="plain">{html.escape(titulo_raw[:100])}</media:title>')
            xml_lines.append(f'        <media:description type="plain">{descricao[:200]}</media:description>')
            xml_lines.append(f'        <media:thumbnail url="{imagem_url}" />')
            xml_lines.append('      </media:content>')
            
            # FORMATO 3: Inserir imagem no início do conteúdo (para garantia)
            conteudo_com_imagem_no_inicio = f'<p><img src="{imagem_url}" alt="{html.escape(titulo_raw)}" style="max-width: 100%; height: auto; margin-bottom: 20px;" /></p>\n{conteudo_limpo}'
            
            if pub_date_str:
                xml_lines.append(f'      <pubDate>{pub_date_str}</pubDate>')
            
            xml_lines.append(f'      <description>{descricao}</description>')
            xml_lines.append(f'      <content:encoded><![CDATA[{conteudo_com_imagem_no_inicio}]]></content:encoded>')
            xml_lines.append('    </item>')
            
            print(f"      📸 Imagem: {imagem_url.split('/')[-1][:40]}...")
        
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
        print(f"\n✅ Feed salvo: {FEED_FILE} ({file_size:,} bytes)")
        
        # Verificação
        print("\n🔍 VERIFICAÇÃO DE IMAGENS:")
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            
            print(f"   📸 Enclosures: {content.count('<enclosure')}/10")
            print(f"   🖼️  Media content: {content.count('<media:content')}/10")
            print(f"   🖼️  Imagens no conteúdo: {len(re.findall(r'<img[^>]+src=', content))}")
            
            # Verificar se TODAS as notícias têm enclosure
            lines = content.split('\n')
            items = [i for i, line in enumerate(lines) if '<item>' in line]
            
            for idx, item_line in enumerate(items, 1):
                # Verificar se este item tem enclosure
                item_content = '\n'.join(lines[item_line:item_line+30])
                has_enclosure = '<enclosure' in item_content
                has_media = '<media:content' in item_content
                
                status = "✅" if has_enclosure and has_media else "❌"
                print(f"   {status} Notícia {idx}: {'Tem imagem' if has_enclosure else 'SEM IMAGEM'}")
        
        print("\n" + "=" * 70)
        print("🎉 FEED COM IMAGENS GARANTIDAS!")
        print("=" * 70)
        print("⚙️  Configuração WP Automatic OBRIGATÓRIA:")
        print("   1. First image as featured: ✅ YES")
        print("   2. Download images: ✅ YES")
        print("   3. Insert images into post: ✅ YES")
        print("   4. Set first image as featured: ✅ YES")
        print("   5. Get full content: ✅ YES")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = criar_feed_com_imagens_garantidas()
    sys.exit(0 if success else 1)
