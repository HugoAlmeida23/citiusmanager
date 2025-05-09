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
import requests
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

def download_document(driver, doc_info, max_retries=3):
    """
    Attempts to download document(s) from a notification.
    Supports multiple documents/attachments with adaptive handling based on page structure.
    Includes retry mechanism for error handling.
    """
    origem = doc_info.get('origem', 'Desconhecido')
    logger.info(f"Attempting to download document(s) for: {doc_info.get('acto', 'N/A')} - {doc_info.get('referencia', 'N/A')} - Origin: {origem}")

    current_url = driver.current_url
    original_timeout_value = 30  # Default in seconds
    
    try:
        for retry_attempt in range(max_retries):
            try:
                if retry_attempt > 0:
                    logger.info(f"Retry attempt {retry_attempt}/{max_retries} for downloading documents")
                    # Navigate back to the document URL on retry attempts
                    driver.get(doc_info['doc_url'])
                    time.sleep(3)  # Wait for page to load
                    
                new_timeout_seconds = 60 if origem == "Mandatário" else 30
                if hasattr(driver, 'set_page_load_timeout'):
                    driver.set_page_load_timeout(new_timeout_seconds)
                else:
                    logger.warning("driver.set_page_load_timeout not available. Page load timeout not changed.")

                if retry_attempt == 0:  # Only log this on first attempt
                    logger.info(f"Navigating to document popup URL: {doc_info['doc_url']}")
                    driver.get(doc_info['doc_url'])
                    
                time.sleep(3) # General pause for initial load

                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                except TimeoutException as e:
                    logger.warning(f"Timeout waiting for body element after navigation: {str(e)}")

                downloaded_documents = []
                all_document_urls = []
                primary_dropdown_processed_successfully = False

                # ====== STEP 1: TRY PRIMARY DROPDOWN APPROACH ======
                try:
                    primary_dropdown_locator = (By.ID, "dropDocs")
                    initial_primary_dropdown_element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(primary_dropdown_locator)
                    )
                    logger.info(f"Found primary dropdown (ID: dropDocs) for {origem} document.")

                    primary_options_data = []
                    for option_element in initial_primary_dropdown_element.find_elements(By.TAG_NAME, "option"):
                        primary_options_data.append({
                            "value": option_element.get_attribute('value'),
                            "text": option_element.text.strip()
                        })

                    if not primary_options_data:
                        logger.info("Primary dropdown (ID: dropDocs) exists but has no options.")
                    else:
                        total_primary_docs = len(primary_options_data)
                        logger.info(f"Found {total_primary_docs} document(s)/attachment(s) in primary dropdown.")

                        for index in range(total_primary_docs):
                            doc_data = primary_options_data[index]
                            doc_value = doc_data["value"]
                            doc_name = doc_data["text"]
                            
                            logger.info(f"Processing primary dropdown item {index + 1}/{total_primary_docs}: '{doc_name}' (Value: '{doc_value}')")
                            
                            try:
                                current_primary_dropdown_element = WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located(primary_dropdown_locator)
                                )
                                select = Select(current_primary_dropdown_element)
                                
                                if doc_value is not None and doc_value != "":
                                    select.select_by_value(doc_value)
                                else:
                                    logger.warning(f"Primary option '{doc_name}' has an empty or no 'value' attribute. Attempting selection by visible text.")
                                    try:
                                        select.select_by_visible_text(doc_name)
                                    except NoSuchElementException:
                                        logger.warning(f"Could not select '{doc_name}' by visible text, trying by index {index}.")
                                        select.select_by_index(index)
                                
                                time.sleep(3) # Wait for selection to potentially update page

                                secondary_docs_result = process_secondary_dropdown(driver, doc_info, doc_name, index)
                                
                                if secondary_docs_result and secondary_docs_result.get('documents'):
                                    downloaded_documents.extend(secondary_docs_result['documents'])
                                    all_document_urls.extend(secondary_docs_result.get('urls', []))
                                    logger.info(f"Processed {len(secondary_docs_result['documents'])} secondary documents for '{doc_name}'.")
                                    primary_dropdown_processed_successfully = True # Mark that at least one primary item led to docs
                                else:
                                    logger.info(f"No secondary documents found or processed for '{doc_name}'.")
                                    
                            except StaleElementReferenceException as sere:
                                logger.error(f"StaleElementReferenceException while processing primary dropdown item {index + 1} ('{doc_name}'): {sere}")
                                driver.save_screenshot(f"/tmp/error_primary_stale_{doc_info.get('referencia', 'unknown')}_{index+1}.png")
                                # Skip this item and continue with the next
                                continue 
                            except Exception as e:
                                logger.error(f"Error processing primary dropdown option {index + 1} ('{doc_name}'): {type(e).__name__} - {str(e)}")
                                driver.save_screenshot(f"/tmp/error_primary_option_{doc_info.get('referencia', 'unknown')}_{index+1}.png")
                                continue
                
                except (NoSuchElementException, TimeoutException):
                    logger.info(f"No primary dropdown (ID: dropDocs) found for {origem} document. Will try alternative approaches.")
                

                # ====== STEP 2: IF PRIMARY APPROACH FAILED/YIELDED NO DOCS, AND ORIGEM IS MANDATARIO ======
                if not downloaded_documents and origem == "Mandatário": # Check if primary dropdown didn't yield docs
                    logger.info("Primary approach yielded no documents for Mandatário, or dropdown not found. Trying specialized Mandatário handler.")
                    # Pass the max_retries parameter to handle_mandatario_document
                    mandatario_docs_result = handle_mandatario_document(driver, doc_info, max_retries=2)
                    if mandatario_docs_result and mandatario_docs_result.get('success'):
                        logger.info("Specialized Mandatário handler was successful.")
                        # If handler was successful, break out of retry loop
                        return mandatario_docs_result 
                    else:
                        logger.info("Specialized Mandatário handler did not succeed or find documents.")
                
                # ====== STEP 3: TRY SECONDARY DROPDOWN DIRECTLY (if no docs from primary/Mandatario specific) ======
                if not downloaded_documents:
                    logger.info("No documents from primary/Mandatário specific. Trying secondary dropdown directly.")
                    secondary_docs_direct = process_secondary_dropdown(driver, doc_info) # No primary_doc_name
                    if secondary_docs_direct and secondary_docs_direct.get('documents'):
                        downloaded_documents.extend(secondary_docs_direct['documents'])
                        all_document_urls.extend(secondary_docs_direct.get('urls', []))
                        logger.info(f"Processed {len(secondary_docs_direct['documents'])} documents from direct secondary dropdown.")
                
                # ====== STEP 4: TRY DIRECT DOWNLOAD LINK (if still no documents) ======
                if not downloaded_documents:
                    logger.info("Still no documents. Trying direct download link (ucActoView_hlDownload).")
                    try:
                        download_link_element = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.ID, "ucActoView_hlDownload"))
                        )
                        pdf_url = download_link_element.get_attribute('href')
                        if pdf_url:
                            logger.info(f"Direct download link found: {pdf_url}")
                            doc_result = download_single_document(driver, pdf_url, "principal_direct", doc_info)
                            if doc_result and doc_result.get('success'):
                                downloaded_documents.append(doc_result)
                                all_document_urls.append(doc_result['doc_url'])
                                logger.info("Direct download successful via ucActoView_hlDownload.")
                        else:
                            logger.warning("Direct download link (ucActoView_hlDownload) found, but href is empty.")
                    except (NoSuchElementException, TimeoutException):
                        logger.warning("No direct download link (ucActoView_hlDownload) found.")
                
                # ====== STEP 5: LAST RESORT - TRY IFRAME EXTRACTION (if still no documents) ======
                if not downloaded_documents:
                    logger.info("As a last resort, trying to extract from iframe.")
                    iframe_docs_result = extract_from_iframe(driver, doc_info)
                    if iframe_docs_result and iframe_docs_result.get('success'):
                        logger.info("Iframe extraction was successful.")
                        # Break out of retry loop
                        return iframe_docs_result
                    else:
                        logger.info("Iframe extraction did not succeed or find documents.")
                
                # --- CHECK IF WE HAVE DOCUMENTS BEFORE CONTINUING ---
                if downloaded_documents:
                    # Success! We have documents, so break out of retry loop
                    logger.info(f"Downloaded {len(downloaded_documents)} document(s), breaking retry loop")
                    break
                else:
                    logger.warning(f"No documents downloaded in attempt {retry_attempt+1}/{max_retries}")
                    # Continue to next retry iteration
                    
            except Exception as e:
                logger.error(f"Critical error during document download attempt {retry_attempt+1}/{max_retries} for {doc_info.get('referencia', 'N/A')}: {type(e).__name__} - {str(e)}")
                driver.save_screenshot(f"/tmp/critical_download_error_{doc_info.get('referencia', 'unknown')}_{retry_attempt+1}.png")
                # Continue to next retry iteration
                
        # At this point, we've either succeeded or exhausted our retries
        try:
            # Navigate back to the original page
            logger.info(f"Returning to original page: {current_url}")
            driver.get(current_url)
        except Exception as nav_error:
            logger.error(f"Could not navigate back to original page: {nav_error}")
                
        # --- CONCLUDE AND RETURN ---
        if downloaded_documents:
            main_doc_result = downloaded_documents[0].copy()
            main_doc_result['all_documents'] = downloaded_documents
            main_doc_result['all_document_urls'] = all_document_urls
            main_doc_result['multi_document'] = len(downloaded_documents) > 1
            main_doc_result['total_documents'] = len(downloaded_documents)
            main_doc_result['origem'] = origem
            # Basic metadata structure, can be expanded by the caller or upload function
            main_doc_result['doc_metadata'] = {
                'processo': doc_info.get('processo', ''),
                'referencia': doc_info.get('referencia', ''),
                'doc': main_doc_result.get('doc_url'), 
                'document_stored': False, 
                'document_type': main_doc_result.get('file_type', 'unknown'),
                'origem': origem,
                'download_attempted': True,
                'last_accessed': datetime.now().isoformat()
            }
            logger.info(f"Successfully downloaded {len(downloaded_documents)} document(s) for {doc_info.get('referencia', 'N/A')}.")
            return main_doc_result
        else:
            # Fallback for Mandatário if NO documents were downloaded after all retries
            if origem == "Mandatário":
                logger.warning("No documents downloaded for Mandatário after all attempts. Using fallback (saving popup URL).")
                fallback_metadata = {
                    'processo': doc_info.get('processo', ''), 'referencia': doc_info.get('referencia', ''),
                    'doc': doc_info['doc_url'], 'document_stored': False, 'document_type': 'html_link',
                    'origem': origem, 'download_attempted': True, 'download_successful': False,
                    'last_accessed': datetime.now().isoformat()
                }
                return {
                    'success': True, 'is_fallback': True, 'file_path': None, 'file_type': 'html_link',
                    'processo': doc_info['processo'], 'referencia': doc_info['referencia'],
                    'doc_identifier': f"{origem.lower()}_fallback_link", 'doc_url': doc_info['doc_url'],
                    'all_documents': [], 'all_document_urls': [doc_info['doc_url']],
                    'multi_document': False, 'total_documents': 0, 'origem': origem,
                    'doc_metadata': fallback_metadata
                }
            else:
                logger.error(f"No documents were successfully downloaded for {origem} ({doc_info.get('referencia', 'N/A')}) after {max_retries} attempts.")
                return {'success': False, 'error_message': f"No documents downloaded for {origem} ({doc_info.get('referencia', 'N/A')}) after {max_retries} attempts"}
    finally:
        if hasattr(driver, 'set_page_load_timeout'):
            try:
                # Restore original timeout
                driver.set_page_load_timeout(original_timeout_value / 1000 if isinstance(original_timeout_value, (int, float)) and original_timeout_value > 1000 else original_timeout_value)
            except Exception as te:
                logger.warning(f"Could not restore page load timeout: {te}")

