import sys
import os

# Set console output encoding to UTF-8 to prevent Windows cp1252 encoding errors with Arabic text
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import argparse
import json
import time
from dotenv import load_dotenv

# Add project root to python path so we can import app.*
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.vector_store import VectorStoreManager
import google.generativeai as genai

# ─────────────────────────────────────────────────────────────
# Load environment variables
# ─────────────────────────────────────────────────────────────
load_dotenv()
gemini_key = os.getenv("GEMINI") or os.getenv("GEMINI_API_KEY")
if not gemini_key:
    print("Error: GEMINI key not found in environment or .env file.")
    sys.exit(1)

os.environ["GOOGLE_API_KEY"] = gemini_key
genai.configure(api_key=gemini_key)

# ─────────────────────────────────────────────────────────────
# STEP 1 — RAG PIPELINE
# ─────────────────────────────────────────────────────────────

def load_dataset(dataset_path: str):
    """Loads the evaluation dataset from JSON."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_rag_pipeline(vector_store: VectorStoreManager, question: str) -> dict:
    """Runs the exact production RAG pipeline logic for a single question."""
    results = vector_store.search(question, n_results=10)

    if not results['documents'] or not results['documents'][0]:
        return {
            "contexts": [],
            "answer": "لم أتمكن من العثور على أية تشريعات مرتبطة بسؤالك."
        }

    contexts = results['documents'][0]

    context_text = "\n\n".join([
        f"--- نص قانوني من تشريع: {meta.get('filename', 'Unknown')} ---\n{doc}"
        for doc, meta in zip(results['documents'][0], results['metadatas'][0])
    ])

    prompt = f"""
أنت مستشار قانوني فلسطيني ذكي ومحترف. 
الرجاء الإجابة على سؤال المستخدم بناءً **فقط** على النصوص القانونية التالية المستخرجة من التشريعات الرسمية:

النصوص القانونية:
{context_text}

سؤال المستخدم:
{question}

