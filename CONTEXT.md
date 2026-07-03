# Context Glossary

## Personal Knowledge Manager

A local Google ADK agent that helps the user capture, organize, retrieve, and develop personal knowledge across papers, Personal Notes, relationship context, ideas, tutor progress, and the User Model. Paper reading remains a grounded capability inside the broader Personal Knowledge Manager rather than the product's whole identity.

## Person

The central object in Relationship Management. A Person represents someone the user knows or wants to track, and acts as the anchor for interactions, relationship notes, commitments, reminders, context, and follow-up history.

## Person Record

The canonical structured representation of a Person in the relationship store. The first Person Record includes stable identity, display name, aliases, relationship type, Relationship Context notes, interaction history, open loops, important dates, tags, Concepts, timestamps, and soft-delete state.

## Relationship Event

An append-only event in the Relationship Store that records how a Person Record changed, such as person_created, context_note_added, interaction_logged, open_loop_added, open_loop_closed, cadence_set, or important_date_added. Relationship Events provide auditability and can be folded into the current Person summary.

## Relationship Correction

An explicit user action that fixes Relationship Management state, such as changing a Relationship Type, separating two people with the same name, removing a context note, closing an open loop, marking context sensitive, or forgetting a Person. Relationship Corrections preserve prior events while marking derived facts as corrected, superseded, rejected, or soft-deleted.

## Derived Person Summary

The current readable state of a Person Record produced from Relationship Events. A Derived Person Summary supports fast lookup while preserving the underlying event history for correction and audit.

## Relationship Management

The agent's local process for remembering people, understanding relationship context, tracking interactions, and helping the user follow up intentionally. Relationship Management belongs inside the main agent as a separate module because it shares Personal Notes, the Concept Graph, reminders, and the User Model.

## Relationship Personalization Boundary

The rule that Relationship Management data may lightly influence relationship-specific recommendations, reminders, and drafting boundaries, but should not broadly infer the user's identity, personality, or explanation style from other people's private context.

## Relationship Context

Private, reflective knowledge about a Person, such as communication style, important life context, shared interests, trust history, boundaries, and what tends to make the relationship better or worse. Relationship Context can personalize recommendations, but it is not an instruction to take action.

## Sensitive Relationship Context

Relationship Context involving health, finances, trauma, conflict, dating, family issues, legal trouble, workplace problems, or similarly private details. Sensitive Relationship Context can be stored after explicit capture, but should be omitted or softened in casual summaries unless the user directly asks for full context.

## Save-First Relationship Extraction

The rule that explicit relationship notes are saved as raw Relationship Events before the agent extracts provisional context, open loops, important dates, Concepts, sensitivity labels, or follow-up angles. The raw relationship note remains the source of truth, and extracted structure is correctable.

## Relationship Operations

Actionable relationship state attached to a Person, such as last interaction, next follow-up, promised actions, reminders, outreach drafts, and open loops. Relationship Operations require stricter auditability and confirmation than Relationship Context because they can lead to external actions.

## Hard Relationship Reminder

A date-based Relationship Operation that should surface at a specific time, usually tied to a concrete promise, deadline, event, or follow-up.

## Soft Relationship Cadence

A relationship-health preference describing how often the user wants to reconnect with a Person or group of people. Soft Relationship Cadence informs Reconnection Recommendations but is not a deadline.

## Reconnection Recommendation

A Relationship Management recommendation that suggests who the user should reconnect with and why. It is based on last interaction, open loops, Relationship Context, Person Concept Links, linked Personal Notes, and Recommendation Confidence.

## Reconnection Recommendation Record

The structured output of recommend_reconnections. It includes person identity, Relationship Type, a short action recommendation, reasons from the Relationship Store, Relationship State Labels, Recommendation Confidence, whether drafting is allowed, and an optional suggested angle without generating a message by default.

## Intentional Reconnection