def handle_mandatario_document(driver, doc_info, max_retries=3):
    """
    Specialized handler for Mandatário documents which have a different structure.
    Focuses on finding the secondary dropdown and download links directly.
    Implements retry mechanism to handle stale element references.
    """
    logger.info("Using specialized Mandatário document handler")
    downloaded_documents = []
    all_document_urls = []
    
    for retry_attempt in range(max_retries):
        try:
            if retry_attempt > 0:
                logger.info(f"Retry attempt {retry_attempt} for Mandatário document handling")
                # Refresh the page on retry attempts to get fresh elements
                driver.refresh()
                time.sleep(3)  # Wait for page to reload
            
            # In Mandatário documents, we should focus directly on the secondary dropdown
            secondary_dropdown = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "ucActoView_ucDocumentosAto_ddlDocumentos"))
            )
            
            # Get all options from the secondary dropdown
            secondary_options = secondary_dropdown.find_elements(By.TAG_NAME, "option")
            secondary_values = [option.get_attribute('value') for option in secondary_options]
            secondary_texts = [option.text for option in secondary_options]
            
            total_secondary_docs = len(secondary_values)
            logger.info(f"Found {total_secondary_docs} document(s) in Mandatário secondary dropdown")
            
            # Store document processing status to identify failures
            processed_docs = [False] * total_secondary_docs
            
            # Process each document in the secondary dropdown
            for index, (doc_value, doc_name) in enumerate(zip(secondary_values, secondary_texts)):
                # Skip already processed documents on retries
                if processed_docs[index]:
                    logger.info(f"Document {index+1}/{total_secondary_docs}: {doc_name} already processed, skipping")
                    continue
                    
                logger.info(f"Processing Mandatário document {index+1}/{total_secondary_docs}: {doc_name}")
                
                try:
                    # Re-fetch the dropdown on each iteration to avoid stale references
                    secondary_dropdown = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "ucActoView_ucDocumentosAto_ddlDocumentos"))
                    )
                    
                    # Re-fetch all options
                    fresh_options = secondary_dropdown.find_elements(By.TAG_NAME, "option")
                    
                    # Ensure the index is still valid for the refreshed list
                    if index < len(fresh_options):
                        # Get current option and its value
                        current_option = fresh_options[index]
                        current_value = current_option.get_attribute('value')
                        current_text = current_option.text
                        
                        # Select this document in the dropdown
                        select = Select(secondary_dropdown)
                        select.select_by_value(current_value)
                        time.sleep(2)  # Wait for selection to load
                        
                        # Find download link for this document
                        download_link = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "ucActoView_hlDownload"))
                        )
                        
                        if download_link:
                            pdf_url = download_link.get_attribute('href')
                            logger.info(f"Download link found for {current_text}: {pdf_url}")
                            
                            # Create specific identifier for this document
                            doc_identifier = f"mandatario_{index+1}_{sanitize_filename(current_text)}"
                            
                            # Download this document
                            doc_result = download_single_document(driver, pdf_url, doc_identifier, doc_info)
                            
                            if doc_result['success']:
                                downloaded_documents.append(doc_result)
                                all_document_urls.append(doc_result['doc_url'])
                                logger.info(f"Mandatário document {index+1} downloaded successfully")
                                processed_docs[index] = True  # Mark as successfully processed
                            else:
                                logger.error(f"Failed to download Mandatário document {index+1}: {doc_result.get('error_message')}")
                        else:
                            logger.warning(f"No download link found for Mandatário document {current_text}")
                    else:
                        logger.warning(f"Index {index} is out of bounds for refreshed options list (length: {len(fresh_options)})")
                
                except StaleElementReferenceException as stale_err:
                    logger.error(f"Stale element reference error processing Mandatário document {index+1}: {stale_err}")
                    # Don't mark as processed, will retry in next iteration
                    driver.save_screenshot(f"/tmp/stale_error_mandatario_{doc_info.get('referencia', 'unknown')}_{index+1}.png")
                    # Break the inner loop to restart with fresh elements
                    break
                    
                except Exception as doc_error:
                    logger.error(f"Error processing Mandatário document {index+1}: {str(doc_error)}")
                    # Don't mark as processed, will retry in next iteration
                    continue
            
            # Check if all documents were processed
            if all(processed_docs):
                logger.info(f"All {total_secondary_docs} Mandatário documents processed successfully")
                # Exit retry loop if all documents were processed
                break
            elif downloaded_documents:
                # Some documents were downloaded, but not all - continue to next retry
                logger.warning(f"Processed {sum(processed_docs)}/{total_secondary_docs} Mandatário documents. Will retry remaining.")
            else:
                # No documents downloaded at all - try iframe approach before next retry
                logger.warning("No documents downloaded in Mandatário handler attempt")
        
        except Exception as e:
            logger.error(f"Error in Mandatário document handler (attempt {retry_attempt+1}/{max_retries}): {str(e)}")
            # Continue to next retry
            
    # End of retry loop
            
    # If we found documents, return results
    if downloaded_documents:
        logger.info(f"Successfully processed {len(downloaded_documents)} Mandatário documents")
        result = downloaded_documents[0].copy()
        result['all_documents'] = downloaded_documents
        result['all_document_urls'] = all_document_urls
        result['multi_document'] = len(downloaded_documents) > 1
        result['total_documents'] = len(downloaded_documents)
        result['mandatario_document'] = True
        return result
    else:
        # Try fallback to iframe approach
        logger.info("No documents downloaded via dropdown method, trying iframe fallback")
        iframe_docs = extract_from_iframe(driver, doc_info)
        if iframe_docs and iframe_docs.get('success'):
            return iframe_docs
        
        logger.warning("No documents downloaded in Mandatário handler after all attempts")
        return {'success': False, 'error_message': "No documents found in Mandatário handler"}
    
