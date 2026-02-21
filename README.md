# Translator Gadget

#### 🚀 INSTALAR PORTAINER EN RASPBERRY PI 400 (ARM64)

- 🟢 Verificar Docker

```groovy
docker --version

curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker pi

docker volume create portainer_data

docker run -d \
  -p 9000:9000 \
  -p 9443:9443 \
  --name portainer \
  --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:latest
  
http://192.168.1.77:9000
- admin
- password
```
    
#### 🚀 Crear imagenes

- Crear imagen del servidor de traducción
```groovy
docker build -t ws-translator:latest ./translator
``` 

- Crear el Stack en Portainer con el siguiente contenido:
```yaml
services:

  spa_eng:
    image: ws-translator:latest
    container_name: translator_spa_eng
    ports:
      - "9001:9001"
    tty: true
    stdin_open: true
    restart: unless-stopped
    command: >
      python ws_translator_server.py
      --port 9001
      --speech-key 5ae052154f2b4437a2bd13e2a8b1e1fc
      --speech-region eastus
      --translator-key eadeeea0de1b4f718ac400db2023d4ad
      --translator-region eastus
      --src-locale es-ES
      --tgt-lang en
      --tts-voice en-US-JennyNeural
      --name SPA-ENG

  eng_spa:
    image: ws-translator:latest
    container_name: translator_eng_spa
    restart: unless-stopped
    ports:
      - "9002:9002"
    tty: true
    stdin_open: true
    command: >
      python ws_translator_server.py
      --port 9002
      --speech-key 5ae052154f2b4437a2bd13e2a8b1e1fc
      --speech-region eastus
      --translator-key eadeeea0de1b4f718ac400db2023d4ad
      --translator-region eastus
      --src-locale en-US
      --tgt-lang es
      --tts-voice es-ES-ElviraNeural
      --name ENG-SPA
```