The goal of Reconnection Recommendations: helping the user care for the right relationships at the right time, not maximizing contact volume or networking throughput. Intentional Reconnection prioritizes open loops, promises, cadence, important dates, shared concepts, and tact around sensitive context.

## Relationship State Label

An explainable non-numeric status used for relationship recommendations, such as needs_follow_up, has_open_loop, cadence_due, recently_connected, dormant, or sensitive_context. Relationship State Labels avoid fake precision while keeping recommendations auditable.

## Relationship Draft Boundary

The rule that the agent may draft outreach for professional, collaboration, or networking relationships when it fits the context, but should avoid drafting intimate personal messages. For personal relationships, the agent can suggest context, reminders, or angles while leaving the actual wording to the user.

## Relationship Type

A user-set classification on a Person Record, such as friend, family, collaborator, mentor, prospect, community, professional, networking, or unknown. The agent may suggest a Relationship Type, but should not silently change it because Relationship Type controls drafting, reminders, privacy, and action boundaries.

## Relationship Store

The canonical local store for Person Records, Relationship Context, interaction history, open loops, important dates, and optional links to Personal Notes. The Relationship Store is separate from the Notes Store because relationship data has more sensitive retrieval, visibility, and deletion rules.

## Explicit Person Capture

The rule that a Person record is created only when the user explicitly asks to add or remember a person. The agent may suggest a possible Person from a relationship note, but ordinary chat should not silently create durable people records.

## Person Disambiguation

The rule that ambiguous names or aliases must be resolved before changing Relationship Management state. When multiple Person Records match, the agent should ask using brief context snippets rather than auto-merging or choosing the strongest match.

## Mobile Relationship Surface

The Discord/mobile-facing Relationship Management surface for capture and lookup commands such as adding a Person, saving a relationship note, logging an interaction, asking who to reconnect with, or inspecting what is known about a Person. Proactive notifications and external sending are excluded from the first mobile surface.

## Source

An external document or reference the Personal Knowledge Manager can read for grounded understanding, such as a Paper, doc, PDF, transcript, manual, web page, or email. Sources provide evidence and citations for Source Mode and Synthesis Mode.

## Paper

A Source document placed in `papers/` for ingestion. Supported forms are `.txt`, `.md`, and optionally `.pdf`.

## Evidence Passage

A short, cited text span extracted from a paper. Evidence passages are the unit used for grounded answers.

## Evidence Scope

An explicit knowledge-base record label that restricts retrieval to a named evidence corpus, such as `mentor:simon` or `mentor:lanier`. Evidence Scopes are stored as record metadata and are the canonical boundary for scoped retrieval.

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

## Person Concept Link

A weak typed relationship between a Person and a Concept, used for relationship retrieval and context surfacing. Person Concept Links are not paper evidence, not automatic User Interests, and not proof of the Person's preferences unless the Relationship Context explicitly says so.

## Personalized Recommendation

A suggested next action that explains which user preference, interest, or text passage caused the suggestion.

## Text Understanding

The agent's source-grounded view of an ingested paper, represented by concepts, notes, evidence passages, and citations.

## Working Knowledge

Captured or sourced material transformed into reusable understanding, personal questions, ideas, decisions, and actions the user can return to.

## Knowledge Management

The agent's broader local process for capturing, organizing, retrieving, and applying the user's working knowledge across Sources, Personal Notes, Relationship Context, Interaction Signals, Candidate Signals, the User Model, the Concept Graph, and Tutor Progress.

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

Turning source evidence into personal recommendations only after the source claim, support, and limitation are understood.

## Research Taste

The Personal Knowledge Manager's ability to judge whether a source is worth skimming, deep study, comparison, or discard for the user's current goals.

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

A compact durable output from a meaningful Personal Knowledge Manager interaction, such as concept cards, decision notes, open questions, Builder Ideas, relationship follow-ups, study prompts, or a reading queue.

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

## Relationship Management Surface