def extract_from_iframe(driver, doc_info):
    """
    Attempt to extract document URLs directly from the iframe.
    This is a fallback method for Mandatário documents when other approaches fail.
    """
    logger.info("Attempting to extract documents from iframe")
    downloaded_documents = []
    all_document_urls = []
    
    try:
        # Find the iframe that contains the document
        iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ucActoView_ifrmDoc"))
        )
        iframe_src = iframe.get_attribute('src')
        
        if iframe_src:
            logger.info(f"Found iframe source: {iframe_src}")
            
            # Check if iframe source is a direct PDF link
            if ".pdf" in iframe_src.lower() or "download" in iframe_src.lower():
                logger.info(f"Using iframe source as direct document: {iframe_src}")
                
                # Download using iframe source
                doc_result = download_single_document(driver, iframe_src, "iframe_pdf", doc_info)
                
                if doc_result['success']:
                    downloaded_documents.append(doc_result)
                    all_document_urls.append(doc_result['doc_url'])
                    logger.info("Document downloaded from iframe source")
            
            # Switch to the iframe to look for links inside
            try:
                driver.switch_to.frame(iframe)
                
                # Try to find document links inside the iframe
                doc_links = driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf') or contains(@href, 'download') or contains(@href, 'NotCitPdf')]")
                
                if doc_links:
                    for i, link in enumerate(doc_links):
                        try:
                            pdf_url = link.get_attribute('href')
                            if pdf_url:
                                logger.info(f"Found document link in iframe: {pdf_url}")
                                
                                # Download this document
                                doc_identifier = f"iframe_doc_{i+1}"
                                doc_result = download_single_document(driver, pdf_url, doc_identifier, doc_info)
                                
                                if doc_result['success']:
                                    downloaded_documents.append(doc_result)
                                    all_document_urls.append(doc_result['doc_url'])
                                    logger.info(f"Document {i+1} downloaded from iframe")
                        except Exception as link_error:
                            logger.error(f"Error processing iframe link {i+1}: {str(link_error)}")
                            continue
                else:
                    logger.warning("No document links found in iframe")
                
                # Switch back to default content
                driver.switch_to.default_content()
            
            except Exception as iframe_error:
                logger.error(f"Error accessing iframe content: {str(iframe_error)}")
                try:
                    driver.switch_to.default_content()
                except:
                    pass
        
        # If we found documents, return results
        if downloaded_documents:
            logger.info(f"Successfully extracted {len(downloaded_documents)} documents from iframe")
            result = downloaded_documents[0].copy()
            result['all_documents'] = downloaded_documents
            result['all_document_urls'] = all_document_urls
            result['multi_document'] = len(downloaded_documents) > 1
            result['total_documents'] = len(downloaded_documents)
            result['iframe_extracted'] = True
            return result
        else:
            logger.warning("No documents extracted from iframe")
            return {'success': False, 'error_message': "No documents found in iframe"}
    
    except Exception as e:
        logger.error(f"Error extracting from iframe: {str(e)}")
        return {'success': False, 'error_message': str(e)}

