# Context Glossary

## Research Paper Agent

A local Google ADK agent that reads papers, extracts grounded concepts, answers questions with citations, and adapts to the user's recurring research interests and communication style.

## Paper

A source document placed in `papers/` for ingestion. Supported forms are `.txt`, `.md`, and optionally `.pdf`.

## Evidence Passage

A short, cited text span extracted from a paper. Evidence passages are the unit used for grounded answers.

## User Model

Local state that represents the user's explicit preferences, recurring interests, phrasing patterns, and useful adaptation rules.

## Interaction Signal

An observation drawn from a user message or feedback event. Interaction signals can suggest interests, question types, tone preferences, grammar patterns, or recurring workflows.

## Adaptation Rule

A user-facing behavior the agent should apply because it fits the user, such as preferring concise answers, asking fewer clarifying questions, or comparing papers by assumptions.

## Confirmed Adaptation

A durable preference, avoidance, behavior rule, concept merge, or self-modification direction that requires explicit user confirmation before it changes long-term behavior.

## Automatic Adaptation

A weak or local state update the agent may make without interrupting the user, such as Candidate Signals, Tutor Progress, graph weights from explicit notes or use, and interaction logs.

## Self-Improvement

The agent's local process of reviewing interaction signals, updating the User Model, and changing future behavior through tools and instructions. It does not rewrite code by itself.

## Knowledge Self-Audit

An inspectable view of what the agent believes it has learned across confirmed preferences, inferred Candidate Signals, Demonstrated Knowledge State, Concept Graph weights, stale concepts, rejected concepts, and merge suggestions.

## Self-Audit Correction

An explicit user action taken from the Knowledge Self-Audit to confirm a Candidate Signal, reject a Candidate Signal, downgrade an over-promoted preference, or suppress a Concept in graph ranking.

## Adaptive Grill

A one-question-at-a-time interview loop where the next question is selected from both the User Model and the ingested text.

## Note-Guided Questioning

The use of Personal Notes and Note Cards as ranking signals and prompt context for Adaptive Grill and Tutor Mode. Note-Guided Questioning can prioritize personally relevant concepts, but teaching, grading, and paper-grounded claims still depend on cited evidence.

## Concept-Derived Backlink

A relationship surfaced because two items share one or more Concepts in the Concept Graph. Concept-Derived Backlinks can connect Personal Notes, Note Cards, Papers, and User Interests without requiring manual wiki-style links.

## Typed Concept Source

A provenance record in the Concept Graph that separates Papers, Personal Notes, and Note Cards as different source types for a Concept. Typed Concept Sources prevent note IDs from being stored as paper references and keep graph relationships auditable.

## Personalized Recommendation

A suggested next action that explains which user preference, interest, or text passage caused the suggestion.

## Text Understanding

The agent's source-grounded view of an ingested paper, represented by concepts, notes, evidence passages, and citations.

## Working Knowledge

Research material transformed into reusable understanding, personal questions, and agent-building ideas the user can act on.

## Knowledge Management

The agent's broader local process for capturing, organizing, retrieving, and applying the user's working knowledge across papers, Personal Notes, Interaction Signals, Candidate Signals, the User Model, the Concept Graph, and Tutor Progress.

## Self-Learning Knowledge Loop

The feedback loop where user prompts, Personal Notes, Interaction Signals, Candidate Signals, corrections, and tutor/grill answers update local agent state so future retrieval, questions, explanations, and recommendations better fit the user's quirks, intelligence, interests, and knowledge level.

## Hybrid Learning Control

The rule that weak, low-risk learning remains always-on while durable, identity-shaping, or self-modifying changes require explicit modes, tools, or confirmation. Hybrid Learning Control lets the agent adapt continuously without making long-term changes invisible.

## Adaptation Evidence

The provenance category for why the agent adapts to the user. Adaptation Evidence separates explicit stated preferences, inferred reasoning patterns, and demonstrated knowledge state so the agent can assign different confidence to each.

