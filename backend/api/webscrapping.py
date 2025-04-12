from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime
from supabase import create_client, Client
from .models import CitiusAccount
import os
import logging
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from django.conf import settings
import boto3
from botocore.exceptions import ClientError
import requests
import uuid
import tempfile
from urllib.parse import urlparse
from pathlib import Path
from .documentmanager import document_manager
from django.utils import timezone


# Set up logging
logger = logging.getLogger(__name__)

# Import your Django models
def get_chrome_driver(options=None):
    """Create and return a Chrome WebDriver with specified options"""
    if options is None:
        options = Options()
        options.add_argument('--headless')  # Run in headless mode (no UI)
        options.add_argument('--disable-gpu')  # Disable GPU acceleration
        options.add_argument('--no-sandbox')  # Disable sandboxing for security
        options.page_load_strategy = "eager"  # Try "normal" or "none" if needed
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-browser-side-navigation')
        
    # Use WebDriver Manager for driver compatibility
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_ACCESS_KEY  # Only two arguments needed for the Supabase client
)

def format_date(date_str):
    """Convert date string from DD-MM-YYYY to YYYY-MM-DD for database"""
    if not date_str:
        return datetime.now().strftime('%Y-%m-%d')
    
    try:
        day, month, year = date_str.split('-')
        return f"{year}-{month}-{day}"
    except:
        return datetime.now().strftime('%Y-%m-%d')

def safe_text(text):
    if isinstance(text, str):
        return text.replace("-", "/")  # Usando hífen não-quebrável (non-breaking hyphen)
    return text

