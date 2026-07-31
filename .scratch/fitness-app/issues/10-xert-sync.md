# 10 — Xert sync job

**What to build:** Nightly per-user sync from Xert: decrypt the user's stored Xert credentials, log in to Xert, pull activities not yet imported (by `source_ref`), and enqueue `ingest_fit` for each new FIT. Manual trigger available from the admin screen (ticket 09). Skip-already-imported logic via `source_ref` (Xert activity ID) so re-syncs don't duplicate. Gated on the Xert export API research ticket confirming Xert's actual export shape (endpoint, auth flow, pagination, rate limits) — the job interface is specified; its internals depend on what the research finds.

**Blocked by:** 08 (arq + Redis — `ingest_fit` is a job to enqueue), 09 (admin screen — manual trigger + `xert_credentials` storage UI)

**Status:** ready-for-agent

- [ ] `xert_credentials` table stores per-user Xert username + encrypted password (AES, key from `FITTER_ENCRYPTION_KEY` env var / docker secret)
- [ ] Admin screen (or a user settings screen) lets a user store their Xert credentials (encrypted at rest)
- [ ] `sync_xert(user_id)` arq job: decrypt credentials, log in to Xert, fetch activity list, download FIT for activities not yet imported (by `source_ref`), enqueue `ingest_fit` for each
- [ ] Already-imported activities (matching `source_ref`) are skipped on re-sync
- [ ] Nightly schedule runs `sync_xert` for every user with stored credentials
- [ ] Manual trigger from admin screen enqueues `sync_xert` for a specific user
- [ ] Credentials are decrypted only inside the job, never in any HTTP response
- [ ] Integration test: stub Xert responses, run `sync_xert`, assert new activities ingested and attributed to the user; re-run and assert no duplicates
- [ ] Unit test: encrypt-then-decrypt round trip; decryption with wrong key raises; decrypted value never logged