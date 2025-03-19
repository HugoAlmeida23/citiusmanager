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
    if options is None:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        # Add these new options
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-application-cache')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--disable-infobars')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--log-level=3')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        # Set lower resource usage
        options.page_load_strategy = "eager"
        
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
    """Scrape data from Citius for all active accounts in batches"""
    active_accounts = CitiusAccount.objects.filter(is_active=True)
    
    if not active_accounts.exists():
        logger.warning("No active Citius accounts found.")
        return 0, []
    
    total_insert_count = 0
    all_new_not = []
    
    # Process accounts in batches of 3
    batch_size = 3
    for i in range(0, len(active_accounts), batch_size):
        batch_accounts = active_accounts[i:i+batch_size]
        
        # Process this batch of accounts
        driver = get_chrome_driver()
        driver.implicitly_wait(30)  # Reduced from 60
        driver.set_page_load_timeout(180)  # Reduced from 300
        
        try:
            supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)
            
            for account in batch_accounts:
                try:
                    insert_count, new_not, email = process_account(driver, supabase, account)
                    total_insert_count += insert_count
                    if new_not:
                        all_new_not.extend(new_not)
                        # Send email immediately for each account
                        if new_not:
                            subject = "Novas notificações Citius"
                            body = f"Tem {len(new_not)} novas notificações:\n\n"
                            for notification in new_not:
                                body += f"Responsável - {notification['advogado']} - {notification['especie']} - {notification['origem']} - {notification['data']}\n"
                            send_email(subject, body, email)
                    
                    account.last_used = datetime.now()
                    account.save()
                except Exception as e:
                    logger.error(f"Error processing account {account.username}: {str(e)}")
        except Exception as e:
            logger.error(f"Error during batch processing: {str(e)}")
        finally:
            driver.quit()
            # Force garbage collection
            import gc
            gc.collect()
            # Give system time to recover
            time.sleep(5)
    
    return total_insert_count, all_new_not

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
    
def process_account(driver, supabase, account):
    """Process a single Citius account with optimized processing"""
    insert_count = 0
    new_not = []
    
    try:
        # Open the login page with fewer retries
        max_retries = 2
        for attempt in range(max_retries):
            try:
                driver.get("https://citius.tribunaisnet.mj.pt/habilus/myhabilus/Login.aspx")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Retry page load: {str(e)}")
                time.sleep(2)
        
        # Faster element location with shorter timeouts
        try:
            username_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "txtUserName"))
            )
            username_field.clear()
            username_field.send_keys(account.username)
            
            password_field = driver.find_element(By.ID, "txtUserPass")
            password_field.clear()
            password_field.send_keys(account.password)
            password_field.send_keys(Keys.RETURN)
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return 0, [], None
            
        # Rest of your function with optimized waits...
        # [Rest of your existing code with reduced timeouts]
        
        # Process fewer rows if needed to prevent timeouts
        max_rows_to_process = 50  # Adjust based on your needs
        rows = driver.find_elements(By.XPATH, '//tr[@style="color:#000066;height:20px;"]')
        rows = rows[:max_rows_to_process]
        
        # Continue with your existing processing logic...
        
    except Exception as e:
        logger.error(f"Error processing account {account.username}: {str(e)}")
        raise
    
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