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

SpeechKit is the primary Russian production voice in v2. Configure
`YANDEX_SPEECHKIT_API_KEY` and `YANDEX_CLOUD_FOLDER_ID` on the worker.
ElevenLabs remains an optional premium alternative:

```env
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
```

With ElevenLabs the worker uses character-level speech timings for subtitles, so phrases change
with the real voice instead of an estimated timer. Edge is emergency-only and is disabled unless
`SHORTS_ALLOW_EDGE_FALLBACK=true`; the editor explicitly marks every fallback render.

Generate a public Railway domain and copy it to the main Content OS service:

```env
MPT_BASE_URL=https://your-shorts-worker.up.railway.app
MPT_API_KEY=the-same-value-as-SHORTS_API_KEY
MPT_TIMEOUT_MINUTES=20
MPT_VOICE_NAME=ru-RU-DmitryNeural
```

The legacy `MPT_*` names stay intentionally: no database migration or bot UI
change is required.

Shorts Studio v2 also accepts a custom MP3, M4A, or Telegram voice message up
to 12 MB. The editor uploads it directly to the worker; audio bytes are never
stored in Supabase. Temporary voice assets expire automatically after 24 hours.

## Independent stage cache

Every approved Studio job carries a stable `studio_job_id`. The worker keeps a
24-hour cache under the persistent volume with separate hashes for voice,
scenes, and captions. Changing only the subtitle preset reuses both audio and
video parts; changing scenes reuses the voice; changing the voice reuses scene
parts when its duration remains the same. The final MP4 is always assembled
fresh, so the selected combination cannot return a stale export.

## Health check

`GET /health` must return `ok: true` and `pexels: true` before rendering.