def send_email(subject, body, recipient_data):
    """
    Send a professional HTML email using AWS SES with responsive design and formatting
    
    Args:
        subject (str): Email subject
        body (str): Raw notification text content
        recipient_data (dict): Dictionary containing primary and additional emails
    """
    import boto3
    from botocore.exceptions import ClientError
    import os
    import logging
    from datetime import datetime
    import re
    
    logger = logging.getLogger(__name__)
    
    # Lista para armazenar todos os emails de destino
    all_recipient_emails = []
    
    # Processar email principal
    primary_email = recipient_data.get('primary')
    if primary_email and isinstance(primary_email, dict) and 'data' in primary_email:
        primary_data = primary_email['data']
        if isinstance(primary_data, list) and len(primary_data) > 0:
            primary = primary_data[0].get('email')
            if primary and isinstance(primary, str) and '@' in primary:
                all_recipient_emails.append(primary)

    # Processar emails adicionais
    additional_emails = recipient_data.get('additional')
    if additional_emails and isinstance(additional_emails, dict) and 'data' in additional_emails:
        for email_obj in additional_emails['data']:
            email = email_obj.get('email')
            if email and isinstance(email, str) and '@' in email:
                all_recipient_emails.append(email)
                
    # Se não houver emails válidos, registre erro e retorne
    if not all_recipient_emails:
        logger.error(f"Nenhum email válido encontrado para envio: {recipient_data}")
        return False
    
    # Remove duplicatas
    all_recipient_emails = list(set(all_recipient_emails))
    
    logger.info(f"Enviando email para {len(all_recipient_emails)} destinatários: {all_recipient_emails}")
    
    # Create SES client
    client = boto3.client(
        'ses',
        aws_access_key_id=os.getenv("aws_access_key_id"),
        aws_secret_access_key=os.getenv("aws_secret_access_key"),
        region_name="eu-north-1"
    )
    
    # Format current date
    current_date = datetime.now().strftime("%d/%m/%Y")
    
    # Parse notifications text and create table rows
    notifications = []
    if "novas notificações:" in body:
        lines = body.split("\n\n")[1].strip().split("\n")
        for line in lines:
            # Parse notification line with regex - agora com campos adicionais
            # Update the regex pattern to capture all four groups
            match = re.match(r"Responsável - (.*?) - (.*?) - (.*?) - (.*?) - (.*?) - (.*?) - (.*)", line)
            if match:
                advogado, especie, acto, tribunal, unidade, origem, data = match.groups()
                notifications.append({
                    
                    "advogado": advogado.strip(),
                    "especie": especie.strip(),
                    "acto": acto.strip(),
                    "tribunal": tribunal.strip(),
                    "unidade": unidade.strip(),
                    "origem": origem.strip(),
                    "data": data.strip()
                })
    
    # Create HTML table rows
    table_rows = ""
    for i, notif in enumerate(notifications):
        bg_color = "#f2f7ff" if i % 2 == 0 else "#ffffff"
        table_rows += f"""
        <tr style="background-color: {bg_color};">
            <td style="padding: 12px; border-bottom: 1px solid #e1e4e8; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word; max-width: 0; white-space: normal; ">{safe_text(notif['advogado'])}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e1e4e8; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word; max-width: 0; white-space: normal;">{safe_text(notif['especie'])}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e1e4e8; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word; max-width: 0; white-space: normal;">{safe_text(notif['acto'])}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e1e4e8; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word; max-width: 0; white-space: normal;">{safe_text(notif['tribunal'])}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e1e4e8; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word; max-width: 0; white-space: normal;">{safe_text(notif['unidade'])}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e1e4e8; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word; max-width: 0; white-space: normal;">{safe_text(notif['origem'])}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e1e4e8; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word; max-width: 0; white-space: normal;">{safe_text(notif['data'])}</td>
        </tr>
        """
    
    # Create HTML email content with responsive design
    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{subject}</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
            body {{
                font-family: 'Roboto', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
                background-color: #f5f7fa;
            }}
            .container {{
                margin: 0 auto;
                padding: 20px;
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                padding: 20px 0;
                text-align: center;
                border-bottom: 1px solid #e1e4e8;
                margin-bottom: 20px;
            }}
            .logo {{
                max-width: 180px;
                height: auto;
            }}
            .content {{
                padding: 0 20px;
            }}
            .notification-count {{
                font-size: 18px;
                font-weight: 500;
                margin-bottom: 20px;
                color: #2d3748;
            }}
            .table-container {{
                overflow-x: auto;
                margin-bottom: 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
                table-layout: fixed;
            }}
            th {{
                background-color: #1a56db;
                color: white;
                font-weight: 500;
                text-align: left;
                padding: 12px;
                font-size: 13px;
                overflow: hidden;
            }}
            td {{
                font-size: 12px;
                padding: 12px;
                border-bottom: 1px solid #e1e4e8;
                word-wrap: break-word;
                overflow-wrap: break-word;
                word-break: break-word;
                vertical-align: top;
                max-width: 0; /* Forces cell to respect width constraints */
            }}
            table td {{
                font-size: 12px;
                padding: 12px;
                border-bottom: 1px solid #e1e4e8;
                word-wrap: break-word;
                overflow-wrap: break-word;
                word-break: break-word;
                vertical-align: top;
                max-width: 0;
                white-space: normal !important; /* Forçar quebra de linha */

            }}
            .footer {{
                text-align: center;
                padding-top: 20px;
                border-top: 1px solid #e1e4e8;
                color: #718096;
                font-size: 14px;
            }}
            @media screen and (max-width: 800px) {{
                .container {{
                    width: 100%;
                    border-radius: 0;
                }}
                table {{
                    display: block;
                    overflow-x: auto;
                }}
                td {{
                font-size: 10px;
                }}
            }}
            /* Ajuste de largura para 7 colunas */
            table th:nth-child(1), table td:nth-child(1) {{ width: 8%; }}  /* advogado */
            table th:nth-child(2), table td:nth-child(2) {{ width: 15%; }} /* especie */
            table th:nth-child(3), table td:nth-child(3) {{ width: 10%; }} /* acto */
            table th:nth-child(4), table td:nth-child(4) {{ width: 25%; }} /* tribunal */
            table th:nth-child(5), table td:nth-child(5) {{ width: 25%; }} /* unidade */
            table th:nth-child(6), table td:nth-child(6) {{ width: 7%; }}  /* origem */
            table th:nth-child(7), table td:nth-child(7) {{ width: 10%; }} /* data */
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <!-- Logo placeholder - replace with your actual logo URL -->
                <h2 style="color: #1a56db; margin: 0;">Notificações Citius</h2>
                <p style="color: #718096; margin: 5px 0 0 0;">Data: {current_date}</p>
            </div>
            
            <div class="content">
                <p class="notification-count">Tem {len(notifications)} novas notificações:</p>
                
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Responsável</th>
                                <th>Espécie</th>
                                <th>Acto</th>
                                <th>Tribunal</th>
                                <th>Unidade</th>
                                <th>Origem</th>
                                <th>Data</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>
                
                <p style="margin-top: 20px;">Para mais detalhes, acesse a sua conta na plataforma Citius.</p>
            </div>
            
            <div class="footer">
                <p>Este é um email automático. Por favor, não responda a esta mensagem.</p>
                <p>&copy; {datetime.now().year} Soft Solutions. Todos os direitos reservados.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Create text version as backup for email clients that don't support HTML
    text_body = f"Notificações Citius - {current_date}\n\n"
    text_body += f"Tem {len(notifications)} novas notificações:\n\n"
    for notif in notifications:
        text_body += f"Responsável: {notif['advogado']}\n"
        text_body += f"Espécie: {notif['especie']}\n"
        text_body += f"Acto: {notif['acto']}\n"
        text_body += f"Tribunal: {notif['tribunal']}\n"
        text_body += f"Unidade: {notif['unidade']}\n"
        text_body += f"Origem: {notif['origem']}\n"
        text_body += f"Data: {notif['data']}\n\n"
    text_body += "Para mais detalhes, acesse a sua conta na plataforma Citius.\n\n"
    text_body += f"© {datetime.now().year} Soft Solutions. Todos os direitos reservados."
    
    try:
        '''# Send email with both HTML and plain text versions
        response = client.send_email(
            Source='no-reply@softsolutions.com.pt',
            Destination={'ToAddresses': all_recipient_emails},  # Agora usando a lista de todos os emails
            Message={
                'Subject': {'Data': subject},
                'Body': {
                    'Text': {'Data': text_body},
                    'Html': {'Data': html_content}
                }
            }
        )'''
        logger.info(f"Enviando email para: {all_recipient_emails}")
        #logger.info(f"Email enviado com sucesso: {response['MessageId']} para {len(all_recipient_emails)} destinatários")
        return True
    except ClientError as e:
        logger.error(f"Falha ao enviar o email: {str(e)}")
        return False

