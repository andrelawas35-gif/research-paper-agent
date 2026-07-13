# Context Glossary

## Personal Knowledge Manager

A local Google ADK agent that helps the user capture, organize, retrieve, and develop personal knowledge across papers, Personal Notes, relationship context, ideas, tutor progress, and the User Model. Paper reading remains a grounded capability inside the broader Personal Knowledge Manager rather than the product's whole identity.

## Regulation Mode

The Personal Knowledge Manager posture that helps the user choose the action most supportive of their welfare, values, boundaries, and long-term outcomes while emotionally activated. It may assess the plausibility of competing interpretations, but neither factual certainty nor immediate emotional relief is its primary objective.
_Avoid_: Life Coach Mode, Reassurance Mode, Relationship Truth Detector

## Regulation Recommendation

An action recommendation based on reported facts, uncertainty, the user's state, personal rules, values, boundaries, likely consequences, and relevant recurring patterns. A Regulation Recommendation must distinguish what is known from what is inferred and can remain useful even when the truth of another person's motives is unresolved.
_Avoid_: Reassurance, verdict

## Regulation Session

An explicitly started interaction in which Regulation Mode guides and, when permitted, records the user's movement from a Trigger through interpretation, emotion, urge, chosen action, and outcome. Ordinary conversation does not silently become a Regulation Session.
_Avoid_: Case, episode

## Private Check-In

An ephemeral Regulation Session whose contents are used for the current interaction but are not added to durable regulation history. A Private Check-In may still produce an explicitly requested user-owned summary before it is discarded.
_Avoid_: Incognito Mode

## Regulation Record

The compact durable representation of a Regulation Session, retaining only information useful for future reflection and adaptation by default. Names, transcripts, sexual specifics, accusations, and other intimate narrative details require explicit retention rather than automatic capture.
_Avoid_: Chat transcript, psychological profile

## Regulation Store

The canonical append-only store for Regulation Events and the Regulation Records derived from them. Its contents influence Regulation Mode and explicit reflection by default rather than becoming general claims about the user's identity.
_Avoid_: Therapy Record, User Profile

## Regulation Pattern

A provisional, correctable summary of recurrence across durable Regulation Records, such as a commonly reported Trigger, urge, action, or outcome. A Regulation Pattern describes the recorded situations and does not by itself define the user's personality or become a Confirmed Adaptation.
_Avoid_: Trait, diagnosis

## Personal Regulation Rule

An explicitly confirmed instruction the user wants Regulation Mode to apply, such as pausing before sending another message or separating facts from interpretations. It may be surfaced outside Regulation Mode only when directly relevant and must not expose the sensitive history from which it arose.
_Avoid_: Treatment rule

## Values Compass

The Personal Knowledge Manager capability that helps the user articulate, confirm, revisit, and act consistently with Core Values, Purpose, and commitments across modes. It provides orientation rather than defining the user's identity from observed behavior.
_Avoid_: Personality Profile, motivational feed

## Candidate Value

A provisional interpretation of what may matter deeply to the user, supported by traceable statements, choices, Personal Notes, goals, or recurring behavior. A Candidate Value cannot become a Core Value without explicit user confirmation.
_Avoid_: Inferred Value, hidden preference

## Core Value

A user-confirmed enduring quality or principle that the user wants to express through choices across multiple areas of life. Interests, topics, activities, and isolated emotional statements are not Core Values merely because they recur.
_Avoid_: Interest, personality trait

## Value Evidence

A traceable statement, choice, Personal Note, goal, or recurring behavior that supports or conflicts with a Candidate Value or Core Value. Value Evidence informs reflection but never silently establishes or removes a Core Value.
_Avoid_: Proof

## Purpose

A user-confirmed broad account of the life direction or contribution the user wants their choices to serve. Purpose orients Core Values, Personal Principles, Goals, and Commitments without requiring every action to justify itself through a single statement.
_Avoid_: Mission statement

## Personal Principle

A user-confirmed behavioral rule that operationalizes one or more Core Values in recurring situations. A Personal Principle is more concrete and revisable than a Core Value and may be refined when outcomes show that it no longer serves its intended values.
_Avoid_: Core Value, commandment

## Goal

A desired, usually time-bounded outcome through which the user currently expresses Purpose and Core Values. A Goal may change without implying that the underlying Core Values changed.
_Avoid_: Purpose, value

## Commitment

A specific near-term promise or chosen action connected to a Goal, Personal Principle, or Core Value. Commitments are the most operational and frequently changing layer of the Values Compass.
_Avoid_: Value, aspiration

## Value Tension

A situation in which two or more Core Values or Personal Principles support different actions. The Values Compass makes the tension explicit and recommends a contextual trade-off rather than imposing one permanent ranking across all situations.
_Avoid_: Value failure, inconsistency

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

## Cognitive Support Model

The correctable, context-specific model of which interaction tactics help the user initiate, sustain, switch, plan, recover, regulate, and complete different kinds of work. It is organized by support dimensions and observed outcomes rather than using ADHD or another diagnostic label as a universal explanation.
_Avoid_: ADHD Profile, capability score

## Cognitive Support Dimension

A separately adaptable area of assistance such as working-memory support, task initiation, sustained attention, task switching, planning, motivation, recovery, or emotional activation. Support can vary by mode and task without implying a global limitation.
_Avoid_: Symptom score

## Cognitive Support Tactic

A concrete interaction strategy offered within a Cognitive Support Dimension, such as showing one step, using a five-minute start, parking a distracting idea, re-anchoring after a pause, or connecting a task to a Core Value. A tactic becomes a durable default only after explicit confirmation.
_Avoid_: Treatment, accommodation

## Support Outcome

A traceable result following a Cognitive Support Tactic, including whether the user accepted it and whether it helped the intended task begin, continue, recover, or complete. Support Outcomes inform provisional recommendations but do not prove why the tactic worked.
_Avoid_: Clinical outcome

## Support Acceptance

Evidence that the user chose or attempted an offered Cognitive Support Tactic. Acceptance is weaker than a helpful outcome and does not establish that the tactic should be repeated.
_Avoid_: Success

## Behavioral Support Outcome

A runtime-observed task event following a Cognitive Support Tactic, such as beginning, continuing, returning to, intentionally pivoting from, or completing the intended activity. It establishes sequence rather than proving that the tactic caused the result.
_Avoid_: Causal proof

## Self-Reported Support Outcome

The user's explicit assessment that a Cognitive Support Tactic helped, hindered, or had no meaningful effect. It complements behavioral evidence and may describe benefits or friction that runtime events cannot observe.
_Avoid_: Rating requirement

## Confirmed Support Default

A context-specific Cognitive Support Tactic the user has explicitly authorized the agent to apply automatically. Repeated positive Support Outcomes justify proposing a default but cannot silently create one.
_Avoid_: Global default, inferred accommodation

## Contextual Reminder

A brief orientation surfaced within an active task because a confirmed Core Value, Personal Principle, Goal, Commitment, or support tactic is directly relevant. Contextual Reminders are enabled by default but must provide a useful connection rather than generic motivation.
_Avoid_: Affirmation

## Event-Driven Check-In

An explicitly enabled prompt attached to a meaningful runtime event such as returning after a gap, repeatedly leaving a Goal unfinished, completing a milestone, or entering Regulation Mode. Permission is scoped to the relevant Goal, Commitment, or workflow.
_Avoid_: Notification

## Scheduled Reflection

An opt-in Values Compass or Cognitive Support review requested for a chosen cadence, such as weekly values review or an end-of-study reflection. A Scheduled Reflection is not created merely because the agent predicts it could be useful.
_Avoid_: Automatic reminder

## Reminder Outcome

The user's explicit or behavioral response to a Contextual Reminder, Event-Driven Check-In, or Scheduled Reflection, including usefulness, timing, repetition, motivation, guilt, irrelevance, or non-response. Reminder Outcomes tune frequency and presentation without silently changing Core Values or Goals.
_Avoid_: Engagement score

## Personal Orientation Snapshot

A read-only, task-scoped projection of the smallest relevant set of confirmed and provisional personal context selected from the User Model, Values Compass, Cognitive Support Model, Regulation Store, Relationship Store, Notes Store, and learning state. It is the single seam through which personalized state reaches model context and is never a canonical store or write target.
_Avoid_: Unified Profile, memory dump

## Orientation Item

One source-attributed entry in a Personal Orientation Snapshot, carrying its owning store, status, confidence where applicable, sensitivity, and relevance to the active task. Conflicting Orientation Items remain visible rather than being silently collapsed.
_Avoid_: Prompt fact

## Orientation Policy

The deterministic rules that decide which stores and Orientation Items are eligible for a Personal Orientation Snapshot based on mode, permission, sensitivity, record status, and explicit user scope. Model-based relevance ranking operates only after Orientation Policy has allowed access.
_Avoid_: Prompt instruction, model discretion

## Orientation Ranking

The ordering of policy-permitted Orientation Items by direct relevance, explicit user priority, confidence, recency, prior outcomes, and the current context budget. Ranking may use model judgment but cannot grant access, restore deleted records, or override sensitivity rules.
_Avoid_: Memory retrieval

