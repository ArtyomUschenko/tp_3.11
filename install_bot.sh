#!/bin/bash

# Сделайте скрипт исполняемым: chmod +x install_bot.sh

#/path/to/installation/
#├── install_bot.sh
#├── bot_files.tar.gz
#│   ├── pip_venv/
#│   │   └── *.deb
#│   ├── pack/
#│   │   └── [python packages]
#│   ├── docker_debs/
#│   │   └── *.deb
#│   ├── docker-images/
#│   │   ├── postgres.tar
#│   │   ├── pgadmin4-7.2.tar
#│   │   └── postgres-exporter.tar
#│   ├── main.py
#│   ├── docker-compose.yml
#│   └── .env

#Запуск скрипта: ./install_bot.sh


# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Начинаем установку бота технической поддержки...${NC}\n"

# 1. Создание структуры директорий
echo -e "${YELLOW}1. Создание директорий...${NC}"
mkdir -p /opt/support_bot
cd /opt/support_bot

# 2. Копирование и распаковка архива
echo -e "${YELLOW}2. Распаковка архива с файлами...${NC}"
if [ -f "bot_files.tar.gz" ]; then
    tar -xzf bot_files.tar.gz
else
    echo -e "${RED}Ошибка: Архив bot_files.tar.gz не найден!${NC}"
    exit 1
fi

# 3. Установка системных зависимостей
echo -e "${YELLOW}3. Установка системных зависимостей...${NC}"
cd ./pip_venv
if ls *.deb 1> /dev/null 2>&1; then
    sudo dpkg -i *.deb
else
    echo -e "${RED}Ошибка: .deb пакеты не найдены!${NC}"
    exit 1
fi

# 4. Создание и активация виртуального окружения
echo -e "${YELLOW}4. Создание виртуального окружения...${NC}"
cd ..
python3 -m venv bot_env
source bot_env/bin/activate

# 5. Установка Python-зависимостей
echo -e "${YELLOW}5. Установка Python-пакетов...${NC}"
cd ./pack
pip install --no-index --find-links . python-dotenv>=1.0.0 aiogram==2.25.1 asyncpg>=0.28.0 aiohttp>=3.8.6 pip==23.2.1 wheel==0.41.2
cd ..

# 6. Установка Docker
echo -e "${YELLOW}6. Установка Docker...${NC}"
cd ./docker_debs
if ls *.deb 1> /dev/null 2>&1; then
    sudo dpkg -i *.deb
else
    echo -e "${RED}Ошибка: Docker .deb пакеты не найдены!${NC}"
    exit 1
fi

# 7. Загрузка Docker-образов
echo -e "${YELLOW}7. Загрузка Docker-образов...${NC}"
cd ../docker-images
if [ -f "postgres.tar" ] && [ -f "pgadmin4-7.2.tar" ] && [ -f "postgres-exporter.tar" ]; then
    sudo docker load -i postgres.tar
    sudo docker load -i pgadmin4-7.2.tar
    sudo docker load -i postgres-exporter.tar
else
    echo -e "${RED}Ошибка: Docker-образы не найдены!${NC}"
    exit 1
fi

# 8. Установка прав
echo -e "${YELLOW}8. Настройка прав доступа...${NC}"
cd ..
sudo chown -R $(whoami):$(whoami) .
chmod -R 755 .
chmod 660 .env

# 9. Запуск Docker Compose
echo -e "${YELLOW}9. Запуск Docker Compose...${NC}"
sudo docker compose -f docker-compose.yml up -d

# 10. Запуск бота
echo -e "${YELLOW}10. Запуск бота...${NC}"
python3 main.py &

echo -e "${GREEN}Установка завершена!${NC}"
echo -e "${YELLOW}Проверьте логи на наличие ошибок.${NC}"
echo -e "Для остановки бота используйте: ${YELLOW}pkill -f 'python3 main.py'${NC}"