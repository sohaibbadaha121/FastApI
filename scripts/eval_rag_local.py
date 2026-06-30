"""
eval_rag_local.py
─────────────────────────────────────────────────────────────────────────────
Local RAG Evaluation — No API Key Required
─────────────────────────────────────────────────────────────────────────────

Metrics computed entirely on-device (no external API calls):

  Faithfulness      — Token overlap: what % of answer tokens appear in contexts
  Context Recall    — ROUGE-L(F1) between ground_truth and retrieved contexts
                      (pre-tokenized with Arabic-aware tokenizer)
  Answer Correctness— BERTScore F1 using xlm-roberta-base (Arabic-aware)
  Answer Relevancy  — Token overlap: what % of question tokens appear in answer

Usage
-----
  python scripts/eval_rag_local.py --eval-only --answers-file rag_eval_with_answers.json
  python scripts/eval_rag_local.py --eval-only --limit 5
  python scripts/eval_rag_local.py --eval-only --output-dir results/

Requirements (install once)
---------------------------
  pip install rouge-score bert-score
"""

import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import argparse
import json
import re
import time


# ─────────────────────────────────────────────────────────────
# Lazy imports with helpful error messages
# ─────────────────────────────────────────────────────────────

def _require(package, pip_name=None):
    import importlib
    try:
        return importlib.import_module(package)
    except ImportError:
        pip_name = pip_name or package.replace("_", "-")
        print(f"\n✗ Missing package: '{package}'")
        print(f"  Install it with:  pip install {pip_name}\n")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────
# Arabic-aware tokeniser
# ─────────────────────────────────────────────────────────────

_ARABIC_STOPWORDS = {
    "في", "من", "إلى", "على", "عن", "مع", "هذا", "هذه", "ذلك", "التي",
    "الذي", "أن", "إن", "كان", "كانت", "قد", "لا", "ما", "لم", "له",
    "لها", "بها", "به", "وفق", "وفقا", "بما", "كل", "أي", "هو", "هي",
    "هم", "نحن", "أنت", "و", "أو", "ثم", "حتى", "عند", "بعد", "قبل",
    "بين", "خلال", "حول", "ضد", "فوق", "تحت", "منذ", "لدى", "إذ",
    "حيث", "كما", "لكن", "بل", "غير", "سوى", "نحو", "مثل", "عبر",
}


def _tokenize(text):
    """Arabic-aware tokenizer: strips diacritics, splits on punctuation/whitespace,
    removes stopwords and single-character tokens."""
    # Strip Arabic diacritics (tashkeel)
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    tokens = re.split(
        r"[\s\u060C\u061B\u061F\u0021-\u002F\u003A-\u0040"
        r"\u005B-\u0060\u007B-\u007E]+",
        text,
    )
    tokens = [t.strip() for t in tokens if t.strip()]
    return [t for t in tokens if len(t) > 1 and t not in _ARABIC_STOPWORDS]


def _token_set(text):
    return set(_tokenize(text))


def _tokenize_for_rouge(text):
    """Return a space-joined pre-tokenized string suitable for rouge_score,
    bypassing its internal (English-only) tokenizer."""
    return " ".join(_tokenize(text))


# ─────────────────────────────────────────────────────────────
# Metric 1 — Faithfulness (token precision)
# ─────────────────────────────────────────────────────────────

def compute_faithfulness(answer, contexts):
    """
    Faithfulness = |answer_tokens ∩ context_tokens| / |answer_tokens|

    Score 1.0 = every answer token appears in the context (fully grounded).
    Lower    = potential hallucination.
    """
    if not answer or not contexts:
        return float("nan")
    answer_tokens = _token_set(answer)
    context_tokens = _token_set(" ".join(contexts))
    if not answer_tokens:
        return float("nan")
    return len(answer_tokens & context_tokens) / len(answer_tokens)


# ─────────────────────────────────────────────────────────────
# Metric 2 — Context Recall (ROUGE-L, Arabic-aware)
# ─────────────────────────────────────────────────────────────

def compute_context_recall(ground_truth, contexts, scorer=None):
    """
    Context Recall = |ground_truth_tokens ∩ context_tokens| / |ground_truth_tokens|
    Measures what fraction of the ground truth's key terms appear in retrieved contexts.
    """
    if not ground_truth or not contexts:
        return float("nan")
    gt_tokens = _token_set(ground_truth)
    ctx_tokens = _token_set(" ".join(contexts))
    if not gt_tokens:
        return float("nan")
    return len(gt_tokens & ctx_tokens) / len(gt_tokens)


# ─────────────────────────────────────────────────────────────
# Metric 3 — Answer Relevancy (token overlap)
# ─────────────────────────────────────────────────────────────

def compute_answer_relevancy(question, answer):
    """
    Answer Relevancy = |question_tokens ∩ answer_tokens| / |question_tokens|

    Measures what fraction of the question's key terms are addressed in
    the answer.

    WHY token overlap instead of ROUGE-L?
      ROUGE-L between a question and its answer is inherently near-zero
      because questions ask *about* something while answers *explain* it —
      they naturally use different vocabulary.  Token overlap on key terms
      (after stopword removal) is a better proxy for topical relevance in
      Arabic RAG evaluation.
    """
    if not question or not answer:
        return float("nan")
    q_tokens = _token_set(question)
    a_tokens = _token_set(answer)
    if not q_tokens:
        return float("nan")
    return len(q_tokens & a_tokens) / len(q_tokens)