## Emergency Regulation Session

A Regulation Session opened when the user reports spiraling or urgent emotional activation. It moves through a user-steerable sequence of Safety Screen, stabilization, fact and interpretation separation, emotion and urge identification, option and boundary assessment, deliberate action selection, pause or execution, outcome recording, and closure.
_Avoid_: Crisis diagnosis, emergency therapy

## Safety Screen

The brief first check in an Emergency Regulation Session for immediate danger, risk of harm to self or others, or an imminent irreversible action. It determines whether ordinary regulation coaching may proceed and is not a diagnosis or broad clinical assessment.
_Avoid_: Risk score, psychological assessment

## Activation Level

A current-session interaction setting describing how much cognitive load Regulation Mode should impose: highly activated, moderately activated, or reflective. Activation Level changes pacing and depth without becoming a durable diagnosis or trait.
_Avoid_: Severity score

## Deliberate Action

The action selected during a Regulation Session after considering facts, uncertainty, emotions, urges, boundaries, values, likely consequences, and applicable Personal Regulation Rules. It may be a pause, one bounded action, or an explicit decision to take no action yet.
_Avoid_: Correct reaction

## Safety Branch

The deterministic Emergency Regulation Session path that temporarily suspends ordinary analysis when the Safety Screen identifies immediate physical danger, imminent self-harm, imminent harm to another person, abuse or coercive control, or an irreversible action underway. It focuses only on the next safe action and exits only when immediate risk is no longer active.
_Avoid_: Regulation coaching, crisis counseling

## Safety Event

The minimal durable record that a Safety Branch was activated and its broad risk category. Detailed crisis content, Candidate Values, Regulation Patterns, and identity-level adaptations are excluded by default.
_Avoid_: Crisis transcript, clinical record

## Relationship Reality Check

A Regulation Mode assessment that separates reported facts, corroboration, interpretations, alternative explanations, comparable pattern history, harm, urgency, reversibility, boundary relevance, and missing information before recommending action. It may estimate plausibility but does not force the situation into a single verdict.
_Avoid_: Truth detector, jealousy test

## Reported Fact

An action, statement, or condition the user presents as directly observed, preserved with its source and without treating the report as independently verified. Reported Facts remain distinct from Interpretations and Corroboration.
_Avoid_: Verified fact, objective truth

## Interpretation

A proposed meaning, motive, or implication attached to one or more Reported Facts. Interpretations may be compared by plausibility but remain uncertain unless sufficient Corroboration exists.
_Avoid_: Fact, diagnosis

## Boundary-Relevant Behavior

Reported behavior that matters because it may cross a user-confirmed boundary regardless of whether another person's motive can be established. Boundary relevance can justify clarification or protective action without proving dishonesty or malicious intent.
_Avoid_: Proven violation

## Reality-Check Assessment

The source-attributed output of a Relationship Reality Check, including evidence strength, potential harm, urgency, reversibility, boundary relevance, uncertainty, and the smallest information-gathering or protective action likely to help the user.
_Avoid_: Verdict

## Rule Strength

The user-confirmed enforcement posture of a Personal Regulation Rule or Personal Principle: Hard Guardrail, Default Principle, or Reflection Prompt. Rule Strength controls how firmly the agent challenges a contemplated action without turning user-owned rules into hidden system policy.
_Avoid_: Importance score

## Hard Guardrail

A user-confirmed rule the agent will not recommend violating, while still allowing the user to inspect and revise the rule outside an activated decision. Safety, anti-coercion, anti-surveillance, anti-retaliation, and anti-harm constraints remain separate non-overridable system guardrails.
_Avoid_: System policy

## Default Principle

A Personal Principle or Personal Regulation Rule the agent recommends following unless a named contextual exception applies. Choosing an exception is recorded for later outcome review without shame or silent weakening of the principle.
_Avoid_: Command

## Reflection Prompt

A user-confirmed question the agent should surface in relevant situations to expose a possible pattern or Value Tension without assuming the answer. It guides examination rather than prescribing behavior.
_Avoid_: Diagnosis, rule

## Pending Outcome

The unresolved state of a closed Regulation Session when the result of its Deliberate Action is not yet known. It may carry an expected review time and follow-up permission but cannot be completed by inference from unrelated conversation.
_Avoid_: Incomplete session, failure

## Regulation Follow-Up

An explicitly authorized prompt to revisit a Pending Outcome at a chosen time or event. It asks whether the user wants to record the result and does not presume that the planned action occurred.
_Avoid_: Automatic monitoring

## Regulation Outcome Review

The later comparison of a planned Deliberate Action with what the user reports actually happened, whether the feared outcome gained support, whether values and boundaries were served, and which rules or support tactics helped or caused friction. Emotional calm is one possible result, not the definition of success.
_Avoid_: Compliance score, calmness score

## Regulation Pattern Review

A conservative aggregate review of comparable Regulation Records that shows counts and denominators, separates completed, pending, and unknown outcomes, preserves contradictory examples, and labels correlation without claiming cause. It ends with at most one proposed focus for user confirmation, modification, or rejection.
_Avoid_: Personality analysis, progress score

## Proposed Regulation Focus

One provisional behavior, question, or Personal Regulation Rule selected from a Regulation Pattern Review for deliberate practice during the next review period. It does not become a Goal, Commitment, or durable rule until the user accepts it.
_Avoid_: Treatment plan

## Values Store

The canonical append-only history of Candidate Values, Core Values, Purpose, Personal Principles, Goals, Commitments, Value Evidence, user confirmations, corrections, and lifecycle changes. Ordinary reminders use a current projection while historical versions remain inspectable.
_Avoid_: User Profile, identity record

## Value Lifecycle State

The user-confirmed current status of a Core Value, Purpose statement, or Personal Principle: active, under review, retired, reframed, or superseded. Only active items enter ordinary Contextual Reminders, while other states remain available for explicit reflection.
_Avoid_: Confidence level

## Values Compass Projection

The current readable view derived from Values Store events, containing active orientation plus visible tensions and items under review. It can be regenerated from history and is not itself canonical.
_Avoid_: Values document

## Restricted Personal Data

Personal data whose disclosure could materially harm or expose the user, including Regulation Records and sensitive Relationship Context. It receives the strictest rules for retrieval, prompt inclusion, logging, backup, export, and deletion.
_Avoid_: Private data

## Personal Data

User-owned information such as Values Compass state, Cognitive Support state, and Personal Notes that requires controlled local handling but is not automatically classified as Restricted Personal Data. Individual records may be elevated to Restricted when their content warrants it.
_Avoid_: Profile data

## Regulation Exclusion

A user-directed state that retains a Regulation Record for inspection while omitting it from Regulation Pattern Reviews and derived aggregates. Exclusion does not alter or delete the source record.
_Avoid_: Delete, reject

## Regulation Redaction

The irreversible removal of selected decryptable fields from a Regulation Record while preserving the remaining record and a non-sensitive correction trail. Redaction is distinct from hiding the field in a view.
_Avoid_: Hide

## Regulation Deletion

Making a Regulation Record irretrievable by destroying its record-specific encryption key and appending a non-sensitive tombstone. Encrypted bytes may remain in append-only media but cannot be used by the agent or restored through ordinary projection rebuilding.
_Avoid_: Soft delete

## Regulation Purge

Physical removal of Regulation Store bytes from storage locations where rewriting is supported, performed in addition to Regulation Deletion. Purge cannot guarantee removal from media outside the system's control.
_Avoid_: Delete

## Historical Candidate Import

An explicitly scoped process that extracts source-linked Candidate Values, Purpose statements, Personal Principles, Goals, Cognitive Support observations, and communication preferences from selected historical conversations into a user-reviewed queue. Imported candidates do not reconstruct Regulation Sessions, create people, establish diagnoses, or become active orientation without confirmation.
_Avoid_: Memory backfill, automatic profiling

## Candidate Review Queue

The inspectable set of proposed personal-orientation items awaiting user confirmation, revision, rejection, or privacy classification. Rejected candidates retain enough non-sensitive identity to prevent repeated proposal without retaining unnecessary source narrative.
_Avoid_: Inbox, inferred profile

## Companion Surface

A user interface through which the user accesses the same Personal Knowledge Manager and personal-data owner. The primary Companion Surface is the responsive web application, while Discord is a rapid-entry surface for capture, urgent check-ins, focus starts, and brief follow-up.
_Avoid_: Separate agent

## Governance Surface

The part of the primary Companion Surface used to inspect evidence, correct or delete records, manage privacy and reminder permissions, review values and patterns, control adaptations, and authorize exports. Governance operations are not delegated to conversational convenience alone.
_Avoid_: Settings page

## Owner

The single authenticated person whose Personal Knowledge Manager state, encrypted personal stores, Companion Surfaces, and channel links belong together. Owner identity is internal and does not depend on a Discord username, display name, channel, or ADK session identifier.
_Avoid_: User Profile, Discord user

