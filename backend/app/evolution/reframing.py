"""Question reframing strategies for NLI evidence scoring.

Inspired by Google's finding that duplicating/rephrasing queries improves RAG retrieval.
Each strategy reformulates the prediction question before feeding it to the NLI model.
Strategies have weights (0-1) that are evolved via mutation.
"""


def apply_reframes(
    question: str,
    category: str | None,
    strategies: dict | None,
) -> list[tuple[str, str]]:
    """Apply reframing strategies to a question.

    Args:
        question: The prediction question
        category: Prediction category (for category_context strategy)
        strategies: Reframe config dict {name: {template, weight}}

    Returns:
        List of (strategy_name, reframed_text) for strategies with weight > 0
    """
    if not strategies:
        return [("baseline", f"This suggests that: {question}")]

    results = []
    # Short version for elaborate strategy
    question_short = question.rstrip("?").split(",")[0] if question else question

    for name, config in strategies.items():
        weight = config.get("weight", 0.0)
        if weight <= 0.0:
            continue

        template = config.get("template", "{question}")
        try:
            text = template.format(
                question=question,
                question_short=question_short,
                category=category or "general",
            )
        except (KeyError, IndexError):
            text = question

        results.append((name, text))

    # Always include at least baseline
    if not results:
        results.append(("baseline", f"This suggests that: {question}"))

    return results


def combine_results(
    results_per_strategy: dict[str, dict],
    strategies: dict | None,
    mode: str = "weighted_avg",
) -> dict:
    """Combine NLI results from multiple reframing strategies.

    Args:
        results_per_strategy: {strategy_name: {entailment, contradiction, neutral}}
        strategies: Reframe config with weights
        mode: "weighted_avg", "best_of", or "max_confidence"

    Returns:
        Combined {entailment, contradiction, neutral} scores
    """
    if not results_per_strategy:
        return {"entailment": 0.0, "contradiction": 0.0, "neutral": 1.0}

    if mode == "best_of":
        # Use the strategy with highest entailment - contradiction
        best_name = max(
            results_per_strategy,
            key=lambda k: results_per_strategy[k].get("entailment", 0)
            - results_per_strategy[k].get("contradiction", 0),
        )
        return results_per_strategy[best_name]

    if mode == "max_confidence":
        # Use strategy with highest max(entailment, contradiction) — most decisive
        best_name = max(
            results_per_strategy,
            key=lambda k: max(
                results_per_strategy[k].get("entailment", 0),
                results_per_strategy[k].get("contradiction", 0),
            ),
        )
        return results_per_strategy[best_name]

    # Default: weighted_avg
    strategies = strategies or {}
    total_weight = 0.0
    combined = {"entailment": 0.0, "contradiction": 0.0, "neutral": 0.0}

    for name, scores in results_per_strategy.items():
        weight = strategies.get(name, {}).get("weight", 1.0)
        if weight <= 0:
            weight = 0.1  # small floor to include all results
        total_weight += weight
        for key in combined:
            combined[key] += scores.get(key, 0.0) * weight

    if total_weight > 0:
        for key in combined:
            combined[key] /= total_weight

    return combined