## Demonstrated Reasoning Pattern

An inferred pattern in how the user thinks, asks questions, evaluates trade-offs, or directs work. Demonstrated Reasoning Patterns begin as Candidate Signals and become durable only after repetition or explicit confirmation.

## Demonstrated Knowledge State

Evidence of what the user understands, misunderstands, has mastered, or is currently learning, usually drawn from Tutor Progress, grill answers, corrections, and repeated prompts. Demonstrated Knowledge State guides teaching level, question selection, and explanation depth.

## Adaptation Dimension

A separate axis of user adaptation that the agent can tune without collapsing the user's abilities into one global level. Core Adaptation Dimensions are content selection, explanation style, and challenge level.

## Content Selection

The Adaptation Dimension controlling which papers, Personal Notes, Concepts, questions, examples, or recommendations the agent surfaces for the user.

## Explanation Style

The Adaptation Dimension controlling how the agent explains ideas, such as concise versus expansive, examples-first versus theory-first, blunt versus exploratory, or operational versus reflective.

## Challenge Level

The Adaptation Dimension controlling how hard the agent pushes the user, how advanced the questions are, and how much scaffolding it gives for a specific concept or task.

## Grounded Transformation

Turning paper evidence into personal recommendations only after the source claim, support, and limitation are understood.

## Research Taste

The agent's ability to judge whether a paper is worth skimming, deep study, comparison, or discard for the user's current goals.

## Adjacent Possibility

A nearby idea the user did not directly ask for, surfaced because the source text strongly suggests it may matter to the user's goals.

## Evidence-First Pushback

A warm challenge when the user's interpretation, desired workflow idea, or stated goal goes beyond what the paper supports.

## Three-Lane Answer

An answer structure that separates paper Evidence, the user's Personal Notes, and the agent's Inference. Three-Lane Answers prevent Personal Notes from being mistaken for cited research evidence while still letting the agent synthesize across both.

## Candidate Signal

A provisional preference or interest inferred from exploratory answers, kept weaker than an explicit instruction until it repeats or the user says to remember it.

## Note Candidate Signal

A provisional preference, interest, or recurring pattern inferred from a Personal Note or Note Card. Note Candidate Signals can shape near-term recommendations, but they do not become durable User Model entries unless the user explicitly asks to remember them or the pattern repeats.

## Recommendation Confidence

A plain-language label that says how strongly a personalized recommendation is supported by citations, user goals, and inference.

## Session Artifact

A compact durable output from a meaningful research interaction, such as concept cards, decision notes, open questions, agent-building ideas, or a reading queue.

## Personal Note

A first-class personal knowledge object created from the user's own prompt input or saved reflections. Personal Notes are separate from Papers: they can connect to the Concept Graph and influence future questions, but they are not treated as source evidence for paper-grounded claims.

## Local Note Boundary

The privacy rule that Personal Notes are stored locally and only relevant note text is sent to the configured model backend during explicit note save or sync operations. The agent must not send the whole notes vault during unrelated prompts.

## Note Card

An extracted atomic idea from a Personal Note. Note Cards are the units used for concept linking, search, backlinks, and future prompt resurfacing while the original Personal Note remains intact.

## Conservative Note Extraction

The rule that a Personal Note should produce only a small number of high-confidence Note Cards, usually one to five. Conservative Note Extraction favors reusable ideas over sentence-by-sentence fragmentation.

## Save-First Note Extraction

The rule that explicitly captured Personal Notes are saved immediately, then returned with an extraction summary of Note Cards, linked Concepts, and Suggested Tags. Save-First Note Extraction keeps capture lightweight while making corrections easy after the fact.

## Note Correction

An explicit user action that fixes a Personal Note or its derived structure after Save-First Note Extraction. Initial Note Corrections include editing note text/title/tags, rejecting a Note Card, and rejecting a Note Concept.

## Explicit Note Capture