## Owner Timezone

The user-controlled IANA timezone used for schedules that should follow the Owner's current local time, initially `Asia/Manila`. It changes only through explicit user action and uses regional identifiers such as `America/Los_Angeles` so daylight-saving transitions remain correct.
_Avoid_: UTC offset, inferred location

## Schedule Time Behavior

The explicit rule governing how a reminder responds to timezone changes: local-time follows the Owner Timezone, fixed-instant remains anchored to one UTC moment, and location-specific retains its own named IANA timezone. Timezone changes preview affected schedules before taking effect.

## Scheduled Job

A durable SQLite record describing work that may become due, including its schedule semantics, permission scope, quiet-hours policy, retry limit, expiry or coalescing behavior, and idempotency key. Becoming due does not itself authorize delivery; permission, relevance, and current state are checked again when the dispatcher claims it.
_Avoid_: Cron entry, notification

## Reminder Delivery

One idempotent attempt to send an authorized reminder through a delivery surface. Delivery, seen, and acted are distinct outcomes; failure or VM downtime cannot silently imply that the user received or ignored it.
_Avoid_: Reminder, engagement

## Quiet Hours

An Owner-configurable local-time interval during which non-urgent reminder delivery is deferred. Quiet Hours affect delivery timing without rewriting the underlying Scheduled Job or its intended timezone semantics.
_Avoid_: Do-not-disturb mode

## Regulation Foundation Slice

The first production-ready vertical slice proving that Regulation Mode can guide an activated user toward a user-aligned action while preserving safety, privacy, explicit capture, offline access, and graceful model degradation. It includes only the minimum confirmed personal orientation needed for coaching; pattern mining, scheduled coaching, and advanced adaptation are later slices.
_Avoid_: MVP chatbot, complete Regulation Mode

## Replacement Seam

A narrow application-owned interface around infrastructure that may later change, such as persistence, retrieval indexing, model providers, background dispatch, or message delivery. A Replacement Seam protects domain behavior and records from a future infrastructure migration without requiring multiple implementations in the first release.
_Avoid_: Premature abstraction, provider wrapper everywhere

## Local-First Production Stack

The single-VM application stack consisting of Python 3.12, Google ADK, FastAPI, Pydantic, a React/TypeScript/Vite PWA, SQLite WAL stores, FTS5 plus a local embedding index, systemd services, and private Tailscale access. Local-first describes operational ownership and data locality, not an assumption that model APIs or backups are always local.
_Avoid_: Prototype stack, offline-only system

## Deterministic Regulation Protocol

The local, code-owned Regulation flow used when personalized model reasoning is unavailable or invalid. It exposes the degradation, preserves safety branching and confirmed resources, and recommends only bounded reversible actions without making truth or relationship judgments.
_Avoid_: Fallback model, canned reassurance

## Model Route

A code-authorized selection of model, reasoning budget, timeout, and fallback behavior for one bounded task. The initial daily route uses GPT-5 mini; GPT-5 requires explicit choice or a qualifying escalation policy, and Regulation failure routes to the Deterministic Regulation Protocol.
_Avoid_: Agent identity, automatic best model

## Model Qualification

The task-specific evaluation a model configuration must pass before it may serve a route. Regulation qualification covers schema validity, personal-rule adherence, reassurance resistance, coercion avoidance, calibrated uncertainty, Cognitive Support delivery, values grounding, latency, and cost rather than relying on general benchmarks alone.
_Avoid_: Benchmark score, provider reputation

## Model Escalation

A visible, code-authorized change from the daily Model Route to a more capable and expensive qualified route because task consequence or reasoning complexity meets an explicit policy. Distress, repetition, reassurance seeking, and conversation length are excluded escalation signals.
_Avoid_: Thinking harder, premium response

## Model Spend Envelope

The configurable set of monthly, workflow, route, and background-work cost limits enforced by the model gateway. Usage is attributed to its originating Mode and workflow, and exhausting the envelope cannot disable the Deterministic Regulation Protocol.
_Avoid_: API bill, token quota

## Context Budget

The maximum evidence and instruction payload assembled for one Model Route according to its task class. It is a relevance, latency, privacy, and cost constraint; exceeding it requires selection, compression, or a visible exceptional workflow rather than automatic history expansion.
_Avoid_: Context window, memory capacity

## Context Overflow Policy

The deterministic priority order used to omit or compress eligible material when it cannot fit within a Context Budget. It preserves present intent, safety, confirmed personal orientation, active state, and direct evidence ahead of provisional inference and general conversation history, while disclosing meaningful exclusions to the model.
_Avoid_: Truncation, summarization strategy

## Memory Candidate

A provenance-linked proposition extracted from a conversation or artifact that may become a typed durable record after sensitivity classification, conflict checks, and any required Owner confirmation. A Memory Candidate is neither authoritative memory nor a personality fact.
_Avoid_: Memory, insight

## Memory Review Item

A pending Owner decision about a sensitive, identity-shaping, duplicated, or conflicting Memory Candidate. It presents the proposed record, source evidence, affected existing records, and available accept, correct, defer, or decline actions.
_Avoid_: Notification, approval task

## Retrieval Explanation

The inspectable account of why a durable record was eligible, selected, and supplied for a response, including its domain, provenance, relevance, authority, and sensitivity constraints. It does not expose hidden reasoning or excluded sensitive content.
_Avoid_: Chain of thought, citation only

## Memory Inbox

The non-urgent review surface in the Data & Privacy Center where small batches of Memory Review Items can be accepted, corrected, deferred, declined, or suppressed. Its presentation is capacity-aware and deliberately avoids engagement pressure.
_Avoid_: Notification inbox, profile setup

## Suppression Fingerprint

The minimal non-semantic identifier retained after a Memory Candidate is declined so the same unsupported proposal is not repeatedly generated. It cannot be retrieved as personal context and may be bypassed only by materially new, displayed evidence.
_Avoid_: Rejected memory, hidden profile

## Historical Backfill

An explicit, bounded, and reversible process that derives Memory Candidates from Owner-selected past conversations or artifacts. It reports scope and cost, excludes sensitive domains by default, pauses at review capacity, and never converts imported history directly into authoritative personal memory.
_Avoid_: Memory migration, profile training

## Processing Consent

The scoped Owner authorization defining which selected material may leave the VM, for what derivation purpose, through which provider route, and for which single batch or interaction. Processing Consent is not implied by data capture, prior imports, or general model use.
_Avoid_: Privacy policy acceptance, connector permission

## Payload Preview

An inspectable representative view of the minimized excerpts, metadata, and instructions that a consented workflow intends to send to an external model provider before execution.
_Avoid_: Prompt debug log, full request archive

## Local-Only Processing

Processing that keeps source content and derived data on Owner-controlled hardware. On the current production VM it consists of deterministic extraction, filtering, retrieval, validation, and manual governance—not a claim that a local LLM provides cloud-equivalent interpretation.
_Avoid_: Offline AI, private model

## Workload Class

One of the VM scheduling priorities: Interactive for active Owner-facing work, Operational for bounded delivery and health duties, or Background for resumable computation that may be paused. Workload Class controls resource limits and preemption without changing domain importance.
_Avoid_: Process priority, task importance

## Background Preemption

The automatic pause or withholding of resumable Background work when Interactive demand or system load crosses a configured threshold. Preempted work retains a durable checkpoint and does not compete with active Regulation or normal daily use.
_Avoid_: Job failure, cancellation

## Tracer-Bullet Milestone

An independently deployable, testable, and reversible end-to-end increment that proves one architectural promise across domain logic, storage, API, and the smallest necessary interface. Later milestones build on verified seams rather than implementing all layers horizontally.
_Avoid_: Development phase, epic

## Shadow Use

A bounded pre-release period in which the Owner uses a deployed capability in realistic conditions while retaining existing alternatives, reviewing advice and persistence, and collecting behavioral, privacy, latency, and recovery evidence before granting it dependable-companion status.
_Avoid_: Beta test, soft launch

## Daily-Use Readiness

The evidence-backed status granted only after domain behavior, safety fallback, privacy controls, recovery, degraded operation, mobile usability, and Shadow Use meet their acceptance criteria. Deployment availability alone does not confer it.
_Avoid_: Production deployed, feature complete

## Shadow-Use Threshold

A measurable behavioral, technical, privacy, latency, or recovery condition used to judge the initial Shadow Use. Thresholds establish product readiness and safe degradation only; they do not diagnose the Owner or claim therapeutic efficacy.
_Avoid_: Clinical outcome, success metric

## Architecture Baseline

The currently approved set of domain and technical decisions that implementation must follow unless new evidence produces a superseding ADR. The baseline preserves decision coherence without claiming that reversible implementation details are permanently fixed.
_Avoid_: Final architecture, immutable specification
_Avoid_: Timezone

## Channel Link

An explicitly authorized association between the Owner and an external channel identity, such as a Discord account. A Channel Link grants only the operations allowed for that surface and can be revoked without moving or deleting Owner data.
_Avoid_: Login, inferred identity

## Now Screen

