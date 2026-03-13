"""LLM Reasoning Tool

Uses Claude to reason about predictions given all available context.
The most flexible tool - can handle any category.

MODES:
1. API mode: Uses Anthropic API directly (costs money)
2. Heuristic mode: Falls back to signal-weighted heuristics when no API key
3. Claude Code mode: Meta-agents run via Claude Code scheduled tasks (free with subscription)

The system prefers Claude Code mode via scheduled tasks for LLM reasoning.
This tool provides a fallback for real-time predictions that can't wait for a scheduled run.
"""

import logging

from app.config import settings
from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


class LLMReasonerTool(BasePredictionTool):
    name = "llm_reasoning"
    tool_type = "llm_reasoning"
    description = "Uses Claude for reasoning (API) or signal-weighted heuristics (free fallback)."
    best_for = ["geopolitical", "tech", "social", "complex"]

    async def predict(self, input: ToolInput) -> ToolOutput:
        # Try API first if configured
        if settings.anthropic_api_key:
            result = await self._predict_with_api(input)
            if result.confidence > 0.1:  # API call succeeded
                return result

        # Fallback: signal-weighted heuristic reasoning
        return self._predict_heuristic(input)

    def _predict_heuristic(self, input: ToolInput) -> ToolOutput:
        """Heuristic reasoning when no LLM is available.

        Uses a weighted combination of available signals to generate
        a prediction without needing an API call.
        """
        signals = input.current_signals
        probability = 0.5
        total_weight = 0.0
        reasoning_parts = []
        signals_used = []

        # Signal 1: Market probability (strongest signal)
        if "market_probability" in signals:
            market_p = signals["market_probability"]
            w = 3.0
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
                agreement_w = 2.0 * (1 - spread)  # Weight by agreement
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
                adjustment = trend * 0.3
                probability += adjustment
                reasoning_parts.append(f"trend={'up' if trend > 0 else 'down'} ({trend:+.2f})")
                signals_used.append("probability_history")

        # Signal 4: News sentiment
        if "news_sentiment" in signals:
            sentiment = signals["news_sentiment"]  # -1 to 1
            adjustment = sentiment * 0.1
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

    async def _predict_with_api(self, input: ToolInput) -> ToolOutput:
        """Use Anthropic API for reasoning."""
        try:
            import anthropic

            context_parts = [f"Question: {input.question}", f"Category: {input.category}", f"Time horizon: {input.time_horizon}"]

            if "market_probability" in input.current_signals:
                context_parts.append(f"Current market probability: {input.current_signals['market_probability']:.1%}")
            if "market_probabilities" in input.current_signals:
                for market, prob in input.current_signals["market_probabilities"].items():
                    context_parts.append(f"  {market}: {prob:.1%}")
            if "news_summary" in input.current_signals:
                context_parts.append(f"Recent news: {input.current_signals['news_summary']}")
            if "probability_history" in input.current_signals:
                history = input.current_signals["probability_history"]
                if history:
                    context_parts.append(f"Probability trend: {history[0]['probability']:.1%} → {history[-1]['probability']:.1%}")
            if "related_events" in input.current_signals:
                context_parts.append(f"Related events: {input.current_signals['related_events']}")

            if input.historical_data:
                correct = sum(1 for h in input.historical_data if h.get("was_correct"))
                total = len(input.historical_data)
                if total > 0:
                    context_parts.append(f"Historical accuracy: {correct}/{total} ({correct/total:.0%})")

            context = "\n".join(context_parts)

            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                system="You are a calibrated forecaster. Provide:\nPROBABILITY: 0.XX\nCONFIDENCE: 0.XX\nREASONING: ...",
                messages=[{"role": "user", "content": f"Predict:\n\n{context}"}],
            )

            text = response.content[0].text
            probability, confidence, reasoning = 0.5, 0.5, text

            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("PROBABILITY:"):
                    try: probability = float(line.split(":")[1].strip())
                    except ValueError: pass
                elif line.startswith("CONFIDENCE:"):
                    try: confidence = float(line.split(":")[1].strip())
                    except ValueError: pass
                elif line.startswith("REASONING:"):
                    reasoning = line.split(":", 1)[1].strip()

            return ToolOutput(
                probability=max(0.01, min(0.99, probability)),
                confidence=max(0.1, min(0.95, confidence)),
                reasoning=reasoning,
                signals_used=list(input.current_signals.keys()),
                metadata={"mode": "api", "model": "claude-sonnet-4-20250514"},
            )

        except Exception as e:
            logger.warning(f"LLM API call failed, falling back to heuristic: {e}")
            return ToolOutput(probability=0.5, confidence=0.1, reasoning=str(e), signals_used=[])

    def get_required_signals(self) -> list[str]:
        return []  # Can work with any signals