def scrape_citius_data():
    """Scrape data from Citius for all active accounts"""

    active_accounts = CitiusAccount.objects.filter(is_active=True, advogado="Tiago")
    
    if not active_accounts.exists():
        logger.warning("No active Citius accounts found. Please add accounts in the management interface.")
        return 0
    
    # Create the Chrome driver
    driver = get_chrome_driver()
    driver.implicitly_wait(60)
    driver.set_page_load_timeout(300)  # Increase timeout to 5 minutes

    total_insert_count = 0
    
    try: 
        try:
            logger.info("Attempting to create Supabase client...")
            supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)
            logger.info("Successfully created Supabase client")
        except Exception as e:
            logger.error(f"Failed to create Supabase client: {str(e)}")
            raise
        
        # Process each account
        for account in active_accounts:
            logger.info(f"Processing account: {account.username}")
            
            try:
                # Process this specific account
                insert_count, new_not, email_data = process_account(driver, supabase, account)
                total_insert_count += insert_count
                
                # Update last_used timestamp
                account.last_used = datetime.now()
                account.save()
                
            except Exception as e:
                logger.error(f"Error processing account {account.username}: {str(e)}")
                # Continue with next account
                
            if new_not:
                # Prepare the email subject and body content
                subject = "Novas notificações Citius"
                body = f"Tem {len(new_not)} novas notificações:\n\n"
                
                # Add details of each new notification to the body
                for notification in new_not:
                    # "acto", "tribunal" e "unid orgânica";
                    body += f"Responsável - {safe_text(notification['advogado'])} - {safe_text(notification['especie'])} - {safe_text(notification['acto'])} - {safe_text(notification['tribunal'])} - {safe_text(notification['unidade'])} - {safe_text(notification['origem'])} - {safe_text(notification['data'])}\n"
                
                # Send the email with new notifications to todos os emails associados
                send_email(subject, body, email_data)
                
        return total_insert_count, new_not
        
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}")
        raise
    finally:
        # Always close the driver
        driver.quit()
        logger.info("Closed WebDriver")


