#!/bin/bash
# Salve como setup-local.sh

# Criar diretório para logs
mkdir -p logs

# Verificar se o arquivo .env existe
if [ ! -f backend/.env ]; then
    echo "Criando arquivo .env a partir do exemplo"
    cp backend/.env.example backend/.env
    echo "Por favor, edite o arquivo backend/.env com suas configurações"
    exit 1
fi

# Construir e iniciar containers
echo "Construindo e iniciando containers Docker..."
docker-compose build
docker-compose up -d

# Verificar status
echo "Verificando status dos containers..."
docker-compose ps

echo "Aplicação iniciada! Acesse:"
echo "- Frontend: http://localhost:3000"
echo "- Backend API: http://localhost:8000"
echo "Para ver logs: docker-compose logs -f"