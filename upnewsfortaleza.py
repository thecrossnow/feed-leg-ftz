#!/usr/bin/env python3
# upnewsfortaleza.py - VERSÃO FINAL COM CONTEÚDO LIMPO E SEM DUPLICAÇÕES

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta, date
import html
import hashlib
import time
from urllib.parse import urljoin, urlparse
import re
import os
import sys

def criar_feed_fortaleza_limpo():
    """
    Extrai conteúdo LIMPO sem duplicações
    """
    
    print("🚀 upnewsfortaleza.py - CONTEÚDO LIMPO SEM DUPLICAÇÕES")
    print("=" * 60)
    
    # ================= CONFIGURAÇÃO =================
    URL_BASE = "https://www.fortaleza.ce.gov.br"
    URL_LISTA = f"{URL_BASE}/noticias"
    FEED_FILE = "feed_fortaleza_hoje.xml"
    
    # Data UTC → Brasília
    utc_agora = datetime.now(timezone.utc)
    HOJE_REF = (utc_agora + timedelta(hours=3)).date()
    
    print(f"📅 Data de referência: {HOJE_REF.strftime('%d/%m/%Y')}")
    print("-" * 60)
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9'
    }
    
    MESES_PT = {
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
        'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
        'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
    }
    
    def extrair_data(texto):
        """Extrai data do texto em português"""
        try:
            texto = texto.lower()
            for mes_pt, mes_num in MESES_PT.items():
                if mes_pt in texto:
                    dia_match = re.search(r'(\d{1,2})', texto)
                    ano_match = re.search(r'(\d{4})', texto)
                    if dia_match:
                        dia = int(dia_match.group(1))
                        ano = int(ano_match.group(1)) if ano_match else HOJE_REF.year
                        return date(ano, mes_num, dia)
        except:
            pass
        return None
    
    def limpar_conteudo(conteudo_html):
        """Remove duplicações e elementos indesejados do conteúdo"""
        if not conteudo_html:
            return ""
        
        # Converter para texto para análise
        soup = BeautifulSoup(conteudo_html, 'html.parser')
        texto_completo = soup.get_text()
        
        # Dividir em parágrafos
        paragrafos = texto_completo.split('\n')
        paragrafos_limpos = []
        
        # Remover elementos indesejados
        termos_remover = [
            'IMPRIMIR', 'Compartilhe:', 'Enviar por Email', 'Compartilhar',
            'Fonte da matéria', 'Prefeitura de Fortaleza inicia fase de testes',
            'Propósito é incentivar', 'PUBLICIDADE', 'ANÚNCIO', 'LEIA TAMBÉM'
        ]
        
        # Padrões de duplicação (procurar blocos repetidos)
        bloco_minimo = 50  # Mínimo de caracteres para considerar um bloco
        blocos_vistos = set()
        
        for para in paragrafos:
            para = para.strip()
            if not para or len(para) < 20:
                continue
            
            # Verificar se contém termos a remover
            if any(termo in para for termo in termos_remover):
                continue
            
            # Verificar se é duplicado (ignorando pequenas variações)
            para_normalizado = re.sub(r'\s+', ' ', para.lower())
            if len(para_normalizado) >= bloco_minimo:
                # Verificar se este parágrafo é similar a um já visto
                duplicado = False
                for bloco_visto in blocos_vistos:
                    # Verificar similaridade (80% de similaridade)
                    if (para_normalizado in bloco_visto or 
                        bloco_visto in para_normalizado or
                        len(set(para_normalizado.split()) & set(bloco_visto.split())) / 
                        max(len(para_normalizado.split()), len(bloco_visto.split())) > 0.8):
                        duplicado = True
                        break
                
                if not duplicado:
                    blocos_vistos.add(para_normalizado)
                    paragrafos_limpos.append(para)
            else:
                # Parágrafos curtos (títulos, etc)
                if para not in ["Mobilidade", "Serviço", "Desafio Mobilidade Cidadã"]:
                    paragrafos_limpos.append(para)
        
        # Se houver poucos parágrafos, usar estratégia alternativa
        if len(paragrafos_limpos) < 3:
            # Tentar extrair conteúdo de forma diferente
            return extrair_conteudo_direto(soup)
        
        # Juntar parágrafos em HTML
        conteudo_limpo = ""
        for para in paragrafos_limpos:
            if len(para) > 30:  # Parágrafos significativos
                conteudo_limpo += f'<p>{html.escape(para)}</p>\n'
        
        return conteudo_limpo
    
    def extrair_conteudo_direto(soup):
        """Extrai conteúdo diretamente dos elementos estruturais"""
        conteudo = ""
        
        # Estratégia 1: Buscar todos os parágrafos significativos
        for p in soup.find_all('p'):
            texto = p.get_text(strip=True)
            if texto and len(texto) > 50:
                # Verificar se não é elemento de interface
                if not any(termo in texto for termo in ['IMPRIMIR', 'Compartilhe', 'PUBLICIDADE']):
                    # Verificar se o parágrafo não está dentro de elementos indesejados
                    parent_classes = []
                    parent = p.parent
                    for _ in range(3):  # Verificar até 3 níveis acima
                        if parent and parent.get('class'):
                            parent_classes.extend(parent['class'])
                        parent = parent.parent if parent else None
                    
                    classes_str = ' '.join(parent_classes).lower()
                    if not any(termo in classes_str for termo in ['social', 'share', 'banner', 'ad']):
                        conteudo += f'<p>{html.escape(texto)}</p>\n'
        
        # Estratégia 2: Se ainda pouco conteúdo, buscar por divs com texto
        if len(conteudo) < 500:
            for div in soup.find_all('div'):
                texto = div.get_text(strip=True)
                if texto and len(texto) > 200:
                    # Contar parágrafos dentro da div
                    ps = div.find_all('p')
                    if len(ps) >= 3:  # Div com estrutura de conteúdo
                        for p in ps:
                            texto_p = p.get_text(strip=True)
                            if texto_p and len(texto_p) > 30:
                                conteudo += f'<p>{html.escape(texto_p)}</p>\n'
                        break
        
        return conteudo
    
    try:
        # ================= 1. COLETAR NOTÍCIAS =================
        print("🔍 Coletando notícias...")
        
        lista_noticias = []
        pagina = 1
        url = URL_LISTA
        
        while url and pagina <= 5:
            print(f"📄 Página {pagina}")
            
            try:
                response = requests.get(url, headers=HEADERS, timeout=15)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                containers = soup.find_all('div', class_='blog-post-item')
                
                for container in containers:
                    try:
                        # Data
                        data_div = container.find('div', class_='blog-time')
                        if not data_div:
                            continue
                            
                        span_data = data_div.find('span', class_='font-lato')
                        if not span_data:
                            continue
                            
                        data_texto = span_data.get_text(strip=True)
                        data_noticia = extrair_data(data_texto)
                        
                        if not data_noticia or data_noticia != HOJE_REF:
                            continue
                        
                        # Link
                        link_tag = container.find('a', class_='btn-reveal')
                        if not link_tag or not link_tag.get('href'):
                            continue
                            
                        link_url = urljoin(URL_BASE, link_tag['href'])
                        
                        # Título
                        titulo = ""
                        intro_div = container.find('div', class_='intro')
                        if intro_div:
                            h2_tag = intro_div.find('h2')
                            if h2_tag:
                                titulo = h2_tag.get_text(strip=True)
                        
                        if not titulo:
                            continue
                        
                        # Hora
                        hora = "00:00"
                        hora_match = re.search(r'(\d{1,2}:\d{2})', data_texto)
                        if hora_match:
                            hora = hora_match.group(1)
                        
                        # Imagem destacada
                        imagem_destaque = None
                        img_tag = container.find('figure', class_='blog-item-small-image')
                        if img_tag:
                            img = img_tag.find('img')
                            if img and img.get('src'):
                                src = img['src']
                                if not src.startswith(('http://', 'https://')):
                                    imagem_destaque = urljoin(URL_BASE, src)
                                else:
                                    imagem_destaque = src
                        
                        lista_noticias.append({
                            'titulo': titulo,
                            'link': link_url,
                            'data_texto': data_texto,
                            'imagem_destaque': imagem_destaque,
                            'hora': hora
                        })
                        
                        print(f"    ✅ [{hora}] {titulo[:60]}...")
                    
                    except:
                        continue
                
                # Próxima página
                paginador = soup.find('div', class_='news-pagination')
                proxima = None
                
                if paginador:
                    link_proximo = paginador.find('a', string=lambda t: t and 'próximo' in str(t).lower())
                    if link_proximo and link_proximo.get('href'):
                        proxima = urljoin(URL_BASE, link_proximo['href'])
                
                if not proxima:
                    break
                
                pagina += 1
                url = proxima
                time.sleep(1)
                
            except:
                break
        
        if not lista_noticias:
            print("📭 Nenhuma notícia hoje")
            return True
        
        # ================= 2. EXTRAIR CONTEÚDO LIMPO =================
        print(f"\n📥 Extraindo conteúdo limpo...")
        
        noticias_completas = []
        
        for i, noticia in enumerate(lista_noticias, 1):
            print(f"🔗 ({i}/{len(lista_noticias)}) {noticia['link'][:70]}...")
            
            try:
                time.sleep(2)
                
                response = requests.get(noticia['link'], headers=HEADERS, timeout=20)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # ================= EXTRAIR CONTEÚDO PRINCIPAL =================
                # Remover elementos indesejados ANTES de extrair
                for tag in soup.find_all(['script', 'style', 'iframe', 'nav', 
                                         'aside', 'header', 'footer', 'form']):
                    tag.decompose()
                
                # Encontrar conteúdo principal
                conteudo_principal = None
                
                # Tentar seletores específicos do site
                seletores = [
                    ('div', {'class': 'item-page'}),
                    ('div', {'itemprop': 'articleBody'}),
                    ('article', {}),
                    ('div', {'class': 'blog-item-small-content'}),
                ]
                
                for tag_name, attrs in seletores:
                    conteudo_principal = soup.find(tag_name, attrs)
                    if conteudo_principal:
                        break
                
                if not conteudo_principal:
                    # Fallback: div com mais texto
                    divs = soup.find_all('div')
                    for div in divs:
                        texto = div.get_text(strip=True)
                        if len(texto) > 500:
                            conteudo_principal = div
                            break
                
                if not conteudo_principal:
                    continue
                
                # Remover elementos de compartilhamento e interface
                elementos_remover = [
                    'social', 'share', 'comentario', 'comment', 'banner',
                    'ad', 'publicidade', 'newsletter', 'related', 'sidebar',
                    'imprimir', 'print', 'email'
                ]
                
                for tag in conteudo_principal.find_all(True):
                    # Verificar por classes
                    classes = tag.get('class', [])
                    id_tag = tag.get('id', '')
                    texto_classe = ' '.join(classes).lower()
                    
                    if any(termo in texto_classe for termo in elementos_remover) or \
                       any(termo in id_tag.lower() for termo in elementos_remover):
                        tag.decompose()
                
                # Converter para HTML
                conteudo_html = str(conteudo_principal)
                
                # ================= LIMPAR CONTEÚDO =================
                conteudo_limpo = limpar_conteudo(conteudo_html)
                
                # Se ainda estiver vazio, usar fallback
                if not conteudo_limpo or len(conteudo_limpo) < 200:
                    # Extrair parágrafos manualmente
                    paragrafos = []
                    for p in soup.find_all('p'):
                        texto = p.get_text(strip=True)
                        if texto and len(texto) > 50:
                            # Verificar se não é menu/interface
                            parent = p.parent
                            parent_html = str(parent).lower() if parent else ""
                            if not any(termo in parent_html for termo in ['menu', 'nav', 'header', 'footer']):
                                paragrafos.append(texto)
                    
                    # Remover duplicações
                    paragrafos_unicos = []
                    for p in paragrafos:
                        if p not in paragrafos_unicos:
                            paragrafos_unicos.append(p)
                    
                    conteudo_limpo = ""
                    for p in paragrafos_unicos[:10]:  # Limitar a 10 parágrafos
                        conteudo_limpo += f'<p>{html.escape(p)}</p>\n'
                
                # ================= MONTAR CONTEÚDO FINAL =================
                conteudo_final = ""
                
                # Imagem destacada
                if noticia['imagem_destaque']:
                    conteudo_final += f'''
                    <div style="margin-bottom: 25px; text-align: center;">
                        <img src="{noticia['imagem_destaque']}" 
                             alt="{html.escape(noticia['titulo'][:100])}"
                             style="max-width: 100%; height: auto; border-radius: 8px;">
                    </div>
                    '''
                
                # Cabeçalho
                conteudo_final += f'''
                <div style="margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #eee;">
                    <h1 style="margin: 0 0 10px 0; color: #333; font-size: 24px;">
                        {html.escape(noticia['titulo'])}
                    </h1>
                    <div style="color: #666; font-size: 14px;">
                        <strong>Publicado em:</strong> {noticia['data_texto']}
                    </div>
                </div>
                '''
                
                # Conteúdo principal
                conteudo_final += conteudo_limpo
                
                # Rodapé
                conteudo_final += f'''
                <div style="margin-top: 30px; padding: 15px; background: #f5f5f5; 
                     border-left: 3px solid #0073aa; font-size: 14px;">
                    <p style="margin: 0;">
                        <strong>Fonte:</strong> Prefeitura de Fortaleza<br>
                        <strong>Link original:</strong> 
                        <a href="{noticia['link']}" target="_blank">{noticia['link']}</a>
                    </p>
                </div>
                '''
                
                noticia['conteudo'] = conteudo_final
                noticia['tamanho'] = len(conteudo_final)
                noticias_completas.append(noticia)
                
                print(f"    ✅ Conteúdo limpo: {len(conteudo_final):,} caracteres")
                
            except Exception as e:
                print(f"    ❌ Erro: {str(e)[:50]}")
                continue
        
        # ================= 3. GERAR XML =================
        print(f"\n📄 Gerando XML com conteúdo limpo...")
        
        noticias_completas.sort(key=lambda x: x['hora'], reverse=True)
        
        xml_parts = []
        
        xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_parts.append('<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">')
        xml_parts.append('<channel>')
        xml_parts.append(f'<title>Notícias Fortaleza - {HOJE_REF.strftime("%d/%m/%Y")}</title>')
        xml_parts.append(f'<link>{URL_BASE}</link>')
        xml_parts.append(f'<description>Notícias limpas sem duplicações - {len(noticias_completas)} notícias</description>')
        xml_parts.append('<language>pt-br</language>')
        xml_parts.append(f'<lastBuildDate>{utc_agora.strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>')
        xml_parts.append('<ttl>60</ttl>')
        
        for noticia in noticias_completas:
            guid = hashlib.md5(noticia['link'].encode()).hexdigest()[:12]
            
            try:
                hora_partes = noticia['hora'].split(':')
                hora = int(hora_partes[0]) if hora_partes else 12
                minuto = int(hora_partes[1]) if len(hora_partes) > 1 else 0
                data_rss = datetime(HOJE_REF.year, HOJE_REF.month, HOJE_REF.day, 
                                  hora, minuto, 0, tzinfo=timezone.utc)
                pub_date = data_rss.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except:
                pub_date = utc_agora.strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            xml_parts.append('<item>')
            xml_parts.append(f'<title>{html.escape(noticia["titulo"])}</title>')
            xml_parts.append(f'<link>{noticia["link"]}</link>')
            xml_parts.append(f'<guid isPermaLink="false">ftz-{guid}</guid>')
            xml_parts.append(f'<pubDate>{pub_date}</pubDate>')
            xml_parts.append(f'<description>{html.escape(noticia["titulo"][:150])} - {noticia["data_texto"]}</description>')
            
            xml_parts.append(f'<content:encoded><![CDATA[ {noticia["conteudo"]} ]]></content:encoded>')
            
            if noticia.get('imagem_destaque'):
                xml_parts.append(f'<enclosure url="{noticia["imagem_destaque"]}" type="image/jpeg" />')
                xml_parts.append(f'<media:content url="{noticia["imagem_destaque"]}" type="image/jpeg" medium="image">')
                xml_parts.append(f'<media:title>{html.escape(noticia["titulo"][:100])}</media:title>')
                xml_parts.append('</media:content>')
            
            xml_parts.append('</item>')
        
        xml_parts.append('</channel>')
        xml_parts.append('</rss>')
        
        # ================= 4. SALVAR =================
        with open(FEED_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_parts))
        
        # ================= 5. RELATÓRIO =================
        print("-" * 60)
        print(f"✅ FEED LIMPO GERADO!")
        print(f"📊 Notícias: {len(noticias_completas)}")
        print(f"📏 Tamanho total: {sum(n.get('tamanho', 0) for n in noticias_completas):,} caracteres")
        print(f"📁 Arquivo: {FEED_FILE}")
        
        if noticias_completas:
            # Mostrar exemplo do conteúdo limpo
            primeira = noticias_completas[0]
            conteudo_texto = BeautifulSoup(primeira['conteudo'], 'html.parser').get_text()
            
            print(f"\n📋 EXEMPLO DE CONTEÚDO LIMPO:")
            linhas = conteudo_texto.split('\n')
            for linha in linhas[:8]:  # Primeiras 8 linhas
                linha_limpa = linha.strip()
                if linha_limpa and len(linha_limpa) > 20:
                    print(f"  • {linha_limpa[:80]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    sucesso = criar_feed_fortaleza_limpo()
    print("=" * 60)
    print(f"🏁 Status: {'✅ SUCESSO' if sucesso else '❌ FALHA'}")
    sys.exit(0 if sucesso else 1)