The initial tool set for working with Relationship Management: add_person, list_people, get_person, search_people, add_relationship_note, log_relationship_interaction, recommend_reconnections, and forget_person. The surface includes soft deletion from the first slice because relationship data is sensitive.

## Personal Notes Module

The implementation boundary for Personal Note storage, extraction, Markdown rendering, search, correction, deletion, and Concept Graph integration. The agent exposes Personal Notes through thin tool wrappers rather than placing the full notes workflow inside the main agent file.

## Relationship Management Module

The implementation boundary for Relationship Management storage, Relationship Events, Derived Person Summaries, search, reconnection recommendations, corrections, and future reminder integration. The agent exposes Relationship Management through thin tool wrappers rather than creating a separate ADK agent or placing the full workflow inside the main agent file.

## Notes Vertical Slice

An incremental implementation step that delivers a usable part of Personal Notes end to end, such as capture/search, extraction, Markdown mirrors, graph integration, answer synthesis, question ranking, or correction workflows.

## Relationship Vertical Slice

An incremental implementation step that delivers a usable part of Relationship Management end to end, such as person capture, relationship note logging, interaction history, reconnection recommendations, correction workflows, concept links, mobile lookup, or reminders.

## First Relationship Slice

The initial Relationship Vertical Slice focused on local Person capture, listing, inspection, lexical search, relationship notes, interaction logging, and Reconnection Recommendations. It intentionally excludes Discord-specific code, proactive notifications, message sending, Markdown mirrors, and model-based extraction.

## Relationship Markdown Mirror

A future human-readable Markdown representation of a Person Record, intended for browsing, portability, and Obsidian-like relationship review. Relationship Markdown Mirrors are excluded from the First Relationship Slice because the core value is capture, lookup, and reconnection behavior.

## First Notes Slice

The initial Notes Vertical Slice focused on local Personal Note capture, listing, inspection, lexical search, explicit note prompt routing, and tests. It intentionally excludes Markdown mirrors, model-based extraction, and Concept Graph integration unless they are needed for the basic capture/search loop.

## Knowledge Self-Audit Slice

A later Notes Vertical Slice focused on inspecting and correcting the Self-Learning Knowledge Loop. It includes a Knowledge Self-Audit view and Self-Audit Corrections, but is intentionally kept out of the First Notes Slice.

## Personal Note Record

The canonical structured representation of a Personal Note in the Notes Store. A Personal Note Record includes stable identity, current text, tags, extracted Note Cards, linked Concepts, Candidate Signals, Markdown mirror location, soft-delete state, and Note Versions.

## Artifact Offer

A specific proposal for a Session Artifact that names the intended shape before the agent creates it.

## Agent Mode

A named operating posture that tells the Personal Knowledge Manager which job to emphasize, such as capturing, retrieving, sourcing, synthesizing, building ideas, grilling, tutoring, reviewing, writing, producing artifacts, reflecting, managing relationships, or administering the system.

## Mode Stack

The rule that a Personal Knowledge Manager response should have one primary Agent Mode and at most one supporting Agent Mode. Mode Stack allows workflows such as Synthesis supported by Retrieve or Tutor supported by Source without letting many modes compete at once.

## Mode Visibility

The rule that the Personal Knowledge Manager infers modes silently by default and names the active mode only when it helps clarify behavior, resolve ambiguity, or explain a mode switch. Mode Visibility avoids prefixing every response with mode labels.

## Capture Mode

An Agent Mode for quickly saving personal knowledge objects, including Personal Notes, Person Records, Relationship Context, idea fragments, open loops, important dates, and explicit user preferences. Capture Mode optimizes for low-friction explicit capture while preserving later correction.

## Capture Classification

The rule that unmarked conversation is not saved, but once the user invokes Capture Mode with language such as note, idea, add person, relationship note, or remember, the Personal Knowledge Manager may infer the captured object's subtype and return a correction affordance.

## Retrieve Mode

