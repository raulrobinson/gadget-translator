```groovy
docker run --rm -it \
  --network host \
  --device /dev/snd \
  --env-file spa-eng.env \
  gadget-translator-spa_eng:latest \
  python ws_translator_server_stream_tts.py
```