def process_account(driver, supabase, account):
    """Process a single Citius account with document download and storage"""
    insert_count = 0
    new_not = []  # Initialize it early so it's always defined
    
    try:
        logger.info("trying to get login")
        # Open the login page with explicit timeout
        driver.set_page_load_timeout(45)  # Timeout mais curto
        driver.get("https://citius.tribunaisnet.mj.pt/habilus/myhabilus/Login.aspx")
        time.sleep(5)
        logger.info(f"Navigated to Citius login page for {account.username}")

        # Find username/email input field and enter credentials
        username_field = driver.find_element(By.ID, "txtUserName")
        username_field.clear()  # Clear any existing text
        username_field.send_keys(account.username)
        time.sleep(1)  # Small pause after typing username

        # Find password input field and enter password
        password_field = driver.find_element(By.ID, "txtUserPass")
        password_field.clear()  # Clear any existing text
        password_field.send_keys(account.password)
        time.sleep(1)  # Small pause after typing password

        # Submit the form explicitly using the submit button instead of Enter key
        try:
            submit_button = driver.find_element(By.ID, "LoginButton")
            submit_button.click()
        except:
            # Fall back to Enter key if button not found
            password_field.send_keys(Keys.RETURN)
            
        logger.info(f"Login submitted for {account.username}")
        
        # Check for login errors with increased timeout
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-danger, #errorMessage"))
            )
            error_element = driver.find_element(By.CSS_SELECTOR, ".alert-danger, #errorMessage")
            logger.error(f"Login failed for {account.username}: {error_element.text}")
            return 0, new_not, None  # Return the initialized empty list
        except:
            # No error found, continue
            logger.info("No login errors detected, continuing")
        
        # Wait for page to load after login with explicit timeout
        logger.info("Waiting for page to load after login...")
        
        # Use a more reliable way to determine if login was successful
        try:
            WebDriverWait(driver, 45).until(
                EC.presence_of_element_located((By.ID, "ctl00_ctl00_Conteudo_Menu1_NotificacoesCitacoesAlert1_lnkMessage"))
            )
            logger.info(f"Successfully logged in to Citius with {account.username}")
        except Exception as e:
            logger.error(f"Timeout waiting for login to complete: {str(e)}")
            # Take a screenshot for debugging
            try:
                screenshot_file = f"/tmp/citius_login_timeout_{account.username}_{int(time.time())}.png"
                driver.save_screenshot(screenshot_file)
                logger.info(f"Saved screenshot to {screenshot_file}")
            except Exception as ss_error:
                logger.error(f"Failed to save screenshot: {str(ss_error)}")
            
            # Return early with empty results
            return 0, new_not, None
        
        # Wait for notifications link and click
        logger.info("Finding and clicking notifications link...")
        link_field = driver.find_element(By.ID, "ctl00_ctl00_Conteudo_Menu1_NotificacoesCitacoesAlert1_lnkMessage")
        driver.execute_script("arguments[0].click();", link_field)  # Use JavaScript click which can be more reliable
        logger.info("Clicked on notifications link")
        time.sleep(5)  # Added wait after clicking
        
        # Click on "Todas" to view all notifications with explicit wait
        logger.info("Waiting for 'Todas' link...")
        try:
            linkTodas_field = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.ID, "ctl00_ctl00_Conteudo_cpHabilus_spanTodas"))
            )
            driver.execute_script("arguments[0].click();", linkTodas_field)  # Use JavaScript click
            logger.info("Clicked on 'Todas' to view all notifications")
        except Exception as e:
            logger.error(f"Timeout waiting for 'Todas' link: {str(e)}")
            # Continue anyway, maybe we can still get data
        
        # Give page time to load
        logger.info("Waiting for notifications to load...")
        time.sleep(10)
        
        # Get all notification rows with a try/except
        try:
            rows = driver.find_elements(By.XPATH, '//tr[@style="color:#000066;height:20px;"]')
            logger.info(f"Found {len(rows)} notification rows for {account.username}")
        except Exception as e:
            logger.error(f"Error finding notification rows: {str(e)}")
            rows = []  # Use empty list if no rows found
        
        # Define database field names
        db_fields = [
            "origem", "data", "acto", "doc", 
            "tribunal", "unidade", "processo", "especie", "referencia", "user_id", "created_at"
        ]
        logger.info(f"Database fields: {db_fields}")
        # Loop through each row and extract data
        for row in rows:
            try:
                # Find all cells within this row and ignore the first one (checkbox)
                cells = row.find_elements(By.TAG_NAME, 'td')[1:]  # Skip the first td

                # Extract the text from each cell
                row_data = [cell.text.strip() for cell in cells]
                
                # Create the dictionary for the row data with proper field names
                row_dict = dict(zip(db_fields, row_data))
                
                # Convert the date format for the database
                row_dict["data"] = format_date(row_dict["data"])
                
                # Add the advogado field from the account
                row_dict["advogado"] = account.advogado
                
                row_dict["user_id"] = account.user_id
                logger.info(f"Added user_id to row_dict: {row_dict['user_id']}")

                row_dict["created_at"] = timezone.now().isoformat()

                # Find the popup link and extract the URL
                doc_url = "em breve"
                row_dict["doc"] = doc_url
                
                # Check if record already exists to avoid duplicates
                existing = (
                    supabase.table('api_processo')
                    .select('*')
                    .eq('referencia', row_dict['referencia'])
                    .eq('user_id', row_dict['user_id'])
                    .execute()
                )                
                
                if len(existing.data) == 0:
                    # Insert new record
                    result = supabase.table('api_processo').insert(row_dict).execute()
                    logger.info(row_dict)
                    new_not.append(row_dict)
                    if result.data:
                        insert_count += 1
                        logger.info(f"Inserted notification with referência: {row_dict['referencia']} for {account.advogado}")
                else:
                    logger.info(f"Record already exists for referência: {row_dict['referencia']}, exiting count: {len(existing.data)}")
                

            except Exception as e:
                logger.error(f"Error processing row: {str(e)}")
        
        logger.info(f"Account {account.username} processing completed. Inserted {insert_count} new notifications.")
        primary_email = {"data": [{"email": account.email}]} if account.email else {"data": []}
        logger.info(f"Primary email for account {account.username}: {primary_email}")
        
        # Get additional emails using Django directly instead of Supabase query
        from .models import CitiusAccountEmail
        additional_email_objects = CitiusAccountEmail.objects.filter(account=account, is_active=True)
        additional_emails = {
            "data": [{"email": email_obj.email} for email_obj in additional_email_objects]
        }
        logger.info(f"Additional emails for account {account.username}: {additional_emails}")
        
        # Create email data object with the correct emails for this account
        email_data = {'primary': primary_email, 'additional': additional_emails}
        
        return insert_count, new_not, email_data
        
    except Exception as e:
        logger.error(f"Error processing account {account.username}: {str(e)}")
        return 0, new_not, None

