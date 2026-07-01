# ADR 0040: Note Signal Decay

Note-derived graph signals will decay slowly for ranking influence while preserving the underlying Personal Notes and Note Cards. A note signal should remain stable for roughly 90 days, lose weight after long inactivity such as 180 days, and refresh when the note is edited, searched, linked, or used in Adaptive Grill or Tutor Mode.

## Considered Options

- Never decay note signals: preserves salience, but old notes can bias future questioning indefinitely.
- Delete stale notes or cards: too destructive for a personal knowledge system.
- Decay ranking influence only: selected because it keeps notes durable while making attention adaptive.
