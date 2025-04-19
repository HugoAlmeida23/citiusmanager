"""
Funções auxiliares para a integração Toggl-Notion
"""
import json
import os
import re
import requests
from base64 import b64encode
from datetime import datetime
from notion_client import Client
import tempfile
from pathlib import Path
import logging
logger = logging.getLogger(__name__)
# Função para extrair ID do Notion a partir da URL
def extrair_id(notion_database_id):
    padrao = r'\/([^\/\?]+)\?'
    resultado = re.search(padrao, notion_database_id)
    if resultado:
        return resultado.group(1)
    else:
        return notion_database_id  # Retorna o próprio ID se não for uma URL

# Função para formatar data
def format_date_string(date_str):
    try:
        # Converter de "YYYY-MM-DD HH:MM:SS" para "YYYY-MM-DD"
        if " " in date_str:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            return date_obj.strftime("%Y-%m-%d")
        return date_str  # Se já estiver no formato correto
    except Exception as e:
        print(f"Erro ao formatar data: {e}")
        return date_str

# Função para obter credenciais do arquivo info.json
def get_credentials():
    try:
        with open('info.json', 'r') as handler:
            info = json.load(handler)
        
        return {
            'email': info.get('email', ''),
            'password': info.get('password', ''),
            'token': info.get('token', ''),
            'workspace': info.get('workspace', '')
        }
    except Exception as e:
        print(f"Erro ao obter credenciais: {e}")
        return None

# Função para salvar as datas do último update
def write_dates_json(start_date, end_date):
    info = {
        "start": start_date,
        "end": end_date,
    }
    
    with open('lastupdate.json', 'w') as outfile:
        json.dump(info, outfile)

# Função para obter as datas do último update
def get_lastupdate():
    if os.path.exists('lastupdate.json'):
        with open('lastupdate.json', 'r') as handler:
            info = json.load(handler)
        
        start_date = info.get('start', None)
        end_date = info.get('end', None)
        
        return start_date, end_date
    else:
        return None, None

# Função para obter o resumo de projetos do Toggl
def post_project_summary(email, password, workspace_id, start_date, end_date):
    # Codifica as credenciais de autenticação para serem enviadas no cabeçalho Authorization
    auth_string = "{}:{}".format(email, password)
    auth_header = "Basic {}".format(b64encode(auth_string.encode()).decode("ascii"))

    # Define os dados a serem enviados no corpo da solicitação
    payload = {
        "start_date": start_date,
        "end_date": end_date
    }

    # Faz a solicitação POST para o endpoint fornecido
    response = requests.post(
        f'https://api.track.toggl.com/reports/api/v3/workspace/{workspace_id}/weekly/time_entries',
        json=payload,
        headers={'content-type': 'application/json', 'Authorization': auth_header}
    )

    # Verifica se a solicitação foi bem-sucedida e retorna os dados em formato JSON
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch project summary: {response.status_code}")
        return None

# Função para obter detalhes dos usuários
def get_user_details(email, password, workspace_id):
    auth_string = "{}:{}".format(email, password)
    auth_header = "Basic {}".format(b64encode(auth_string.encode()).decode("ascii"))
    
    url = f'https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/users'
    response = requests.get(url, headers={'content-type': 'application/json', 'Authorization': auth_header})
    
    if response.status_code == 200:  
        return response.json()
    else:
        print(f"Failed to fetch user details: {response.status_code}")
        return None

# Função para fazer consulta ao Toggl
def togll_run(start_date, end_date, valid_email, valid_password, workspace_id):
    # Chama a função toggl_search para obter os dados dos projetos do usuário
    toggl_data = toggl_search(start_date, end_date, valid_email, valid_password)
    print("Dados do toggl", toggl_data)
    # Verifica se os dados foram obtidos com sucesso
    if toggl_data is not None:
        # Lista para armazenar os dados dos projetos com os detalhes do cliente e os segundos reais
        processed_projects = []
        
        # Itera sobre os projetos e obtém os detalhes do cliente para cada projeto
        for project in toggl_data:
            print("Toggl data 123", toggl_data)
            client_id = project.get("client_id")
            print("Client ID", client_id)
            if client_id is not None:
                client_details = get_client_details(valid_email, valid_password, workspace_id, client_id)
                if client_details is not None:
                    # Salva o nome do projeto, o nome do cliente e os segundos reais em variáveis
                    project_name = project.get("name")
                    client_name = client_details.get("name")
                    actual_seconds = project.get("actual_seconds")
                    
                    # Adiciona os dados processados à lista
                    processed_projects.append({
                        "project_name": project_name,
                        "client_name": client_name,
                        "actual_seconds": actual_seconds
                    })
                
                    
                else:
                    print(f"Failed to fetch client details for project:", project.get("name"))
            else:
                print(f"Client ID not found for project:", project.get("name"))
        
        # Exibe os dados processados
        print("Processed Projects:", processed_projects)
        
    else:
        print("Failed to fetch user projects data. Exiting...")
        
    return processed_projects