def test_citius_login(username, password):
    """Test Citius login credentials without scraping data"""
    # Initialize options for the Chrome driver
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Create the Chrome driver
    driver = get_chrome_driver()
    driver.implicitly_wait(10)
    
    try:
        # Open the login page
        driver.get("https://citius.tribunaisnet.mj.pt/habilus/myhabilus/Login.aspx")
        logger.info(f"Navigated to Citius login page for test: {username}")

        # Find username/email input field and enter credentials
        username_field = driver.find_element(By.ID, "txtUserName")
        username_field.clear()
        username_field.send_keys(username)

        # Find password input field and enter password
        password_field = driver.find_element(By.ID, "txtUserPass")
        password_field.clear()
        password_field.send_keys(password)

        password_field.send_keys(Keys.RETURN)  # Press Enter
        
        # Check for login errors
        try:
            # Wait briefly for error message
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-danger, #errorMessage"))
            )
            error_element = driver.find_element(By.CSS_SELECTOR, ".alert-danger, #errorMessage")
            error_message = error_element.text
            return False, error_message
        except:
            # Try to find an element that would only be present after successful login
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "ctl00_ctl00_Conteudo_Menu1_NotificacoesCitacoesAlert1_lnkMessage"))
                )
                return True, "Login successful"
            except:
                return False, "Login failed - could not verify successful login"
    
    except Exception as e:
        return False, f"Login test error: {str(e)}"
    finally:
        driver.quit()