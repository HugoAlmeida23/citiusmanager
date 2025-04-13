"""
Script para testar a extração de documentos do Citius.
Este é um arquivo de teste isolado para explorar como extrair documentos
do sistema Citius e armazená-los no Supabase.
Versão aprimorada: Suporta o download de múltiplos documentos de uma única notificação.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import os
import logging
import tempfile
import json
import re
import unicodedata
from datetime import datetime
from supabase import create_client, Client
from PyPDF2 import PdfMerger
from postgrest.exceptions import APIError # Import APIError for more specific error handling if needed

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('citius_document_scraper')


# Credenciais do Supabase
SUPABASE_URL = "https://shzvugthjndlagxlcowp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNoenZ1Z3Roam5kbGFneGxjb3dwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0MDUyMDk1NywiZXhwIjoyMDU2MDk2OTU3fQ.bmJ7wr2uCPdy1RIqW2A2Xmk0bcx6zjiBYb8NszzadsM"
SUPABASE_BUCKET_NAME = "citiusdocuments"  # Nome do bucket no Supabase Storage

def update_db_record(supabase: Client, doc_metadata: dict):
   
    try:
        target_referencia = doc_metadata.get('referencia')
        target_user_id = doc_metadata.get('user_id')  # Adiciona user_id para filtro
        
        if not target_user_id:
            logger.error("Erro: 'user_id' ausente nos metadados do documento. Impossível atualizar DB.")
            return False
        
        if not target_referencia:
            logger.error("Erro: 'referencia' ausente nos metadados do documento. Impossível atualizar DB.")
            return False

        # 1. Verificar se o registro já existe e obter o ID e o valor atual de 'doc'
        # Agora também selecionamos o campo 'doc' para verificar seu valor atual
        result = (
            supabase.table('api_processo')
            .select('id, doc')
            .eq('referencia', target_referencia)
            .eq('user_id', target_user_id)
            .limit(1)
            .execute()
        )

        if result.data:
            record_id = result.data[0]['id']
            current_doc = result.data[0].get('doc', '')
            
            # Verificar se o valor atual de 'doc' já é válido (não é "em breve")
            if current_doc and current_doc != "em breve":
                logger.info(f"Registro ID {record_id} (referencia: {target_referencia}) já possui um documento válido: '{current_doc}'. Nenhuma atualização necessária.")
                return True

            logger.info(f"Registro encontrado para referencia '{target_referencia}', ID: {record_id}. Atualizando...")

            # 2. Preparar os dados para a atualização
            update_data = {
                'doc': doc_metadata.get('doc'), # A URL do arquivo
            }

            logger.info(f"Dados a serem atualizados: {update_data}")

            # Remover quaisquer chaves com valor None
            update_data = {k: v for k, v in update_data.items() if v is not None}

            if not update_data.get('doc'):
                 logger.error(f"Erro: URL do documento ('doc') está faltando nos metadados para referencia '{target_referencia}'.")
                 return False

            # 3. Executar a atualização
            update_result = (
                supabase.table('api_processo')
                .update(update_data)
                .eq('id', record_id)
                .execute()
            )

            logger.info(f"Resultado da atualização: {update_result}")
            logger.info(f"Registro ID {record_id} (referencia: {target_referencia}) atualizado com sucesso.")
            
            return True
        else:
            # Registro não encontrado
            logger.warning(f"Registro com referencia '{target_referencia}' não encontrado no banco de dados. Nenhuma atualização realizada.")
            return True

    except APIError as api_e:
        logger.error(f"Erro de API do Supabase ao atualizar registro para referencia '{doc_metadata.get('referencia')}': {api_e}")
        logger.error(f"Detalhes do erro da API: {api_e.json()}")
        return False
    except Exception as e:
        logger.error(f"Erro inesperado ao atualizar registro no banco de dados para referencia '{doc_metadata.get('referencia')}': {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
def sanitize_filename(filename):
    if not isinstance(filename, str):
        filename = str(filename)

    # 1. Normalize unicode characters (e.g., 'á' -> 'a', 'ç' -> 'c')
    try:
        # NFKD decomposes characters into base char + combining marks
        normalized = unicodedata.normalize('NFKD', filename)
        # Encode to ASCII bytes, ignore characters that cannot be represented
        ascii_bytes = normalized.encode('ascii', 'ignore')
        # Decode back to a clean ASCII string
        ascii_string = ascii_bytes.decode('ascii')
    except Exception as e:
        # Fallback in case of unexpected normalization/encoding errors
        print(f"Warning: Error during unicode normalization/encoding for '{filename}': {e}. Using basic sanitization.")
        # Basic fallback: remove common problematic chars
        ascii_string = re.sub(r'[^\x00-\x7F]+', '', filename) # Remove non-ASCII

    # 2. Replace disallowed characters with underscores
    # Allow letters, numbers, underscore, hyphen, period. Replace others.
    # Disallow characters like [], (), {}, ?, *, etc.
    # IMPORTANT: Explicitly replace '/' as it's a path separator
    sanitized = ascii_string.replace('/', '_')
    sanitized = re.sub(r'[^\w\._-]', '_', sanitized) # \w is alphanumeric + underscore

    # 3. Clean up potential issues
    # Replace multiple consecutive underscores/hyphens/periods with a single underscore
    sanitized = re.sub(r'[_.-]+', '_', sanitized)
    # Remove leading/trailing underscores/hyphens/periods
    sanitized = sanitized.strip('_.-')

    # 4. Handle edge case: empty filename after sanitization
    if not sanitized:
        return "sanitized_empty"

    # 5. Optional: Limit length (e.g., S3 limits are 1024 bytes, but shorter is often safer)
    # MAX_LEN = 100
    # sanitized = sanitized[:MAX_LEN]

    return sanitized

def merge_pdf_documents(pdf_file_paths, output_path=None):
    """
    Merge multiple PDF files into a single PDF.
    
    Args:
        pdf_file_paths: List of paths to PDF files to merge
        output_path: Optional path for the merged PDF. If None, a temp file is created.
        
    Returns:
        Path to the merged PDF file
    """
    try:
        logger.info(f"Merging {len(pdf_file_paths)} PDF documents into a single file")
        
        # Create a PdfMerger object
        merger = PdfMerger()
        
        # Add each PDF to the merger
        for pdf_path in pdf_file_paths:
            # Skip non-PDF files
            if not pdf_path.lower().endswith('.pdf'):
                logger.warning(f"Skipping non-PDF file: {pdf_path}")
                continue
                
            try:
                merger.append(pdf_path)
                logger.info(f"Added {pdf_path} to merger")
            except Exception as e:
                logger.error(f"Error adding {pdf_path} to merger: {str(e)}")
                # Continue with other PDFs
                continue
        
        # If no output path specified, create a temporary file
        if output_path is None:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                output_path = temp_file.name
        
        # Write the merged PDF to the output path
        merger.write(output_path)
        merger.close()
        
        logger.info(f"Successfully merged PDFs to: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error merging PDFs: {str(e)}")
        return None
    
def get_document_urls(driver):
    """Extrai URLs de documentos das notificações."""
    try:
        document_data = []
        
        # Encontrar todas as linhas de notificações
        rows = driver.find_elements(By.XPATH, '//tr[@style="color:#000066;height:20px;"]')
        logger.info(f"Encontradas {len(rows)} notificações")
        
        for index, row in enumerate(rows):
                
            try:
                # Extrair os dados da notificação
                cells = row.find_elements(By.TAG_NAME, 'td')[1:]  # Ignorar a primeira célula (checkbox)
                
                # Extrair informações básicas para usar na organização dos documentos
                origem = cells[0].text.strip() if len(cells) > 0 else "Desconhecido"
                data = cells[1].text.strip() if len(cells) > 1 else "Desconhecido"
                acto = cells[2].text.strip() if len(cells) > 2 else "Desconhecido"
                tribunal = cells[4].text.strip() if len(cells) > 4 else "Desconhecido"
                unidade = cells[5].text.strip() if len(cells) > 5 else "Desconhecido"
                processo = cells[6].text.strip() if len(cells) > 6 else "Desconhecido"
                especie = cells[7].text.strip() if len(cells) > 7 else "Desconhecido"
                referencia = cells[8].text.strip() if len(cells) > 8 else "Desconhecido"
                
                # No Citius, a coluna Doc (index 3) contém o link para o documento
                doc_cell = cells[3] if len(cells) > 3 else None
                
                if doc_cell:
                    # Procurar pelo link específico do popup
                    # O padrão identificado no HTML fornecido é um link com onclick contendo popupWindow
                    doc_link = doc_cell.find_element(By.XPATH, './/a[contains(@onclick, "popupWindow")]') if doc_cell else None
                    
                    if doc_link:
                        # Extrair a URL do atributo onclick
                        onclick_attr = doc_link.get_attribute('onclick')
                        
                        # Extrair o parâmetro w da URL usando expressão regular
                        popup_url_match = re.search(r"popupWindow\('([^']+)'", onclick_attr)
                        if popup_url_match:
                            popup_url = popup_url_match.group(1)
                            # Extrair o token w
                            w_param_match = re.search(r"w=([^&]+)", popup_url)
                            doc_token = w_param_match.group(1) if w_param_match else None
                            
                            # Formar a URL completa para o documento
                            base_url = "https://citius.tribunaisnet.mj.pt"
                            doc_url = f"{base_url}{popup_url}"
                            
                            document_data.append({
                                'origem': origem,
                                'data': data,
                                'acto': acto,
                                'tribunal': tribunal,
                                'unidade': unidade,
                                'processo': processo,
                                'especie': especie,
                                'referencia': referencia,
                                'doc_url': doc_url,
                                'doc_token': doc_token,
                                'row_index': index
                            })
                            logger.info(f"Documento encontrado: {acto} - {referencia}")
                        else:
                            logger.warning(f"Não foi possível extrair a URL do popupWindow para notificação {index + 1}")
                    else:
                        logger.warning(f"Nenhum link de popupWindow encontrado para notificação {index + 1}")
                else:
                    logger.warning(f"Célula de documento não encontrada para notificação {index + 1}")
            
            except Exception as row_error:
                logger.error(f"Erro ao processar linha {index + 1}: {str(row_error)}")
                
        return document_data
    
    except Exception as e:
        logger.error(f"Erro ao extrair URLs de documentos: {str(e)}")
        driver.save_screenshot("document_extraction_error.png")
        return []

def download_document(driver, doc_info):
    """
    Tenta baixar o(s) documento(s) de uma notificação.
    Suporta múltiplos documentos/anexos usando ambos os dropdowns disponíveis.
    """
    logger.info(f"Tentando baixar documento(s) para: {doc_info['acto']} - {doc_info['referencia']} - Origem: {doc_info.get('origem', 'N/A')}")
    
    # Special handling for "Mandatário" origin
    is_mandatario = doc_info.get('origem') == "Mandatário"
    if is_mandatario:
        logger.info("Detectado documento com origem 'Mandatário'. Usando abordagem alternativa.")
    
    current_url = driver.current_url
    
    # Definir timeout mais curto para este processamento específico
    original_timeout = driver.timeouts.page_load
    # Longer timeout for Mandatário documents
    driver.set_page_load_timeout(60 if is_mandatario else 30)

    try:
        # Navegar para a URL do popup com tratamento especial para Mandatário
        try:
            logger.info(f"Navegando para a URL do popup: {doc_info['doc_url']}")
            driver.get(doc_info['doc_url'])
            
            # For Mandatário documents, wait longer and use different selectors
            if is_mandatario:
                time.sleep(5)  # Wait longer for Mandatário documents
                # Ensure the page is fully loaded
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            else:
                time.sleep(3)
        except Exception as e:
            logger.warning(f"Timeout ao carregar popup: {str(e)}")
            # Try to capture screenshot for debugging
            try:
                screenshot_path = f"/tmp/popup_timeout_{doc_info['referencia']}_{int(time.time())}.png"
                driver.save_screenshot(screenshot_path)
                logger.info(f"Screenshot salvo em {screenshot_path}")
            except:
                pass
                
            # Tentar interromper carregamento
            try:
                driver.execute_script("window.stop();")
            except:
                pass
        
        # Lista para armazenar todos os documentos baixados
        downloaded_documents = []
        all_document_urls = []
        
        # For Mandatário documents, try direct download first
        if is_mandatario:
            try:
                # Try to find download button directly - using a more flexible approach
                download_links = driver.find_elements(By.XPATH, "//a[contains(@id, 'Download') or contains(@id, 'download')]")
                
                if download_links:
                    for i, download_link in enumerate(download_links):
                        try:
                            pdf_url = download_link.get_attribute('href')
                            if pdf_url and ('pdf' in pdf_url.lower() or 'download' in pdf_url.lower()):
                                logger.info(f"Link de download direto encontrado para Mandatário: {pdf_url}")
                                
                                # Create a specific identifier
                                doc_identifier = f"mandatario_{i+1}"
                                
                                # Download this specific document
                                doc_result = download_single_document(driver, pdf_url, doc_identifier, doc_info)
                                
                                if doc_result['success']:
                                    downloaded_documents.append(doc_result)
                                    all_document_urls.append(doc_result['doc_url'] if 'doc_url' in doc_result else pdf_url)
                                    logger.info(f"Documento Mandatário {i+1} baixado com sucesso")
                                else:
                                    logger.error(f"Falha ao baixar documento Mandatário {i+1}: {doc_result.get('error_message')}")
                        except Exception as link_error:
                            logger.error(f"Erro ao processar link de download Mandatário {i+1}: {str(link_error)}")
                            continue
                            
                    # If we found and processed any documents, return now
                    if downloaded_documents:
                        # Return the first document as main and attach the list of all
                        result = downloaded_documents[0].copy()
                        result['all_documents'] = downloaded_documents
                        result['all_document_urls'] = all_document_urls
                        result['multi_document'] = True
                        result['total_documents'] = len(downloaded_documents)
                        return result
            except Exception as direct_error:
                logger.error(f"Erro ao tentar download direto para Mandatário: {str(direct_error)}")

        # PRIMEIRO: Verificar e processar o dropdown principal de anexos (dropDocs)
        try:
            # Localizar o dropdown principal de anexos
            main_dropdown = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "dropDocs"))
            )
            
            # Obter todos os options do dropdown principal
            main_options = main_dropdown.find_elements(By.TAG_NAME, "option")
            main_option_values = []
            main_option_texts = []
            
            # Armazenar os valores e textos dos options
            for option in main_options:
                main_option_values.append(option.get_attribute('value'))
                main_option_texts.append(option.text)
            
            total_main_documents = len(main_option_values)
            logger.info(f"Encontrados {total_main_documents} documentos/anexos no dropdown principal")
            
            # Processar cada anexo do dropdown principal
            for index in range(total_main_documents):
                doc_name = main_option_texts[index]
                doc_value = main_option_values[index]
                logger.info(f"Processando anexo {index+1}/{total_main_documents}: {doc_name}")
                
                try:
                    # Selecionar o anexo no dropdown principal
                    select_element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "dropDocs"))
                    )
                    select = Select(select_element)
                    select.select_by_value(doc_value)
                    time.sleep(3)  # Aguardar o carregamento do anexo
                    
                    # SEGUNDO: Para cada anexo, verificar o dropdown secundário (ucActoView_ucDocumentosAto_ddlDocumentos)
                    try:
                        # Localizar o dropdown secundário
                        secondary_dropdown = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "ucActoView_ucDocumentosAto_ddlDocumentos"))
                        )
                        
                        # Obter todos os options do dropdown secundário
                        secondary_options = secondary_dropdown.find_elements(By.TAG_NAME, "option")
                        secondary_option_values = []
                        secondary_option_texts = []
                        
                        # Armazenar os valores e textos dos options secundários
                        for option in secondary_options:
                            secondary_option_values.append(option.get_attribute('value'))
                            secondary_option_texts.append(option.text)
                        
                        total_secondary_documents = len(secondary_option_values)
                        logger.info(f"Encontrados {total_secondary_documents} documentos no dropdown secundário para o anexo {doc_name}")
                        
                        # Processar cada documento do dropdown secundário
                        for sec_index in range(total_secondary_documents):
                            sec_doc_name = secondary_option_texts[sec_index]
                            sec_doc_value = secondary_option_values[sec_index]
                            logger.info(f"Processando documento secundário {sec_index+1}/{total_secondary_documents}: {sec_doc_name}")
                            
                            try:
                                # Selecionar o documento no dropdown secundário
                                sec_select_element = WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located((By.ID, "ucActoView_ucDocumentosAto_ddlDocumentos"))
                                )
                                sec_select = Select(sec_select_element)
                                sec_select.select_by_value(sec_doc_value)
                                time.sleep(2)  # Aguardar o carregamento do documento
                                
                                # Tentar obter o link de download após a seleção
                                download_link = WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located((By.ID, "ucActoView_hlDownload"))
                                )
                                
                                if download_link:
                                    pdf_url = download_link.get_attribute('href')
                                    logger.info(f"Link de download encontrado para {doc_name} - {sec_doc_name}: {pdf_url}")
                                    
                                    # Criar identificador específico para o documento
                                    doc_identifier = f"{index+1}_{sanitize_filename(doc_name)}_{sec_index+1}_{sanitize_filename(sec_doc_name)}"
                                    
                                    # Baixar este documento específico
                                    doc_result = download_single_document(driver, pdf_url, doc_identifier, doc_info)
                                    
                                    if doc_result['success']:
                                        downloaded_documents.append(doc_result)
                                        all_document_urls.append(doc_result['doc_url'] if 'doc_url' in doc_result else pdf_url)
                                        logger.info(f"Documento {index+1}.{sec_index+1} baixado com sucesso")
                                    else:
                                        logger.error(f"Falha ao baixar documento {index+1}.{sec_index+1}: {doc_result.get('error_message')}")
                                else:
                                    logger.warning(f"Botão de download não encontrado para o documento {sec_doc_name}")
                            
                            except Exception as sec_doc_error:
                                logger.error(f"Erro ao processar documento secundário {sec_index+1}/{total_secondary_documents}: {str(sec_doc_error)}")
                                # Continuar com o próximo documento mesmo se houver erro neste
                                continue
                    
                    except NoSuchElementException:
                        # Nenhum dropdown secundário encontrado, tentar baixar diretamente o documento atual
                        logger.info(f"Nenhum dropdown secundário encontrado para o anexo {doc_name}, tentando download direto")
                        
                        try:
                            download_link = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.ID, "ucActoView_hlDownload"))
                            )
                            
                            if download_link:
                                pdf_url = download_link.get_attribute('href')
                                logger.info(f"Link de download direto encontrado para {doc_name}: {pdf_url}")
                                
                                # Criar identificador específico para o documento
                                doc_identifier = f"{index+1}_{sanitize_filename(doc_name)}"
                                
                                # Baixar este documento específico
                                doc_result = download_single_document(driver, pdf_url, doc_identifier, doc_info)
                                
                                if doc_result['success']:
                                    downloaded_documents.append(doc_result)
                                    all_document_urls.append(doc_result['doc_url'] if 'doc_url' in doc_result else pdf_url)
                                    logger.info(f"Documento {index+1} baixado com sucesso")
                                else:
                                    logger.error(f"Falha ao baixar documento {index+1}: {doc_result.get('error_message')}")
                            else:
                                logger.warning(f"Botão de download não encontrado para o anexo {doc_name}")
                        
                        except Exception as download_error:
                            logger.error(f"Erro ao tentar download direto para {doc_name}: {str(download_error)}")
                    
                except Exception as doc_error:
                    logger.error(f"Erro ao processar anexo {index+1}/{total_main_documents}: {str(doc_error)}")
                    # Continuar com o próximo anexo mesmo se houver erro neste
                    continue
            
        except NoSuchElementException:
            # Nenhum dropdown principal encontrado, tentar usar apenas o dropdown secundário
            logger.info("Nenhum dropdown principal de anexos encontrado, verificando apenas o dropdown secundário")
            
            try:
                # Verificar o dropdown secundário (ucActoView_ucDocumentosAto_ddlDocumentos)
                secondary_dropdown = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "ucActoView_ucDocumentosAto_ddlDocumentos"))
                )
                
                # Obter todos os options do dropdown secundário
                secondary_options = secondary_dropdown.find_elements(By.TAG_NAME, "option")
                secondary_option_values = []
                secondary_option_texts = []
                
                # Armazenar os valores e textos dos options secundários
                for option in secondary_options:
                    secondary_option_values.append(option.get_attribute('value'))
                    secondary_option_texts.append(option.text)
                
                total_secondary_documents = len(secondary_option_values)
                logger.info(f"Encontrados {total_secondary_documents} documentos no dropdown secundário")
                
                # Processar cada documento do dropdown secundário
                for sec_index in range(total_secondary_documents):
                    sec_doc_name = secondary_option_texts[sec_index]
                    sec_doc_value = secondary_option_values[sec_index]
                    logger.info(f"Processando documento secundário {sec_index+1}/{total_secondary_documents}: {sec_doc_name}")
                    
                    try:
                        # Selecionar o documento no dropdown secundário
                        sec_select_element = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "ucActoView_ucDocumentosAto_ddlDocumentos"))
                        )
                        sec_select = Select(sec_select_element)
                        sec_select.select_by_value(sec_doc_value)
                        time.sleep(2)  # Aguardar o carregamento do documento
                        
                        # Tentar obter o link de download após a seleção
                        download_link = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "ucActoView_hlDownload"))
                        )
                        
                        if download_link:
                            pdf_url = download_link.get_attribute('href')
                            logger.info(f"Link de download encontrado para {sec_doc_name}: {pdf_url}")
                            
                            # Criar identificador específico para o documento
                            doc_identifier = f"{sec_index+1}_{sanitize_filename(sec_doc_name)}"
                            
                            # Baixar este documento específico
                            doc_result = download_single_document(driver, pdf_url, doc_identifier, doc_info)
                            
                            if doc_result['success']:
                                downloaded_documents.append(doc_result)
                                all_document_urls.append(doc_result['doc_url'] if 'doc_url' in doc_result else pdf_url)
                                logger.info(f"Documento {sec_index+1} baixado com sucesso")
                            else:
                                logger.error(f"Falha ao baixar documento {sec_index+1}: {doc_result.get('error_message')}")
                        else:
                            logger.warning(f"Botão de download não encontrado para o documento {sec_doc_name}")
                    
                    except Exception as sec_doc_error:
                        logger.error(f"Erro ao processar documento secundário {sec_index+1}/{total_secondary_documents}: {str(sec_doc_error)}")
                        # Continuar com o próximo documento mesmo se houver erro neste
                        continue
            
            except NoSuchElementException:
                # Nenhum dropdown encontrado, tentar usar o link de download direto
                logger.info("Nenhum dropdown encontrado, processando como documento único")
                
                try:
                    download_link = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "ucActoView_hlDownload"))
                    )
                    
                    if download_link:
                        pdf_url = download_link.get_attribute('href')
                        logger.info(f"Link de download direto encontrado: {pdf_url}")
                        
                        # Baixar o documento único
                        doc_result = download_single_document(driver, pdf_url, "principal", doc_info)
                        
                        if doc_result['success']:
                            downloaded_documents.append(doc_result)
                            all_document_urls.append(doc_result['doc_url'] if 'doc_url' in doc_result else pdf_url)
                        else:
                            logger.warning("Botão de download encontrado, mas URL não obtida")
                
                except NoSuchElementException:
                    logger.error("Botão de download não encontrado")
                    driver.save_screenshot("no_download_button.png")

                # For Mandatário documents, try a more general approach if nothing else worked
                if is_mandatario and not downloaded_documents:
                    logger.info("Tentando abordagem alternativa para Mandatário...")
                    try:
                        # Try to find the iframe that contains the document
                        iframe = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "ucActoView_ifrmDoc"))
                        )
                        iframe_src = iframe.get_attribute('src')
                        
                        if iframe_src:
                            logger.info(f"Found iframe source: {iframe_src}")
                            
                            # Switch to the iframe
                            driver.switch_to.frame(iframe)
                            
                            # Try to find PDF links inside the iframe
                            pdf_links = driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf') or contains(@href, 'download')]")
                            
                            if pdf_links:
                                for i, link in enumerate(pdf_links):
                                    try:
                                        pdf_url = link.get_attribute('href')
                                        if pdf_url:
                                            logger.info(f"Found PDF link in iframe: {pdf_url}")
                                            
                                            # Download this document
                                            doc_identifier = f"iframe_pdf_{i+1}"
                                            doc_result = download_single_document(driver, pdf_url, doc_identifier, doc_info)
                                            
                                            if doc_result['success']:
                                                downloaded_documents.append(doc_result)
                                                all_document_urls.append(doc_result['doc_url'] if 'doc_url' in doc_result else pdf_url)
                                                logger.info(f"Documento do iframe {i+1} baixado com sucesso")
                                    except Exception as iframe_link_error:
                                        logger.error(f"Error processing iframe link {i+1}: {str(iframe_link_error)}")
                                        continue
                                
                                # Switch back to default content
                                driver.switch_to.default_content()
                            else:
                                # If no PDF links in iframe, try to use the iframe source directly
                                if ".pdf" in iframe_src.lower() or "download" in iframe_src.lower():
                                    logger.info(f"Using iframe source as direct PDF: {iframe_src}")
                                    
                                    # Download using iframe source
                                    doc_result = download_single_document(driver, iframe_src, "iframe_source", doc_info)
                                    
                                    if doc_result['success']:
                                        downloaded_documents.append(doc_result)
                                        all_document_urls.append(doc_result['doc_url'] if 'doc_url' in doc_result else iframe_src)
                                        logger.info(f"Documento do iframe baixado com sucesso")
                                
                                # Switch back to default content
                                driver.switch_to.default_content()
                    except Exception as iframe_error:
                        logger.error(f"Error processing iframe for Mandatário: {str(iframe_error)}")
                        # Try to switch back to default content
                        try:
                            driver.switch_to.default_content()
                        except:
                            pass
        
        # Voltar para a página anterior
        driver.get(current_url)
        
        # Verificar se baixamos algum documento
        if downloaded_documents:
            # Retornar o primeiro documento como principal e anexar a lista de todos
            result = downloaded_documents[0].copy()
            result['all_documents'] = downloaded_documents
            result['all_document_urls'] = all_document_urls
            result['multi_document'] = True
            result['total_documents'] = len(downloaded_documents)
            return result
        else:
            # Extra handling for Mandatário when no documents were found
            if is_mandatario:
                logger.info("No documents downloaded for Mandatário. Using fallback approach.")
                
                # Create a placeholder for Mandatário documents
                # This prevents repeated failed attempts to download the same document
                fallback_result = {
                    'success': True, 
                    'file_path': None,
                    'file_type': 'html',
                    'processo': doc_info['processo'],
                    'referencia': doc_info['referencia'],
                    'doc_identifier': 'mandatario_fallback',
                    'doc_url': doc_info['doc_url'],  # Use the original URL
                    'is_fallback': True,
                    'mandatario_document': True
                }
                
                # For database record
                doc_metadata = {
                    'processo': doc_info.get('processo', ''),
                    'referencia': doc_info.get('referencia', ''),
                    'doc': doc_info['doc_url'],  # Use original URL as doc link
                    'document_stored': False,
                    'document_type': 'mandatario',
                    'mandatario_document': True,
                    'download_attempted': True,
                    'last_accessed': datetime.now().isoformat()
                }
                
                # Create a result with fallback metadata
                result = fallback_result.copy()
                result['all_documents'] = [fallback_result]
                result['all_document_urls'] = [doc_info['doc_url']]
                result['multi_document'] = False
                result['total_documents'] = 1
                result['doc_metadata'] = doc_metadata
                
                return result
            else:
                logger.error("Nenhum documento foi baixado com sucesso")
                return {'success': False, 'error_message': "Nenhum documento foi baixado com sucesso"}
    
    except Exception as e:
        logger.error(f"Erro ao baixar documento: {str(e)}")
        # Take a screenshot for debugging
        try:
            driver.save_screenshot(f"/tmp/download_error_{doc_info['referencia']}_{int(time.time())}.png")
        except:
            pass
            
        # Voltar para a página anterior
        try:
            driver.get(current_url)
        except:
            pass
        
        return {'success': False, 'error_message': str(e)}
        
    finally:
        # Restaurar timeout original
        driver.set_page_load_timeout(original_timeout)
           
def download_single_document(driver, pdf_url, doc_identifier, doc_info):
    """Baixa um único documento a partir de uma URL direta."""
    try:
        # Configurar uma sessão de requests com os cookies do navegador
        import requests
        session = requests.Session()
        cookies = driver.get_cookies()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        
        # URL completa
        if not pdf_url.startswith('http'):
            base_url = "https://citius.tribunaisnet.mj.pt"
            if pdf_url.startswith('/'):
                pdf_url = base_url + pdf_url
            else:
                pdf_url = base_url + '/' + pdf_url
        
        # Fazer o download
        response = session.get(pdf_url, stream=True)
        
        if response.status_code == 200:
            # Verificar se é realmente um PDF
            content_type = response.headers.get('Content-Type', '')
            if 'application/pdf' in content_type or '.pdf' in pdf_url.lower():
                # Salvar o PDF em arquivo temporário
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    for chunk in response.iter_content(chunk_size=1024):
                        temp_file.write(chunk)
                    temp_path = temp_file.name
                
                logger.info(f"PDF baixado com sucesso para: {temp_path}")
                
                return {
                    'success': True,
                    'file_path': temp_path,
                    'file_type': 'pdf',
                    'processo': doc_info['processo'],
                    'referencia': doc_info['referencia'],
                    'doc_identifier': doc_identifier,
                    'doc_url': pdf_url
                }
            else:
                logger.warning(f"O link de download não retornou um PDF (Content-Type: {content_type})")
                
                # Tentar salvar o conteúdo recebido, seja qual for
                with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as temp_file:
                    for chunk in response.iter_content(chunk_size=1024):
                        temp_file.write(chunk)
                    temp_path = temp_file.name
                
                return {
                    'success': True,
                    'file_path': temp_path,
                    'file_type': 'html',
                    'processo': doc_info['processo'],
                    'referencia': doc_info['referencia'],
                    'doc_identifier': doc_identifier,
                    'doc_url': pdf_url
                }
        else:
            logger.error(f"Falha ao baixar documento, código de status: {response.status_code}")
            return {
                'success': False,
                'error_message': f"Erro HTTP: {response.status_code}"
            }
    except Exception as e:
        logger.error(f"Erro ao baixar documento único: {str(e)}")
        return {
            'success': False,
            'error_message': str(e)
        }

def upload_to_supabase(file_path, file_type, doc_info,user_id):
    """
    Faz upload do documento para o Supabase Storage.
    Suporta upload de documentos únicos ou múltiplos documentos.
    Usa a abordagem de dicionário direto para opções de upload, como no script antigo.
    """
    try:
        # Verificar se é um caso de múltiplos documentos
        is_multi_document = 'doc_identifier' in doc_info and doc_info['doc_identifier'] != 'principal'

        # Sanitizar a referência para uso como pasta/nome base
        # Ensure doc_info['referencia'] is a string before sanitizing
        referencia_raw = str(doc_info.get('referencia', 'sem_referencia'))
        referencia = sanitize_filename(referencia_raw)


        # Para múltiplos documentos, usar um padrão de numeração
        if is_multi_document:
            # Extrair o identificador do documento (já tem índice no formato)
            # Sanitize identifier as well if it comes from external source
            doc_identifier = sanitize_filename(str(doc_info['doc_identifier']))
            # Usar identificador no nome do arquivo
            unique_filename = f"{referencia}_{doc_identifier}.{file_type}"
        else:
            # Para documentos únicos, usar o padrão simples
            unique_filename = f"{referencia}.{file_type}"

        # Definir o caminho no storage usando a referência como pasta
        storage_path = f"{referencia}/{unique_filename}"

        # Ler o conteúdo do arquivo
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Inicializar cliente Supabase
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Determinar o content-type correto (como no script antigo)
        content_types = {
            'pdf': 'application/pdf',
            'html': 'text/html',
            'pdf_html': 'text/html'
        }
        # Use a default or raise error if file_type is unexpected
        content_type = content_types.get(file_type, 'application/octet-stream') # Default to binary stream if unknown
        if file_type not in content_types:
             logger.warning(f"Tipo de arquivo desconhecido '{file_type}', usando default 'application/octet-stream'.")


        # --- FAZER UPLOAD USANDO A ABORDAGEM DO SCRIPT ANTIGO (DICIONÁRIO DIRETO) ---
        # --- Combinado com a lógica de Upsert ---
        logger.info(f"Fazendo upload para Supabase: {storage_path} com Content-Type: {content_type}")

        try:
            # Tentativa inicial com upsert=True usando o dicionário direto
            upload_options = {
                "content-type": content_type,
                "upsert": "true" # Include upsert here
            }
            logger.debug(f"Opções de upload (tentativa 1): {upload_options}")
            response = supabase.storage.from_(SUPABASE_BUCKET_NAME).upload(
                path=storage_path, # Use named arguments for clarity
                file=file_content,
                file_options=upload_options # Pass the dictionary here
            )
           

        except Exception as upload_error:
            # Log detailed error, check if it's the 'Header value must be str or bytes' again
            logger.warning(f"Erro no upload inicial ({type(upload_error).__name__}), tentando remover e reenviar: {str(upload_error)}")
            # If the error was the boolean header type again, passing upsert=True here might still fail.
            # The remove-then-upload strategy is safer.

            try:
                # Tentar remover o arquivo existente (se houver)
                logger.info(f"Tentando remover arquivo existente: {storage_path}")
                remove_response = supabase.storage.from_(SUPABASE_BUCKET_NAME).remove([storage_path])
                logger.debug(f"Resultado da remoção: {remove_response}") # Log removal result

                # Tentar fazer upload novamente, SEM upsert desta vez
                upload_options_retry = {
                    "content-type": content_type
                }
                logger.info(f"Reenviando arquivo para {storage_path} com opções: {upload_options_retry}")
                response = supabase.storage.from_(SUPABASE_BUCKET_NAME).upload(
                    path=storage_path,
                    file=file_content,
                    file_options=upload_options_retry # Pass the dictionary without upsert
                )

            except Exception as remove_upload_error:
                logger.error(f"Falha crítica ao remover e/ou reenviar arquivo: {str(remove_upload_error)}")
                import traceback
                logger.error(traceback.format_exc())
                raise # Re-raise the error to indicate failure


        # Criar URL pública para o arquivo
        file_url = supabase.storage.from_(SUPABASE_BUCKET_NAME).get_public_url(storage_path)

        logger.info(f"Documento enviado para o Supabase: {file_url}")
        logger.info(f"Verifique se o Content-Type está correto no Supabase para: {storage_path}")


        # Dados do documento para atualização no banco de dados
        doc_metadata = {
            'processo': doc_info.get('processo', ''), # Use .get for safety
            'referencia': doc_info.get('referencia', ''),
            'origem': doc_info.get('origem', ''),
            'data': doc_info.get('data', ''),
            'acto': doc_info.get('acto', ''),
            'tribunal': doc_info.get('tribunal', ''),
            'unidade': doc_info.get('unidade', ''),
            'especie': doc_info.get('especie', ''),
            'doc': file_url,
            'document_stored': True,
            'document_type': file_type,
            'document_size': os.path.getsize(file_path),
            'last_accessed': datetime.now().isoformat(),
            'user_id': user_id  # Adicionar o ID do usuário
        }

        # Para uploads de múltiplos documentos, adicionar metadados adicionais
        if is_multi_document:
            doc_metadata['doc_identifier'] = doc_info['doc_identifier']

        update_db_record(supabase, doc_metadata)

        return {
            'success': True,
            'file_url': file_url,
            'doc_metadata': doc_metadata
        }

    except Exception as e:
        logger.error(f"Erro geral na função upload_to_supabase: {str(e)}")
        import traceback
        logger.error(traceback.format_exc()) # Log full traceback
        return {
            'success': False,
            'error_message': str(e)
        }
    finally:
        # Remover o arquivo temporário
        if 'file_path' in locals() and os.path.exists(file_path):
             try:
                 os.unlink(file_path)
                 logger.debug(f"Arquivo temporário removido: {file_path}")
             except Exception as unlink_err:
                 logger.warning(f"Não foi possível remover o arquivo temporário {file_path}: {unlink_err}")

def upload_multiple_documents(download_result, doc_info, user_id, merge_pdfs=True):
    """
    Faz upload de múltiplos documentos para o Supabase.
    Opcionalmente combina múltiplos PDFs em um único arquivo.
    """
    if not download_result.get('multi_document', False) or not download_result.get('all_documents'):
        # Não é um resultado de múltiplos documentos, tratar como documento único
        return upload_to_supabase(download_result['file_path'], download_result['file_type'], doc_info, user_id)
    
    # Lista de documentos baixados
    pdf_documents = []
    non_pdf_documents = []
    
    # Separar PDFs de outros tipos de documentos
    for doc_data in download_result['all_documents']:
        if doc_data['success']:
            if doc_data['file_type'].lower() == 'pdf':
                pdf_documents.append(doc_data)
            else:
                non_pdf_documents.append(doc_data)
    
    # Se temos PDFs e a opção de merge está ativa
    if pdf_documents and merge_pdfs and len(pdf_documents) > 1:
        # Extrair caminhos dos PDFs
        pdf_paths = [doc['file_path'] for doc in pdf_documents]
        
        # Mesclar os PDFs em um único arquivo
        merged_pdf_path = merge_pdf_documents(pdf_paths)
        
        if merged_pdf_path:
            logger.info(f"PDFs mesclados com sucesso: {merged_pdf_path}")
            
            # Criar informações de documento para o PDF mesclado
            merged_doc_info = doc_info.copy()
            merged_doc_info['doc_identifier'] = "merged_pdf"
            
            # Fazer upload do PDF mesclado
            upload_result = upload_to_supabase(merged_pdf_path, 'pdf', merged_doc_info, user_id)
            
            if upload_result['success']:
                logger.info(f"PDF mesclado enviado para o Supabase: {upload_result['file_url']}")
                
                # Atualizar metadados
                upload_result['doc_metadata']['merged_from'] = len(pdf_documents)
                
                # Upload dos documentos não-PDF separadamente, se houver
                additional_docs = []
                for doc_data in non_pdf_documents:
                    non_pdf_result = upload_to_supabase(doc_data['file_path'], doc_data['file_type'], doc_data, user_id)
                    if non_pdf_result['success']:
                        additional_docs.append(non_pdf_result['doc_metadata'])
                
                # Incluir informações sobre documentos adicionais
                if additional_docs:
                    upload_result['additional_docs'] = additional_docs
                    upload_result['doc_metadata']['additional_docs'] = json.dumps(
                        [doc['doc'] for doc in additional_docs]
                    )
                
                return upload_result
            else:
                logger.error(f"Falha ao enviar PDF mesclado: {upload_result.get('error_message')}")
                # Continuar com o upload individual como fallback
        else:
            logger.error("Falha ao mesclar PDFs, continuando com upload individual")
    
    # Se chegamos aqui, ou não temos PDFs para mesclar, ou falhou o merge, ou merge=False
    # Vamos fazer o upload individual dos documentos
    
    # Lista de documentos enviados com sucesso
    uploaded_docs = []
    primary_url = None
    
    # Processar cada documento
    for index, doc_data in enumerate(download_result['all_documents']):
        if doc_data['success']:
            # Fazer upload deste documento
            upload_result = upload_to_supabase(doc_data['file_path'], doc_data['file_type'], doc_data, user_id)
            
            if upload_result['success']:
                uploaded_docs.append(upload_result['doc_metadata'])
                
                # O primeiro upload bem-sucedido se torna a URL principal do documento
                if primary_url is None:
                    primary_url = upload_result['file_url']
    
    # Se nenhum documento foi enviado com sucesso
    if not uploaded_docs:
        return {
            'success': False,
            'error_message': "Falha ao enviar qualquer documento"
        }
    
    # Criar uma string JSON com todas as URLs dos documentos
    all_documents_json = json.dumps([doc['doc'] for doc in uploaded_docs])
    
    # Criar metadados para atualização do banco de dados
    combined_metadata = {
        'processo': doc_info['processo'],
        'referencia': doc_info['referencia'],
        'doc': primary_url,  # URL do documento principal
        'all_documents': all_documents_json,  # String JSON com todas as URLs dos documentos
        'document_stored': True,
        'document_type': 'multi',  # Tipo especial para múltiplos documentos
        'document_count': len(uploaded_docs),
        'total_documents': download_result['total_documents'],
        'merged': False,  # Indicar que não foi feito merge
        'last_accessed': datetime.now().isoformat()
    }
    
    return {
        'success': True,
        'file_url': primary_url,
        'doc_metadata': combined_metadata,
        'all_documents': uploaded_docs
    }

def check_document_exists(supabase, referencia):
    """Verifica se já existe uma pasta para esta referência no Supabase."""
    try:
        # Sanitizar a referência
        referencia = sanitize_filename(referencia)
        
        # Listar os arquivos no bucket para verificar se a pasta existe
        result = supabase.storage.from_(SUPABASE_BUCKET_NAME).list(referencia)
        
        # Se a lista não estiver vazia, a pasta existe e contém arquivos
        if result and len(result) > 0:
            logger.info(f"Documento com referência {referencia} já existe no Supabase. Pulando processamento.")
            return True
                
        # Nenhum documento encontrado para esta referência
        return False
        
    except Exception as e:
        # Se ocorrer um erro (por exemplo, pasta não existe), consideramos que o documento não existe
        logger.warning(f"Erro ao verificar existência do documento {referencia}: {str(e)}")
        return False

def document_manager(driver, supabase, user_id):
    try:
        # Extrair URLs de documentos
        document_data = get_document_urls(driver)
        
        if not document_data:
            logger.warning("Nenhum documento encontrado.")
            return
        
        logger.info(f"Foram encontrados {len(document_data)} documentos.")
            
        # Para cada documento, verificar se já existe e, caso contrário, processar
        for doc_info in document_data:
            logger.info(f"Processando documento: {doc_info['acto']} - {doc_info['referencia']}")
            
            # Verificar se o documento já existe no Supabase
            referencia_sanitized = sanitize_filename(doc_info['referencia'])
            document_exists = False
            existing_doc_url = None
            
            try:
                # Listar os arquivos no bucket para verificar se a pasta existe
                result = supabase.storage.from_(SUPABASE_BUCKET_NAME).list(referencia_sanitized)
                
                # Se a lista não estiver vazia, o documento existe
                if result and len(result) > 0:
                    document_exists = True
                    # Obter a URL do documento existente (primeiro arquivo na pasta)
                    file_name = result[0]["name"]
                    existing_doc_url = supabase.storage.from_(SUPABASE_BUCKET_NAME).get_public_url(
                        f"{referencia_sanitized}/{file_name}"
                    )
                    logger.info(f"Documento com referência {doc_info['referencia']} já existe no Supabase.")
            except Exception as e:
                logger.warning(f"Erro ao verificar existência do documento {doc_info['referencia']}: {str(e)}")
            
            if document_exists and existing_doc_url:
                logger.info(f"Usando URL do documento existente: {existing_doc_url}")
                
                # Atualizar o campo doc para esta notificação
                doc_metadata = {
                    'referencia': doc_info['referencia'],
                    'doc': existing_doc_url,
                    'document_stored': True,
                    'document_type': 'shared',
                    'last_accessed': datetime.now().isoformat(),
                    'user_id': user_id  # Adicionar o ID do usuário
                }
                
                # Atualizar o registro no banco de dados
                update_db_record(supabase, doc_metadata)
                
                # Log para o usuário
                print(f"\nURL do documento atualizada com link compartilhado:")
                print(f"Processo: {doc_info['processo']}")
                print(f"Referência: {doc_info['referencia']}")
                print(f"Ato: {doc_info['acto']}")
                print(f"URL compartilhada: {existing_doc_url}")
                print("-" * 50)
                
                continue
            
            # Se chegou aqui, o documento não existe e precisa ser processado
            # Baixar o documento
            download_result = download_document(driver, doc_info)
            
            if download_result['success']:
                logger.info(f"Documento(s) baixado(s) com sucesso")
                
                # Verificar se é um caso de múltiplos documentos
                if download_result.get('multi_document', False):
                    # Upload de múltiplos documentos, com opção de mesclar PDFs
                    upload_result = upload_multiple_documents(download_result, doc_info, user_id, merge_pdfs=True)
                    
                    if upload_result['success']:
                        # Verificar se houve mesclagem de PDF
                        if upload_result['doc_metadata'].get('merged_from'):
                            logger.info(f"PDF mesclado enviado para o Supabase com {upload_result['doc_metadata']['merged_from']} documentos. URL: {upload_result['file_url']}")
                            
                            # Para o teste, mostrar o resultado
                            print(f"\nMúltiplos PDFs mesclados com sucesso:")
                            print(f"Processo: {doc_info['processo']}")
                            print(f"Referência: {doc_info['referencia']}")
                            print(f"Ato: {doc_info['acto']}")
                            print(f"Documentos mesclados: {upload_result['doc_metadata']['merged_from']}")
                            print(f"URL do PDF mesclado: {upload_result['file_url']}")
                            
                            # Se houver documentos adicionais não-PDF
                            if 'additional_docs' in upload_result:
                                print(f"Documentos adicionais não-PDF: {len(upload_result['additional_docs'])}")
                            
                            print("-" * 50)
                        else:
                            logger.info(f"Múltiplos documentos enviados para o Supabase. Principal: {upload_result['file_url']}")
                            
                            # Para o teste, mostrar o resultado
                            print(f"\nMúltiplos documentos processados com sucesso:")
                            print(f"Processo: {doc_info['processo']}")
                            print(f"Referência: {doc_info['referencia']}")
                            print(f"Ato: {doc_info['acto']}")
                            print(f"Total de documentos: {upload_result['doc_metadata'].get('document_count', 0)}/{upload_result['doc_metadata'].get('total_documents', 0)}")
                            print(f"URL principal: {upload_result['file_url']}")
                            print("-" * 50)
                    else:
                        logger.error(f"Falha no upload para o Supabase: {upload_result.get('error_message')}")
                else:
                    # Upload para o Supabase (documento único)
                    upload_result = upload_to_supabase(
                        download_result['file_path'],
                        download_result['file_type'],
                        doc_info,
                        user_id
                    )
                    
                    if upload_result['success']:
                        logger.info(f"Documento enviado para o Supabase: {upload_result['file_url']}")
                        
                        # Para o teste, mostrar o resultado
                        print(f"\nDocumento processado com sucesso:")
                        print(f"Processo: {doc_info['processo']}")
                        print(f"Referência: {doc_info['referencia']}")
                        print(f"Ato: {doc_info['acto']}")
                        print(f"URL do documento: {upload_result['file_url']}")
                        print("-" * 50)
                    else:
                        logger.error(f"Falha no upload para o Supabase: {upload_result.get('error_message')}")
            else:
                logger.error(f"Falha ao baixar documento: {download_result.get('error_message')}")
        
        logger.info("Script de teste concluído com sucesso!")
    
    except Exception as e:
        logger.error(f"Erro durante a execução do script: {str(e)}")
    finally:
        logger.info("Processo concluído")