# Função para obter detalhes do cliente
def get_client_details(email, password, workspace_id, client_id):
    # Codifica as credenciais de autenticação para serem enviadas no cabeçalho Authorization
    auth_string = "{}:{}".format(email, password)
    auth_header = "Basic {}".format(b64encode(auth_string.encode()).decode("ascii"))
    
    # Faz a solicitação GET para a API do Toggl para obter os detalhes do cliente pelo ID
    url = f'https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/clients/{client_id}'
    response = requests.get(url, headers={'content-type': 'application/json', 'Authorization': auth_header})
    
    # Verifica se a solicitação foi bem sucedida e retorna os dados em formato JSON
    if response.status_code == 200:  
        return response.json()
    else:
        print(f"Failed to fetch client details:", response.status_code)
        return None

# Função para obter o nome do projeto
def get_project_name(email, password, workspace_id, project_id):
    auth_string = "{}:{}".format(email, password)
    auth_header = "Basic {}".format(b64encode(auth_string.encode()).decode("ascii"))
    
    url = f'https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/projects/{project_id}'
    response = requests.get(url, headers={'content-type': 'application/json', 'Authorization': auth_header})
    
    if response.status_code == 200:  
        return response.json()
    else:
        print(f"Failed to fetch project details:", response.status_code)
        return None

# Função para obter o nome do usuário
def get_user_name(user_id, data):
    for user in data:
        if user.get("id") == user_id:
            return user.get("fullname")
    return None

# Função para corrigir os segundos no formato esperado
def make_secondsright(toggl_data):
    for item in toggl_data:
        seconds = item['seconds']
        total_seconds = sum(seconds)
        item['seconds'] = total_seconds
        
    return toggl_data

# Função para obter o nome do cliente
def get_client_name(project_name, toggl_original_data):
    for item in toggl_original_data:
        if project_name and item.get("project_name") == project_name.get("name"):
            return item.get("client_name")
    return None

# Função para obter projetos do Toggl
def toggl_search(start_date, end_date, email, password):
    def get_user_projects(email, password):
        # Codifica as credenciais de autenticação
        auth_string = "{}:{}".format(email, password)
        auth_header = "Basic {}".format(b64encode(auth_string.encode()).decode("ascii"))
        
        # Faz a solicitação GET para a API do Toggl
        response = requests.get('https://api.track.toggl.com/api/v9/me/projects', 
                                headers={'Content-Type': 'application/json', 'Authorization': auth_header})
        
        # Verifica se a solicitação foi bem sucedida
        if response.status_code == 200:
            projects = response.json()
            print(projects)
            # Extracting only desired variables from each project
            extracted_projects = []
            for project in projects:
                extracted_project = {
                    "name": project["name"],
                    "client_id": project["client_id"],
                    "actual_seconds": project["actual_seconds"]
                }
                extracted_projects.append(extracted_project)
            
            return extracted_projects
        else:
            print(f"Failed to fetch projects:", response.status_code)
            return None

    # Obtém os projetos do usuário e imprime os resultados
    projects = get_user_projects(email, password)
    if projects is not None:
        print("User Projects:", projects)
        
    return projects

# Função para processar dados do Toggl
def process_toggl_data(toggl_data, data, toggl_original_data, valid_email, valid_password, workspace_id):
    toggl_data = make_secondsright(toggl_data)
    if toggl_data is not None:
        processed_toggl_data = []
        
        for project in toggl_data:
            project_id = project.get("project_id")
            #já temos a data dos user ids, vamos comparar o user id dessa data com o user id daqui, e pegar no nome dele
            user_id = project.get("user_id")
            if project_id is not None:
                project_name = get_project_name(valid_email, valid_password, workspace_id, project_id)
                user_name = get_user_name(user_id, data)
                client_name = get_client_name(project_name, toggl_original_data)
                if project_name is not None:
                    if project_name is not None:
                        project_name = project_name.get("name")
                        user_id = user_name
                        seconds = project.get("seconds")
                    
                    # Adiciona os dados processados à lista
                    processed_toggl_data.append({
                        "project_name": project_name,
                        "client_name": client_name,
                        "user_id": user_id,
                        "seconds": seconds
                    }) 
                    
                else:
                    print("Failed to fetch client details for project:", project.get("project_id"))
            else:
                print("Project ID not found for project:", project.get("project_id"))
            
    else:
        print("toggl_data is None")
                    
    return processed_toggl_data

