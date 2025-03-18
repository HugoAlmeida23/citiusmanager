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

# Set up logging
logger = logging.getLogger(__name__)

# Import your Django models
def get_chrome_driver(options=None):
    """Create and return a Chrome WebDriver with specified options"""
    if options is None:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
    
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

def scrape_citius_data():
    """Scrape data from Citius for all active accounts"""

    active_accounts = CitiusAccount.objects.filter(is_active=True)
    
    if not active_accounts.exists():
        logger.warning("No active Citius accounts found. Please add accounts in the management interface.")
        return 0
    
    # Initialize options for the Chrome driver
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.page_load_strategy = "eager"  # Try "normal" or "none" if needed

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
                insert_count, new_not, email = process_account(driver, supabase, account)
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
                    body += f"Responsável - {notification['advogado']} - {notification['especie']} - {notification['origem']} - {notification['data']}\n"
                
                # Send the email with new notifications
                send_email(subject, body, email)
                
        return total_insert_count, new_not
        
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}")
        raise
    finally:
        # Always close the driver
        driver.quit()
        logger.info("Closed WebDriver")

def send_email(subject, body, email):
    """Send an email using AWS SES"""
    client = boto3.client(
        'ses',
        aws_access_key_id=os.getenv("aws_access_key_id"),
        aws_secret_access_key=os.getenv("aws_secret_access_key"),
        region_name="eu-north-1"
    )
    logger.info(email)
    # Ensure email is extracted as a string from Supabase response
    if hasattr(email, 'data') and isinstance(email.data, list) and len(email.data) > 0:
        email = email.data[0].get('email', None)  # Extract email from first item in list

    if not isinstance(email, str):
        logger.error(f"Invalid email format after extraction: {email}")
        return  # Stop execution if email is still invalid

    
    logger.debug(f"Email data type: {type(email)}, value: {email}")

    try:
        response = client.send_email(
            Source='no-reply@softsolutions.com.pt',  # Your verified sender email
            Destination={
                'ToAddresses': [
                    email,  # Recipient email address
                ],
            },
            Message={
                'Subject': {
                    'Data': subject,
                },
                'Body': {
                    'Text': {
                        'Data': body,
                    },
                },
            }
        )
        logger.info(f"Email sent successfully: {response['MessageId']}")
    except ClientError as e:
        logger.error(f"Failed to send email: {str(e)}")

