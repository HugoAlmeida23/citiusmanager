#!/bin/bash
# Salve como deploy-ec2.sh

# Configurações
APP_DIR="/home/ubuntu/citius-app"

# Atualizar sistema
echo "Atualizando o sistema..."
sudo apt update && sudo apt upgrade -y

# Instalar Docker e Docker Compose se não estiverem instalados
if ! command -v docker &> /dev/null; then
    echo "Instalando Docker..."
    sudo apt install -y docker.io
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker $USER
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Instalando Docker Compose..."
    sudo apt install -y docker-compose
fi

# Criar diretório da aplicação
echo "Criando diretório da aplicação..."
mkdir -p $APP_DIR
cd $APP_DIR

# Copiar arquivos
# Nota: Este script presume que você já copiou os arquivos para o servidor
# Use scp ou rsync para copiar os arquivos antes de executar este script

# Configurar variáveis de ambiente
if [ ! -f backend/.env ]; then
    echo "ERRO: Arquivo backend/.env não encontrado!"
    echo "Por favor, crie o arquivo .env com as configurações necessárias."
    exit 1
fi

# Construir e iniciar containers
echo "Construindo e iniciando containers Docker..."
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Configurar para iniciar na reinicialização
echo "Configurando para iniciar na reinicialização..."
(crontab -l 2>/dev/null; echo "@reboot cd $APP_DIR && docker-compose -f docker-compose.prod.yml up -d") | crontab -

echo "Deploy concluído! A aplicação está rodando em:"
echo "- Frontend: http://$(curl -s http://checkip.amazonaws.com):3000"
echo "- Backend API: http://$(curl -s http://checkip.amazonaws.com):8000"
echo "Para ver logs: docker-compose -f docker-compose.prod.yml logs -f"