#!/bin/bash
sudo apt-get -y update
sudo apt-get -y install apt-transport-https ca-certificates gnupg2 software-properties-common
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_releasudo apt-get update)"
sudo apt-get -y install ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get -y update
sudo apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo apt-get -y install docker-compose
sudo apt-get -y install openssl
chmod +x /usr/local/bin/docker-compose
systemctl start docker
systemctl enable docker
clear
echo "Сгенерировать сертификат (Y/n)"
read rrr
rrr=$(echo "$rrr" | tr '[:upper:]' '[:lower:]')

if [ "$rrr" = "y" ]; then
    openssl req -newkey rsa:4096 \
            -x509 \
            -sha256 \
            -days 3650 \
            -nodes \
            -out vpn_bot/ssl/fullchain1.pem \
            -keyout vpn_bot/ssl/privkey1.pem \
            -subj "/C=SI/ST=Ljubljana/L=Ljubljana/O=Security/OU=IT Department/CN=companyia.site"
elif [ "$rrr" = "n" ]; then
    echo "Ok"
fi

echo "Добавить генерацию в crontab? (Y/n)"
read rrr
rrr=$(echo "$rrr" | tr '[:upper:]' '[:lower:]')

if [ "$rrr" = "y" ]; then
    CRON_COMMAND="0 2 */90 * * /root/vpn_bot/cron.sh"
    (crontab -l ; echo "$CRON_COMMAND") | crontab -
elif [ "$rrr" = "n" ]; then
    echo "Ok"
fi
sudo docker-compose up -d
echo "Import dump in DB..."
sleep 22
sudo docker exec -i mysql sh -c 'exec mysql -uroot -p"G1Z8ORTBdD1F" vpn_db' < init.sql
#chmod +x vpn_bot/restart_bot.sh
#bash vpn_bot/restart_bot.sh
