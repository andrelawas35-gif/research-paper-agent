# Personal Knowledge Manager

A local Google ADK agent for capturing, organizing, retrieving, and developing personal knowledge across papers, personal notes, concepts, ideas, tutor progress, and the local user model.

The Python package and deployment paths still use `research_paper_agent` for now. The product/domain name is **Personal Knowledge Manager**; a package/service rename is deferred to a separate migration.

## What It Does

- Captures explicit personal notes locally in `user_model/personal_notes.jsonl`
- Writes Markdown note mirrors under `user_model/notes/` for Obsidian-style browsing
- Ingests `.txt`, `.md`, and optionally `.pdf` sources from `papers/`
- Extracts metadata, concepts, methods, findings, limitations, and open questions
- Stores page-aware evidence passages with stable citation IDs
- Searches ingested evidence with weighted lexical ranking before answering
- Compares sources by concepts, methods, findings, and limitations
- Builds citation-backed study guides and recall questions
- Tracks local preferences, interests, question patterns, candidate signals, and tutor progress
- Separates source evidence, personal notes, and inference
- Supports a documented mode taxonomy for capture, retrieval, synthesis, building ideas, tutoring, review, writing, artifacts, and admin workflows

## Setup

1. Create a Python 3.10+ virtual environment and install dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

In this local Codex workspace, the bundled Python 3.12 runtime works:

```bash
/Users/andrelawas/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m venv .venv
```

2. Put source documents in `papers/`.
3. Copy `.env.example` to `.env`.
4. Add your DeepSeek API key.
5. From the parent folder, run:

```bash
research_paper_agent/.venv/bin/adk run research_paper_agent
```

For a browser UI:

```bash
research_paper_agent/.venv/bin/adk web .
```

The launcher creates `.adk` storage and passes explicit SQLite/artifact paths to ADK. Use it if the web UI reports `sqlite3.OperationalError: unable to open database file`.

## Useful Prompts

Capture and notes:

- `note: Concept-derived backlinks should come before manual wiki links.`
- `save note: Builder Mode should make loose ideas cohesive before implementation.`
- `Search my notes for concept graph.`
- `Show me note backlinks for note_20260701_001.`

Sources:

- `Ingest all papers in the papers folder.`
- `List the main concepts you found.`
- `Give me a brief for each paper.`
- `Search for evidence about benchmark evaluation.`
- `What does the Smith paper say about retrieval augmented generation?`
- `Compare the limitations across the papers.`
- `Compare the papers on evaluation methodology.`
- `Make me a study guide with recall questions.`
- `Quiz me on the most important concepts from the papers.`

Personalization and reflection:

- `Learn this about me: I like short answers with exact commands.`
- `Remember that I care about AI agents, research workflows, and self-improving tools.`
- `Audit how you should improve around my style.`

Grill, builder, and synthesis:

- `Grill me on this paper based on what you know about me.`
- `Ask me questions and recommendations from the text and my quirks.`
- `Builder Mode: help me make this loose idea more cohesive.`
- `Connect my notes about knowledge graphs with the papers I ingested.`
- `Review this ADR for risks and missing decisions.`

## Tool Capabilities

- `list_papers`: shows files available in `papers/`
- `ingest_paper`: ingests one paper and writes a JSON record; optionally accepts `evidence_scope` such as `mentor:simon`
- `ingest_all_papers`: ingests every supported paper
- `list_concepts`: lists extracted concepts by paper
- `search_evidence`: returns cited passages for a query; optionally filters by `evidence_scope` such as `mentor:simon` or `mentor:lanier`
- `paper_brief`: summarizes one or all ingested papers from stored notes
- `compare_papers`: compares papers overall or around a topic
- `make_study_guide`: creates citation-backed recall questions
- `get_user_profile`: shows the local personalization profile
- `learn_from_user_message`: updates the profile from a message
- `record_interaction`: appends an interaction event to the local log
- `set_user_preference`: stores an explicit preference, interest, quirk, or avoidance
- `save_personal_note`: stores an explicit personal note locally
- `list_personal_notes`: lists non-deleted personal notes
- `get_personal_note`: returns a full note by ID
- `search_personal_notes`: searches note text, tags, concepts, and cards
- `delete_personal_note`: soft-deletes a personal note
- `edit_personal_note`: edits a note while preserving version history
- `reject_note_card`: rejects an extracted note card
- `reject_note_concept`: rejects a linked note concept
- `get_note_backlinks`: finds notes that share concepts
- `render_note_markdown`: returns a note's Markdown mirror
- `import_markdown_notes`: imports explicit Markdown mirror edits
- `add_person`: creates a Person record through explicit relationship capture
- `list_people`: lists non-deleted people with summary metadata
- `get_person`: returns one Person record by ID, display name, or alias
- `search_people`: searches people by name, aliases, context, interactions, tags, and concepts
- `add_relationship_note`: saves explicit Relationship Context for a Person
- `log_relationship_interaction`: logs an interaction with a Person
- `recommend_reconnections`: recommends who to reconnect with and why
- `forget_person`: soft-deletes a Person record from normal relationship retrieval
- `self_improvement_audit`: suggests how the agent should adapt next
- `knowledge_self_audit`: inspects what the agent believes it has learned
- `self_audit_correction`: applies explicit corrections to the self-audit
- `adaptive_grill`: asks personalized questions from the user model and ingested text
- `respond_to_adaptive_grill`: learns from a grill answer and recommends the next step
- `record_tutor_answer`: grades a tutor response and updates concept mastery
- `get_tutor_progress`: inspects concept-level tutor progress
- `get_concept_graph`: inspects local interest-to-concept graph state
- `suggest_concept_merges`: suggests near-duplicate concepts for approval

