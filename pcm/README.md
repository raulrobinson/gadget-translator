```groovy
python ws_translator_server_stream_tts.py \
  --port 9001 \
  --speech-key "$SPEECH_KEY" \
  --speech-region "$SPEECH_REGION" \
  --translator-key "$TRANSLATOR_KEY" \
  --translator-region "$TRANSLATOR_REGION" \
  --src-locale "$SRC_LOCALE" \
  --tgt-lang "$TGT_LANG" \
  --tts-voice "$TTS_VOICE" \
  --name SPA-ENG
```