The sparse default Companion Surface showing at most one relevant orientation, one active Commitment, one pending item, two primary actions, and one optional suggestion. It reduces choice burden and exposes why each personalized item was selected without presenting the user's life as a metrics dashboard.
_Avoid_: Dashboard, daily scorecard

## Companion Voice

The stable interpersonal character of the Personal Knowledge Manager: warm, direct, curious, uncertainty-aware, evidence-specific, agency-preserving, willing to disagree, and non-clinical outside safety needs. It does not use stored familiarity to claim unique understanding or encourage emotional dependence.
_Avoid_: Persona, simulated friend

## Mode Stance

The task-specific expression of Companion Voice, such as brief and firm in Regulation Mode, reflective in Values Compass work, energetic and structured in tutoring, or plain and urgent in a Safety Branch. Mode Stance changes delivery and emphasis without changing evidence, privacy, or safety rules.
_Avoid_: Persona switch

## Firmness Setting

A context-specific user preference of gentle, direct, or firm that controls how strongly the agent phrases challenge and accountability. It cannot turn gentleness into unsupported reassurance or firmness into aggression, humiliation, or shame.
_Avoid_: Strictness, honesty level

## Workspace

A stable user-facing area that groups related PKM objects and workflows while Agent Modes remain inferred behavioral postures within it. The primary Workspaces are Now, Chat, Library, Work, People, Compass, Reviews, and Settings.
_Avoid_: Mode, agent

## Data and Privacy Center

The Governance Surface for inspecting what each store contains, why it exists, where it may be used, its sensitivity, permissions, reminder access, channel links, encryption, retention, backup, export, correction, deletion, audit, and projection state. It also previews the Personal Orientation available to each mode.
_Avoid_: Settings, privacy policy

## Diagnostic Session

A temporary, explicitly authorized capture of selected technical detail for debugging, with a preview, field-level redaction, visible stop control, automatic expiry, and local storage by default. Personal or Restricted content remains excluded unless separately approved.
_Avoid_: Debug logging, telemetry

## Access Audit

A content-free record of which authenticated channel performed or attempted an operation on which store or record, under which permission and sensitivity classification, and whether it succeeded. It supports accountability without duplicating personal payloads into logs.
_Avoid_: Interaction log

## Task Workspace

A focused interaction that pairs a conversation with one current durable Work Object. Conversation supports questioning and refinement while the Work Object preserves the evolving result, provenance, confirmation state, and version history.
_Avoid_: Chat thread, mode session

## Work Object

A durable PKM output such as a Paper Brief, Comparison, Synthesis Note, Design, Study Session, Draft, Decision Record, PRD, guide, Regulation Record, or Values Compass item. It is not considered saved merely because related text appeared in conversation.
_Avoid_: Message, response

## Library Item

A searchable object in Library that retains its epistemic and provenance type, such as Source evidence, Personal Note, Note Card, Synthesis Note, confirmed decision, model inference, Concept, or saved Work Object. Unified discovery never collapses these types into interchangeable documents.
_Avoid_: Document, generic memory

## Retrieval Projection

A disposable, rebuildable lexical or vector representation of a typed Library Item or passage used to find candidates without becoming canonical knowledge. It retains stable source identity, provenance type, sensitivity, model version where applicable, and deletion linkage.
_Avoid_: Knowledge base record, memory

## Hybrid Retrieval

Retrieval that combines typed lexical and vector candidates after store permissions are applied, then fuses and optionally reranks them while preserving provenance. Neither vector similarity nor rank fusion changes the epistemic type or evidence strength of a result.
_Avoid_: Semantic memory

## Retrieval Chunk

A structure-aware, typed unit derived from a versioned Library Item for lexical or vector retrieval, identified by stable item and logical-section identity rather than transient position. It retains page or section location, text hash, provenance, sensitivity, confirmation state, and embedding policy.
_Avoid_: Text window, memory fragment

## Embedding Policy

The store- and record-type rule deciding whether a Retrieval Chunk may receive a vector representation. It permits grounded and confirmed knowledge selectively while excluding raw conversations, raw Regulation Records, and other Restricted narrative by default.
_Avoid_: Index setting

## Quick Capture

The global low-friction entry point for saving a raw thought, Source, Person or interaction, idea, Goal, Commitment, outcome, or private check-in before optional organization. It may propose multiple typed destinations and links but writes to each owning store only after explicit routing confirmation.
_Avoid_: Universal memory, auto-file

## Capture Routing Proposal

A correctable suggestion that a captured item belongs in one or more domain stores, with the proposed record type, extracted links, and privacy implications shown before cross-store persistence. The raw capture remains available even when the user postpones organization.
_Avoid_: Automatic classification

## Study Session

A bounded Tutor Mode Work Object with a target, available time, current capacity, learning sequence, parked questions, concept-specific evidence, and a closing Commitment. It may be extended, resized, intentionally pivoted, paused, or released without treating every deviation as failure.
_Avoid_: Tutoring chat, study streak

## Question Parking Lot

A visible list of valuable but currently off-target questions captured during a Study Session so attention can return to the session target without losing curiosity. Parked questions do not automatically become Goals or Personal Notes.
_Avoid_: Distractions, backlog

## Mastery Evidence

Task- and Concept-specific evidence of understanding, recall, or application gathered through the user's responses and work. Reading an explanation, continuing to chat, or stating confidence does not alone establish mastery.
_Avoid_: Mastery score, confidence

## Design Workspace

A Builder Mode Task Workspace that develops a raw idea through purpose, constraints, candidate designs, decisions, risks, evidence, selection, and an optional artifact or experiment. It keeps unresolved decisions, assumptions, rejected alternatives, provenance, and parked branches visible without treating exploration as implementation commitment.
_Avoid_: Planning Mode, implementation funnel

## Parked Branch

A potentially valuable design direction deliberately preserved outside the active Design so exploration can continue without changing the current scope. A Parked Branch may later be resumed, linked, or discarded.
_Avoid_: Rejected idea, backlog item

## Draft Workspace

A Writing Mode Task Workspace that keeps Source material, user-authored draft text, and agent-proposed revisions visibly distinct. It applies one revision goal and Polish Preference at a time, supports field-level acceptance and version history, and preserves authorship and provenance when producing an Artifact.
_Avoid_: Text editor, generated document

## Revision Goal

The explicit purpose of the current writing pass, such as clarify, shorten, restructure, expand, or adapt for an audience. Improvements outside the Revision Goal are parked rather than silently expanding the edit.
_Avoid_: Prompt

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

## Now Screen

The mobile-first PWA landing workspace: a sparse orientation surface for the current moment, with a primary Regulation entry point and a small set of deliberate next actions. It is not a dashboard, mood score, streak surface, or unsolicited psychological interpretation.

## Regulation Entry State

The focused Now Screen state that starts an emotional self-regulation check-in, prioritizing interruption, facts-versus-interpretation separation, and a pause before action.

## Visual Direction

The PWA combines three cues with a calm studio as the dominant tone: quiet field-notebook evidence cues, spacious studio composition, and precise command-center structure only when the user is deciding or reviewing. The visual identity should feel grounded and readable before it feels analytical.

## Regulation Anchor

The primary Regulation entry surface is a quiet, high-confidence anchor: visually unmistakable and easy to reach, but not animated, urgent, nagging, or reassurance-seeking. It becomes more structured only after the user chooses it.

## Persistent Navigation

The PWA keeps five primary destinations visible: Now, Chat, Work, Compass, and Reviews. This is the stable orientation layer; deeper modes and domain actions open within these workspaces rather than replacing the global map.

## What Matters Today

The Now orientation card presents one concise reminder drawn only from confirmed values, commitments, or active work. It supports dismissal and correction, and never presents an inferred or provisional pattern as a fact about the user.

## On-demand Provenance

The What Matters Today card keeps provenance out of the default visual path but exposes a “Why am I seeing this?” action. That disclosure reveals the exact confirmed source behind the reminder.

## Guided Regulation Sequence

Regulation Mode presents one prompt at a time in the sequence facts → story → emotion → urge → action. A quiet orientation rail makes the sequence legible without becoming a score, streak, or gamified progress indicator.

## Regulation Orientation Rail

The Regulation sequence uses a thin vertical line with one active node. Completed steps remain as evidence, the current step has strongest contrast, and no visual state implies performance or emotional success scoring.

## Regulation Answer Field

Each Regulation step uses a spacious single prompt field with optional examples. Examples are explicitly marked as scaffolding, never prefilled interpretations; the user's own wording remains the canonical answer.

## Quiet Safety Escalation

Safety escalation remains available in the Regulation header and becomes prominent only when relevant safety signals appear. Ordinary reflection stays calm and non-medicalized; immediate danger, self-harm, violence, or abuse takes precedence over coaching.

## Smallest Next Action

Each completed Regulation sequence recommends one smallest values-consistent next action. The action should be specific, time-bounded, and reversible where possible, rather than a generic advice list or overconfident command.

## Delayed Regulation Outcome