def process_secondary_dropdown(driver, doc_info, primary_doc_name=None, primary_index=None):
    """
    Process the secondary dropdown to find and download documents.
    Can be called directly or from within a primary dropdown loop.
    Handles stale element references by refreshing elements after each interaction.
    """
    downloaded_documents = []
    all_document_urls = []
    
    try:
        # Find the secondary dropdown
        secondary_dropdown = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ucActoView_ucDocumentosAto_ddlDocumentos"))
        )
        
        # Get all options from the secondary dropdown
        secondary_options = secondary_dropdown.find_elements(By.TAG_NAME, "option")
        
        # Store option values and texts in separate lists to avoid stale references
        secondary_values = []
        secondary_texts = []
        
        for option in secondary_options:
            try:
                secondary_values.append(option.get_attribute('value'))
                secondary_texts.append(option.text)
            except StaleElementReferenceException:
                # If element became stale while extracting attributes, break and try again
                logger.warning("Encountered stale element while preparing secondary dropdown options, refreshing elements")
                # Re-fetch elements
                secondary_dropdown = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "ucActoView_ucDocumentosAto_ddlDocumentos"))
                )
                secondary_options = secondary_dropdown.find_elements(By.TAG_NAME, "option")
                # Clear lists and start over
                secondary_values = []
                secondary_texts = []
                # Get all values and texts in one pass to minimize stale references
                for opt in secondary_options:
                    secondary_values.append(opt.get_attribute('value'))
                    secondary_texts.append(opt.text)
                break
        
        total_secondary_docs = len(secondary_values)
        if primary_doc_name:
            logger.info(f"Found {total_secondary_docs} documents in secondary dropdown for {primary_doc_name}")
        else:
            logger.info(f"Found {total_secondary_docs} documents in secondary dropdown")
        
        # Keep track of processed documents
        processed_docs = [False] * total_secondary_docs
        
        # Try up to 3 times to process all documents
        for retry in range(3):
            # Process each document in the secondary dropdown
            for sec_index in range(total_secondary_docs):
                # Skip already processed documents
                if processed_docs[sec_index]:
                    continue
                    
                try:
                    # Re-find the dropdown element for each iteration
                    secondary_dropdown = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "ucActoView_ucDocumentosAto_ddlDocumentos"))
                    )
                    
                    current_value = secondary_values[sec_index]
                    current_text = secondary_texts[sec_index]
                    
                    logger.info(f"Processing secondary document {sec_index+1}/{total_secondary_docs}: {current_text}")
                    
                    # Select this document in the dropdown
                    select = Select(secondary_dropdown)
                    select.select_by_value(current_value)
                    time.sleep(2)  # Wait for selection to load
                    
                    # Find download link for this document
                    download_link = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "ucActoView_hlDownload"))
                    )
                    
                    if download_link:
                        pdf_url = download_link.get_attribute('href')
                        logger.info(f"Download link found for {current_text}: {pdf_url}")
                        
                        # Create specific identifier for this document
                        if primary_doc_name:
                            doc_identifier = f"{primary_index+1}_{sanitize_filename(primary_doc_name)}_{sec_index+1}_{sanitize_filename(current_text)}"
                        else:
                            doc_identifier = f"{sec_index+1}_{sanitize_filename(current_text)}"
                        
                        # Download this document
                        doc_result = download_single_document(driver, pdf_url, doc_identifier, doc_info)
                        
                        if doc_result['success']:
                            downloaded_documents.append(doc_result)
                            all_document_urls.append(doc_result['doc_url'])
                            logger.info(f"Secondary document {sec_index+1} downloaded successfully")
                            processed_docs[sec_index] = True  # Mark as processed
                        else:
                            logger.error(f"Failed to download secondary document {sec_index+1}: {doc_result.get('error_message')}")
                    else:
                        logger.warning(f"No download link found for document {current_text}")
                
                except StaleElementReferenceException as stale_err:
                    logger.warning(f"Stale element reference while processing secondary document {sec_index+1}: {stale_err}")
                    # Don't mark as processed, will retry
                    break  # Break inner loop to refresh all elements
                    
                except Exception as doc_error:
                    logger.error(f"Error processing secondary document {sec_index+1}: {str(doc_error)}")
                    # Continue with next document
                    continue
            
            # Check if all documents have been processed
            if all(processed_docs):
                logger.info("All secondary documents processed successfully")
                break
            elif retry < 2:  # Don't log this on last iteration
                logger.info(f"Retry {retry+1}/3: Some secondary documents not processed, refreshing elements")
                # Refresh the page or elements before next retry
                try:
                    # Try refreshing the dropdown without reloading the page
                    secondary_dropdown = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "ucActoView_ucDocumentosAto_ddlDocumentos"))
                    )
                    time.sleep(1)
                except:
                    # If dropdown can't be found, we may need more aggressive refresh
                    pass
        
        # Return results
        if downloaded_documents:
            return {
                'documents': downloaded_documents,
                'urls': all_document_urls
            }
        else:
            return None
    
    except Exception as e:
        logger.error(f"Error processing secondary dropdown: {str(e)}")
        return None
               
