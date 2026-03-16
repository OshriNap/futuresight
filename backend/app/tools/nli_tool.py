"""NLI (Natural Language Inference) prediction tool.

Uses cross-encoder/nli-distilroberta-base (~250MB VRAM) to score whether
news headlines entail or contradict a prediction question. Adjusts the
market probability based on aggregated NLI evidence.
"""

import asyncio
import logging

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)

# Lazy-loaded model
_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        import torch
        from transformers import pipeline

        device = 0 if torch.cuda.is_available() else -1
        logger.info(f"Loading NLI model on {'GPU' if device == 0 else 'CPU'}...")
        _pipeline = pipeline(
            "zero-shot-classification",
            model="cross-encoder/nli-distilroberta-base",
            device=device,
        )
        logger.info("NLI model loaded.")
    return _pipeline


def _run_nli(question: str, headlines: list[str]) -> list[dict]:
    """Run NLI inference: does each headline support or contradict the question?"""
    pipe = _get_pipeline()
    results = []

    hypothesis_yes = f"This suggests that: {question}"

    for headline in headlines[:15]:  # cap to avoid GPU OOM
        try:
            output = pipe(
                headline,
                candidate_labels=["entailment", "contradiction", "neutral"],
                hypothesis_template="{}",
            )
            # output: {labels: [...], scores: [...]}
            label_scores = dict(zip(output["labels"], output["scores"]))
            results.append({
                "headline": headline,
                "entailment": label_scores.get("entailment", 0),
                "contradiction": label_scores.get("contradiction", 0),
                "neutral": label_scores.get("neutral", 0),
            })
        except Exception as e:
            logger.warning(f"NLI failed for headline: {e}")

    return results


class NLITool(BasePredictionTool):
    name = "nli_evidence"
    tool_type = "ml_classifier"
    description = "Uses NLI model to score whether news evidence supports or contradicts a prediction."
    best_for = ["technology", "geopolitics", "economy", "politics"]

    async def predict(self, input: ToolInput) -> ToolOutput:
        params = input.genome_params or {}
        market_prob = input.current_signals.get("market_probability", 0.5)

        # Get matched headlines from embedding matching
        matched_sources = input.current_signals.get("matched_sources", [])
        headlines = [m["title"] for m in matched_sources if m.get("title")]

        headline_cap = int(params.get("nli.headline_cap", 15))
        headlines = headlines[:headline_cap]

        if not headlines:
            return ToolOutput(
                probability=market_prob,
                confidence=0.1,
                reasoning="No matched news headlines for NLI analysis",
                signals_used=["market_probability"],
            )

        # Run NLI on GPU in thread
        nli_results = await asyncio.to_thread(_run_nli, input.question, headlines)

        if not nli_results:
            return ToolOutput(
                probability=market_prob,
                confidence=0.15,
                reasoning="NLI analysis produced no results",
                signals_used=["market_probability"],
            )

        # Aggregate: net evidence score
        # entailment pushes toward YES (higher prob), contradiction toward NO
        total_support = 0.0
        total_contradict = 0.0
        for r in nli_results:
            total_support += r["entailment"]
            total_contradict += r["contradiction"]

        n = len(nli_results)
        avg_support = total_support / n
        avg_contradict = total_contradict / n
        net_evidence = avg_support - avg_contradict  # [-1, 1]

        # Adjust market probability by evidence
        adjustment_scale = params.get("nli.adjustment_scale", 0.15)
        adjustment = net_evidence * adjustment_scale
        adjusted_prob = max(0.02, min(0.98, market_prob + adjustment))

        confidence = min(0.6, 0.2 + n * 0.03)

        direction = "supports" if net_evidence > 0.05 else "contradicts" if net_evidence < -0.05 else "neutral"
        reasoning = (
            f"NLI analysis of {n} headlines: "
            f"avg_support={avg_support:.2f}, avg_contradict={avg_contradict:.2f}, "
            f"net={net_evidence:+.2f} ({direction}). "
            f"Adjusted {market_prob:.1%} → {adjusted_prob:.1%}"
        )

        return ToolOutput(
            probability=adjusted_prob,
            confidence=confidence,
            reasoning=reasoning,
            signals_used=["market_probability", "matched_sources"],
            metadata={
                "nli_results_count": n,
                "avg_support": round(avg_support, 3),
                "avg_contradict": round(avg_contradict, 3),
                "net_evidence": round(net_evidence, 3),
                "adjustment": round(adjustment, 4),
            },
        )

    def get_required_signals(self) -> list[str]:
        return ["market_probability"]

    def can_handle(self, input: ToolInput) -> tuple[bool, str]:
        # Need market probability AND matched sources
        if "market_probability" not in input.current_signals:
            return False, "Missing market_probability"
        matched = input.current_signals.get("matched_sources", [])
        if not matched:
            return False, "No matched news sources for NLI"
        return True, "ok"
