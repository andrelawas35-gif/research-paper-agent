# ADR 0044: First Notes Slice Acceptance

The first Personal Notes implementation slice is done when `save_personal_note` creates a Personal Note Record in `user_model/personal_notes.jsonl`, `list_personal_notes` shows non-deleted notes, `get_personal_note` returns a full record by ID, and `search_personal_notes` finds matches from note text, cards, tags, and Concepts. Explicit note prompts should route to save behavior, and tests should cover save/list/get/search plus soft-deleted notes being hidden.

Markdown mirrors, model-based extraction, and Concept Graph integration are deferred from the first slice unless they fall out naturally from the basic capture/search loop.
