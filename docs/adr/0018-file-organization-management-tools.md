# ADR 0018 — File Organization and Management Tools

**Date:** 2026-07-01
**Status:** Accepted

## Context

The `papers/` directory has grown to 9 files across 3 research clusters. Filenames are inconsistent (some cryptic like `4393835.pdf`, some full-length, some with spaces). There is no subdirectory structure. The agent has no tools to rename, move, or delete files — only ingest and read.

## Decisions

### 1. Naming scheme: `Author_Year_ShortTitle.ext`

First-author surname + year + short descriptive title. Institutional or survey works without a single named author keep their source abbreviation (e.g., `SEP_2023_...`, `JSim_2026_...`, `OHAL_Ch25_...`).

### 2. Folder structure: threshold-based

- Clusters with ≥3 papers get a subdirectory (currently only `abm/`).
- Clusters with <3 papers stay flat with a `PREFIX_` on the filename (`CULT_`, `LING_`).
- Rationale: avoids single-file folders while keeping large clusters scannable.

### 3. Destructive tools require dry-run confirmation

`delete_paper` defaults to `dry_run=True`. The agent describes what it *would* delete (file + KB record) and waits for explicit confirmation ("actually do it") before executing.

### 4. Rename is atomic across file, KB record, and concept graph

`rename_paper(old, new)` must:
1. Rename the file in `papers/`
2. Rename the corresponding `knowledge_base/*.json` record
3. Patch the `"source"` field inside the record
4. Migrate concept graph edges referencing the old filename

If any step fails, the operation rolls back.

### 5. Delete cleans up KB record atomically

`delete_paper` removes both the file and its `knowledge_base/*.json` record. Concept graph edges are cleaned up as well.

### 6. Cluster weight biases research-taste and recommendations

When a cluster has ≥3 papers with explicit interconnections (per concept graph), the agent applies a soft cluster-weight bias: research-taste judgments, compare-papers suggestions, and grill questions favor that cluster. It is a signal, not a filter — smaller clusters still surface when relevant.

## Consequences

- Three new tools must be added to `agent.py`: `rename_paper`, `delete_paper`, `organize_papers`.
- `ingest_paper` already keys KB records by filename; the rename tool must keep these in sync.
- The user profile (`profile.json`) gains an optional `cluster_weights` field populated from concept graph density.
- The `abmphi.pdf` (0 bytes) and `Hall_Edward_T_Beyond_Culture_ocr.pdf` (redundant, pending quality comparison) are candidates for deletion after tools are added.

## Target file layout

```
papers/
  abm/
    Macy-Willer_2002_From-Factors-to-Actors.pdf
    Angere_2010_Knowledge-in-a-Social-Network.pdf
    SEP_2023_ABM-in-Philosophy-of-Science.pdf
    JSim_2026_ABMS-Economic-Markets-Review.pdf
  CULT_Hall_1976_Beyond-Culture.txt
  CULT_UF-IFAS_2026_Understanding-Monochronic-Polychronic-Time.pdf
  LING_OHAL_Ch25_Austronesian-Archaeolinguistics.pdf
```