The rule that a prompt becomes a Personal Note only when the user marks it with note-oriented language such as "note:", "save note:", or "remember note:". Unmarked messages can still be used in the current conversation, but they do not automatically enter the notes store or Concept Graph.

## Notes Store

The canonical agent-readable store for Personal Notes and extracted Note Cards. It preserves stable IDs, timestamps, card extraction, graph-link metadata, and migration-friendly structure.

## Note Version

A preserved historical state of a Personal Note after an edit. Note Versions keep the note's prior wording auditable so graph links, Note Cards, and Candidate Signals can be traced back to the text that produced them.

## Soft-Deleted Note

A Personal Note hidden from normal retrieval and excluded from future ranking or personalization influence, while remaining in the Notes Store for auditability. Soft-Deleted Notes can be inspected only through explicit deleted-note queries unless later purged.

## Markdown Note Mirror

A human-readable Markdown representation of a Personal Note, intended for Obsidian-like browsing, linking, and portability. The Markdown Note Mirror is derived from the Notes Store rather than being the canonical source of agent state.

## Markdown Note Frontmatter

Structured metadata at the top of a Markdown Note Mirror, including the note ID, timestamps, tags, concepts, and canonical Notes Store path. It makes Markdown notes inspectable without making them the canonical agent state.

## Explicit Markdown Sync

The rule that edits made directly to Markdown Note Mirrors affect the canonical Notes Store only when the user explicitly asks to import or sync them. This prevents accidental file edits or half-written notes from silently changing the Concept Graph or User Model.

## User Tag

A note tag intentionally assigned by the user for organization or retrieval. User Tags are durable user-authored metadata and should not be silently created from agent suggestions.

## Suggested Tag

A note tag inferred by the agent from a Personal Note or Note Card. Suggested Tags support retrieval and browsing, but remain separate from User Tags because they are generated metadata.

## Note Management Surface

The initial tool set for working with Personal Notes: save a note, search notes, list notes by tag or concept, and inspect one note by ID. Broader graph exploration and backlink workflows should build on this surface before becoming separate tools.

## Personal Notes Module

The implementation boundary for Personal Note storage, extraction, Markdown rendering, search, correction, deletion, and Concept Graph integration. The agent exposes Personal Notes through thin tool wrappers rather than placing the full notes workflow inside the main agent file.

## Notes Vertical Slice

An incremental implementation step that delivers a usable part of Personal Notes end to end, such as capture/search, extraction, Markdown mirrors, graph integration, answer synthesis, question ranking, or correction workflows.

## First Notes Slice

The initial Notes Vertical Slice focused on local Personal Note capture, listing, inspection, lexical search, explicit note prompt routing, and tests. It intentionally excludes Markdown mirrors, model-based extraction, and Concept Graph integration unless they are needed for the basic capture/search loop.

## Knowledge Self-Audit Slice

A later Notes Vertical Slice focused on inspecting and correcting the Self-Learning Knowledge Loop. It includes a Knowledge Self-Audit view and Self-Audit Corrections, but is intentionally kept out of the First Notes Slice.

## Personal Note Record

The canonical structured representation of a Personal Note in the Notes Store. A Personal Note Record includes stable identity, current text, tags, extracted Note Cards, linked Concepts, Candidate Signals, Markdown mirror location, soft-delete state, and Note Versions.

## Artifact Offer

A specific proposal for a Session Artifact that names the intended shape before the agent creates it.

## Agent Mode

A named operating posture that tells the agent which research behavior to emphasize, such as reading faithfully, grilling, building, judging taste, producing artifacts, or updating the user profile.

## Session Goal

The user's current task or purpose for a research interaction, which takes priority over long-term profile preferences.

## Goal Clarification

A single question the agent asks only when the session goal is ambiguous enough to materially change the output.

## Improvement Proposal

A suggested change to the research agent, supported by evidence and confidence, that requires explicit approval before any code is modified.

## Concept Graph

