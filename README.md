# Research Paper Agent

A local Google ADK agent that reads papers, extracts concepts, and answers questions with source-grounded evidence.

## What It Does

- Ingests `.txt`, `.md`, and optionally `.pdf` files from `papers/`
- Extracts metadata, concepts, methods, findings, limitations, and open questions
- Stores page-aware passages with stable citation IDs
- Saves reusable notes in `knowledge_base/`
- Searches ingested evidence with weighted lexical ranking before answering
- Compares papers by concepts, methods, findings, and limitations
- Builds citation-backed study guides and recall questions
- Learns local user preferences, interests, question patterns, and communication quirks
- Separates source-backed claims from inference

## Setup

1. Install dependencies:

```powershell
C:\Users\Andre\AppData\Local\Microsoft\WindowsApps\python3.13.exe -m pip install -r research_paper_agent\requirements.txt
```

2. Put papers in `papers/`.
3. Copy `.env.example` to `.env`.
4. Add your DeepSeek API key.
5. From the parent folder, run:

```powershell
C:\Users\Andre\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\adk.exe run research_paper_agent
```

For a browser UI:

```powershell
C:\Users\Andre\Documents\Codex\2026-06-30\g\outputs\research_paper_agent\start_web.ps1
```

The launcher creates `.adk` storage and passes explicit SQLite/artifact paths to ADK. Use it if the web UI reports `sqlite3.OperationalError: unable to open database file`.

## Useful Prompts

- `Ingest all papers in the papers folder.`
- `List the main concepts you found.`
- `Give me a brief for each paper.`
- `Search for evidence about benchmark evaluation.`
- `What does the Smith paper say about retrieval augmented generation?`
- `Compare the limitations across the papers.`
- `Compare the papers on evaluation methodology.`
- `Make me a study guide with recall questions.`
- `Quiz me on the most important concepts from the papers.`
- `Learn this about me: I like short answers with exact commands.`
- `Remember that I care about AI agents, research workflows, and self-improving tools.`
- `Audit how you should improve around my style.`
- `Grill me on this paper based on what you know about me.`
- `Ask me questions and recommendations from the text and my quirks.`

## Tool Capabilities

- `list_papers`: shows files available in `papers/`
- `ingest_paper`: ingests one paper and writes a JSON record
- `ingest_all_papers`: ingests every supported paper
- `list_concepts`: lists extracted concepts by paper
- `search_evidence`: returns cited passages for a query
- `paper_brief`: summarizes one or all ingested papers from stored notes
- `compare_papers`: compares papers overall or around a topic
- `make_study_guide`: creates citation-backed recall questions
- `get_user_profile`: shows the local personalization profile
- `learn_from_user_message`: updates the profile from a message
- `record_interaction`: appends an interaction event to the local log
- `set_user_preference`: stores an explicit preference, interest, quirk, or avoidance
- `self_improvement_audit`: suggests how the agent should adapt next
- `adaptive_grill`: asks personalized questions from the user model and ingested text
- `respond_to_adaptive_grill`: learns from a grill answer and recommends the next step

## Personalization

The agent stores personalization locally under `user_model/`. It can learn from explicit preferences and repeated interaction signals, then adapt answers around your interests, phrasing, and common question types.

Useful prompts:

- `What do you know about my interests?`
- `Remember: I prefer blunt answers when I ask operational questions.`
- `Learn from this message: okay go improve it.`
- `Audit your user model and tell me what you should do differently.`
- `Start an adaptive grill on evaluation methodology.`
- `Ask me one question at a time based on my quirks and this paper.`

The profile is inspectable at `user_model/profile.json`. Interaction logs are written to `user_model/interaction_log.jsonl`.

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

```powershell
C:\Users\Andre\AppData\Local\Microsoft\WindowsApps\python3.13.exe -m pip install -r research_paper_agent\requirements.txt
```