def download_and_store_document(driver, document_url):
    """
    Opens the document URL in a new tab, downloads the document, and returns the document URL.
    
    Args:
        driver: Selenium WebDriver instance
        document_url: URL of the document page
    
    Returns:
        The extracted download URL, or None if not found.
    """
    logger.info(f"Accessing document page: {document_url}")

    try:
        # Open the document URL in a new tab
        driver.execute_script(f"window.open('{document_url}', '_blank');")

        # Switch to the new tab (index -1 gets the last opened tab)
        driver.switch_to.window(driver.window_handles[-1])

        # Wait for the page to load and ensure the download link is available
        download_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ucActoView_hlDownload"))
        )

        # Extract the download link
        download_url = download_element.get_attribute("href")

        if download_url:
            logger.info(f"Found document download link: {download_url}")
            
            # Close the current tab (the new tab) after extracting the document URL
            driver.close()

            # Switch back to the original tab (main tab)
            driver.switch_to.window(driver.window_handles[0])
            
            return download_url
        else:
            logger.warning("Download link not found.")
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            return None

    except Exception as e:
        logger.error(f"Error extracting download link: {str(e)}")
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        return None


    
def process_account(driver, supabase, account):
    """Process a single Citius account with document download and storage"""
    insert_count = 0
    new_not = []
    
    try:
        # Open the login page
        driver.get("https://citius.tribunaisnet.mj.pt/habilus/myhabilus/Login.aspx")
        logger.info(f"Navigated to Citius login page for {account.username}")

        # Find username/email input field and enter credentials
        username_field = driver.find_element(By.ID, "txtUserName")
        username_field.clear()  # Clear any existing text
        username_field.send_keys(account.username)

        # Find password input field and enter password
        password_field = driver.find_element(By.ID, "txtUserPass")
        password_field.clear()  # Clear any existing text
        password_field.send_keys(account.password)

        password_field.send_keys(Keys.RETURN)  # Press Enter
        logger.info(f"Logged in to Citius with {account.username}")
        
        # Check for login errors
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-danger, #errorMessage"))
            )
            error_element = driver.find_element(By.CSS_SELECTOR, ".alert-danger, #errorMessage")
            logger.error(f"Login failed for {account.username}: {error_element.text}")
            return 0, [], None
        except:
            # No error found, continue
            pass
        
        # Wait for notifications link and click
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "ctl00_ctl00_Conteudo_Menu1_NotificacoesCitacoesAlert1_lnkMessage"))
        )
        link_field = driver.find_element(By.ID, "ctl00_ctl00_Conteudo_Menu1_NotificacoesCitacoesAlert1_lnkMessage")
        link_field.click()
        logger.info("Navigated to notifications page")
        
        # Click on "Todas" to view all notifications
        linkTodas_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "ctl00_ctl00_Conteudo_cpHabilus_spanTodas"))
        )
        linkTodas_field.click()
        logger.info("Clicked on 'Todas' to view all notifications")
        
        # Give page time to load
        time.sleep(3)
        
        prelink = "https://citius.tribunaisnet.mj.pt"
        
        # Get all notification rows
        rows = driver.find_elements(By.XPATH, '//tr[@style="color:#000066;height:20px;"]')
        logger.info(f"Found {len(rows)} notification rows for {account.username}")
        
        # Define database field names
        db_fields = [
            "origem", "data", "acto", "doc", 
            "tribunal", "unidade", "processo", "especie", "referencia", "user_id"
        ]
        
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

                # Find the popup link and extract the URL
                doc_url = None
                try:
                    # Look specifically for an <a> tag with an onclick attribute containing 'popupWindow'
                    popup_links = row.find_elements(By.XPATH, './/a[contains(@onclick, "popupWindow")]')
                    if popup_links:
                        popup_link = popup_links[0]
                        onclick_attr = popup_link.get_attribute('onclick')
                        # Extract URL from onclick attribute
                        url_start = onclick_attr.find("popupWindow('") + 13  # Length of "popupWindow('"
                        url_end = onclick_attr.find("'", url_start)
                        extracted_url = onclick_attr[url_start:url_end]
                        # Combine with prelink
                        doc_url = prelink + extracted_url
                    else:
                        logger.warning("Could not find popup link for this row")
                except Exception as e:
                    logger.error(f"Error finding popup link: {str(e)}")
                
                # Check if record already exists to avoid duplicates
                existing = (
                    supabase.table('api_processo')
                    .select('*')
                    .eq('referencia', row_dict['referencia'])
                    .eq('user_id', row_dict['user_id'])
                    .execute()
                )                
                
                email = supabase.table('api_citiusaccount').select('email').eq('username',account.username).execute() 
                
                if len(existing.data) == 0:
                    # If we have a document URL, download and store it
                    if doc_url:
                        try:
                            # Download and store the document
                            stored_url = download_and_store_document(
                                driver, 
                                doc_url
                            )
                            # Update the doc field with the Supabase storage URL
                            row_dict["doc"] = stored_url
                        except Exception as e:
                            logger.error(f"Error downloading document: {str(e)}")
                            # Fallback to original URL
                            row_dict["doc"] = doc_url
                    
                    # Insert new record
                    result = supabase.table('api_processo').insert(row_dict).execute()
                    logger.info(row_dict)
                    new_not.append(row_dict)
                    if result.data:
                        insert_count += 1
                        logger.info(f"Inserted notification with referência: {row_dict['referencia']} for {account.advogado}")
            except Exception as e:
                logger.error(f"Error processing row: {str(e)}")
        
        logger.info(f"Account {account.username} processing completed. Inserted {insert_count} new notifications.")
        return insert_count, new_not, email
        
    except Exception as e:
        logger.error(f"Error processing account {account.username}: {str(e)}")
        # Re-raise to be caught by the main function
        raise
    
    # Add this function to your scraping.py or webscrapping.py file
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