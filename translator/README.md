## Clientes

```groovy
pi@pi-400:~ $ arecord -l
**** List of CAPTURE Hardware Devices ****
card 0: Headset [Logitech USB Headset], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 3: Device [USB Audio Device], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
```

🎧 SPA → ENG
```groovy
docker run --rm -it \
  --name spa-eng-client \
  --network host \
  --device /dev/snd \
  gadget-translator-spa_eng:latest \
  python ws_audio_client.py \
  --ws ws://127.0.0.1:9001 \
  --capture hw:0,0 \
  --playback plughw:0,0 \
  --name SPA-ENG
```



🎧 ENG → SPA
```groovy
docker run --rm -it \
  --name eng-spa-client \
  --network host \
  --device /dev/snd \
  gadget-translator-eng_spa:latest \
  python ws_audio_client.py \
  --ws ws://127.0.0.1:9002 \
  --capture hw:3,0 \
  --playback plughw:0,0 \
  --name ENG-SPA
```

---

```groovy
docker run --rm -it \
  --network host \
  --device /dev/snd \
  unified-spa_eng \
  python ws_audio_client.py \
  --ws ws://127.0.0.1:9001 \
  --capture hw:1,0 \
  --playback plughw:3,0 \
  --name SPA-ENG
  
docker run --rm -it \
  --network host \
  --device /dev/snd \
  unified-spa_eng \
  python ws_audio_client.py \
  --ws ws://127.0.0.1:9001 \
  --capture plughw:3,0 \
  --playback plughw:1,0 \
  --rate 16000 \
  --channels 1 \
  --name SPA-ENG
```

---

```groovy
docker run --rm -it --name spa-eng-client --network host --device /dev/snd gadget-translator-spa_eng:latest python ws_audio_client.py --ws ws://127.0.0.1:9001 --capture plughw:2,0 --playback plughw:3,0 --name SPA-ENG

docker run --rm -it --name eng-spa-client --network host --device /dev/snd gadget-translator-eng_spa:latest python ws_audio_client.py --ws ws://127.0.0.1:9002 --capture plughw:3,0 --playback plughw:2,0 --name ENG-SPA
```

```groovy
docker run --rm -it --name spa-fra-client --network host --device /dev/snd gadget-translator-spa_fra:latest python ws_audio_client.py --ws ws://127.0.0.1:9003 --capture plughw:2,0 --playback plughw:3,0 --name SPA-FRA

docker run --rm -it --name fra-spa-client --network host --device /dev/snd gadget-translator-fra_spa:latest python ws_audio_client.py --ws ws://127.0.0.1:9004 --capture plughw:3,0 --playback plughw:2,0 --name FRA-SPA
```