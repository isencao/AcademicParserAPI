"""
evaluation.py — Semantic Knowledge Extraction Evaluation Layer

Compares cards in the database against gold-standard expected cards
stored in eval/expected/*.json and produces structured metrics.
"""

import re
import json
import csv
import io
from pathlib import Path
from typing import Dict, Any, List, Optional

EXPECTED_DIR = Path(__file__).parent / "eval" / "expected"

CARD_SCHEMA = {
    "card_id": {
        "type": "string",
        "description": "Unique identifier combining doc_id, page/para index, card index, kind, and title slug.",
        "example": "doc1_graph_connectivity_0000_00_definition_graph"
    },
    "source_document": {
        "type": "string",
        "description": "Original filename of the source PDF/TXT/MD document.",
        "example": "doc1_graph_connectivity.md"
    },
    "card_type": {
        "type": "enum",
        "values": ["definition", "theorem", "lemma", "example", "question", "note", "summary"],
        "description": "Semantic category of the extracted knowledge unit."
    },
    "title": {
        "type": "string",
        "description": "Short, human-readable label for the card.",
        "example": "Menger's Theorem"
    },
    "body": {
        "type": "string",
        "description": "Full extracted text content of the card."
    },
    "tags": {
        "type": "array[string]",
        "description": "2–5 lowercase hyphenated topic tags extracted by LLM.",
        "example": ["graph-theory", "np-hard"]
    },
    "anchors": {
        "type": "array[string]",
        "description": "3–10 key tokens including LaTeX expressions and core terms.",
        "example": ["$G$", "$O(n)$", "vertex", "edge"]
    },
    "span_hint": {
        "type": "string",
        "description": "Page or paragraph number where the card was found.",
        "example": "3"
    },
    "confidence": {
        "type": "float",
        "range": "0.0 – 1.0",
        "description": (
            "Extraction confidence score. "
            "1.0 = explicit label in text, "
            "0.8 = structural inference, "
            "0.6 = content inference, "
            "0.4 = ambiguous kind."
        )
    },
    "extraction_method": {
        "type": "enum",
        "values": ["llm", "rule_based", "ocr"],
        "description": (
            "How the card was extracted: "
            "llm (Groq Llama-3.3-70b), "
            "rule_based (regex fallback when LLM unavailable), "
            "ocr (Tesseract fallback for scanned pages)."
        )
    },
    "relations": {
        "type": "array[Relation]",
        "description": "Typed edges to other cards in the knowledge graph.",
        "relation_types": {
            "related_to": "Generic semantic overlap (threshold: 3+ shared anchors).",
            "depends_on": "Card A relies on concept defined in card B.",
            "example_of": "Card A is a concrete instance of card B.",
            "uses": "Theorem/proof uses a lemma.",
            "generalizes": "Card A is a generalisation of card B."
        }
    }
}


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower().strip()).strip("-")


def _best_match(expected_card: dict, extracted: List[dict]) -> Optional[dict]:
    """Find the best matching extracted card for a given expected card.

    Matching heuristic (same as run_eval.py, priority order):
      1. kind matches AND at least one key_term appears in title or body  → score 10+
      2. kind matches AND title Jaccard > 0.5                             → score  5+
      3. at least two key_terms appear in body regardless of kind         → score  3+
    Returns None if nothing scores above zero.
    """
    exp_title_words = set(_slugify(expected_card["title"]).split("-"))
    exp_terms = {t.lower() for t in expected_card.get("key_terms", [])}

    best, best_score = None, 0

    for card in extracted:
        ext_body  = (card.get("body",  "") or "").lower()
        ext_title = (card.get("title", "") or "").lower()
        combined  = ext_title + " " + ext_body

        term_hits = sum(1 for t in exp_terms if t in combined)
        ext_words = set(_slugify(ext_title).split("-"))
        union     = exp_title_words | ext_words
        jaccard   = len(exp_title_words & ext_words) / len(union) if union else 0
        kind_match = card.get("kind", "").lower() == expected_card["kind"].lower()

        score = 0
        if kind_match and term_hits >= 1:
            score = 10 + term_hits + jaccard
        elif kind_match and jaccard > 0.5:
            score = 5 + jaccard
        elif term_hits >= 2:
            score = 3 + term_hits

        if score > best_score:
            best_score = score
            best = card

    return best if best_score > 0 else None


