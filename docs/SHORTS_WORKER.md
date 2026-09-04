# Content OS Shorts Worker

This lightweight Railway service replaces MoneyPrinterTurbo while keeping the
same endpoints used by the editor bot. It creates a Russian voiceover, downloads
several relevant portrait clips from Pexels, crops them to 9:16, burns compact
subtitles and returns a Telegram-ready MP4.

## Railway

Create a new service from this repository and set its **Root Directory** to
`shorts_service`. Add a persistent Volume mounted at `/data` so tasks and output
videos survive restarts.

Worker variables:

```env
PEXELS_API_KEY=...
SHORTS_API_KEY=use-one-long-random-secret
SHORTS_DATA_DIR=/data
```

For a much more natural voice, add optional ElevenLabs variables to the worker:

```env
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
```

With ElevenLabs the worker uses character-level speech timings for subtitles, so phrases change
with the real voice instead of an estimated timer. Without these variables it uses the free
Microsoft Edge voice. If ElevenLabs is temporarily unavailable, rendering continues with Edge
and the editor bot explicitly marks the MP4 as a fallback render.

Generate a public Railway domain and copy it to the main Content OS service:

```env
MPT_BASE_URL=https://your-shorts-worker.up.railway.app
MPT_API_KEY=the-same-value-as-SHORTS_API_KEY
MPT_TIMEOUT_MINUTES=20
MPT_VOICE_NAME=ru-RU-DmitryNeural
```

The legacy `MPT_*` names stay intentionally: no database migration or bot UI
change is required.

## Health check

`GET /health` must return `ok: true` and `pexels: true` before rendering.
