"""Knowledge self-audit and correction — inspectable agent state.

Extracted from agent.py per Python Module Architecture Plan Phase 4.
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from typing import Any

from .paths import CANDIDATE_SIGNALS_PATH, INTERACTION_LOG_PATH

logger = logging.getLogger(__name__)


def knowledge_self_audit() -> dict[str, Any]:
    """Inspectable view of what the agent has learned across all knowledge channels."""
    from research_paper_agent import concept_graph, personal_notes  # noqa: PLC0415
    from research_paper_agent.agent import (  # noqa: PLC0415
        PERSONAL_NOTES_PATH, _load_tutor_progress,
        _load_user_profile,
    )
    from .paths import now_iso  # noqa: PLC0415

    profile = _load_user_profile()
    now = now_iso()

    # ── confirmed preferences ──────────────────────────────────────────
    confirmed = {
        "preferences": [
            {"type": "style", "value": p.get("preference", ""), "source": str(p.get("source", ""))[:200]}
            for p in profile.get("style_preferences", [])
        ],
        "avoidances": [
            {"type": "avoidance", "value": a.get("preference", ""), "source": str(a.get("source", ""))[:200]}
            for a in profile.get("avoidances", [])
        ],
        "interests": [
            {"name": i.get("name", ""), "confidence": i.get("confidence", 0.0),
             "evidence": str(i.get("evidence", ""))[:200]}
            for i in profile.get("interests", [])
        ],
        "adaptation_rules": profile.get("adaptation_rules", []),
    }

    # ── candidate signals ──────────────────────────────────────────────
    candidate_signals: list[dict[str, Any]] = []
    candidate_count = 0
    if CANDIDATE_SIGNALS_PATH.exists():
        try:
            raw = [json.loads(line) for line in CANDIDATE_SIGNALS_PATH.open("r", encoding="utf-8") if line.strip()]
            candidate_count = len(raw)
            signal_types: Counter = Counter()
            for entry in raw[-40:]:
                for sig in entry.get("signals", []):
                    signal_types[sig.get("type", "unknown")] += 1
            candidate_signals = [
                {"type": st, "count": c, "status": "candidate — not yet confirmed"}
                for st, c in signal_types.most_common(8)
            ]
        except Exception:
            candidate_signals = [{"error": "Could not parse candidate signals file."}]

    # ── concept graph health ───────────────────────────────────────────
    concept_health: dict[str, Any] = {"strongest": [], "stale": [], "rejected": [], "merge_suggestions": []}
    try:
        graph = concept_graph.get_concept_graph()
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        ranked = sorted(nodes, key=lambda n: n.get("weight", 0.0), reverse=True)
        concept_health["strongest"] = [
            {"name": n["name"], "weight": n.get("weight", 0.0), "sources": n.get("sources", [])}
            for n in ranked[:5] if n.get("weight", 0) > 0
        ]
        concept_health["stale"] = [
            {"name": n["name"], "weight": n.get("weight", 0.0)}
            for n in nodes if 0 < n.get("weight", 0) < 0.3
        ][:5]
        concept_health["rejected"] = [
            {"name": n["name"]} for n in nodes if n.get("rejected")
        ][:5]
        name_to_neighbors: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            if src and tgt:
                name_to_neighbors[src].add(tgt)
                name_to_neighbors[tgt].add(src)
        seen_pairs: set[tuple[str, str]] = set()
        for name_a, neighbors_a in name_to_neighbors.items():
            for name_b, neighbors_b in name_to_neighbors.items():
                if name_a >= name_b:
                    continue
                pair = (name_a, name_b)
                if pair in seen_pairs:
                    continue
                overlap = neighbors_a & neighbors_b
                if len(overlap) >= 3:
                    seen_pairs.add(pair)
                    concept_health["merge_suggestions"].append({
                        "concept_a": name_a, "concept_b": name_b,
                        "shared_neighbors": sorted(overlap)[:5],
                        "rationale": f"Share {len(overlap)} neighbor concepts — consider merging.",
                    })
        concept_health["merge_suggestions"] = concept_health["merge_suggestions"][:5]
    except Exception:
        concept_health = {"error": "Concept graph not available or unreadable."}

    # ── tutor state ────────────────────────────────────────────────────
    tutor_state: dict[str, Any] = {"mastered": [], "weak": [], "total_concepts": 0}
    try:
        progress = _load_tutor_progress()
        concepts = progress.get("concepts", {})
        tutor_state["total_concepts"] = len(concepts)
        for key, entry in concepts.items():
            asked = max(entry.get("times_asked", 0), 1)
            ratio = entry.get("times_correct", 0) / asked
            if ratio >= 0.8:
                tutor_state["mastered"].append({"concept": key, "ratio": round(ratio, 2)})
            elif asked >= 2 and ratio < 0.5:
                tutor_state["weak"].append({"concept": key, "ratio": round(ratio, 2), "asked": asked})
        tutor_state["mastered"] = sorted(tutor_state["mastered"], key=lambda c: c["ratio"], reverse=True)[:8]
        tutor_state["weak"] = sorted(tutor_state["weak"], key=lambda c: c["ratio"])[:8]
    except Exception:
        tutor_state = {"error": "Tutor progress unavailable."}

    # ── note-derived signals ───────────────────────────────────────────
    note_signals: dict[str, Any] = {"total_notes": 0, "recent_concepts": []}
    try:
        all_notes = personal_notes.list_notes(path=PERSONAL_NOTES_PATH).get("notes", [])
        note_signals["total_notes"] = len(all_notes)
        note_concepts: Counter = Counter()
        for n in all_notes[-30:]:
            for c in n.get("concepts", []):
                note_concepts[c] += 1
        note_signals["recent_concepts"] = [
            {"concept": c, "note_count": cnt} for c, cnt in note_concepts.most_common(8)
        ]
    except Exception:
        note_signals = {"error": "Personal notes unavailable."}

    # ── interaction summary ────────────────────────────────────────────
    interaction_summary: dict[str, Any] = {"total": 0, "recent_tags": []}
    if INTERACTION_LOG_PATH.exists():
        try:
            interactions = [
                json.loads(line) for line in INTERACTION_LOG_PATH.open("r", encoding="utf-8") if line.strip()
            ]
            interaction_summary["total"] = len(interactions)
            tag_counts: Counter = Counter()
            for entry in interactions[-50:]:
                for tag in str(entry.get("tags", "")).split(","):
                    tag = tag.strip()
                    if tag:
                        tag_counts[tag] += 1
            interaction_summary["recent_tags"] = [
                {"tag": t, "count": c} for t, c in tag_counts.most_common(8)
            ]
        except Exception:
            interaction_summary = {"error": "Interaction log unreadable."}

    correction_actions = [
        {"action": "confirm_signal", "description": "Promote a candidate signal to a durable preference."},
        {"action": "reject_signal", "description": "Mark a candidate signal as rejected."},
        {"action": "downgrade_preference", "description": "Reduce the weight of an over-promoted preference."},
        {"action": "suppress_concept", "description": "Suppress a concept in graph ranking."},
    ]

    return {
        "audit_generated_at": now,
        "confirmed": confirmed,
        "candidate_signals": {"count": candidate_count, "top_types": candidate_signals, "path": str(CANDIDATE_SIGNALS_PATH)},
        "concept_graph": concept_health,
        "tutor_state": tutor_state,
        "notes": note_signals,
        "interaction_summary": interaction_summary,
        "correction_actions_available": correction_actions,
    }


def self_audit_correction(action: str, target: str, reason: str = "") -> dict[str, Any]:
    """Apply a user-directed correction to the knowledge model."""
    from research_paper_agent import concept_graph  # noqa: PLC0415
    from research_paper_agent.agent import (  # noqa: PLC0415
        CANDIDATE_SIGNALS_PATH, _load_user_profile,
        _save_user_profile,
    )
    from .paths import now_iso  # noqa: PLC0415

    valid_actions = {"confirm_signal", "reject_signal", "downgrade_preference", "suppress_concept"}
    if action not in valid_actions:
        return {"status": "error", "message": f"Unknown action '{action}'. Valid: {sorted(valid_actions)}"}

    profile = _load_user_profile()
    now = now_iso()

    if action == "confirm_signal":
        if ":" in target:
            category, value = target.split(":", 1)
        else:
            category, value = "interest", target

        if category == "interest":
            existing = [i for i in profile.get("interests", []) if i.get("name", "").lower() == value.lower()]
            if existing:
                existing[0]["confidence"] = min(1.0, existing[0].get("confidence", 0.5) + 0.2)
                existing[0]["evidence"] = f"{existing[0].get('evidence', '')}; confirmed via audit: {reason}"[:400]
            else:
                profile.setdefault("interests", []).append({
                    "name": value, "confidence": 0.85,
                    "evidence": f"Confirmed via audit: {reason}"[:400],
                })
        elif category in ("style", "preference"):
            profile.setdefault("style_preferences", []).append({
                "preference": value, "source": f"Audit correction: {reason}"[:400],
            })
        elif category == "rule":
            profile.setdefault("adaptation_rules", []).append({
                "rule": value, "source": f"Audit correction: {reason}"[:400], "confirmed_at": now,
            })
        profile["updated_at"] = now
        _save_user_profile(profile)
        return {"status": "ok", "action": "confirm_signal", "target": target, "reason": reason}

    if action == "reject_signal":
        rejection = {"timestamp": now, "target": target, "reason": reason, "action": "rejected"}
        CANDIDATE_SIGNALS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CANDIDATE_SIGNALS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(rejection) + "\n")
        return {"status": "ok", "action": "reject_signal", "target": target, "reason": reason}

    if action == "downgrade_preference":
        for bucket in ["interests", "style_preferences"]:
            for item in profile.get(bucket, []):
                name = item.get("name") or item.get("preference", "")
                if target.lower() in name.lower():
                    item["confidence"] = max(0.1, item.get("confidence", 0.5) - 0.3)
                    item["downgraded_at"] = now
                    item["downgrade_reason"] = reason[:300]
        profile["updated_at"] = now
        _save_user_profile(profile)
        return {"status": "ok", "action": "downgrade_preference", "target": target, "reason": reason}

    if action == "suppress_concept":
        try:
            concept_graph.reject_concept(target, reason)
        except Exception:
            pass
        return {"status": "ok", "action": "suppress_concept", "target": target, "reason": reason}

    return {"status": "error", "message": "Unhandled action."}