An Agent Mode for finding and connecting existing knowledge across Personal Notes, Papers, People, Concepts, prior decisions, Session Artifacts, and the User Model. Retrieve Mode optimizes for recall, cross-linking, and provenance-aware answers.

## Synthesis Mode

An Agent Mode for making meaning across retrieved knowledge, such as connecting Personal Notes with Papers, comparing user beliefs with literature evidence, finding themes across notes or relationship context, and turning fragments into a coherent theory or interpretation. Synthesis Mode differs from Retrieve Mode because it creates structured understanding rather than only finding relevant material.

## Writing Mode

An Agent Mode for transforming knowledge into prose with attention to voice, flow, expression, and audience. Writing Mode handles essays, reflections, drafted messages, explanations, proposals, narrative summaries, and polished notes, while Artifact Mode handles durable structured outputs.

## Source Mode

An Agent Mode for faithfully understanding external sources such as Papers, docs, PDFs, transcripts, manuals, web pages, or emails with citations, evidence passages, concepts, limitations, and grounded summaries. Source Mode is the evidence-first reading capability inside the broader Personal Knowledge Manager.

## Reader Mode

An alias for Source Mode retained for paper/doc-reading prompts and existing ADR language.

## Reflect Mode

An Agent Mode for inspecting, explaining, and correcting what the Personal Knowledge Manager believes it knows about the user, including confirmed preferences, Candidate Signals, Concept Graph weights, Tutor Progress, Relationship boundaries, User Profile entries, and Knowledge Self-Audit findings. Reflect Mode replaces Profile Mode as a top-level operating posture.

## Relationship Mode

An Agent Mode for managing people, Relationship Context, interaction history, open loops, soft cadence, important dates, and Reconnection Recommendations. Relationship Mode stays top-level because relationship data has special privacy, disambiguation, drafting, retrieval, and personalization boundaries.

## Taste Mode

An Agent Mode for judging whether a knowledge object, source, idea, note, project, workflow, or relationship-management direction deserves attention. Taste Mode can recommend skim, study, build, compare, park, discard, research further, or transform, and should justify the judgment with provenance and user fit.

## Review Mode

An Agent Mode for inspecting an existing artifact, code change, ADR, note, plan, idea, user-model assumption, or recommendation for quality, correctness, risks, gaps, regressions, and missing tests. Review Mode differs from Taste Mode because it evaluates the quality of something already produced rather than whether it deserves attention.

## Grill Mode

An Agent Mode for one-question-at-a-time pressure testing of papers, plans, beliefs, preferences, relationship ideas, learning gaps, or design assumptions. Grill Mode is the broad operating posture; Builder Grill is a specialized technique used inside Builder Mode.

## Admin Mode

An Agent Mode for operational management of the Personal Knowledge Manager, including settings, imports, exports, sync, deletion, purging, backups, health checks, migrations, deployment, secrets, model/backend config, API/mobile surfaces, and storage health.

## Session Goal

The user's current task or purpose for a Personal Knowledge Manager interaction, which takes priority over long-term profile preferences.

## Goal Clarification

A single question the agent asks only when the session goal is ambiguous enough to materially change the output.

## Improvement Proposal

A suggested change to the Personal Knowledge Manager, supported by evidence and confidence, that requires explicit approval before any code is modified.

## Concept Graph

A local typed projection connecting User Interests, Concepts, Papers, Personal Notes, Note Cards, People, Relationship Events, and prerequisite hints. The Concept Graph supports ranking, retrieval, backlinks, questioning, and synthesis, but canonical facts remain owned by their source stores.

## Typed Knowledge Projection

A rebuildable graph view over canonical stores such as the Notes Store, Relationship Store, Knowledge Base, User Model, Tutor Progress, and interaction logs. A Typed Knowledge Projection preserves provenance and cross-domain traversal without becoming the source of truth for notes, people, papers, or preferences.

## Projection Plumbing