def build_report(db) -> Dict[str, Any]:
    """Build the full evaluation report.

    1. Reads every JSON file from eval/expected/.
    2. Pulls all non-summary cards from the DB, grouped by document stem.
    3. Runs _best_match for each expected card.
    4. Merges with persisted user verdicts from evaluation_verdicts table.
    5. Returns a structured dict with per-doc rows + overall metrics.
    """
    if not EXPECTED_DIR.exists():
        return {
            "error": "eval/expected/ directory not found. Create it and add gold-standard JSON files.",
            "docs": [],
            "overall": {}
        }

    all_notes = db.get_all_notes()
    raw_verdicts: List[dict] = db.get_verdicts()
    verdict_map: Dict[str, dict] = {v["row_id"]: v for v in raw_verdicts}

    # Group DB cards by document stem (strip extension)
    doc_notes: Dict[str, List[dict]] = {}
    for note in all_notes:
        if note.get("kind") == "summary":
            continue
        doc_id = note.get("doc_id", "") or ""
        stem = Path(doc_id).stem if doc_id else doc_id
        doc_notes.setdefault(stem, []).append(note)

    docs_result: List[dict] = []
    g_expected = g_extracted = g_matched = 0
    g_correct  = g_wrong_type = g_missing = g_noise = g_wrong_split = 0

    for exp_file in sorted(EXPECTED_DIR.glob("*.json")):
        stem = exp_file.stem
        try:
            with open(exp_file, encoding="utf-8") as f:
                expected: List[dict] = json.load(f)
        except Exception:
            continue

        extracted = doc_notes.get(stem, [])
        rows: List[dict] = []
        matched_card_ids: set = set()

        for exp in expected:
            match = _best_match(exp, extracted)
            row_id = f"{stem}_row_{_slugify(exp['title'])}"
            persisted = verdict_map.get(row_id, {})

            if match is None:
                auto_status = "missing"
                rows.append({
                    "row_id":           row_id,
                    "expected_title":   exp["title"],
                    "expected_kind":    exp["kind"],
                    "extracted_title":  None,
                    "extracted_kind":   None,
                    "extracted_card_id": None,
                    "status":           auto_status,
                    "verdict":          persisted.get("verdict") or auto_status,
                    "note":             persisted.get("note", ""),
                })
                continue

            match_uid = match.get("card_id") or str(id(match))
            if match_uid in matched_card_ids:
                auto_status = "wrong_split"
            elif match.get("kind", "").lower() == exp["kind"].lower():
                auto_status = "correct"
            else:
                auto_status = "wrong_type"

            matched_card_ids.add(match_uid)

            rows.append({
                "row_id":           row_id,
                "expected_title":   exp["title"],
                "expected_kind":    exp["kind"],
                "extracted_title":  match.get("title"),
                "extracted_kind":   match.get("kind"),
                "extracted_card_id": match.get("card_id"),
                "status":           auto_status,
                "verdict":          persisted.get("verdict") or auto_status,
                "note":             persisted.get("note", ""),
            })

        noise_cards = [
            {"card_id": c.get("card_id"), "title": c.get("title"), "kind": c.get("kind")}
            for c in extracted
            if (c.get("card_id") or str(id(c))) not in matched_card_ids
        ]

        # Metrics are based on the final verdict (user override or auto if untouched)
        correct      = sum(1 for r in rows if r["verdict"] == "correct")
        wrong_type   = sum(1 for r in rows if r["verdict"] == "wrong_type")
        missing      = sum(1 for r in rows if r["verdict"] == "missing")
        wrong_split  = sum(1 for r in rows if r["verdict"] == "wrong_split")
        noise        = len(noise_cards)
        matched      = len(rows) - missing

        docs_result.append({
            "doc":         stem,
            "rows":        rows,
            "noise_cards": noise_cards,
            "metrics": {
                "expected":    len(expected),
                "extracted":   len(extracted),
                "matched":     matched,
                "correct":     correct,
                "wrong_type":  wrong_type,
                "missing":     missing,
                "wrong_split": wrong_split,
                "noise":       noise,
            }
        })

        g_expected   += len(expected)
        g_extracted  += len(extracted)
        g_matched    += matched
        g_correct    += correct
        g_wrong_type += wrong_type
        g_missing    += missing
        g_noise      += noise
        g_wrong_split += wrong_split

    overall = {
        "expected":    g_expected,
        "extracted":   g_extracted,
        "matched":     g_matched,
        "correct":     g_correct,
        "wrong_type":  g_wrong_type,
        "missing":     g_missing,
        "wrong_split": g_wrong_split,
        "noise":       g_noise,
        "accuracy":    round(g_correct / g_expected * 100, 1) if g_expected else 0.0,
    }

    return {"docs": docs_result, "overall": overall}