# ─────────────────────────────────────────────────────────────
# Metric 4 — Answer Correctness (BERTScore F1)
# ─────────────────────────────────────────────────────────────

def compute_answer_correctness_batch(answers, ground_truths, model_type="xlm-roberta-base", device=None):
    """
    BERTScore F1 between generated answers and ground truths.
    Uses xlm-roberta-base which supports Arabic and 100+ languages.
    Runs in batch (much faster than per-sample).
    """
    bert_score_module = _require("bert_score", pip_name="bert-score")

    valid_indices = [
        i for i, (a, g) in enumerate(zip(answers, ground_truths)) if a and g
    ]
    if not valid_indices:
        return [float("nan")] * len(answers)

    valid_answers = [answers[i]       for i in valid_indices]
    valid_gts     = [ground_truths[i] for i in valid_indices]

    try:
        print(f"\n  Computing BERTScore for {len(valid_answers)} samples "
              f"(model: {model_type})")
        print("  First run downloads ~1 GB model, then it is cached locally.\n")
        _, _, F1 = bert_score_module.score(
            cands=valid_answers,
            refs=valid_gts,
            model_type=model_type,
            lang="ar",
            verbose=True,
            device=device,
        )
        f1_list = F1.tolist()
    except Exception as e:
        print(f"  ⚠ BERTScore failed: {e}")
        return [float("nan")] * len(answers)

    results = [float("nan")] * len(answers)
    for rank, orig_i in enumerate(valid_indices):
        results[orig_i] = f1_list[rank]
    return results


# ─────────────────────────────────────────────────────────────
# Main evaluation loop
# ─────────────────────────────────────────────────────────────

def run_local_evaluation(eval_data, bert_model="xlm-roberta-base"):
    # Must import the submodule explicitly
    from rouge_score import rouge_scorer as _rouge_scorer
    scorer = _rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)

    print(f"\n{'='*60}")
    print(f"  Local RAG Evaluation — {len(eval_data)} items")
    print(f"  Metrics: Faithfulness | Context Recall | Relevancy | Correctness")
    print(f"{'='*60}\n")

    per_item = []
    for i, d in enumerate(eval_data, 1):
        question     = d.get("question", "")
        answer       = d.get("answer", "")
        contexts     = d.get("contexts", [])
        ground_truth = d.get("ground_truth", "")

        faith   = compute_faithfulness(answer, contexts)
        ctx_rec = compute_context_recall(ground_truth, contexts, scorer)
        ans_rel = compute_answer_relevancy(question, answer)   # ← fixed

        per_item.append({
            "question":           question,
            "answer":             answer,
            "ground_truth":       ground_truth,
            "contexts_count":     len(contexts),
            "faithfulness":       faith,
            "context_recall":     ctx_rec,
            "answer_relevancy":   ans_rel,
            "answer_correctness": float("nan"),
        })

        def fmt(v):
            return f"{v:.3f}" if v == v else " nan"

        print(
            f"  [{i:02d}/{len(eval_data)}] "
            f"Faith={fmt(faith)}  CtxRecall={fmt(ctx_rec)}  "
            f"Relevancy={fmt(ans_rel)}"
            f"  |  {question[:50]}..."
        )

    # BERTScore (batch)
    answers       = [d["answer"]       for d in per_item]
    ground_truths = [d["ground_truth"] for d in per_item]
    bert_scores   = compute_answer_correctness_batch(
        answers, ground_truths, model_type=bert_model
    )
    for item, bs in zip(per_item, bert_scores):
        item["answer_correctness"] = bs

    return per_item


# ─────────────────────────────────────────────────────────────
# Save results
# ─────────────────────────────────────────────────────────────

LABEL_MAP = {
    "faithfulness":       "Faithfulness (token grounding)",
    "context_recall":     "Context Recall (ROUGE-L, Arabic-aware)",
    "answer_relevancy":   "Answer Relevancy (token overlap)",
    "answer_correctness": "Answer Correctness (BERTScore F1)",
}
METRICS = list(LABEL_MAP.keys())


def _fmt(v):
    try:
        return f"{v:.4f}" if v == v else "nan"
    except Exception:
        return "nan"