The write-side coordination that updates the Typed Knowledge Projection after canonical stores change. Projection Plumbing belongs after canonical writes and before graph inspection, so retrieval and audits reflect notes, tutor answers, grill answers, and relationship events without making those stores depend on the graph.

## Best-Effort Projection Update

A synchronous projection update attempted immediately after a canonical store write succeeds. Best-Effort Projection Updates must not roll back the canonical write when projection refresh fails, but should return or log enough status for later inspection.

## Projection Status

A compact tool-result field that reports whether a Best-Effort Projection Update succeeded, failed, was skipped, or was not applicable. Projection Status keeps stale graph/retrieval behavior inspectable without turning projection failures into canonical write failures.

## Projection Rebuild Path

A future maintenance path that can reconstruct the Typed Knowledge Projection from canonical stores and typed provenance. The Projection Rebuild Path is not required for the first projection slice, but first-slice projection records should preserve enough source type and source ID information to make it possible later.

## Canonical Knowledge Store

The source-of-truth local store for a specific kind of knowledge, such as Personal Notes, Relationship Events, paper records, User Model entries, or Tutor Progress. Canonical Knowledge Stores own correction, deletion, privacy, and migration rules for their records.

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

An Agent Mode where the Personal Knowledge Manager teaches concepts through an explain-then-quiz loop, grades free-text answers, and adapts the curriculum to the user's mastery level. Tutor Mode can draw from Sources, Personal Notes, Concept Graph links, Builder Ideas, and Tutor Progress, while preserving evidence boundaries for factual or source-grounded grading.

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

## Builder Mode

An agent mode for Socratic ideation and design partnership. Builder Mode helps the user formulate loose ideas into more cohesive designs through clarification, structured idea generation, provenance, and component-level grilling. Builder Mode draws from all three knowledge sources: User Model for personalization, ingested papers for grounding, and LLM knowledge for breadth.

## Planning Mode

A possible future Agent Mode for sequencing concrete work into milestones, dependencies, issues, and acceptance criteria. Planning Mode is not top-level initially because Artifact Mode can produce PRDs, issue lists, and build plans until planning becomes frequent enough to deserve its own posture.

## Decision Mode

A possible future Agent Mode for high-stakes option selection and trade-off resolution. Decision Mode is not top-level initially because Builder Mode clarifies options, Taste Mode judges attention, Reflect Mode checks preference conflicts, and Artifact Mode can preserve decision notes or ADRs.

## Briefing Mode

A possible future Agent Mode for on-request or proactive daily/weekly summaries of notes to revisit, open loops, reconnection candidates, queued Sources, weak concepts, stale ideas, and admin warnings. Briefing Mode is deferred until the underlying stores and reminder/cadence behavior are stable.

## Builder Co-Authorship

The rule that Builder Mode treats cohesive ideas as co-authored with the user. The agent may propose structure, names, theses, components, and critiques, but should repeatedly check what feels alive, wrong, worth preserving, or closest to the user's intent.

## Builder Entry Condition

The rule that Builder Mode activates when the user is designing, inventing, comparing, brainstorming, or stress-testing a system, product, workflow, or plan. Builder Mode should not hijack direct implementation, paper-reading, tutoring, or note-capture requests because it is intentionally slower and more Socratic.

## Builder First Response

The first move in Builder Mode: ask exactly one Socratic question that exposes the most important missing constraint, with a brief explanation only when it helps the user answer. Builder First Response avoids immediate proposals, long questionnaires, and broad decision inventories.

## Builder Audience Constraint

A missing audience or user-context detail that materially changes a Builder Idea. Builder Mode should ask about audience when it affects components, privacy, workflow, or success criteria, but should not ask by default when the audience is already clear enough from the prompt.

## Builder Clarification Budget

The rule that Builder Mode normally generates ideas after the user's first Socratic answer. The agent may ask one additional clarifying question only when the target remains materially ambiguous enough that idea generation would likely be wrong.