def sanitize_filename(filename):
    """
    Sanitizes a filename to ensure it's safe for file systems.
    Removes invalid characters and normalizes unicode.
    """
    if not isinstance(filename, str):
        filename = str(filename)

    # Normalize unicode characters (e.g., 'á' -> 'a', 'ç' -> 'c')
    try:
        # NFKD decomposes characters into base char + combining marks
        normalized = unicodedata.normalize('NFKD', filename)
        # Encode to ASCII bytes, ignore characters that cannot be represented
        ascii_bytes = normalized.encode('ascii', 'ignore')
        # Decode back to a clean ASCII string
        ascii_string = ascii_bytes.decode('ascii')
    except Exception as e:
        # Fallback in case of unexpected normalization/encoding errors
        logger.warning(f"Unicode normalization error for '{filename}': {e}. Using basic sanitization.")
        # Basic fallback: remove common problematic chars
        ascii_string = re.sub(r'[^\x00-\x7F]+', '', filename)  # Remove non-ASCII

    # Replace disallowed characters with underscores
    # Allow letters, numbers, underscore, hyphen, period. Replace others.
    sanitized = ascii_string.replace('/', '_')
    sanitized = re.sub(r'[^\w\._-]', '_', sanitized)  # \w is alphanumeric + underscore

    # Clean up potential issues
    # Replace multiple consecutive underscores/hyphens/periods with a single underscore
    sanitized = re.sub(r'[_.-]+', '_', sanitized)
    # Remove leading/trailing underscores/hyphens/periods
    sanitized = sanitized.strip('_.-')

    # Handle edge case: empty filename after sanitization
    if not sanitized:
        sanitized = "sanitized_file"
        
    # Limit length to avoid extremely long filenames
    MAX_LEN = 100
    sanitized = sanitized[:MAX_LEN]

    return sanitized