def save_results(results, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    # Averages (ignore nan)
    averages = {}
    for m in METRICS:
        vals = [r[m] for r in results if r[m] == r[m]]
        averages[m] = sum(vals) / len(vals) if vals else float("nan")

    # ── JSON ──────────────────────────────────────────────────
    json_path = os.path.join(output_dir, "local_eval_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "metadata": {
                    "date":         time.strftime("%Y-%m-%d %H:%M:%S"),
                    "dataset_size": len(results),
                    "method": (
                        "local — ROUGE-L (Arabic pre-tokenized) + "
                        "token-overlap relevancy + BERTScore (xlm-roberta-base), "
                        "no API key"
                    ),
                },
                "averages":     averages,
                "per_question": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\n✓ JSON report saved  → {json_path}")

    # ── Markdown ──────────────────────────────────────────────
    md_path = os.path.join(output_dir, "local_eval_report.md")
    with open(md_path, "w", encoding="utf-8") as md:
        md.write("# RAG Pipeline — Local Evaluation Report\n\n")
        md.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
        md.write(f"**Dataset size:** {len(results)} questions  \n")
        md.write(
            "**Method:** Fully local — ROUGE-L (Arabic pre-tokenized) + "
            "token-overlap relevancy + BERTScore (xlm-roberta-base), "
            "no API key required\n\n---\n\n"
        )

        md.write("## Overall Average Scores\n\n")
        md.write("| Metric | Average Score |\n| :--- | :---: |\n")
        for m in METRICS:
            md.write(f"| {LABEL_MAP[m]} | {_fmt(averages[m])} |\n")

        md.write("\n---\n\n## Metric Explanations\n\n")
        md.write("| Metric | Method | What it measures |\n| :--- | :--- | :--- |\n")
        md.write(
            "| **Faithfulness** | Token overlap (answer ∩ context) "
            "| Is the answer grounded in retrieved passages? |\n"
        )
        md.write(
            "| **Context Recall** | ROUGE-L with Arabic pre-tokenization "
            "(ground_truth vs contexts) "
            "| Did the retriever find the right passages? |\n"
        )
        md.write(
            "| **Answer Relevancy** | Token overlap (question ∩ answer) "
            "| Does the answer address the question's key terms? |\n"
        )
        md.write(
            "| **Answer Correctness** | BERTScore F1 (answer vs ground_truth) "
            "| Is the answer semantically correct? |\n"
        )

        md.write("\n---\n\n## Per-Question Scores\n\n")
        md.write(
            "| # | Question | Faith. | Ctx Recall | Relevancy | Correctness |\n"
        )
        md.write("| :---: | :--- | :---: | :---: | :---: | :---: |\n")
        for i, r in enumerate(results, 1):
            q = r["question"][:60] + "..."
            md.write(
                f"| {i} | {q} | {_fmt(r['faithfulness'])} "
                f"| {_fmt(r['context_recall'])} "
                f"| {_fmt(r['answer_relevancy'])} "
                f"| {_fmt(r['answer_correctness'])} |\n"
            )

    print(f"✓ Markdown report saved → {md_path}")

    # ── Console bar chart ──────────────────────────────────────
    print(f"\n{'='*60}\n  EVALUATION RESULTS SUMMARY\n{'='*60}")
    bar_w = 28
    for m in METRICS:
        v = averages[m]
        if v == v:
            bar = "█" * int(v * bar_w) + "░" * (bar_w - int(v * bar_w))
            print(f"  {LABEL_MAP[m]:<46} {bar}  {v:.4f}")
        else:
            print(f"  {LABEL_MAP[m]:<46} {'—' * bar_w}  nan")
    print(f"{'='*60}\n")


# ─────────────────────────────────────────────────────────────
# Dependency check
# ─────────────────────────────────────────────────────────────

def check_dependencies():
    missing = []
    try:
        import rouge_score  # noqa
    except ImportError:
        missing.append("rouge-score")
    try:
        import bert_score   # noqa
    except ImportError:
        missing.append("bert-score")

    if missing:
        print("\n" + "=" * 60)
        print("  Missing dependencies — install with:")
        print("=" * 60)
        for pkg in missing:
            print(f"    pip install {pkg}")
        print("=" * 60 + "\n")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Local RAG evaluation — Arabic-aware ROUGE-L + token-overlap "
            "relevancy + BERTScore, no API key needed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--answers-file", type=str, default="rag_eval_with_answers.json",
        help="JSON file with RAG answers (question/contexts/answer/ground_truth).",
    )
    parser.add_argument(
        "--output-dir", type=str, default=".",
        help="Directory for output reports (default: project root).",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Evaluate only first N questions (0 = all).",
    )
    parser.add_argument(
        "--bert-model", type=str, default="xlm-roberta-base",
        help="HuggingFace model for BERTScore (default: xlm-roberta-base).",
    )
    parser.add_argument(
        "--eval-only", action="store_true",
        help="(compatibility flag, ignored)",
    )
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def resolve(p):
        return p if os.path.isabs(p) else os.path.join(base_dir, p)

    answers_path = resolve(args.answers_file)
    output_dir   = resolve(args.output_dir)

    check_dependencies()

    if not os.path.exists(answers_path):
        print(f"✗ File not found: {answers_path}")
        sys.exit(1)

    with open(answers_path, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    if args.limit > 0:
        eval_data = eval_data[: args.limit]

    print(f"Loaded {len(eval_data)} items from: {answers_path}")

    t0      = time.time()
    results = run_local_evaluation(eval_data, bert_model=args.bert_model)
    elapsed = time.time() - t0
    print(f"\n  Evaluation completed in {elapsed:.1f}s")

    save_results(results, output_dir)


if __name__ == "__main__":
    main()