## Builder Idea

A coherent candidate design generated in Builder Mode. A Builder Idea includes a name, thesis, three to six major components, why it fits the user, key risks, and a Builder Next Move.

## Builder Thesis

The central bet of a Builder Idea. A Builder Thesis explains what the idea is really trying to make true, why its components belong together, what novelty must serve, and what the Builder Grill should test.

## Builder Output Shape

The light structured format for Builder Mode responses. Generated Builder Ideas use name, thesis, components, why it fits the user, novel move, risks, and Builder Next Move; Builder Grill turns use component, current read, and one question, with conversational connective tissue where useful.

## Builder Next Move

The suggested next action after a Builder Idea or Builder Grill step. A Builder Next Move may be to build a first slice, write a PRD, save a Personal Note, create an ADR, find papers, run a prototype, keep grilling one component, discard the idea, or park it for later.

## Builder Optimization Order

The priority order for shaping Builder Ideas: coherence first, personal fit second, grounding third, and idea-fitting novelty fourth. Novelty should strengthen the Builder Idea's thesis, components, or next move rather than adding unrelated cleverness.

## Builder Novelty Floor

The rule that every Builder Idea should include at least one idea-fitting novel move. Conservative Builder Ideas get a small twist, robust Builder Ideas get one or two architectural or process innovations, and Weird-Adjacent Builder Ideas may make novelty the main framing.

## Builder Idea Set

The group of candidate designs generated after Builder clarification. Builder Mode produces three competing Builder Ideas by default: a conservative fastest path, a robust long-term architecture, and a weird-adjacent high-upside experiment. It may produce five ideas only for broad or explicitly exploratory brainstorming.

## Builder Recommendation

The agent's point-of-view selection of one Builder Idea from the generated set, justified briefly by user fit, risk, and next-move clarity. Builder Recommendation preserves user agency by asking which idea or component the user wants to grill next rather than forcing the recommended path.

## Builder Choice Point

The handoff after Builder Ideas are generated. The agent gives a Builder Recommendation, then asks the user to choose an idea to grill, combine pieces, sharpen the set, or take a Builder Next Move; it does not automatically grill the recommended idea.

## Builder Recombination

The act of combining components from multiple Builder Ideas into a new cohesive Builder Idea. Builder Recombination must produce a new name, thesis, retained components, dropped components, risks, and Builder Next Move rather than merely mashing ideas together.

## Builder Fork

An unresolved option inside a Builder Idea, such as two possible storage models or user surfaces. Builder Mode may preserve Builder Forks briefly during exploration, but should converge before artifact or implementation handoff, or explicitly mark the fork as an unresolved decision.

## Builder Reframing

The Builder Mode response to weak or incoherent ideas. Builder Reframing preserves the user's core desire, names the current incoherence or conflict, offers two or three stronger framings, and asks which framing feels closest.

## Builder Taste Judgment

The Builder Mode ability to say an idea is not worth pursuing in its current form while offering a salvage path. Builder Taste Judgment can recommend parking, discarding, researching, reframing, or transforming an idea based on coherence, fit, cost, constraints, and value.

## Weird-Adjacent Builder Idea

The high-upside Builder Idea that bends framing, architecture, workflow, or user surface while still respecting hard user constraints. Weird-Adjacent Builder Ideas may be imaginative, but must not violate privacy boundaries, budget constraints, local-only requirements, explicit non-negotiables, or action boundaries.

## Builder Component

A decision-bearing part of a Builder Idea that should be stress-tested before implementation, such as memory store, retrieval strategy, agent workflow, input surface, privacy boundary, correction loop, deployment model, or evaluation method. Builder Components exclude low-level implementation details unless those details materially affect the design.

## Ideation Provenance

A component-level source tag in a Builder Idea marking the origin of that component: `[from your notes]` for User Model or Personal Notes content, `[cited: source]` for paper-grounded claims, and `[inference]` for LLM-generated suggestions. Every component gets at least one dominant tag, with multiple tags allowed when a component mixes sources.

