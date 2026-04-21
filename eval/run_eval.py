import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime

# Allow importing from project root
sys.path.insert(0, str(Path(__file__).parent.parent))
from services import analyze_with_groq

DOCS_DIR    = Path(__file__).parent / "docs"
EXPECTED_DIR = Path(__file__).parent / "expected"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


# ── helpers ──────────────────────────────────────────────────────────────────

def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower().strip()).strip("-")


def load_expected(doc_stem: str) -> list[dict]:
    path = EXPECTED_DIR / f"{doc_stem}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def best_match(expected_card: dict, extracted: list[dict]) -> dict | None:
    """Find the best matching extracted card for an expected card.

    Matching heuristic (in priority order):
      1. kind matches AND at least one key_term appears in title or body
      2. kind matches AND title similarity > 0.5 (Jaccard on words)
      3. at least two key_terms appear in body (regardless of kind)
    Returns None if nothing scores.
    """
    exp_title_words = set(slugify(expected_card["title"]).split("-"))
    exp_terms = {t.lower() for t in expected_card.get("key_terms", [])}

    best, best_score = None, 0

    for card in extracted:
        ext_body  = (card.get("body", "") or "").lower()
        ext_title = (card.get("title", "") or "").lower()
        combined  = ext_title + " " + ext_body

        # key-term hits in combined text
        term_hits = sum(1 for t in exp_terms if t.lower() in combined)

        # Jaccard on title words
        ext_words = set(slugify(ext_title).split("-"))
        union = exp_title_words | ext_words
        jaccard = len(exp_title_words & ext_words) / len(union) if union else 0

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


def evaluate_doc(doc_path: Path, expected: list[dict]) -> dict:
    """Run extraction on one document and compare against expected cards."""
    text = doc_path.read_text(encoding="utf-8")
    extracted, tokens = analyze_with_groq(text, target_lang="en")

    # Drop summary cards — they are auto-generated, not evaluated
    extracted_eval = [c for c in extracted if c.get("kind") != "summary"]

    rows = []
    matched_extracted_ids = set()

    for exp in expected:
        match = best_match(exp, extracted_eval)

        if match is None:
            rows.append({
                "expected_title": exp["title"],
                "expected_kind":  exp["kind"],
                "extracted_title": "—",
                "extracted_kind":  "—",
                "correct_type":    "❌",
                "missing":         "✅ MISSING",
                "wrong_split":     "—",
            })
            continue

        match_id = id(match)
        wrong_split = "✅ DUPLICATE" if match_id in matched_extracted_ids else "—"
        matched_extracted_ids.add(match_id)

        correct_type = "✅" if match.get("kind", "").lower() == exp["kind"].lower() else f"❌ got `{match.get('kind')}`"

        rows.append({
            "expected_title":  exp["title"],
            "expected_kind":   exp["kind"],
            "extracted_title": match.get("title", "?"),
            "extracted_kind":  match.get("kind", "?"),
            "correct_type":    correct_type,
            "missing":         "—",
            "wrong_split":     wrong_split,
        })

    # Noise cards: extracted cards that were never matched
    noise_cards = [c for c in extracted_eval if id(c) not in matched_extracted_ids]

    return {
        "doc": doc_path.stem,
        "rows": rows,
        "noise": noise_cards,
        "tokens_used": tokens,
        "total_expected": len(expected),
        "total_extracted": len(extracted_eval),
    }


# ── stats helpers ─────────────────────────────────────────────────────────────

def count_issues(result: dict) -> dict:
    missing    = sum(1 for r in result["rows"] if r["missing"] != "—")
    wrong_type = sum(1 for r in result["rows"] if r["correct_type"].startswith("❌"))
    wrong_split = sum(1 for r in result["rows"] if r["wrong_split"].startswith("✅ DUPLICATE"))
    noise      = len(result["noise"])
    correct    = sum(1 for r in result["rows"] if r["correct_type"] == "✅" and r["missing"] == "—")
    return {"correct": correct, "missing": missing, "wrong_type": wrong_type,
            "wrong_split": wrong_split, "noise": noise}


# ── markdown rendering ────────────────────────────────────────────────────────

def render_table(result: dict) -> str:
    lines = []
    lines.append(f"## Document: `{result['doc']}`\n")
    lines.append(f"- Expected cards: **{result['total_expected']}** | Extracted (non-summary): **{result['total_extracted']}** | Tokens used: `{result['tokens_used']}`\n")

    header = "| Expected Title | Expected Kind | Extracted Title | Extracted Kind | Correct type? | Missing? | Wrong split? |"
    sep    = "|---|---|---|---|---|---|---|"
    lines.append(header)
    lines.append(sep)

    for r in result["rows"]:
        lines.append(
            f"| {r['expected_title']} | `{r['expected_kind']}` "
            f"| {r['extracted_title']} | `{r['extracted_kind']}` "
            f"| {r['correct_type']} | {r['missing']} | {r['wrong_split']} |"
        )

    if result["noise"]:
        lines.append(f"\n**Noise cards ({len(result['noise'])}) — extracted but not in expected:**\n")
        for nc in result["noise"]:
            lines.append(f"- `[{nc.get('kind')}]` {nc.get('title', '?')}")

    issues = count_issues(result)
    lines.append(f"\n**Summary:** ✅ Correct: {issues['correct']} | ❌ Missing: {issues['missing']} | ❌ Wrong type: {issues['wrong_type']} | ⚠️ Duplicate split: {issues['wrong_split']} | 🔊 Noise: {issues['noise']}\n")

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    doc_files = sorted(DOCS_DIR.glob("*.md")) + sorted(DOCS_DIR.glob("*.txt"))

    if not doc_files:
        print("No documents found in eval/docs/")
        return

    report_lines = [
        "# Evaluation Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    all_correct = all_missing = all_wrong_type = all_wrong_split = all_noise = 0

    for doc_path in doc_files:
        expected_file = EXPECTED_DIR / f"{doc_path.stem}.json"
        if not expected_file.exists():
            print(f"[SKIP] No expected file for {doc_path.name}")
            continue

        print(f"[EVAL] Processing {doc_path.name} ...")
        expected = load_expected(doc_path.stem)
        result   = evaluate_doc(doc_path, expected)

        table_md = render_table(result)
        report_lines.append(table_md)
        report_lines.append("---\n")

        issues = count_issues(result)
        all_correct    += issues["correct"]
        all_missing    += issues["missing"]
        all_wrong_type += issues["wrong_type"]
        all_wrong_split += issues["wrong_split"]
        all_noise      += issues["noise"]

        print(f"  ✅ Correct: {issues['correct']}  ❌ Missing: {issues['missing']}  "
              f"❌ Wrong type: {issues['wrong_type']}  ⚠️  Dup split: {issues['wrong_split']}  "
              f"🔊 Noise: {issues['noise']}")

    report_lines.append("## Overall Summary\n")
    report_lines.append(f"| Metric | Count |")
    report_lines.append(f"|---|---|")
    report_lines.append(f"| ✅ Correctly extracted | {all_correct} |")
    report_lines.append(f"| ❌ Missing cards | {all_missing} |")
    report_lines.append(f"| ❌ Wrong card type | {all_wrong_type} |")
    report_lines.append(f"| ⚠️ Wrong split (duplicate) | {all_wrong_split} |")
    report_lines.append(f"| 🔊 Noise cards | {all_noise} |")

    out_path = RESULTS_DIR / "eval_report.md"
    out_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    main()