def report_to_csv_string(report: Dict[str, Any]) -> str:
    """Serialise the report rows as CSV (in-memory string)."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "doc", "expected_title", "expected_kind",
        "extracted_title", "extracted_kind",
        "auto_status", "verdict", "note"
    ])
    for doc in report.get("docs", []):
        for row in doc["rows"]:
            writer.writerow([
                doc["doc"],
                row["expected_title"],
                row["expected_kind"],
                row.get("extracted_title") or "",
                row.get("extracted_kind") or "",
                row["status"],
                row["verdict"],
                row.get("note", ""),
            ])
    return output.getvalue()


def report_to_markdown_string(report: Dict[str, Any]) -> str:
    """Serialise the report as a Markdown document."""
    lines = ["# Evaluation Report\n"]

    o = report.get("overall", {})
    lines += [
        "## Overall Metrics\n",
        "| Expected | Extracted | Matched | Correct | Wrong Type | Missing | Wrong Split | Noise | Accuracy |",
        "|---|---|---|---|---|---|---|---|---|",
        (f"| {o.get('expected',0)} | {o.get('extracted',0)} | {o.get('matched',0)}"
         f" | {o.get('correct',0)} | {o.get('wrong_type',0)} | {o.get('missing',0)}"
         f" | {o.get('wrong_split',0)} | {o.get('noise',0)} | **{o.get('accuracy',0)}%** |"),
        "",
    ]

    STATUS_EMOJI = {
        "correct": "✅", "wrong_type": "❌", "missing": "⚠️",
        "wrong_split": "🔀", "noise": "🔊", "pending": "⏳",
    }

    for doc in report.get("docs", []):
        m = doc["metrics"]
        lines.append(f"\n## `{doc['doc']}`\n")
        lines.append(
            f"Expected: **{m['expected']}** · Extracted: **{m['extracted']}** · "
            f"Correct: **{m['correct']}** · Missing: **{m['missing']}** · "
            f"Wrong type: **{m['wrong_type']}** · Noise: **{m['noise']}**\n"
        )
        lines += [
            "| # | Exp Kind | Expected Title | Extracted Title | Ext Kind | Status | Verdict | Note |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for i, row in enumerate(doc["rows"], 1):
            s_emoji = STATUS_EMOJI.get(row["status"], row["status"])
            v_emoji = STATUS_EMOJI.get(row["verdict"], row["verdict"])
            lines.append(
                f"| {i} | `{row['expected_kind']}` | {row['expected_title']}"
                f" | {row.get('extracted_title') or '—'} | `{row.get('extracted_kind') or '—'}`"
                f" | {s_emoji} {row['status']} | {v_emoji} {row['verdict']}"
                f" | {row.get('note','') or ''} |"
            )

        if doc.get("noise_cards"):
            noise_list = ", ".join(
                f"`[{c['kind']}]` {c['title'] or '?'}"
                for c in doc["noise_cards"]
            )
            lines.append(f"\n**Noise ({len(doc['noise_cards'])}):** {noise_list}\n")

        lines.append("\n---\n")

    return "\n".join(lines)