Regulation outcomes are captured through an optional delayed follow-up asking whether the action helped, hurt, or changed nothing. The interaction gathers behavioral evidence without immediate self-rating or emotional performance scoring.

## Firm-but-Choiceful Companion

When a user wants to ignore a recommended Regulation action, the companion names the conflict with a confirmed personal rule or value, explains the likely short-term relief versus longer-term cost, and leaves the final choice with the user.

## Daily Regulation Review

Daily Review is a five-minute, skippable guided ritual with three prompts: strongest emotion, trigger and reaction, and a better response for tomorrow. It is not scored.

## Provisional Pattern Review

Weekly Review presents patterns in a small evidence table with denominators, uncertainty, and inspectable source sessions. It describes provisional behavior patterns rather than fixed personality traits or diagnoses.

## Pattern Correction

Weekly patterns expose a direct “Correct this pattern” action. The user can edit the interpretation, reject it, or mark its evidence incomplete; corrections remain provenance rather than silently replacing history.

## Permissioned Reminders

Values, purpose, and personal-rule reminders use explicit permission tiers: off by default, occasional, or active. Each reminder exposes its source and supports dismissal, correction, and pause without penalty.

## Companion Voice

The default companion voice is calm, direct, and grounded. It avoids hype and reassurance loops; firmness increases only when a confirmed rule or safety condition requires it.

## Attention Recovery

The primary ADHD adaptation is attention recovery: one next step, short prompts, pause-aware resume context, and no recap dumps. Time scaffolding and low-stimulation controls remain later configurable layers.

## Attention Recovery Anchor

After a pause, the UI shows one sentence containing the active context, stopping point, and next available step. Expanded history is optional rather than automatically presented.

## Global Capture

Global Capture saves raw input first and routes it later through an explicit user choice. It can route to notes, work, research, relationships, or Regulation, but never silently infers a sensitive destination.

## Capture Composer

Global Capture opens as a focused bottom sheet with one large field and a single Save action. Routing is deferred until after the raw capture is safely persisted.

## Deferred Capture Routing

After saving, Global Capture offers “Route now or later,” defaulting to later. Routing presents explicit domains and preserves the raw capture unchanged.

## Unified Library Results

Library uses one cross-domain result stream with visible provenance labels. Notes, papers, conversations, work objects, captures, and sensitive records remain distinguishable rather than being flattened into one anonymous semantic answer.

## Evidence-first Detail

Opening a Library result shows original content, provenance, timestamp, domain, and match rationale before generated synthesis. Summaries remain secondary to inspectable evidence.

## Typed Work Objects

Conversations may propose typed work objects—draft, decision, experiment, or task—but persistence requires an explicit user review and authorization step. A conversation is not silently promoted into durable project state.

## Work Object Review

Before persistence, a proposed work object appears in a compact diff-style review with proposed fields, source excerpts, confidence, and explicit Save, Edit, or Discard actions.

## Layered Compass

Compass organizes direction as purpose → values → principles → goals → commitments. Each layer remains distinct, inspectable, and explicitly confirmed rather than inferred into one personality profile.

## Versioned Direction

When a confirmed value changes, Compass creates a new version with effective dates and an optional reason. Prior versions remain preserved and recoverable rather than being edited away.

## Evidence-based Reviews

Reviews emphasize qualitative evidence and behavior trends: what helped, what worsened things, and whether actions matched values. They do not use streaks, completion rates, or emotional performance scores.

## Data & Privacy Workspace

Data & Privacy is a first-class workspace. It exposes domain-separated records, retention, provenance, export, correction, and deletion controls rather than hiding governance inside Settings.

## Privacy Domain Map

Data & Privacy opens with a domain map covering Regulation, Values, Notes, Relationships, Work, Research, and Session Metadata. Each domain explains storage purpose, retention, provenance, and available user controls.

## Quiet Privacy Cues

Sensitive domains use small lock/state indicators and plain-language sensitivity labels. Privacy boundaries remain legible without warning colors or alarm-heavy visual treatment.

## Source Stamps

Provenance appears as small plain-language source stamps, for example “Captured · Regulation · Jul 12,” with subtle separation from primary content. They avoid generic metadata-pill styling.

## Graceful Degradation Banner

When model or API access is unavailable, the UI shows a quiet capability banner that names what remains local—capture, review, and the deterministic Regulation protocol—and what is paused, such as synthesis.

## Processing Source Stamps

Responses expose subtle processing/source stamps such as “Local protocol” or “Model-assisted · GPT.” The distinction remains visible for trust and capability awareness without dominating the interface.

## Model Draft State

Model-assisted responses render as calm provisional drafts with a visible Stop action. Partial output is not treated as durable content until the user explicitly accepts or routes it.

## Model Output Authorization

Completed model output exposes explicit Accept, Edit, Route, or Discard actions. Model output remains a proposal until the user authorizes persistence or routing.

## Explicit Mode Posture

Chat shows an explicit mode header and switcher for Regulation, Tutor, Research, Builder, Relationship, and other supported postures. The current mode is always visible; mode changes are deliberate rather than inferred invisibly.

## Mode Switcher Sheet

The mode switcher opens as a compact sheet with mode names, one-line descriptions, and safety posture. It supports deliberate low-memory switching without turning navigation into a configuration screen.

## Relationship Reality Check

Relationship reality checks follow facts → interpretations → possible explanations → boundaries → next question. They focus on observable behavior and user choices without diagnosing partners or reducing uncertainty to a trust score.

## Observed-versus-Meaning View

Relationship evidence appears in a two-column comparison: Observed and Added meaning. This makes interpretation visible without turning relationship support into a courtroom-style historical prosecution.

## Personal Rule List

Personal Rules appear as concise entries with strength, scope, and exceptions. They guide behavior contextually rather than acting as rigid system blocks.

## Rule Confirmation Flow

Creating or changing a Personal Rule follows propose → test against examples → confirm. The agent can sharpen wording, but only explicit user confirmation makes the rule active.

## Historical Rule Candidates

Possible rules found in historical conversations enter a reviewed candidate queue with evidence, confidence, and Confirm, Edit, or Decline actions. Historical inference cannot silently activate a rule or value.

## Batched Candidate Review

Candidate rules are surfaced in a batched review, usually weekly or when Compass is opened. The system avoids immediate post-conversation nudges that could pressure acceptance.

## Confirmed-versus-Candidate Status

Values and rules use explicit status text—Confirmed or Candidate—plus a quiet visual distinction, provenance, and available actions. Color is supportive, never the sole semantic channel.

## Compass Empty State

When Compass has no confirmed values, it offers one small articulation prompt and saves the response as a draft. The first answer is not treated as a permanent identity claim.

## Delayed Value Confirmation

Draft values become Confirmed only through a later review after examples and lived use. The user can confirm, edit, or discard; the agent may provide evidence but cannot decide identity.

## Figma Information Architecture

The Figma file is organized as Foundations → Components → Workspaces → Flows → Architecture handoff. Reusable tokens and components remain distinct from screen explorations and implementation mappings.

## Tokenized Design Foundation

The Figma foundation uses named variables for color, spacing, type, radius, and motion. Tokens are the shared backbone for consistency and future desktop, dark, or low-stimulation variants.

## Color Mode Sequence

Design starts with the light calm-studio mode, followed by a low-stimulation dark mode using the same semantic variables. Dark mode is an accessibility and adaptability layer, not a separate visual identity.

## Typography Roles

Atkinson Hyperlegible is the UI and body face. Source Serif 4 is reserved for rare reflective headings in Compass and Reviews, adding human texture without compromising Regulation readability.

## Reflective Typography Boundary

Source Serif 4 appears only in Compass and Reviews headings. Regulation, Work, Chat, and active task surfaces use the readable UI face to remain crisp and operational.

## Motion Direction

Motion uses restrained transitions that clarify state, focus, and step changes. It avoids ambient urgency, pulsing, gamified celebration, and motion that could increase activation or distraction.

## State-based Motion

Motion is limited to short transitions for focus, step changes, and confirmation. There is no ambient animation; reduced-motion preferences remove nonessential transitions.

## Focus Accessibility

Interactive elements use a visible high-contrast focus ring with a calm teal accent. Focus must remain obvious for keyboard and switch-access users without relying on subtle border changes or color alone.

## Desktop Contextual Rail

Desktop preserves the mobile-first content column and adds a quiet contextual rail. The rail holds provenance, active-work context, or source detail without becoming a multi-panel dashboard.

## Desktop Rail Default

The contextual rail defaults to current context: active task, source stamp, and one next-step reminder. History stays available on demand so returning users are not met with recap overload.

## Focused-flow Navigation

Focused flows may temporarily reduce global navigation to preserve attention, but must retain an obvious back path and quiet access to safety escalation. The user never becomes trapped inside a mode.

## Regulation Focus Navigation

During a focused Regulation flow, global bottom navigation collapses to an obvious back control and quiet safety access. Competing destinations return after completion or intentional exit.

## Regulation Exit Draft

Exiting Regulation saves a clearly marked private draft with Resume and Discard actions. An unfinished sequence is never presented as a completed session or pattern evidence.

