# Account Corpus

This directory holds per-account Instagram research used to improve `instagram-strategy.md`.

## Method

- Source list: `resources/instagram_handles.md`
- Account folder naming: exact handle, lowercase, including `@`
- One `analysis.md` per account
- One `posts/<index>_<shortcode>/` folder per scraped post
- Each post folder stores `metadata.json`, `comments.json`, `caption.txt`, and `media/` assets
- Cross-account patterns belong in `SYNTHESIS.md`

## Status

- Status reporting is maintained without embedding specific account handles in this document.
- See the account directory structure for concrete per-account outputs when needed.

## Notes

- Comments are fetched to exhaustion via authenticated pagination whenever Instagram returns cursors.
- Per-post media downloads are stored under each post folder's `media/` directory.
