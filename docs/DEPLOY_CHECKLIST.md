# Railway deployment map

The repository runs as three Railway services. Variables are service-specific; do not paste
worker secrets into the editor service.

## 1. Content OS editor + shop bot

- Root Directory: repository root
- Variables: copy the root `.env.example`
- `MPT_BASE_URL`: public HTTPS domain of Shorts Worker
- `MPT_API_KEY`: exactly the same value as Shorts Worker's `SHORTS_API_KEY`
- `MATCHLENS_BASE_URL`: public HTTPS domain of MatchLens
- `MATCHLENS_API_KEY`: exactly the same value as MatchLens Worker's key
- Keep `AUTO_PUBLISH=false` until manual publishing, scheduling and both channels pass acceptance.
- Keep `CONTENT_OS_RUNTIME=legacy` until the v2 smoke test is ready. Switch only the editor service to `CONTENT_OS_RUNTIME=v2` for acceptance.
- Do not add `YANDEX_SPEECHKIT_*` to this service. They belong to Shorts Worker only.

## 2. Shorts Worker

- Root Directory: `shorts_service`
- Volume: `/data`
- Variables: `shorts_service/.env.example`
- Required production voice variables: `YANDEX_SPEECHKIT_API_KEY` and `YANDEX_CLOUD_FOLDER_ID`
- `SHORTS_API_KEY` must equal editor `MPT_API_KEY`
- Keep `SHORTS_ALLOW_EDGE_FALLBACK=false` during acceptance so a missing SpeechKit setup cannot silently produce the old emergency voice.
- Health URL: `https://DOMAIN/health`
- Healthy response must show `ok`, `pexels`, persistent `/data`, and SpeechKit as available.

## 3. MatchLens Worker

- Root Directory: `matchlens_service`
- Volume: `/data`
- Variables: `matchlens_service/.env.example`
- Health URL: `https://DOMAIN/health`
- Start with a short 1–3 minute football clip before trying a full match.
- MatchLens remains Experimental during Content OS 2.0 rollout; it must not block core Content/Shorts/Sales acceptance.

## Supabase migration before v2 Growth/Sales acceptance

Run the current `supabase_schema.sql` once in the Supabase SQL editor. It is additive/idempotent and adds:

- 1/6/24/48h Growth metric fields (`comments`, subscriber delta, clicks, leads, orders, sales, revenue);
- richer funnel event types used by Shop 2.0;
- campaign/order attribution fields and indexes.

The v2 persistence bridge can temporarily degrade new funnel event names to legacy names, but that is rollout compatibility only. Apply the schema before evaluating real conversion analytics.

## Acceptance order

1. Run CI on the exact `content-os-v2` head; pytest, compileall and smoke imports must all be green.
2. Apply `supabase_schema.sql`.
3. Open both worker `/health` URLs.
4. In Content OS → System verify editor env readiness. Do not expose secret values; only missing variable names matter.
5. Set only editor `CONTENT_OS_RUNTIME=v2`. Keep `AUTO_PUBLISH=false`.
6. Open TODAY and PROJECTS. Generate one Football Challenge draft and send it through Director review.
7. Generate one normal Gifts draft and one Liga draft. Check anti-repeat and Creative Director.
8. Request A/B/C visual variants and select a different card.
9. Run Content Remix from one approved material.
10. Build one Shorts MP4. Inspect hook, cuts, Russian voice, subtitles, mobile safe-zone and whether scene choices actually support the voiceover.
11. Publish one short draft with a card to each channel.
12. Schedule one draft, cancel it, schedule again and wait for publication.
13. Open Shop from at least two different campaign deep links; create a test order and verify source attribution.
14. Accept the order in the editor and verify the customer notification.
15. Submit a short MatchLens clip only after the core loop is healthy.
16. Rollback test: remove/change `CONTENT_OS_RUNTIME=v2` and verify legacy starts unchanged.
17. Only after the complete acceptance run consider `AUTO_PUBLISH=true`.

## Deliberate blockers before calling v2 production-ready

- Real Railway/SpeechKit MP4 smoke test.
- Real Telegram publish/schedule/cancel cycle.
- Real Supabase Growth/Sales attribution after migration.
- Mixed-media Shorts assets beyond stock video are still a separate acceptance item; do not label them production-ready until the renderer actually consumes those asset types.
- Uploaded MP3/custom-audio UX is not complete end-to-end yet.
