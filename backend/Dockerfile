FROM python:3.10-slim

WORKDIR /app

# Instalar dependências do Chrome e Selenium para webscraping
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    xvfb \
    libgbm1 \
    libnss3 \
    libxi6 \
    libgconf-2-4 \
    libfontconfig1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*


# Use a stable ChromeDriver version as fallback
RUN wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver.zip \
    && chmod +x /usr/local/bin/chromedriver

# Copiar requirements.txt
COPY requirements.txt .

# Instalar pacotes Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código do projeto
COPY . .

# Porta para a aplicação Django
EXPOSE 8000

# Define o comando padrão para o container
CMD ["sh", "-c", "python manage.py makemigrations && python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