## Regulation Draft Retention

Unfinished Regulation drafts use a short, configurable retention window with explicit deletion. The default balances resume support with sensitive-data minimization.

## Calm Retention Control

Draft retention uses a simple default with an on-demand “Change retention” control. Normal flows avoid repeated privacy prompts while preserving discoverable user control.

## Figma Component Naming

Figma components use semantic slash names that mirror the product model, such as `Regulation/Prompt`, `Regulation/OrientationRail`, `Now/OrientationCard`, `Library/SourceStamp`, and `Privacy/DomainRow`. Names describe user-facing meaning rather than implementation details.

## Figma Variant Naming

Component variants use user-visible states—Default, Focused, Disabled, Draft, Confirmed, Candidate, and Offline—rather than implementation flags or purely visual color names.

## First Figma Component Set

The first reusable component set is Regulation-focused: Prompt Field, Orientation Rail, Safety Access, Next Action, and Draft State. It validates the highest-risk workflow before broader primitives are generalized.

## Regulation Prompt Field States

The first Prompt Field variants are Default, Focused, Draft, Confirmed, and Offline. They map to the Regulation lifecycle rather than generic form validation alone.

## Offline Prompt Copy

The Offline Prompt Field says: “Local protocol available. Model assistance is paused.” This preserves the deterministic Regulation workflow while making model capability boundaries explicit.

## Confirmed Prompt Provenance

Confirmed Regulation answers show a small source stamp beneath the field, including persistence state and processing source where relevant. The stamp is visible but secondary to the user’s answer.

## Compact Orientation Labels

The Regulation rail keeps the five labels visible but compact: Facts, Story, Emotion, Urge, Action. Labels support orientation without adding explanatory paragraphs to an activated flow.

## Active Rail Node

The current Regulation step uses a filled deep-teal node and strongest label contrast. Completed nodes use a quieter confirmed treatment; future nodes remain neutral. No completion percentage or celebration is shown.

## Safety Access Control

Regulation exposes a small text control labeled “Need immediate help?” It remains quiet by default and becomes prominent only when safety-relevant content is detected.

## Safety Access Panel

Opening Safety Access prioritizes an immediate-danger check and direct local options: contact emergency services, contact a trusted person, or leave the flow and return to safety. It does not diagnose, debate, or coach before safety is addressed.

## Regulation Next Action Card

The final Regulation recommendation appears as one action card with “Why this?” provenance and Accept / Change controls. It is specific and accountable while preserving the user’s final choice.

## Next Action Change

Change edits the proposed action without restarting the entire reflection. The user can adjust scope, timing, or wording while preserving the original recommendation and provenance.

## Private Draft Card

An unfinished Regulation session appears as a private draft card with Resume, Change retention, and Discard actions. It is visible enough to support continuity without presenting as an error or warning.

## Draft Placement on Now

Saved private Regulation drafts appear directly below the Regulation anchor on Now. This keeps the interrupted flow close without allowing unfinished reflection to dominate the current moment.

## Now Action Rows

Now action rows use an icon, action title, one-line purpose, and chevron. This supports fast scanning and attention recovery without turning the landing workspace into a tile-heavy dashboard.

## Icon Language

Navigation and action icons use simple outline geometry with one consistent stroke weight. Active state is communicated through placement and semantic color rather than switching icon metaphors or adding visual weight.

## Now Orientation Header

The Now header shows time, place/context, and a quiet user marker. It provides orientation without metrics, streaks, or attention-demanding personalized greetings.

## Neutral User Marker

The Now header uses a neutral initial/avatar mark rather than a profile photo. It provides personal orientation without exposing additional identity data or adding visual noise.

## Paper-and-Surface Background

Now uses a warm paper background with true white content surfaces. The distinction provides calm hierarchy without gradients, texture, or decorative atmosphere.

## Surface Elevation

Surfaces use hairline borders with minimal elevation. Grouping should feel tactile and organized without turning the PWA into a floating-card dashboard.

## Radius Scale

The visual system uses semantic radii: 8px controls, 16px rows and fields, 20px panels, and a 28px screen shell. Radius communicates hierarchy rather than being applied uniformly.

## Primary Button Shape

Primary buttons use a 48px height and compact 12px radius. Pill shapes are reserved for genuinely rounded controls rather than applied to every action.

## Button Hierarchy

Buttons use a filled teal primary, white hairline-bordered secondary, and text-only tertiary action. This creates clear hierarchy without competing emphasis.

## Destructive Actions

Destructive actions use quiet text controls with explicit wording, such as “Discard draft” or “Delete records.” Confirmation appears only when the action is irreversible; ambiguous icons and alarm-heavy red buttons are avoided.

## Directional Empty States

Empty states use a plain explanation and one useful next action. They avoid illustrations, motivational filler, and dead-end blank surfaces.

## Focused Search Workspace

Global Search opens as a focused full-screen workspace with one query field, recent searches, provenance-rich results, and filters that appear only after they become useful.

## Search Filter Priority

Search filters prioritize source, sensitivity, and date range. Semantic similarity may support ranking but never obscures the domains being searched.

## Transparent Search Ranking

Search ranks through a transparent blend of exact match, recency, and user-selected source filters. Every result exposes “Why this matched”; semantic retrieval can assist but cannot become opaque.

## Research Lanes

Research uses three visible lanes: Evidence, Notes, and Synthesis. Original sources, user thinking, and generated work remain distinct through the full research workflow.

## Explicit Evidence Ingestion

Research Evidence uses an explicit Add source flow for URLs, files, notes, or captures, with visible provenance and processing status. Personal capture never silently becomes research evidence.

## Evidence-first Source Detail

Opening a Research Evidence item shows the original source first, with highlights and linked notes in a side panel. Summaries and synthesis remain secondary, inspectable aids.

## Citable Research Notes

Research Notes are standalone user-authored objects that can cite exact source passages. This preserves authorship while maintaining inspectable evidence chains across sources.

## Cited Research Synthesis

Research Synthesis is an editable draft with inline citations to Evidence and Notes. Material claims remain inspectable and traceable to source content.

## Citation Preview

Inline citations open a compact source preview with an explicit Open full source action. This preserves writing flow while keeping every material claim verifiable.

## Explicit Research Export

Research export uses an explicit review for format, citation style, included notes, and provenance metadata. Nothing leaves the PKM invisibly.

## Layered Writing Mode

Writing Mode keeps Source material, user draft, and agent suggestions visibly separate. The separation preserves authorship, provenance, and explicit revision scope.

## Explicit Revision Goal

Each Writing Mode pass begins with one explicit revision goal such as clarify, shorten, restructure, expand, or adapt for an audience. Unrelated changes do not silently expand the current pass.

## Field-level Writing Acceptance

Meaningful writing suggestions use field-level Accept, Edit, or Reject controls. This preserves user control and reversibility without forcing a whole-document decision.

## Staged Builder Workspace

Builder Mode organizes work as purpose → constraints → candidate designs → decisions → risks → evidence → chosen experiment. It keeps exploration, uncertainty, and rejected paths visible without confusing them with implementation commitment.

## Comparable Builder Candidates

Builder candidates appear as comparable cards with explicit trade-offs and evidence. Early exploration remains legible without false precision or premature ranking.

## Parked Builder Branches

Parked Branches are visible but collapsible alternatives with a reason for parking and a path to resume. They are neither discarded ideas nor automatic implementation-backlog items.

## Separated People Workspace

People separates context, operations, and restricted links. Useful relationship information remains available without flattening sensitive context into a single contact profile or surveillance-style timeline.

## Minimal Person Creation

Creating a person starts with minimal context: name or label, relationship context, and optional privacy level. Details remain optional and user-directed; nothing is automatically extracted from conversations.

## User-authored Relationship Events

Relationship events are user-authored, event-based records with a clear purpose, such as a conversation, boundary discussion, or follow-up. They support context and choices rather than hidden monitoring.

## Context-rich Work Tasks

Work tasks are context-rich next actions with one clear action, a linked project or source, and optional due context. Work supports meaningful resumption rather than a generic productivity dashboard.

## Semantic Task Timing

Task timing is optional, semantic, and timezone-aware. Users can use phrases such as “this evening” or “next Friday,” and reminders resolve against the user's current locale.

## Quiet Task Completion

Completing a task produces quiet confirmation and preserves the task's context in history. The interface avoids confetti, streaks, and reward mechanics while retaining traceability for review.

## Intentional Task Deferral

Deferring a task asks one short question: “When should this return?” Semantic timing options are offered, with an optional reason. Deferral is a deliberate reschedule rather than silent disappearance.

## Capacity-aware Study Start

Study/Tutor starts with a short capacity check—available time, energy, and goal—then offers one bounded learning activity. It avoids high-friction curriculum-dashboard planning.

## Active Learning First

Tutor sessions begin with active recall or a small applied prompt. Mastery evidence comes from demonstrated understanding or application, not passive reading or shallow scores.

## Study Session Close

