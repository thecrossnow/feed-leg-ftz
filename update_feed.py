#!/usr/bin/env python3
"""
FEED RSS 2.0 - VERSÃO COM IMAGENS E CONTROLE DE TIMESTAMP
Garante imagem destacada E notícias novas detectadas
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

# Arquivo para armazenar última data processada
STATE_FILE = "last_processed.json"

def carregar_ultima_data():
    """Carrega a última data processada do arquivo"""
    if Path(STATE_FILE).exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Converter string para datetime
                last_date = datetime.fromisoformat(data['last_date'])
                return last_date
        except:
            pass
    # Retorna data de 24 horas atrás se não existir arquivo
    return datetime.now(timezone.utc) - timedelta(hours=24)

def salvar_ultima_data(data):
    """Salva a última data processada"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_date": data.isoformat()}, f)

def criar_feed_com_imagens_garantidas():
    """Cria feed RSS com imagens destacadas garantidas"""
    
    print("=" * 70)
    print("🚀 GERANDO FEED COM IMAGENS DESTACADAS E CONTROLE DE TIMESTAMP")
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
        'meioambiente': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/09/sustentabilidade-1024x683.jpg',
        'sessao': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/10/plenario-sessao-1024x683.jpg',
        'projeto': 'https://www.cmfor.ce.gov.br/wp-content/uploads/2024/11/projetos-lei-1024x683.jpg',
    }
    
    try:
        # Carregar última data processada
        ultima_data = carregar_ultima_data()
        print(f"📅 Última data processada: {ultima_data.isoformat()}")
        
        # Buscar mais notícias para garantir novidades
        print("📡 Buscando notícias...")
        
        # Formatar data para API (remover microsegundos se houver)
        after_date = ultima_data.replace(microsecond=0).isoformat()
        
        response = requests.get(API_URL, params={
            "per_page": 20,  # Buscar mais para ter variedade
            "orderby": "date",
            "order": "desc",
            "_embed": "true",
            "after": after_date  # Filtrar apenas as mais novas
        }, timeout=30)
        
        if response.status_code != 200:
            print(f"⚠️  Erro {response.status_code}, buscando todas...")
            # Se falhar, busca todas
            response = requests.get(API_URL, params={
                "per_page": 15,
                "orderby": "date",
                "order": "desc",
                "_embed": "true"
            }, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro {response.status_code} na API")
            return False
        
        noticias = response.json()
        print(f"✅ {len(noticias)} notícias encontradas")
        
        # Se não houver notícias novas, adiciona algumas antigas para manter o feed
        if len(noticias) < 3:
            print("⚠️  Poucas notícias novas, adicionando algumas antigas...")
            response_old = requests.get(API_URL, params={
                "per_page": 10,
                "orderby": "date",
                "order": "desc",
                "_embedded": "true",
                "offset": 5  # Pula as 5 mais recentes
            }, timeout=30)
            
            if response_old.status_code == 200:
                noticias_antigas = response_old.json()
                # Adiciona apenas algumas para completar
                noticias.extend(noticias_antigas[:3])
                print(f"➕ Adicionadas {len(noticias_antigas[:3])} notícias antigas")
        
        # Ordenar por data (mais nova primeiro) - CRÍTICO!
        noticias_ordenadas = sorted(noticias, 
                                   key=lambda x: datetime.fromisoformat(
                                       x.get('date', '').replace('Z', '+00:00')
                                   ), 
                                   reverse=True)
        
        # Manter apenas 10-12 para o feed
        noticias_feed = noticias_ordenadas[:12]
        
        # Atualizar última data processada
        if noticias_feed:
            try:
                data_mais_recente = datetime.fromisoformat(
                    noticias_feed[0].get('date', '').replace('Z', '+00:00')
                )
                salvar_ultima_data(data_mais_recente)
                print(f"📅 Nova última data: {data_mais_recente.isoformat()}")
            except Exception as e:
                print(f"⚠️  Erro ao salvar data: {e}")
                salvar_ultima_data(datetime.now(timezone.utc))
        
        # Criar XML
        print("📝 Criando feed com imagens...")
        
        xml_lines = []
        xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_lines.append('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">')
        xml_lines.append('  <channel>')
        xml_lines.append('    <title>Câmara Municipal de Fortaleza</title>')
        xml_lines.append('    <link>https://www.cmfor.ce.gov.br</link>')
        xml_lines.append('    <description>Notícias Oficiais da Câmara Municipal de Fortaleza</description>')
        xml_lines.append('    <language>pt-br</language>')
        xml_lines.append('    <generator>GitHub Actions - Feed Dinâmico</generator>')
        
        # Adicionar timestamp único no feed
        timestamp = int(time.time())
        last_build = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        xml_lines.append(f'    <lastBuildDate>{last_build}</lastBuildDate>')
        xml_lines.append(f'    <pubDate>{last_build}</pubDate>')
        xml_lines.append(f'    <docs>https://thecrossnow.github.io/feed-leg-ftz/feed.xml?v={timestamp}</docs>')
        xml_lines.append('    <ttl>15</ttl>')  # TTL mais curto
        xml_lines.append(f'    <atom:link href="https://thecrossnow.github.io/feed-leg-ftz/feed.xml?v={timestamp}" rel="self" type="application/rss+xml" />')
        
        # Processar cada notícia
        for i, item in enumerate(noticias_feed, 1):
            titulo_raw = item.get('title', {}).get('rendered', 'Sem título')
            print(f"\n   [{i}/{len(noticias_feed)}] {titulo_raw[:70]}...")
            
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
            
            # =============== EXTRAÇÃO DE IMAGENS ===============
            imagem_url = None
            featured_media = item.get('featured_media', 0)
            
            # 1. TENTAR IMAGEM DESTACADA DA API
            if featured_media and '_embedded' in item and 'wp:featuredmedia' in item['_embedded']:
                try:
                    media_data = item['_embedded']['wp:featuredmedia'][0]
                    if 'source_url' in media_data:
                        imagem_url = media_data['source_url']
                        print(f"      ✅ Imagem destacada da API")
                except:
                    pass
            
            # 2. SE NÃO TIVER, EXTRAIR DO CONTEÚDO
            if not imagem_url:
                conteudo_raw = item.get('content', {}).get('rendered', '')
                
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
                    imagem_url = todas_imagens[0]
                    print(f"      ✅ {len(todas_imagens)} imagem(ns) no conteúdo")
            
            # 3. SE AINDA NÃO TIVER, USAR IMAGEM TEMÁTICA
            if not imagem_url:
                titulo_lower = titulo_raw.lower()
                
                # Determinar tema da notícia
                if any(p in titulo_lower for p in ['transporte', 'uber', '99', 'motocicleta', 'ônibus']):
                    imagem_url = IMAGENS_TEMATICAS['transporte']
                elif any(p in titulo_lower for p in ['educação', 'escola', 'professor', 'aluno']):
                    imagem_url = IMAGENS_TEMATICAS['educacao']
                elif any(p in titulo_lower for p in ['saúde', 'hospital', 'médico', 'vacina']):
                    imagem_url = IMAGENS_TEMATICAS['saude']
                elif any(p in titulo_lower for p in ['sessão', 'plenário', 'vereador', 'votação']):
                    imagem_url = IMAGENS_TEMATICAS['sessao']
                elif any(p in titulo_lower for p in ['projeto', 'lei', 'regulamenta', 'aprova']):
                    imagem_url = IMAGENS_TEMATICAS['projeto']
                elif any(p in titulo_lower for p in ['cultura', 'evento', 'música', 'teatro']):
                    imagem_url = IMAGENS_TEMATICAS['cultura']
                elif any(p in titulo_lower for p in ['esporte', 'arena', 'atleta', 'jogo']):
                    imagem_url = IMAGENS_TEMATICAS['esporte']
                else:
                    imagem_url = IMAGENS_TEMATICAS['default']
                
                print(f"      🎨 Usando imagem temática")
            # ====================================================
            
            # Conteúdo
            conteudo_raw = item.get('content', {}).get('rendered', '')
            
            # Criar descrição
            texto = re.sub('<[^>]+>', '', conteudo_raw)
            texto = html.unescape(texto)
            texto = ' '.join(texto.split())
            descricao = (texto[:250] + "...") if len(texto) > 250 else texto
            descricao = html.escape(descricao)
            
            # Preparar conteúdo
            conteudo_limpo = conteudo_raw.replace(':8080', '')
            conteudo_limpo = conteudo_limpo.replace('"', '"').replace('"', '"')
            
            if ']]>' in conteudo_limpo:
                conteudo_limpo = conteudo_limpo.replace(']]>', ']]]]><![CDATA[>')
            
            # GUID único baseado no link + timestamp do feed
            guid_hash = hashlib.md5(f"{link}{timestamp}".encode()).hexdigest()
            guid_unico = f"cmfor-{guid_hash}"
            
            xml_lines.append('    <item>')
            xml_lines.append(f'      <title>{html.escape(titulo_raw)}</title>')
            xml_lines.append(f'      <link>{link}</link>')
            xml_lines.append(f'      <guid isPermaLink="false">{guid_unico}</guid>')
            
            if pub_date_str:
                xml_lines.append(f'      <pubDate>{pub_date_str}</pubDate>')
            
            # Adicionar categoria se existir
            if '_embedded' in item and 'wp:term' in item['_embedded']:
                for term_group in item['_embedded']['wp:term']:
                    for term in term_group:
                        if term.get('taxonomy') == 'category':
                            cat_name = term.get('name', '')
                            if cat_name:
                                xml_lines.append(f'      <category>{html.escape(cat_name)}</category>')
            
            # ADICIONAR IMAGENS
            xml_lines.append(f'      <enclosure url="{imagem_url}" type="image/jpeg" length="100000" />')
            xml_lines.append(f'      <media:content url="{imagem_url}" medium="image" type="image/jpeg">')
            xml_lines.append(f'        <media:title type="plain">{html.escape(titulo_raw[:100])}</media:title>')
            xml_lines.append('      </media:content>')
            
            # Adicionar imagem no conteúdo
            conteudo_com_imagem = f'<p><img src="{imagem_url}" alt="{html.escape(titulo_raw)}" /></p>\n{conteudo_limpo}'
            
            xml_lines.append(f'      <description>{descricao}</description>')
            xml_lines.append(f'      <content:encoded><![CDATA[{conteudo_com_imagem}]]></content:encoded>')
            xml_lines.append('    </item>')
            
            print(f"      📅 {pub_date_str.split(' ')[1:4] if pub_date_str else 'Sem data'} | 📸 {imagem_url.split('/')[-1][:30]}...")
        
        xml_lines.append('  </channel>')
        xml_lines.append('</rss>')
        
        xml_final = '\n'.join(xml_lines)
        
        # Salvar
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_final)
        
        file_size = os.path.getsize(FEED_FILE)
        print(f"\n✅ Feed salvo: {FEED_FILE} ({file_size:,} bytes)")
        
        # Estatísticas
        print("\n📊 ESTATÍSTICAS DO FEED:")
        print(f"   📰 Notícias no feed: {len(noticias_feed)}")
        print(f"   🆕 Notícias novas desde {ultima_data.strftime('%d/%m %H:%M')}: {len(noticias)}")
        print(f"   ⏱️  Próxima verificação: TTL 15min")
        print(f"   🔗 URL com timestamp: ?v={timestamp}")
        
        # Verificar se a primeira URL mudou
        first_link = None
        for line in xml_lines:
            if '<link>http' in line and 'cmfor.ce.gov.br' in line and not 'channel' in line:
                first_link = line.replace('<link>', '').replace('</link>', '').strip()
                break
        
        if first_link:
            print(f"   🔄 Primeira URL do feed: {first_link.split('/')[-2]}/...")
        
        print("\n" + "=" * 70)
        print("🎉 FEED ATUALIZADO COM CONTROLE DE TIMESTAMP!")
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