## Builder Citation Boundary

The rule that Builder Mode may use `[cited: source]` only after retrieving paper evidence with a grounding tool such as search_evidence. Components inspired by remembered concepts or general model knowledge without retrieved evidence must be tagged `[inference]`.

## Builder Domain Gap

A domain area in a Builder Idea where the agent lacks grounded sources or sufficient user-provided context. Builder Mode can still help structure the idea around a Builder Domain Gap, but must label domain-specific claims as inference and offer research, document ingestion, or assumption prototyping as Builder Next Moves.

## Builder Codebase Grounding

The rule that Builder Mode should inspect current code, docs, tests, and worktree constraints when the user is designing this agent or another local codebase. For external or non-code ideas, Builder Mode may stay conceptual unless the user asks for implementation.

## Builder Note Boundary

The rule that Personal Notes can shape fit, vocabulary, recurring constraints, prior design taste, and candidate components in Builder Mode, but cannot serve as source evidence for factual or architectural claims. Note-derived synthesis should be tagged `[from your notes] [inference]`.

## Builder Relationship Boundary

The rule that Relationship Management data may shape Builder Mode only when the user is designing relationship-related workflows or explicitly asks to use relationship context. Builder Mode should not use relationship data for unrelated ideas, broad personality inference, or examples naming real people unless directly relevant and requested.

## Builder Artifact Boundary

The rule that Builder Mode does not automatically save brainstorms, design choices, or inferred preferences as durable Personal Notes or User Model entries. At the end of a Builder session, the agent may offer a specific Session Artifact such as a decision note, build plan, issue list, or ADR, and only saves it after explicit user approval.

## Builder Artifact Offer

A specific offer to preserve a Builder Mode result as a Session Artifact after a meaningful cohesion point, such as an emerged thesis, stabilized component map, explicit decision, requested save, or chosen Builder Next Move. Builder Artifact Offers should not appear after every small exchange.

## Builder Session State

The transient conversational state of a Builder Mode interaction, including the current Builder Idea Set, selected Builder Idea, current Builder Component, and resolved grill questions. Builder Session State is not durably stored in the first version; durable output is created only through an explicit Session Artifact.

## Builder Stopping Condition

The point where a Builder Mode session is done enough: the Builder Thesis is clear, components are named and fit together, major risks and trade-offs are visible, provenance is labeled, and a Builder Next Move is chosen or intentionally parked. Builder Mode should not keep grilling after this point merely to exhaust every possible question.

## Builder Tool Boundary

The rule that Builder Mode remains instruction-only in its first version, using existing profile, notes, evidence, and tutor tools rather than adding a dedicated generate_builder_ideas tool. A builder tool becomes justified only if idea format, provenance tagging, selected-idea tracking, or resumability proves inconsistent.

## Builder Tutor Adaptation

The narrow use of Tutor Progress inside Builder Mode. Builder Tutor Adaptation tunes explanation depth, scaffolding, grill sharpness, and knowledge-gap warnings for relevant concepts, but must not lower the user's ambition, decide what the user is capable of building, or override the user's stated goal.

## Builder Grill

The component-level stress-test phase of Builder Mode. The agent probes one component at a time across seven dimensions: feasibility, trade-offs, hidden assumptions, risks, adjacent possibilities from papers or notes, conflicts with the user's stated preferences, and knowledge gaps surfaced by Tutor Progress. Questions are asked one at a time, one component at a time.

## Record Validation

The guarantee that a loaded record matches its expected shape before any business logic touches it. Implemented via TypedDict schemas and assert guards at load boundaries in each data module. Catches structural corruption from malformed JSONL lines, missing required keys, or wrong-typed fields without adding external dependencies.

## Web Evidence

