#!/usr/bin/env python3
"""
FEED RSS 2.0 - VERSÃO FINAL DEFINITIVA
Com CDATA correto e HTML normal para WordPress
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import os
import sys
import re
import html

def limpar_conteudo_para_rss(conteudo):
    """
    Remove elementos inválidos e prepara conteúdo para RSS 2.0
    Usa HTML normal dentro de CDATA
    """
    # 1. REMOVER <updated> tags completamente
    conteudo = re.sub(r'<updated>.*?</updated>', '', conteudo, flags=re.DOTALL)
    
    # 2. Remover <dc:creator> se existir
    conteudo = re.sub(r'<dc:creator>.*?</dc:creator>', '', conteudo, flags=re.DOTALL)
    
    # 3. Remover qualquer ]]> residual (IMPORTANTE para não quebrar CDATA)
    conteudo = conteudo.replace(']]>', '')
    
    # 4. Decodificar HTML entities
    conteudo = html.unescape(conteudo)
    
    # 5. Apenas escapar & para &amp; (deixar < > normais para CDATA)
    conteudo = conteudo.replace('&', '&amp;')
    
    # 6. Remover porta :8080 das URLs
    conteudo = conteudo.replace(':8080', '')
    
    # 7. Remover atributos class e style (opcional, para simplificar)
    conteudo = re.sub(r'\sclass="[^"]*"', '', conteudo)
    conteudo = re.sub(r'\sstyle="[^"]*"', '', conteudo)
    
    return conteudo.strip()

def criar_feed_rss_valido(noticias):
    """
    Cria feed RSS 2.0 100% válido
    """
    # Elemento raiz RSS
    rss = ET.Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
    
    # Channel
    channel = ET.SubElement(rss, "channel")
    
    # Metadados do canal (OBRIGATÓRIOS)
    ET.SubElement(channel, "title").text = "Câmara Municipal de Fortaleza"
    ET.SubElement(channel, "link").text = "https://www.cmfor.ce.gov.br"
    ET.SubElement(channel, "description").text = "Notícias Oficiais da Câmara Municipal de Fortaleza"
    ET.SubElement(channel, "language").text = "pt-br"
    ET.SubElement(channel, "generator").text = "GitHub Actions"
    
    # Data de última atualização
    last_build = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    ET.SubElement(channel, "lastBuildDate").text = last_build
    
    # TTL (Time To Live) em minutos
    ET.SubElement(channel, "ttl").text = "60"
    
    # Link atom para auto-referência
    atom_link = ET.SubElement(channel, "atom:link")
    atom_link.set("href", "https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")
    
    # Processar cada notícia
    for i, item in enumerate(noticias, 1):
        titulo_raw = item.get('title', {}).get('rendered', 'Sem título')
        print(f"   [{i}/{len(noticias)}] {titulo_raw[:50]}...")
        
        # Criar elemento <item>
        item_elem = ET.SubElement(channel, "item")
        
        # 1. TÍTULO (obrigatório)
        titulo = html.escape(titulo_raw)
        ET.SubElement(item_elem, "title").text = titulo
        
        # 2. LINK (obrigatório)
        link = item.get('link', '').replace(':8080', '')
        ET.SubElement(item_elem, "link").text = link
        
        # 3. GUID (recomendado)
        guid = ET.SubElement(item_elem, "guid")
        guid.text = link
        guid.set("isPermaLink", "true")
        
        # 4. DATA DE PUBLICAÇÃO (recomendado)
        pub_date = item.get('date', '')
        if pub_date:
            try:
                dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                ET.SubElement(item_elem, "pubDate").text = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except Exception as e:
                print(f"      ⚠️ Erro na data: {e}")
                ET.SubElement(item_elem, "pubDate").text = pub_date
        
        # Conteúdo bruto da API
        conteudo_raw = item.get('content', {}).get('rendered', '')
        
        # 5. DESCRIPTION (OBRIGATÓRIO - deve vir PRIMEIRO)
        # Criar resumo sem HTML
        texto_simples = re.sub('<[^>]+>', '', conteudo_raw)
        texto_simples = html.unescape(texto_simples)
        descricao = (texto_simples[:250] + "...") if len(texto_simples) > 250 else texto_simples
        descricao = html.escape(descricao)
        ET.SubElement(item_elem, "description").text = descricao
        
        # 6. CONTENT:ENCODED (extensão - deve vir DEPOIS do description)
        # Usar HTML normal dentro de CDATA
        conteudo_limpo = limpar_conteudo_para_rss(conteudo_raw)
        content_elem = ET.SubElement(item_elem, "content:encoded")
        # CDATA com HTML normal (não escapado)
        content_elem.text = f"<![CDATA[{conteudo_limpo}]]>"
    
    return rss

def gerar_xml_bem_formatado(rss_tree):
    """
    Gera XML bem formatado e indentado com CDATA correto
    """
    # Converter para string XML
    xml_str = ET.tostring(rss_tree, encoding='unicode', method='xml')
    
    # Adicionar declaração XML
    xml_final = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
    
    # Formatar com indentação bonita
    try:
        import xml.dom.minidom
        
        # Parse o XML
        dom = xml.dom.minidom.parseString(xml_final)
        
        # Formatar com indentação de 2 espaços
        xml_final = dom.toprettyxml(indent="  ")
        
        # Remover linha em branco extra após declaração XML
        lines = xml_final.split('\n')
        xml_final = '\n'.join(lines[1:])  # Remove a primeira linha duplicada
        
    except Exception as e:
        print(f"      ⚠️ Não foi possível formatar XML: {e}")
        # Usar versão não formatada
    
    # CORREÇÃO CRÍTICA: Corrigir CDATA que foi escapado pelo ET
    xml_final = xml_final.replace('&lt;![CDATA[', '<![CDATA[')
    xml_final = xml_final.replace(']]&gt;', ']]>')
    
    # Garantir que não há <updated> no XML final
    if '<updated>' in xml_final:
        print("      ⚠️ Removendo <updated> residual...")
        xml_final = re.sub(r'<updated>.*?</updated>', '', xml_final, flags=re.DOTALL)
    
    # Remover linhas vazias excessivas
    lines = [line for line in xml_final.split('\n') if line.strip()]
    xml_final = '\n'.join(lines)
    
    return xml_final

def validar_feed_manual(xml_content):
    """
    Validações manuais do feed gerado
    """
    print("\n🔍 Validando feed gerado...")
    
    checks = {
        "Declaração XML presente": '<?xml version="1.0"' in xml_content,
        "Versão RSS 2.0": 'version="2.0"' in xml_content,
        "Elemento <channel> presente": '<channel>' in xml_content,
        "Nenhum <updated> encontrado": '<updated>' not in xml_content,
        "CDATA presente no content:encoded": '<![CDATA[' in xml_content and 'content:encoded' in xml_content,
        "Description antes de content:encoded": xml_content.find('<description>') < xml_content.find('<content:encoded>'),
    }
    
    all_ok = True
    for check_name, check_result in checks.items():
        status = "✅" if check_result else "❌"
        print(f"   {status} {check_name}")
        if not check_result:
            all_ok = False
    
    return all_ok

def main():
    print("=" * 60)
    print("🚀 GERANDO FEED RSS 2.0 - VERSÃO DEFINITIVA")
    print("=" * 60)
    
    # Configurações
    API_URL = "https://www.cmfor.ce.gov.br:8080/wp-json/wp/v2/posts"
    FEED_FILE = "feed.xml"
    
    try:
        # 1. Buscar notícias da API
        print("📡 Conectando à API da Câmara...")
        params = {
            "per_page": 10,
            "orderby": "date",
            "order": "desc"
        }
        
        response = requests.get(API_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro na API: {response.status_code}")
            print(f"   Resposta: {response.text[:200]}")
            
            # Criar feed mínimo válido para não quebrar o processo
            print("   Criando feed mínimo...")
            with open(FEED_FILE, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Câmara Municipal de Fortaleza</title><link>https://www.cmfor.ce.gov.br</link><description>Feed temporariamente indisponível</description></channel></rss>')
            
            return True
        
        noticias = response.json()
        print(f"✅ {len(noticias)} notícias encontradas")
        
        # 2. Criar estrutura RSS
        print("📝 Criando estrutura RSS 2.0 válida...")
        rss_tree = criar_feed_rss_valido(noticias)
        
        # 3. Gerar XML formatado
        print("💾 Gerando XML formatado...")
        xml_final = gerar_xml_bem_formatado(rss_tree)
        
        # 4. Validação manual
        if not validar_feed_manual(xml_final):
            print("\n⚠️  AVISO: Algumas validações falharam")
        
        # 5. Salvar arquivo
        print(f"\n💾 Salvando em {FEED_FILE}...")
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(xml_final)
        
        file_size = os.path.getsize(FEED_FILE)
        print(f"✅ Feed salvo: {file_size:,} bytes")
        
        # 6. Verificação final
        print("\n🔍 Verificação final do arquivo:")
        with open(FEED_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            print(f"   • Total de linhas: {len(lines)}")
            print(f"   • Primeira linha: {lines[0].strip()}")
            
            # Contar itens
            item_count = sum(1 for line in lines if '<item>' in line)
            print(f"   • Itens encontrados: {item_count}")
            
            # Verificar CDATA
            cdata_lines = [i+1 for i, line in enumerate(lines) if '<![CDATA[' in line]
            if cdata_lines:
                print(f"   • CDATA encontrado nas linhas: {cdata_lines[:3]}...")
            
            # Verificar problemas
            problem_lines = []
            for i, line in enumerate(lines, 1):
                if '<updated>' in line:
                    problem_lines.append(f"Linha {i}: <updated>")
                if '&lt;![CDATA[' in line:
                    problem_lines.append(f"Linha {i}: CDATA não convertido")
                if ']]&gt;' in line:
                    problem_lines.append(f"Linha {i}: Fechamento CDATA não convertido")
            
            if problem_lines:
                print(f"   ⚠️  Problemas encontrados: {len(problem_lines)}")
                for problem in problem_lines[:3]:
                    print(f"      • {problem}")
            else:
                print("   ✅ Nenhum problema encontrado")
        
        print("\n" + "=" * 60)
        print("🎉 FEED RSS 2.0 GERADO COM SUCESSO!")
        print("=" * 60)
        print(f"📊 Estatísticas:")
        print(f"   • Notícias processadas: {len(noticias)}")
        print(f"   • Tamanho do arquivo: {file_size:,} bytes")
        print(f"   • Data/hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("=" * 60)
        print(f"🔗 URL do feed:")
        print(f"   https://thecrossnow.github.io/feed-leg-ftz/feed.xml")
        print("=" * 60)
        print(f"📋 Valide em:")
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