def download_single_document(driver, pdf_url, doc_identifier, doc_info):
    """
    Downloads a single document from a direct URL.
    
    Args:
        driver: Selenium WebDriver instance
        pdf_url: URL to download the document from
        doc_identifier: Identifier for this specific document
        doc_info: Information about the parent notification
        
    Returns:
        Dictionary with download results
    """
    try:
        # Configure a requests session with the browser's cookies
        import requests
        session = requests.Session()
        cookies = driver.get_cookies()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        
        # Ensure URL is complete
        if not pdf_url.startswith('http'):
            base_url = "https://citius.tribunaisnet.mj.pt"
            if pdf_url.startswith('/'):
                pdf_url = base_url + pdf_url
            else:
                pdf_url = base_url + '/' + pdf_url
        
        # Download the document
        logger.info(f"Downloading document from: {pdf_url}")
        response = session.get(pdf_url, stream=True)
        
        if response.status_code == 200:
            # Check content type to determine file type
            content_type = response.headers.get('Content-Type', '')
            is_pdf = 'application/pdf' in content_type or '.pdf' in pdf_url.lower()
            file_suffix = '.pdf' if is_pdf else '.html'
            file_type = 'pdf' if is_pdf else 'html'
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as temp_file:
                for chunk in response.iter_content(chunk_size=1024):
                    temp_file.write(chunk)
                temp_path = temp_file.name
            
            logger.info(f"Document downloaded successfully as {file_type} to: {temp_path}")
            
            return {
                'success': True,
                'file_path': temp_path,
                'file_type': file_type,
                'processo': doc_info['processo'],
                'referencia': doc_info['referencia'],
                'doc_identifier': doc_identifier,
                'doc_url': pdf_url,
                'content_type': content_type
            }
        else:
            logger.error(f"Failed to download document, status code: {response.status_code}")
            return {
                'success': False,
                'error_message': f"HTTP Error: {response.status_code}"
            }
    except requests.exceptions.RequestException as re:
        logger.error(f"Request error downloading document: {str(re)}")
        return {
            'success': False,
            'error_message': f"Request error: {str(re)}"
        }
    except Exception as e:
        logger.error(f"Error downloading document: {str(e)}")
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
