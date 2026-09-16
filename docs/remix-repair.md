# Remix and card-caption repair

Base: `content-os-v2`, `814eb42c773a97f5cc7882fe0de8b29473756693`.

## Behavior

- Validate Remix field types, poll options and the 64–105-word Shorts contract. Repair only invalid fields, retain valid text and label template recovery. Transport and authentication errors remain visible with a retry button.
- Give Remix a 3600-token response budget and detect truncated completions. Other LLM callers retain their existing budget.
- Save each bundle under its own ID before sending previews. Buttons reference that immutable bundle. Old numeric bundle callbacks explicitly ask for a new Remix instead of silently using overwritten data.
- Import the ready voiceover into Shorts Studio without another LLM call or rendering. Initial scenes are text scenes; scene remix remains available. Rendering still requires script approval.
- Save real polls as structured metadata. Publish them through the existing Premium MTProto account, including premium question entities; no automatic publication happens on Remix save.
- Save a sales bridge separately or as a new long/short draft with the bridge. Keep the source and its FactPack.
- Repeated saves reuse drafts and Shorts sessions. Draft inserts use the existing unique source-hash index to recover after a lost settings-pointer write. Shorts creation uses a process-local lock: run one polling Editor process; creation across multiple processes is not transactionally coordinated.
- Back navigation displays the source without a new Director/LLM pass. Empty Studio lists differ from database errors.
- Oversize card captions offer “Подогнать под карточку”. Up to two shortening attempts are checked against the final rendered caption (including CTA and UTF-16 emoji length) and the editorial quality gate. The original text is backed up; failed fitting leaves it unchanged. Successful fitting requires another explicit publish click.

## Persistence and deployment

No schema migration or new secret is needed. New records use the existing settings table and source-hash uniqueness in both SQLite and Supabase. Existing drafts remain readable.

The editor image builds from `content-os-v2`; the Docker entrypoint is `python -m content_os.entrypoint` and `CONTENT_OS_RUNTIME=v2` (the default). The workflow now embeds the commit revision in the image. It is visible in startup logs and SYSTEM. Images built outside that workflow can pass `--build-arg APP_REVISION=<sha>`.

After merging, deploy the Editor image tagged with the resulting full commit SHA. Verify that exact revision in SYSTEM/logs. The Shorts and MatchLens images do not need rebuilding for this patch. Live Railway state and live Telegram publishing were not accessed during development.

## Acceptance

Run `python -m pytest -q` and `python -m compileall -q content_os shorts_service`. Dispatcher tests use real aiogram routing and a fake Telegram transport; no channel messages, LLM calls or paid voice/render operations are sent.

In a test channel after deployment: create Remix, open each output, repeat save, restart and reopen Shorts, return to the source, preview a poll, and fit an oversize caption. Confirm publication separately. Check all original poll options and the single photo+caption result.