طريقة الإجابة الإلزامية:
1. أجب باللغة العربية الفصحى بشكل دقيق ومباشر.
2. اعتمد حصرياً على النصوص المرفقة، ولا تؤلف أي قوانين أو عقوبات من خارجها.
3. اُذكر اسم التشريع الذي اعتمدت عليه لتعزيز موثوقية جوابك إن أمكن.
4. رتب إجابتك في نقاط واضحة (Bullet points) لتسهيل القراءة.
5. أعطِ الإجابة مباشرة وفوراً، ولا تبدأ أبداً بعبارات مثل "بناءً على النصوص" أو "بصفتي مستشار" أو ختام بـ "هل تحتاج شيئاً آخر".
"""
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    answer = response.text if hasattr(response, "text") else ""

    return {"contexts": contexts, "answer": answer}


def run_rag_pipeline_with_retry(vector_store: VectorStoreManager, question: str, max_retries: int = 3) -> dict:
    """Wrapper with exponential backoff on transient failures."""
    for attempt in range(max_retries):
        try:
            return run_rag_pipeline(vector_store, question)
        except Exception as e:
            err_str = str(e)
            print(f"  ⚠ Attempt {attempt+1} failed: {err_str[:120]}")
            if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                wait = 60 * (attempt + 1)
                print(f"  ⏳ Rate-limit detected. Waiting {wait}s before retry...")
                time.sleep(wait)
            elif attempt < max_retries - 1:
                time.sleep(2 ** attempt + 1)
            else:
                raise e
    raise RuntimeError("Max retries exceeded")


def generate_answers_for_dataset(dataset: list, limit: int = 50) -> list:
    """
    Retrieves context and generates answers for each question.
    Hard-capped at `limit` questions (default=50) to avoid rate limits.
    """
    vector_store = VectorStoreManager()
    output_dataset = []

    subset = dataset[:limit]
    total = len(subset)

    print(f"\n{'='*60}")
    print(f"  RAG Answer Generation — {total} questions")
    print(f"{'='*60}\n")

    for i, item in enumerate(subset, 1):
        question = item["question"]
        ground_truth = item["ground_truth"]

        print(f"[{i:02d}/{total}] {question[:70]}...")

        start_time = time.time()
        try:
            rag_output = run_rag_pipeline_with_retry(vector_store, question)
            contexts = rag_output["contexts"]
            answer = rag_output["answer"]

            output_dataset.append({
                "question": question,
                "contexts": contexts,
                "answer": answer,
                "ground_truth": ground_truth
            })

            elapsed = time.time() - start_time
            print(f"  ✓ Done in {elapsed:.1f}s | Contexts: {len(contexts)}")

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            output_dataset.append({
                "question": question,
                "contexts": [],
                "answer": f"ERROR: {str(e)}",
                "ground_truth": ground_truth
            })

        if i < total:
            time.sleep(2.0)

    return output_dataset


# ─────────────────────────────────────────────────────────────
# STEP 2 — RAGAS EVALUATION
# ─────────────────────────────────────────────────────────────

def trim_contexts_for_ragas(
    contexts: list,
    top_k: int = 3,
    max_chars_per_chunk: int = 600
) -> list:
    """
    Reduces token usage during RAGAS evaluation by:
      1. Keeping only the top-k most relevant chunks.
      2. Truncating each chunk to max_chars_per_chunk characters.
    """
    trimmed = []
    for ctx in contexts[:top_k]:
        if len(ctx) > max_chars_per_chunk:
            cut = ctx[:max_chars_per_chunk]
            last_space = cut.rfind(' ')
            cut = cut[:last_space] + " ..." if last_space > max_chars_per_chunk // 2 else cut + " ..."
            trimmed.append(cut)
        else:
            trimmed.append(ctx)
    return trimmed


# ── Rate-limited LLM wrapper ──────────────────────────────────────────────────
# Free-tier gemini-2.5-flash: 5 req/min, 20 req/day.
# We throttle to ~4 req/min (one call per 15 s) to stay safely under the limit.

class _RateLimitedLLM:
    """
    Thin proxy around a RAGAS LLM that inserts a minimum gap between calls
    so we never exceed the free-tier quota of 5 req/min.

    Uses __getattr__ to transparently forward every attribute/method to the
    inner LLM, and only intercepts the generate* methods to add throttling.
    """
    def __init__(self, llm, min_gap: float = 15.0):
        # Store via object.__setattr__ to avoid triggering __getattr__ recursion
        object.__setattr__(self, "_llm",      llm)
        object.__setattr__(self, "_min_gap",  min_gap)
        object.__setattr__(self, "_last_ts",  0.0)

    def __getattr__(self, name):
        # Forward every unknown attribute to the inner LLM transparently
        return getattr(object.__getattribute__(self, "_llm"), name)

    def _throttle(self):
        last_ts  = object.__getattribute__(self, "_last_ts")
        min_gap  = object.__getattribute__(self, "_min_gap")
        elapsed  = time.time() - last_ts
        if elapsed < min_gap:
            wait = min_gap - elapsed
            print(f"  ⏳ Rate-limiter: sleeping {wait:.1f}s to respect 5 req/min quota...")
            time.sleep(wait)
        object.__setattr__(self, "_last_ts", time.time())

    def generate(self, *args, **kwargs):
        self._throttle()
        # InstructorLLM does not accept the `n` kwarg that RAGAS 0.4.x passes
        kwargs.pop("n", None)
        return object.__getattribute__(self, "_llm").generate(*args, **kwargs)

    async def agenerate(self, *args, **kwargs):
        self._throttle()
        kwargs.pop("n", None)
        return await object.__getattribute__(self, "_llm").agenerate(*args, **kwargs)

    def generate_text(self, *args, **kwargs):
        self._throttle()
        kwargs.pop("n", None)
        return object.__getattribute__(self, "_llm").generate_text(*args, **kwargs)

    async def agenerate_text(self, *args, **kwargs):
        self._throttle()
        kwargs.pop("n", None)
        return await object.__getattribute__(self, "_llm").agenerate_text(*args, **kwargs)


def run_ragas_evaluation(eval_data: list, gemini_key: str):
    print(f"\n{'='*60}")
    print(f"  RAGAS Evaluation — {len(eval_data)} items")
    print(f"{'='*60}\n")

    try:
        from ragas import EvaluationDataset, evaluate
        from ragas.metrics._faithfulness import Faithfulness
        from ragas.metrics._answer_relevance import AnswerRelevancy
        from ragas.metrics._context_recall import ContextRecall
        from ragas.metrics._answer_correctness import AnswerCorrectness
        from ragas.llms import llm_factory
        from ragas import RunConfig
        from google import genai as google_genai
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return None

    # ── Configure Gemini LLM ───────────────────────────────────
    google_client = google_genai.Client(api_key=gemini_key)

    _base_llm = llm_factory(
        model="gemini-2.5-flash",
        provider="google",
        client=google_client
    )

    # Wrap with rate-limiter: ≤4 LLM calls per minute (free tier = 5/min)
    evaluator_llm = _RateLimitedLLM(_base_llm, min_gap=15.0)

    # ── Configure embeddings ───────────────────────────────────
    # models/embedding-001 is supported on the free v1beta endpoint.
    # text-embedding-004 requires v1 (paid). Use embedding-001 to avoid 404.
    evaluator_embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=gemini_key
    )

    # ── Build dataset ──────────────────────────────────────────
    print("Converting dataset to RAGAS EvaluationDataset format...")
    print("  Trimming contexts: top 3 chunks, max 600 chars each")

    formatted_list = []
    total_ctx_chars_before = 0
    total_ctx_chars_after  = 0

    for d in eval_data:
        if d["answer"].startswith("ERROR:") and not d["contexts"]:
            print(f"  ⚠ Skipping errored item: {d['question'][:60]}...")
            continue

        raw_contexts = d["contexts"]
        trimmed_contexts = trim_contexts_for_ragas(raw_contexts, top_k=3, max_chars_per_chunk=600)

        total_ctx_chars_before += sum(len(c) for c in raw_contexts)
        total_ctx_chars_after  += sum(len(c) for c in trimmed_contexts)

        formatted_list.append({
            "user_input":         d["question"],
            "retrieved_contexts": trimmed_contexts,
            "response":           d["answer"],
            "reference":          d["ground_truth"],
        })

    if not formatted_list:
        print("✗ No valid items to evaluate.")
        return None

    saved_pct = (1 - total_ctx_chars_after / max(total_ctx_chars_before, 1)) * 100
    print(f"  Context chars: {total_ctx_chars_before:,} → {total_ctx_chars_after:,}  (saved {saved_pct:.0f}%)")
    print(f"  Evaluating {len(formatted_list)} valid items...")
    print(f"  ⚠ Free-tier mode: ~15 s gap between LLM calls to stay under 5 req/min quota.")
    print(f"  Estimated time: ~{len(formatted_list) * 4 * 15 // 60} minutes\n")

    eval_dataset = EvaluationDataset.from_list(formatted_list)

    # ── Metrics ────────────────────────────────────────────────
    faithfulness      = Faithfulness()
    answer_relevancy  = AnswerRelevancy()
    context_recall    = ContextRecall()
    answer_correctness = AnswerCorrectness()

    faithfulness.llm            = evaluator_llm
    answer_relevancy.llm        = evaluator_llm
    answer_relevancy.embeddings = evaluator_embeddings
    context_recall.llm          = evaluator_llm
    answer_correctness.llm      = evaluator_llm
    answer_correctness.embeddings = evaluator_embeddings

    metrics = [faithfulness, answer_relevancy, context_recall, answer_correctness]

    # ── RunConfig ──────────────────────────────────────────────
    # max_workers=1  → strictly sequential, no burst of parallel calls
    # max_retries=10 → retry on transient 429s (RAGAS will wait max_wait before each retry)
    # max_wait=180   → wait up to 3 min before each retry attempt
    # timeout=180    → generous per-call timeout
    run_config = RunConfig(
        max_workers=1,
        max_wait=180,
        timeout=180,
        max_retries=10,
        seed=42,
    )

    # ── Evaluate ───────────────────────────────────────────────
    print("Running RAGAS evaluation (sequential, rate-limited)...\n")
    results = evaluate(
        dataset=eval_dataset,
        metrics=metrics,
        run_config=run_config,
    )

    return results

# ─────────────────────────────────────────────────────────────
# STEP 3 — SAVE RESULTS
# ─────────────────────────────────────────────────────────────

def save_results(results, eval_data: list, output_dir: str = "."):
    """Saves JSON + Markdown reports."""
    if results is None:
        print("No results to save.")
        return

    # ── JSON report ───────────────────────────────────────────
    try:
        report_df = results.to_pandas()
        json_path = os.path.join(output_dir, "ragas_eval_report.json")
        report_df.to_json(json_path, orient="records", force_ascii=False, indent=2)
        print(f"\n✓ JSON report saved → {json_path}")
    except Exception as e:
        print(f"  ⚠ Could not save JSON: {e}")
        report_df = None

    # ── Markdown report ───────────────────────────────────────
    md_path = os.path.join(output_dir, "ragas_eval_report.md")
    try:
        with open(md_path, "w", encoding="utf-8") as md:
            md.write("# RAG Pipeline Evaluation Report\n\n")
            md.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            md.write(f"**Dataset size:** {len(eval_data)} questions evaluated\n\n")

            md.write("## Overall Average Scores\n\n")
            md.write("| Metric | Average Score |\n")
            md.write("| :--- | :---: |\n")

            scores = {}
            try:
                for metric_name, score in results.items():
                    scores[metric_name] = score
                    md.write(f"| {metric_name} | {score:.4f} |\n")
            except Exception:
                md.write("| (see JSON report) | — |\n")

            md.write("\n")
            md.write("## Metric Explanations\n\n")
            md.write("| Metric | What it measures |\n")
            md.write("| :--- | :--- |\n")
            md.write("| **Faithfulness** | Is the answer grounded only in the retrieved contexts? (no hallucinations) |\n")
            md.write("| **Answer Relevancy** | Does the generated answer directly address the question? |\n")
            md.write("| **Context Recall** | Do the retrieved contexts contain all parts of the ground truth? |\n")
            md.write("| **Answer Correctness** | Factual + semantic correctness vs. ground truth |\n")
            md.write("\n")

            if report_df is not None:
                md.write("## Per-Question Scores\n\n")
                cols = {
                    "faithfulness":       "Faithfulness",
                    "answer_relevancy":   "Relevancy",
                    "context_recall":     "Ctx Recall",
                    "answer_correctness": "Correctness",
                }
                existing = [c for c in cols if c in report_df.columns]
                header = "| # | Question | " + " | ".join(cols[c] for c in existing) + " |"
                sep    = "| :---: | :--- | " + " | ".join(":---:" for _ in existing) + " |"
                md.write(header + "\n")
                md.write(sep + "\n")
                for idx, row in report_df.iterrows():
                    q = (row.get('user_input', row.get('question', ''))[:60] + "...")
                    vals = " | ".join(
                        f"{row[c]:.3f}" if c in row and row[c] is not None else "N/A"
                        for c in existing
                    )
                    md.write(f"| {idx+1} | {q} | {vals} |\n")

        print(f"✓ Markdown report saved → {md_path}")

    except Exception as e:
        print(f"  ⚠ Could not save Markdown: {e}")

    # ── Print summary to console ──────────────────────────────
    print("\n" + "="*60)
    print("  EVALUATION RESULTS SUMMARY")
    print("="*60)
    try:
        for metric_name, score in results.items():
            bar_len = int(score * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
            print(f"  {metric_name:<25} {bar}  {score:.4f}")
    except Exception:
        print(results)
    print("="*60 + "\n")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate RAG pipeline using RAGAS + Gemini.\n\n"
                    "Modes:\n"
                    "  1) Full run (default):   generate answers → evaluate\n"
                    "  2) --eval-only:          load existing answers file → evaluate\n"
                    "  3) --generate-only:      generate answers only, save to file\n",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset",       type=str, default="rag_eval_dataset.json",
                        help="Path to evaluation dataset (question + ground_truth pairs).")
    parser.add_argument("--answers-file",  type=str, default="rag_eval_with_answers.json",
                        help="File to save/load RAG answers (with contexts).")
    parser.add_argument("--output-dir",    type=str, default=".",
                        help="Directory to write report files.")
    parser.add_argument("--limit",         type=int, default=50,
                        help="Max questions to process (default=50 to respect rate limits).")
    parser.add_argument("--eval-only",     action="store_true",
                        help="Skip RAG generation; load answers from --answers-file and evaluate.")
    parser.add_argument("--generate-only", action="store_true",
                        help="Only generate RAG answers; skip RAGAS evaluation.")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def resolve(p):
        return p if os.path.isabs(p) else os.path.join(base_dir, p)

    dataset_path  = resolve(args.dataset)
    answers_path  = resolve(args.answers_file)
    output_dir    = resolve(args.output_dir)

    # ── STEP 1: Load or Generate Answers ──────────────────────
    if args.eval_only:
        print(f"Loading existing answers from: {answers_path}")
        if not os.path.exists(answers_path):
            print(f"✗ File not found: {answers_path}")
            print("  Run without --eval-only first to generate answers.")
            sys.exit(1)
        with open(answers_path, "r", encoding="utf-8") as f:
            eval_data = json.load(f)
        eval_data = eval_data[:args.limit]
        print(f"  Loaded {len(eval_data)} items.")
    else:
        print(f"Loading dataset from: {dataset_path}")
        dataset = load_dataset(dataset_path)
        print(f"  Dataset contains {len(dataset)} questions.")
        print(f"  Processing first {args.limit} (--limit={args.limit}).\n")

        eval_data = generate_answers_for_dataset(dataset, limit=args.limit)

        os.makedirs(output_dir, exist_ok=True)
        with open(answers_path, "w", encoding="utf-8") as f:
            json.dump(eval_data, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Answers saved → {answers_path}")

    if args.generate_only:
        print("--generate-only flag set. Skipping RAGAS evaluation.")
        return

    # ── STEP 2: Run RAGAS Evaluation ──────────────────────────
    results = run_ragas_evaluation(eval_data, gemini_key)

    # ── STEP 3: Save Reports ───────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    save_results(results, eval_data, output_dir)


if __name__ == "__main__":
    main()