A local typed graph connecting User Interests, Concepts, Papers, Personal Notes, Note Cards, and prerequisite hints, stored in `user_model/concept_graph.json`. The graph preserves source provenance while letting the user's own notes and ingested papers meet through shared concepts.

## Graph Edge

A directed connection from a User Interest to a Paper Concept. Three edge types exist: **ingest** (passive keyword match created when a paper is ingested — never decays, weak signal), **engaged** (created or incremented when the user answers a grill question about the concept — decays after 30 days without re-engagement, drops to zero after 60), and **saved** (created when the user explicitly says to remember something — never decays, strongest signal).

## Note Signal

A medium-strength graph signal created when a Personal Note or Note Card links to a Concept. Note Signals are stronger than passive paper ingestion because note capture is intentional, but weaker than active engagement or explicit saved memory.

## Note Signal Decay

The slow reduction of a Note Signal's ranking influence when a Personal Note has not been edited, searched, linked, or used in questioning for a long period. Note Signal Decay affects ranking only; it never deletes the underlying Personal Note or Note Card.

## Prerequisite Hint

A soft pedagogical dependency between two Paper Concepts, stored in the Concept Graph's `dependencies` section. A **requires-before** relationship: "embeddings" should be taught before "vector search." Inferred by LLM at paper ingest time. The Tutor Mode uses prerequisite hints as a one-hop priority boost when selecting the next concept — the hint is advisory, never blocking. The user can override at any time by naming a concept directly. Cycles are harmless because only one hop is ever inspected.

## Concept Match

The agent's annotation of a paper concept with an interest-match label (high/medium/low) derived from the Concept Graph. Used in paper briefs to signal relevance to the user's stated interests.

## Lexical Note Retrieval

The first retrieval strategy for Personal Notes, based on token scoring across note text, Note Cards, tags, and Concepts, with Concept Graph boosts for related ideas. Lexical Note Retrieval avoids introducing embeddings or a vector database until note-search pain justifies it.

## Note Concept

A concept introduced or reinforced by a Personal Note or Note Card. Note Concepts share the same concept vocabulary as Paper Concepts so later paper ingestion can connect literature evidence back to the user's own thinking.

## Concept Merge Suggestion

A proposed consolidation of similar Concepts that the agent surfaces for user approval. Concept Merge Suggestions are not applied automatically because concept names represent the user's evolving interpretation.

## Tutor Mode

An Agent Mode where the agent teaches paper concepts through an explain-then-quiz loop, grades free-text answers via LLM, and adapts the curriculum to the user's mastery level. Defaults to alternating between weak-area drilling and interest-aligned exploration, with the user able to steer at any time.

## Tutor Session

A durable teaching interaction tracked in `user_model/tutor_progress.json` (concept-level mastery summary) and `user_model/tutor_sessions.jsonl` (full answer audit trail). Each entry records the concept, question, user answer, correctness verdict, and an optional mastery hint.

## Mastery Level

A per-concept score derived from `times_correct / max(1, times_asked)` stored in the Tutor Progress file. Concepts with mastery below 0.5 are considered weak and prioritized for drilling; concepts at 1.0 are considered mastered and deprioritized.

## Answer Grading

An internal LLM call that judges a free-text tutor answer against the cited passage, returning CORRECT or INCORRECT with a one-sentence reason and an optional mastery hint (e.g., "correct but confused retrieval with generation"). Not exposed as a user-facing tool.

## Curriculum Pathing

The tutor's concept-selection strategy. Alternates between the lowest-mastery concept (weak-area drilling) and the highest-interest unmastered concept (engagement). The user can override at any point by naming a concept or topic.

## OCR Fallback

A transparent extraction path in `_read_pdf_pages` that activates when pypdf returns empty text for a page. Renders the page to an image via PyMuPDF (fitz) and runs Tesseract OCR (one system dependency, installed separately). Text-native PDFs are unaffected — the OCR path is never entered for them. Scanned or image-based PDFs are now ingestable as first-class papers.
