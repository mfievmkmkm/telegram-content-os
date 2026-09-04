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

## 2. Shorts Worker

- Root Directory: `shorts_service`
- Volume: `/data`
- Variables: `shorts_service/.env.example`
- Health URL: `https://DOMAIN/health`
- Healthy response must show `ok`, `pexels`, `persistent` and `voice`.

## 3. MatchLens Worker

- Root Directory: `matchlens_service`
- Volume: `/data`
- Variables: `matchlens_service/.env.example`
- Health URL: `https://DOMAIN/health`
- Start with a short 1–3 minute football clip before trying a full match.

## Acceptance order

1. Open both worker `/health` URLs.
2. In Content OS open System → Status; both workers must have a green real health response.
3. Publish one short draft with a card to each channel.
4. Schedule one draft, cancel it, schedule again and wait for publication.
5. Build one Shorts MP4 and inspect hook, cuts, voice, subtitles and mobile safe-zone.
6. Submit a short match clip, refresh by button, select a tracker ID and open the report.
7. Add the completed match to a Player Passport and verify observable metrics.
8. Open the shop bot from Liga and Gifts deep links, create a test order with an attachment,
   accept it in the editor and verify the customer notification.
9. Only after all checks enable `AUTO_PUBLISH=true`.