Ending a study session captures one takeaway, one uncertainty, and one next review cue. The close supports future retrieval and mastery evidence without adding excessive paperwork.

## Permissioned Study Reminders

Study review reminders are contextual and permissioned, with snooze and adjustment controls. They may surface alongside related work rather than interrupting through a rigid schedule.

## Low-stimulation Mode

Low-stimulation mode changes density, motion, and contrast while preserving the same information architecture. The user gains a calmer interface without needing to learn a second app.

## Low-stimulation Quick Setting

Low-stimulation mode is controlled through a visible but quiet quick setting, mirrored in Settings. The system does not infer stress and switch modes automatically.

## Authorized Notification Policy

Notifications are limited to user-authorized reminders and safety-critical notices. Each names its purpose and source and provides a clear pause control; engagement-oriented nudges are excluded.

## Notification Actions

Each notification offers one primary action plus Snooze and Pause. The interaction stays clear and non-coercive, with no escalating nag behavior.

## Notification Audit Log

Notification history appears as a small inspectable log in Data & Privacy showing what was sent, why, and which permission allowed it. It is not an engagement-oriented app inbox.

## Domain-selectable Data Export

Personal data export is domain-selectable and human-readable by default, with provenance included. A machine-readable recovery archive may also be offered, but is not the only meaningful export.

## Scoped Irreversible Deletion

Irreversible deletion begins with a scope review showing affected domains, record counts, and linked consequences. High-impact deletion requires an explicit confirmation phrase; soft deletion does not replace real deletion.

## Recovery Readiness Card

Data & Privacy includes a quiet recovery status card with last successful encrypted backup, recovery readiness, and a Test recovery action. Recovery remains verifiable without becoming daily visual noise.

## Degraded-only Service Status

Normal service health is not shown as daily telemetry. When degraded, the UI presents a small actionable status detail explaining the available local fallback.

## Devices and Sessions Panel

Data & Privacy includes a concise Your devices and sessions panel with the current session, linked channels, last access, and revoke control. It supports a single-owner system without an enterprise security dashboard.

## Discord as Rapid Entry

Discord is presented as a linked rapid-entry channel with clear capabilities, boundaries, and unlink controls. The web PWA remains the primary workspace.

## Consent-first Onboarding

First-run onboarding is short and consent-first: explain privacy boundaries, choose a reminder tier, optionally draft one value or rule, then enter Now. Personalization is earned through review rather than extracted through a long questionnaire.

## First Onboarding Prompt

The first personal onboarding prompt is: “What would you like this companion to help you do better?” It invites user-owned direction without demanding identity claims or intense disclosure before trust exists.

## First Now Orientation Draft

The first Now orientation card reflects the user's stated onboarding goal as a draft with a Refine later action. It provides continuity without converting one answer into a confirmed value or rule.

## First-week Calibration

After the first week, the PWA invites a brief calibration review asking what helped, what felt off, and what should change. Stronger personalization requires this feedback rather than automatic expansion.

## Quiet Annotation Margin

The PWA's signature visual element is a quiet annotation margin: a slim edge rail that carries sequence, provenance, active context, and privacy detail across screens. It unifies calm studio composition, field-notebook evidence cues, and selective command-center precision.

## Inline Confirmation

Ordinary changes receive brief inline confirmations near the changed item, for example “Draft saved” or “Value confirmed.” Confirmations state what happened and fade quietly without global-toast accumulation or modal friction.

## Recoverable Error Guidance

Recoverable errors use a plain explanation and one repair action, stating what failed, what remains safe, and what to do next. Technical details do not lead the primary UI.

## Contextual Background Status

Background work appears as quiet contextual status only where it matters, such as “Source indexing…” within that source. Relevant controls can cancel or retry; no global activity dashboard is required.

## Visible Contextual Sort

Lists expose a visible contextual default such as Most relevant, Most recent, or Needs review, with a simple change control. Ranking is never hidden or implied to be objective truth.

## Explicit Bulk Actions

Bulk actions appear only after the user explicitly enters multi-select. Normal lists remain calm while export, routing, archiving, and deletion remain practical at scale.

## Mobile Reachability

Mobile primary actions sit in thumb-reachable lower content or a bottom action bar with safe-area spacing. Core workflows do not depend on top-right actions or generic floating buttons.

## Discoverable Desktop Shortcuts

Desktop provides a discoverable shortcut sheet with only high-value controls: search, capture, resume, and close. It improves flow without turning the PWA into an overwhelming command-center interface.

## Readability Scaling

The PWA supports system text scaling plus a compact in-app readability control. Layouts reflow rather than clip when type increases.

## Restrained Semantic Color

Semantic color is limited to deep teal for primary/action, muted amber for caution, and restrained red for irreversible or safety-critical states. Text and icons always carry the meaning too.

## Low-stimulation Dark Mode

Dark mode is a true low-stimulation mode with darker neutral surfaces, reduced contrast spikes, and the same semantic hierarchy. It is not a direct color inversion.

## Three Responsive Layouts

The PWA has three deliberate layouts: phone first, tablet with more breathing room, and desktop with a contextual rail. The information model stays stable while spacing and structure adapt intentionally.

## First Figma Flow

When Figma access is available, the first detailed artifact is the complete mobile Regulation flow: Facts → Story → Emotion → Urge → Action, plus Draft and Outcome states, using the approved primitives.

## Regulation Walkthrough Validation

The first Regulation flow review uses short scripted walkthroughs for ordinary activation, an incomplete-information spiral, and a genuine boundary concern. Validation tests behavioral and safety fit before broader workspace design.

## Regulation Walkthrough Pass Criteria

A Regulation walkthrough passes only when the user can identify facts versus meaning, pause before action, reach safety help when needed, and leave with one values-consistent next step. Visual polish supports these outcomes but does not replace them.

## Walkthrough Iteration Record

After each Regulation walkthrough, record observed friction, safety ambiguity, cognitive-load issues, and one focused design change. Iteration remains evidence-based rather than a vague aesthetic review.

## Shared Component Change Governance

When walkthrough evidence requires a component change, update the shared Figma component and log the reason in the architecture handoff. Screen-local patches are avoided so known problems do not spread as drift.

## Safety-first Figma Gate

Before implementation, Figma must include an approved mobile Regulation flow, Now screen, token foundation, key empty/offline/error states, and walkthrough evidence. This supports a safety-first tracer bullet rather than broad shallow coverage.

## Design-to-code Handoff

Implementation handoff includes Figma node links, token table, component/state inventory, interaction notes, accessibility notes, and ADR mappings. The build remains traceable to architecture rather than relying on screenshots alone.

## Decision-critical Prototype

The Figma prototype covers only decision-critical interactions: enter Regulation, advance through steps, exit and resume drafts, safety access, accept or change next action, and offline state. It avoids brittle simulation of every possible interaction.

## Prototype Motion

Figma prototype transitions use short dissolves or slides only where they clarify a context change, such as entering a focused Regulation step. Motion reinforces orientation rather than adding personality or stimulation.

## Safety Prototype Annotations

Safety-sensitive prototype screens include design-review annotations explaining safety overrides and data-retention boundaries. These annotations support implementation review and are not part of everyday user-facing UI.

## End-to-end First-slice Review

The first-slice Figma review is a guided end-to-end walkthrough from Now through Regulation, outcome, and later review. It validates continuity across the behavioral loop, not merely screen-level polish.

## Contextual Chat Composer

Chat uses a calm multi-line composer with explicit mode context and an optional attachment or capture action. It supports reflective, research, and work-oriented input without hiding current posture.

## Local Chat Drafts

Unsent Chat text persists locally as a clearly labeled draft. It survives interruption without being treated as sent content or durable memory.

## Purposeful Conversation Sessions

Conversation history groups messages into purposeful sessions with a human-editable title and visible mode label. Sessions support resumption and retrieval without opaque automatic topic clustering.

## Quiet Session Closeout

When a session appears complete, the UI offers a quiet closeout that summarizes intent and proposes durable objects while leaving the session open unless the user explicitly closes it. Automatic archival is avoided.

## Provenance-aware Session Summary

Session closeouts distinguish what the user said, what the agent inferred, and what requires confirmation. This keeps memory formation auditable and challengeable.

## Reviewable Memory Candidates

Proposed memory candidates show the proposed statement, supporting excerpts, domain, confidence, and Confirm, Edit, or Decline actions. Plausible inference cannot become personal memory without review.

## Declined Candidate Suppression

Declining a memory candidate offers “Don't suggest this again” and records a suppression signal. The system learns from correction without requiring a detailed reason or repeatedly surfacing the same mistaken inference.

## Plain-language Evidence Strength

Candidate confidence uses plain-language evidence strength, for example “Supported by 3 conversations” or “Limited evidence,” rather than pseudo-precise percentages.

## Unified New Action

The global New action opens the same save-first Capture sheet across the PWA, with optional route choices after saving. Creation does not require learning a different menu in each workspace.

## Attachment Review

Attachments show compact local previews with file type, origin, processing state, and a remove action before sending or saving. Sensitive material remains reviewable at the moment it enters the system.