The fourth provenance lane in the agent's answer taxonomy. Tagged `[from web: domain.com]`, presented separately from paper evidence because the trust bar is lower than peer-reviewed research, but still cited with source URLs. Web-sourced claims are capped at Medium recommendation confidence — never High.

## Source Quality

A classification tag on web search results indicating the type of source. Values include `official-docs`, `peer-reviewed`, `technical-blog`, `forum`, `vendor`, and `unknown`. Used alongside Recommendation Confidence to help the user gauge the trustworthiness of web-sourced claims.

## Web Search Pipeline

The end-to-end flow for search-augmented Q&A: user query → LLM query rewriting → search API → fetch top 3 result pages → HTML text extraction → structured results with source_quality tags and provenance labels.

## Polish Preference

A per-context adaptation setting controlling how much the agent rewrites the user's prose. Levels: `none` (keep exactly as written), `light` (grammar only), `moderate` (grammar + flow), `full` (significant restructuring). Learned from explicit corrections and stored in the User Model, keyed by context (chat, technical, creative, default). The agent starts proactive at `moderate` and adapts downward when the user pushes back.

## Writing Mode

An Agent Mode for transforming knowledge into prose with attention to voice, flow, expression, and audience. Writing Mode applies Polish Preferences to the user's prompts and responses, handling essays, reflections, drafted messages, explanations, proposals, narrative summaries, and polished notes. Distinct from Artifact Mode, which handles durable structured outputs.

## Cognitive Adaptation

Agent behavior adjustments that account for cognitive traits like attention variability, working memory constraints, and motivation drivers. The agent defaults to ADHD-aware interaction patterns: chunked answers, upfront structure, relevance-first explanations, varied pacing, concrete next actions, and drift-tolerant re-anchoring on session resume.

## Session Metadata

Lightweight per-session summary fields stored in `session_meta.jsonl`: session timing, message count, inferred goal, topic stability, completion status, and question depth trajectory. Enables future passive engagement inference without real-time tracking. Follows the same append-only JSONL pattern as interaction logs and candidate signals.

## Performance Budget

A per-turn runtime policy that controls latency-sensitive agent behavior, including how much context is preloaded, which tool groups are exposed, when durable memory writes are allowed, and when fresh tool calls should replace system-instruction context.

## Performance Budget Tier

One of three runtime performance postures: `fast` for minimal context and narrow tools, `balanced` for normal agent work, and `deep` for richer retrieval and multi-step synthesis.

## Attention Drift Recovery

The agent's pattern for re-engaging after a pause: acknowledge the gap without judgment, offer the anchoring context in one sentence, and ask whether to continue or pivot. Prevents recap dumps that overwhelm working memory.

## Agent Persona

*Replaced by Cognitive Mentor (ADR 0068).*

## Mentor Mode

An Agent Mode where the agent thinks through a specific thinker's cognitive framework using their ingested papers as the reasoning substrate. The default cognitive mentor is Herbert Simon (systematic design thinking, bounded rationality, evidence-grounded); Jaron Lanier is invoked by name (human-centered, contrarian, philosophical). The mentor grounds every claim in cited evidence from the thinker's own work and adapts delivery to the user's personality and cognitive traits through the full PKM infrastructure.

## Cognitive Mentor

An agent mode where the agent thinks through a specific thinker's frameworks using their ingested papers as the reasoning substrate, grounding every claim in cited evidence from that thinker's work. Distinct from a persona — the mentor doesn't quote, they reason through the evidence.

## Mentor Relationship

The bidirectional adaptation between cognitive mentor and mentee: the mentor's ingested papers provide the intellectual lens and evidence base, while the User Model personalizes delivery, pacing, and context selection for the specific person being mentored.

## Builder Grill Sequence

The preferred order for stress-testing a Builder Component: purpose, boundary, risk, trade-off, evidence/provenance, user fit, and first-slice test. Builder Grill Sequence is adaptive: the agent should stop probing a component once its major uncertainty is resolved rather than asking every possible question mechanically.
