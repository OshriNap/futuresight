"""LLM Reasoning Tool

Provides signal-weighted heuristic predictions as a real-time fallback.
LLM-powered reasoning is handled by Claude Code scheduled tasks (free with subscription).
This tool provides a heuristic for real-time predictions that can't wait for a scheduled run.
"""

import logging

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


class LLMReasonerTool(BasePredictionTool):
    name = "llm_reasoning"
    tool_type = "llm_reasoning"
    description = "Signal-weighted heuristic reasoning. LLM thinking handled by Claude Code scheduled tasks."
    best_for = ["geopolitical", "tech", "social", "complex"]

    async def predict(self, input: ToolInput) -> ToolOutput:
        return self._predict_heuristic(input)

    def _predict_heuristic(self, input: ToolInput) -> ToolOutput:
        """Heuristic reasoning using weighted combination of available signals."""
        params = input.genome_params or {}
        signals = input.current_signals
        probability = 0.5
        total_weight = 0.0
        reasoning_parts = []
        signals_used = []

        # Signal 1: Market probability (strongest signal)
        # Weight increases with time_decay (market is more reliable near resolution)
        if "market_probability" in signals:
            market_p = signals["market_probability"]
            time_decay = signals.get("time_decay", 0.5)
            base_w = params.get("llm.market_weight_base", 3.0)
            time_scale = params.get("llm.market_weight_time_scale", 2.0)
            w = base_w + time_decay * time_scale
            probability = (probability * total_weight + market_p * w) / (total_weight + w)
            total_weight += w
            reasoning_parts.append(f"market={market_p:.1%}")
            signals_used.append("market_probability")

        # Signal 2: Multi-market agreement
        if "market_probabilities" in signals:
            probs = list(signals["market_probabilities"].values())
            if probs:
                avg = sum(probs) / len(probs)
                spread = max(probs) - min(probs) if len(probs) > 1 else 0
                mm_base = params.get("llm.multi_market_weight_base", 2.0)
                agreement_w = mm_base * (1 - spread)  # Weight by agreement
                probability = (probability * total_weight + avg * agreement_w) / (total_weight + agreement_w)
                total_weight += agreement_w
                reasoning_parts.append(f"multi_market_avg={avg:.1%} (spread={spread:.1%})")
                signals_used.append("market_probabilities")

        # Signal 3: Trend direction
        if "probability_history" in signals:
            history = signals["probability_history"]
            if len(history) >= 3:
                recent = [h["probability"] for h in history[-5:]]
                trend = recent[-1] - recent[0]
                # Slight adjustment in trend direction
                trend_adj = params.get("llm.trend_adjustment", 0.3)
                adjustment = trend * trend_adj
                probability += adjustment
                reasoning_parts.append(f"trend={'up' if trend > 0 else 'down'} ({trend:+.2f})")
                signals_used.append("probability_history")

        # Signal 4: News sentiment
        if "news_sentiment" in signals:
            sentiment = signals["news_sentiment"]  # -1 to 1
            sent_adj = params.get("llm.sentiment_adjustment", 0.1)
            adjustment = sentiment * sent_adj
            probability += adjustment
            reasoning_parts.append(f"sentiment={sentiment:+.2f}")
            signals_used.append("news_sentiment")

        # Clamp
        probability = max(0.05, min(0.95, probability))

        # Confidence based on signal count
        confidence = min(0.6, 0.15 + len(signals_used) * 0.1)

        return ToolOutput(
            probability=probability,
            confidence=confidence,
            reasoning=f"Heuristic reasoning (no LLM): {', '.join(reasoning_parts) or 'no signals available'}",
            signals_used=signals_used,
            metadata={"mode": "heuristic"},
        )

    def get_required_signals(self) -> list[str]:
        return []  # Can work with any signals