## Reviewable OCR

OCR presents the original attachment alongside editable extracted text and a confidence note. Extraction is a reviewable aid rather than an invisible transformation of user material.

## Per-batch Cloud Processing Choice

Before sensitive attachment content is sent to a cloud model, the UI requires an explicit per-batch processing choice. It states what will leave the VM and offers a local-only path.

## Editable Redaction

Redaction is previewable and editable before cloud processing. Detected sensitive spans can be changed or removed, then the user explicitly confirms the processed batch.

## Domain-specific Attachment Retention

Attachment retention is chosen by domain with a visible default: retain as Evidence, retain briefly as a private draft, or delete after extraction. A single global policy is too blunt for research and sensitive reflection.

## Adaptive Locale Defaults

The PWA uses device locale by default with simple overrides for language, date format, and timezone. This supports travel and adjustable reminders without repeated configuration.

## Semantic Time Display

When timezone changes, reminders and deadlines show resolved local time alongside original semantic intent, for example “This evening · 7:00 PM Manila.” This preserves meaning while keeping current actionability.

## First Offline Entry

When the PWA opens offline for the first time, it presents one calm screen explaining local capabilities and offering Capture or the Regulation protocol. It sets expectations without blocking useful work.

## Progressive Advanced Controls

Advanced controls use progressive disclosure under clear More options labels. The primary path remains calm while power and governance functions stay discoverable.

## Contextual Screen Help

Screen-level help uses contextual How this works disclosures next to unfamiliar or safety-sensitive controls. Help remains specific, skippable, and attached to the point of decision.

## Block-level Model Labels

Model-assisted content is labeled at the content-block level with its source/provenance stamp. The distinction remains clear without repeating technical warnings line by line.

## Conditional User-authored Labels

User-authored material is labeled “You wrote” only when it appears alongside agent or model content. Authorship stays clear where ambiguity exists without repetitive labels in ordinary notes.

## Evidence Excerpts

Source excerpts appear as indented evidence blocks with a source stamp and Open source action. They remain visibly distinct from user and model prose while supporting immediate verification.

## Unsupported Claim Handling

When the system lacks evidence for a claim, it states the uncertainty plainly and offers the next research action. It does not present unsupported synthesis as confident knowledge.

## Quiet Citation Gaps

Weak or missing citations use a quiet inline Needs support marker with an evidence-search action. Gaps are visible during drafting without treating ordinary uncertainty as an error.

## Named Version Checkpoints

Version history uses named checkpoints with a compact diff, such as Before restructure, Draft 2, and Approved export. History stays understandable and recoverable without a developer-style interface.

## Privacy-aware Sharing Review

Sharing or exporting sensitive content runs a provenance and privacy review first. The user sees linked sources and personal references, then chooses whether to include or strip them.

## Meaningful Tone Presets

Companion tone uses a small set of behaviorally meaningful presets: Calm direct, More concise, and More challenging, each with a clear explanation. Tone is configurable without exposing an unconstrained persona prompt.

## Regulation Tone Safety Override

Regulation Mode may override the selected tone only toward calmer, more direct safety language when activation or danger warrants it. Outside these conditions, the user's chosen delivery preference remains in control.

## Situational Autonomy Reinforcement

The companion reinforces autonomy only in high-stakes or repeated reassurance contexts: use the system as a pause and structure, then decide in real life. It avoids repetitive disclaimers that feel cold or scripted.

## Reassurance Loop Redirect

When the user repeats a reassurance question, the system names the loop, restates known facts once, and redirects to the next values-consistent action. The boundary is firm without punishment or shame.

## Inline Reassurance Boundary

Reassurance-loop redirects appear as a calm inline boundary card with one next action. The pattern and path forward stay visible without a blocking modal or punitive tone.

## Evidence-bound Relationship Guidance

Relationship-boundary guidance presents a clear boundary statement, the present behavior it addresses, and one calm question or action. It avoids verdicts about the relationship and vague self-care substitutions.

## Restricted Relationship Records

Safety-sensitive relationship records require an explicit Restricted designation and stay out of ordinary cross-domain suggestions. They are available only where the user intentionally grants relevant context.

## Just-in-time Restricted Linking

Linking a restricted record into a Regulation or relationship session requires just-in-time confirmation showing the exact record and why it may help. Blanket permission and automatic similarity-based linkage are excluded.

## On-demand Context Disclosure

When prior confirmed context influences a suggestion, the UI offers a compact Using this context disclosure on demand. It can show the relevant value, rule, or task without making history omnipresent or hidden.

## Direct Context Correction

The Using this context disclosure includes a direct Correct this context action. Users can edit, unconfirm, or change context scope at the moment it proves wrong or outdated.

## Focused Context Notice

When limited context materially affects an answer for speed or privacy, the UI may say Using focused context. It clarifies important omissions without exposing internal diagnostics in routine use.

## Bounded Low-confidence Answer

When confidence or context is incomplete, the system gives a bounded answer when useful and names the one fact, source, or permission that would improve it. It avoids both stonewalling and generic filler.

## Quiet Loading States

Loading uses quiet structural placeholders that preserve layout without animated shimmer by default. Loading is a brief pause in a stable workspace rather than a visual spectacle.

## Accessible State Announcements

Important state changes use concise screen-reader status messages for saved drafts, mode changes, errors, and safety escalation. Feedback remains informative without narrating every visual change.

## Tablet Content Model

Tablet retains one primary content column with an optional collapsible context panel. It gains space without inheriting a permanent desktop rail or losing the calm mobile mental model.

## Return-position Preservation

Returning to a workspace restores prior scroll position and shows the one-sentence attention anchor only when context changed. The UI preserves momentum without disorienting the user.

## Deliberate External Links

External links show a clear destination preview with an explicit Open externally action. Source navigation remains deliberate without adding an embedded browsing system to the first slice.

## Safe Inline Undo

Reversible actions such as routing, archiving, and non-destructive edits offer a brief inline Undo. Irreversible deletion uses explicit scope review rather than misleading undo behavior.

## Reversible Archive

Archive hides an item from default active views while preserving search, provenance, and a restore action. It is a reversible organizational state, not a disguised delete action.

## Scoped Recently Viewed

Recently viewed is limited to the current workspace and appears only when it helps resume work. The PWA avoids a global activity feed that could feel like surveillance.

## Plain-language Audit Events

Audit and history use plain human actions, such as “You exported Regulation records” or “The system indexed this source locally.” Accountability remains understandable without technical event names.

## Visible Domain-scoped Automations

Future automations are visible, pausable, and scoped by domain. Each explains what runs, why, and when; hidden background behavior is excluded.

## Compact Automation Outcomes

Automation history uses a compact outcome log with optional details, such as “Weekly review prepared; not sent” or “Reminder skipped; paused.” Accountability stays visible without everyday technical traces.

## User-centered Settings Groups

Settings are grouped as Experience, Companion, Reminders, Privacy, and System. Categories reflect user decisions rather than internal module names.

## Consequence-aware Settings

Impactful setting changes show a one-line consequence before saving, such as “Active reminders may appear during related work.” Preferences remain understandable without an overly long confirmation flow.

## Scoped Reset Controls

Reset controls are scoped and explicit: reset Experience, reset Companion preferences, or erase a specific domain. The UI avoids an ambiguous global Reset app action.

## Bounded Historical Import

Historical import uses a selected, bounded, reversible review flow: choose sources, inspect import scope, set processing and retention, then confirm. It does not import everything automatically.

## Import Batch Provenance

Imported content carries a permanent import source stamp and batch reference. Each backfill batch remains inspectable, correctable, and deletable without guessing its origin.

## Reviewable Import Duplicates

Potential imported duplicates appear as a comparison with Keep both, Merge, or Skip. Cleanup preserves provenance and user control rather than silently merging records.

## Plain-language Retrieval Signals

Hybrid retrieval explanations name contributing signals in plain language, such as exact terms, recent use, linked context, or semantic similarity. The UI avoids both opaque relevance and raw ranking internals.

## Local Recent-search Privacy

Search queries are stored locally only as optional, clearable recent-search history. They support resumption and are not used for hidden profiling or automatic personal inference.

## Redacted Restricted Search Results

Restricted search results appear as redacted shells until the user explicitly reveals them. They preserve intentional discoverability while protecting glance privacy in shared spaces.

## Configurable Privacy Lock

The PWA uses a configurable short inactivity timeout and a privacy-safe lock screen with no sensitive previews. It resumes after local authentication without locking on every backgrounding event.

## Privacy-safe Unlock Return

After unlocking, the PWA returns to the prior screen while sensitive fields remain obscured until re-focused. Continuity is preserved without reopening private content at a glance.

## Plain Lock Timeout Control

Lock timeout appears as a plain setting with its consequence explained, for example “Lock after 5 minutes of inactivity.” Privacy controls remain concrete rather than abstract security labels.

## Monthly Model Budget View

System includes a compact monthly model/API budget view with estimated spend, model usage by task class, and an adjustable cap. Cost remains governable without token counters in everyday work.