## Modes

The Personal Knowledge Manager uses modes as operating postures. It infers modes silently by default and names them only when that helps clarify behavior. A response should have one primary mode and at most one supporting mode.

Active mode taxonomy:

- **Capture Mode**: save notes, people, relationship context, ideas, open loops, and explicit preferences.
- **Retrieve Mode**: find existing notes, papers, people, concepts, decisions, artifacts, and user-model entries.
- **Source Mode**: understand external sources faithfully with citations. Reader Mode remains an alias.
- **Synthesis Mode**: connect retrieved knowledge into themes, theories, comparisons, or interpretations.
- **Builder Mode**: help formulate loose ideas into cohesive designs.
- **Grill Mode**: pressure-test one question at a time.
- **Tutor Mode**: teach and quiz concepts with mastery tracking.
- **Reflect Mode**: inspect and correct what the PKM believes about the user. This replaces Profile Mode.
- **Relationship Mode**: manage people, follow-ups, relationship context, and reconnection recommendations.
- **Taste Mode**: judge whether a source, idea, note, project, or workflow deserves attention.
- **Review Mode**: inspect existing artifacts, code, docs, plans, notes, or assumptions for risks and gaps.
- **Writing Mode**: turn knowledge into prose with attention to voice, flow, and audience.
- **Artifact Mode**: produce durable outputs such as ADRs, PRDs, issue lists, decision notes, reading queues, and study guides.
- **Admin Mode**: manage settings, imports, exports, sync, deletion, backups, migrations, deployment, API/mobile access, and backend configuration.

Deferred modes:

- **Planning Mode**: may become top-level if sequencing work into milestones/issues becomes frequent.
- **Decision Mode**: may become top-level for high-stakes option selection.
- **Briefing Mode**: may become top-level after stores and cadence/reminder behavior stabilize.

## Personalization

The agent stores personalization locally under `user_model/`. It can learn from explicit preferences and repeated interaction signals, then adapt answers around your interests, phrasing, common question types, demonstrated knowledge, and correction history.

Useful prompts:

- `What do you know about my interests?`
- `Remember: I prefer blunt answers when I ask operational questions.`
- `Learn from this message: okay go improve it.`
- `Audit your user model and tell me what you should do differently.`
- `Start an adaptive grill on evaluation methodology.`
- `Ask me one question at a time based on my quirks and this paper.`

The profile is inspectable at `user_model/profile.json`. Interaction logs are written to `user_model/interaction_log.jsonl`. Candidate signals stay provisional until explicitly confirmed or repeated enough to justify promotion.

## Personal Notes

The agent saves personal notes only when you explicitly ask, using prompts like `note:`, `save note:`, or `remember note:`. Notes are local JSONL records in `user_model/personal_notes.jsonl` and are treated as your knowledge/context, not as cited paper evidence. JSONL stays canonical; Markdown mirrors are written under `user_model/notes/` for reading and Obsidian-style browsing.

On save, the agent performs conservative local extraction:

- up to 5 reusable note cards from high-signal sentences
- suggested tags from repeated or early meaningful terms
- concepts from explicit concepts plus conservative phrase candidates

Deleted notes are soft-deleted: normal list/search hides them, but the record stays on disk for recovery and future audit tools.

## Source Reading

Source Mode is the evidence-first reading capability inside the broader Personal Knowledge Manager. It should retrieve source passages before making factual claims about ingested papers or documents, then cite the returned citation fields.

When answers combine sources and personal notes, the agent should keep three lanes clear:

- **Evidence**: cited source passages
- **Your Notes**: relevant Personal Notes or Note Cards
- **Inference**: the agent's synthesis between them

## Builder Mode

Builder Mode helps turn loose ideas into cohesive designs. It is not an implementation funnel by default.

The intended flow is:

1. Ask one high-leverage Socratic question.
2. Generate a small set of coherent Builder Ideas when enough context exists.
3. Label component provenance as `[from your notes]`, `[cited: source]`, and/or `[inference]`.
4. Recommend one idea while preserving user choice.
5. Grill decision-bearing components only when useful.
6. Offer an artifact after a meaningful cohesion point.

Builder Mode optimizes for coherence first, personal fit second, grounding third, and idea-fitting novelty fourth.

## Adaptive Grill

The adaptive grill combines the local user model with cited paper passages. It asks one question first, explains why that question fits you or the text, and gives a recommendation for what to do with your answer. After you answer, it can update the user model and choose the next direction.

The agent now keeps grill questions short and pointed, but gives fuller, more personality-shaped answers for explanations, research synthesis, and recommendations.

Grill answers are provisional by default. They are logged as candidate signals in `user_model/candidate_signals.jsonl`; the agent only promotes them to durable preferences when you explicitly say things like `remember this`, `always`, or `never`, or when a pattern repeats over time.

## Model Backend

The agent uses DeepSeek through ADK's OpenAI-compatible model wrapper.

Set these in `.env`:

```powershell
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_MAX_TOKENS=4096
```

Use `deepseek-v4-pro` for a stronger model, or `deepseek-v4-flash` for the default faster path.

## PDF Support

PDF ingestion uses `pypdf` for local text extraction. It is included in `requirements.txt`:

```bash
.venv/bin/pip install -r requirements.txt
```