# Função para somar strings de tempo
def sum_time_string(x, y_seconds):
    # Convertendo a string X em horas, minutos e segundos
    hours, minutes, seconds = map(int, x.split(":"))

    # Convertendo a string Y (em segundos) em horas, minutos e segundos
    y_hours = y_seconds // 3600
    remaining_seconds = y_seconds % 3600
    y_minutes = remaining_seconds // 60
    y_seconds = remaining_seconds % 60

    # Somando as horas, minutos e segundos
    total_hours = hours + y_hours
    total_minutes = minutes + y_minutes
    total_seconds = seconds + y_seconds

    # Ajustando caso os segundos ou minutos excedam 59
    total_minutes += total_seconds // 60
    total_seconds %= 60
    total_hours += total_minutes // 60
    total_minutes %= 60

    # Formatando a string de resultado
    result = "{:02d}:{:02d}:{:02d}".format(total_hours, total_minutes, total_seconds)
    print(result)
    return result

# Função para obter o ID da página do Notion
def getPageID(client, notion_databaseid):
    try:
        logger.info(f"Attempting to query Notion database: {notion_databaseid}")
        db_rows = client.databases.query(database_id=notion_databaseid)
        
        # Salvar os resultados em um arquivo temporário para debug
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json') as temp_file:
            json.dump(db_rows, temp_file)
            db_rows_file = temp_file.name
        
        simple_rows = []
        
        for row in db_rows['results']:
            client_name = safe_get(row, 'properties.Cliente.title.0.text.content')
            project = safe_get(row, 'properties.Processo.rich_text.0.text.content')
            user_id = safe_get(row, 'properties.Responsável.rich_text.0.text.content')
            hours = safe_get(row, 'properties.Tempo.rich_text.0.text.content')
            url = safe_get(row, 'url')
            
            match = re.search(r'(?<=-)[a-f0-9]{32}', url)

            if match:
                id_from_url = match.group(0)
                print("ID extraído da URL:", id_from_url)
            else:
                print("ID não encontrado na URL")
                
            simple_rows.append({
                'client': client_name,
                'projeto': project,
                'horas': hours,
                'user_id': user_id,
                'url': id_from_url
            })
        
        # Salvar as linhas simplificadas em um arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json') as temp_file:
            json.dump(simple_rows, temp_file)
            simple_rows_file = temp_file.name
        
        return simple_rows, simple_rows_file
    except Exception as e:
        logger.error(f"Notion API error: {str(e)}")
        # Check if it's an access error
        if "Make sure the relevant pages and databases are shared" in str(e):
            raise Exception("This database is not shared with your Notion integration. Please share it through the Notion interface.")
        elif "Could not find database" in str(e):
            raise Exception("The database ID is invalid. Please check your database ID and try again.")
        else:
            raise

# Função para verificar o valor de forma segura em dicionários aninhados
def safe_get(data, dot_chained_keys):
    keys = dot_chained_keys.split('.')
    for key in keys:
        try:
            if isinstance(data, list):
                if key.isdigit():  # Check if the key is an integer
                    data = data[int(key)]
                else:
                    return None  # Key is not an integer, cannot access list element
            else:
                data = data[key]
        except (KeyError, TypeError, IndexError):
            return None
    return data

# Função para atualizar uma linha no Notion
def write_1row(client, notion_database_id, client_name, hours, project_name, url):
    page_id = url  # preciso de fazer a comparação dos projetos e encontrar o url

    # Define the properties you want to update
    properties = {
        #'Cliente': {'title': [{'text': {'content': client_name}}]},
        #'Projeto': {'rich_text': [{'text': {'content': project_name}}]},
        'Tempo': {'rich_text': [{'text': {'content': hours}}]},
    }

    # Update the page
    client.pages.update(page_id=page_id, properties=properties)

# Função para inserir dados do Toggl no Notion
def write_from_toggl(objetsToggl, client, notion_database_id, notion_info):
    for project in objetsToggl:
        client_name = project.get("client_name")
        project_name = project.get("project_name")
        user_id = project.get("user_id")
        hours = project.get("seconds")
        
        # Obter o URL correspondente do notioninfo
        url = get_url_from_notioninfo(project_name, user_id, notion_info)
        horas = get_hours_from_notion(project_name, user_id, notion_info)
        
        if horas is not None:
            horas = sum_time_string(horas, hours)
            print(horas)
        
        if horas is None:
            print(f"Projeto '{project_name}' não encontrado no arquivo notioninfo")
            continue
        
        if url:
            write_1row(client, notion_database_id, client_name, horas, project_name, url)
        else:
            print(f"Projeto '{project_name}' não encontrado no arquivo notioninfo")

# Função para obter URL do notioninfo
def get_url_from_notioninfo(project_name, user_id, notion_info):
    for item in notion_info:
        if item["projeto"] == project_name and item["user_id"] == user_id:
            return item["url"]
    return None  # Retorna None se o projeto não for encontrado

# Função para obter horas do Notion
def get_hours_from_notion(project_name, user_id, notion_info):
    for item in notion_info:
        if item["projeto"] == project_name and item["user_id"] == user_id:
            return item["horas"]
    return None  # Retorna None se o projeto não for encontrado