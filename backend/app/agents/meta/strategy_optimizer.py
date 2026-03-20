"""Strategy Optimizer Meta-Agent

Analyzes prediction calibration, tool performance, category accuracy,
and detects recurring patterns from scored predictions.
Writes findings to scratchpad and validated patterns to PredictionPattern table.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.agents.meta.base_meta import BaseMetaAgent
from app.database import async_session
from app.models.meta import PredictionPattern
from app.models.prediction import Prediction, PredictionScore
from app.models.source import Source

logger = logging.getLogger(__name__)


class StrategyOptimizer(BaseMetaAgent):
    agent_type = "strategy_optimizer"

    async def think(self) -> dict:
        """Analyze calibration, tool performance, and detect patterns."""
        actions = []
        scratchpad_entries = []

        async with async_session() as db:
            # 1. Overall stats
            total_preds = (await db.execute(select(func.count(Prediction.id)))).scalar() or 0
            scored_preds = (await db.execute(
                select(func.count(PredictionScore.id))
            )).scalar() or 0
            avg_brier = (await db.execute(
                select(func.avg(PredictionScore.brier_score))
            )).scalar()

            actions.append(f"Total predictions: {total_preds}, Scored: {scored_preds}, Avg Brier: {avg_brier}")

            # 2. Calibration analysis
            if scored_preds >= 5:
                result = await db.execute(
                    select(Prediction.confidence, Source.actual_outcome)
                    .join(Source, Prediction.source_id == Source.id)
                    .join(PredictionScore, PredictionScore.prediction_id == Prediction.id)
                    .where(Source.actual_outcome.isnot(None))
                )
                rows = result.all()

                bins = defaultdict(lambda: {"count": 0, "actual_yes": 0, "sum_conf": 0.0})
                for conf, outcome in rows:
                    bucket = round(conf * 10) / 10
                    bins[bucket]["count"] += 1
                    bins[bucket]["actual_yes"] += 1 if outcome == "yes" else 0
                    bins[bucket]["sum_conf"] += conf

                calibration_lines = []
                total_cal_error = 0.0
                for bucket in sorted(bins):
                    b = bins[bucket]
                    actual_rate = b["actual_yes"] / b["count"]
                    avg_conf = b["sum_conf"] / b["count"]
                    cal_error = abs(avg_conf - actual_rate)
                    total_cal_error += cal_error * b["count"]
                    calibration_lines.append(
                        f"  {bucket:.0%} bucket: {b['count']} preds, "
                        f"actual rate {actual_rate:.0%}, cal error {cal_error:.2f}"
                    )

                avg_cal_error = total_cal_error / len(rows) if rows else 0
                cal_text = "\n".join(calibration_lines)

                scratchpad_entries.append({
                    "title": "Calibration Analysis",
                    "content": f"Average calibration error: {avg_cal_error:.3f}\n\n{cal_text}",
                    "category": "analysis",
                    "priority": "high" if avg_cal_error > 0.15 else "medium",
                    "tags": ["calibration", "accuracy"],
                })
                actions.append(f"Calibration error: {avg_cal_error:.3f}")

            # 3. Per-tool performance from data_signals
            if scored_preds >= 3:
                result = await db.execute(
                    select(Prediction.data_signals, PredictionScore.brier_score)
                    .join(PredictionScore, PredictionScore.prediction_id == Prediction.id)
                )
                tool_scores = defaultdict(list)
                for signals, brier in result.all():
                    for tool in (signals or {}).get("tools_used", []):
                        tool_scores[tool].append(brier)

                if tool_scores:
                    tool_lines = []
                    for tool, scores in sorted(tool_scores.items(), key=lambda x: sum(x[1]) / len(x[1])):
                        avg = sum(scores) / len(scores)
                        tool_lines.append(f"  {tool}: Brier {avg:.3f} (n={len(scores)})")

                    scratchpad_entries.append({
                        "title": "Tool Performance Ranking",
                        "content": "\n".join(tool_lines),
                        "category": "analysis",
                        "priority": "medium",
                        "tags": ["tools", "performance"],
                    })
                    actions.append(f"Analyzed {len(tool_scores)} tools")

            # 4. Per-category performance
            if scored_preds >= 3:
                result = await db.execute(
                    select(Source.category, func.avg(PredictionScore.brier_score), func.count(PredictionScore.id))
                    .join(Prediction, Prediction.source_id == Source.id)
                    .join(PredictionScore, PredictionScore.prediction_id == Prediction.id)
                    .group_by(Source.category)
                )
                cat_lines = []
                for cat, avg_b, cnt in sorted(result.all(), key=lambda x: x[1] if x[1] else 1):
                    cat_lines.append(f"  {cat or 'unknown'}: Brier {avg_b:.3f} (n={cnt})")

                if cat_lines:
                    scratchpad_entries.append({
                        "title": "Category Performance",
                        "content": "\n".join(cat_lines),
                        "category": "analysis",
                        "priority": "medium",
                        "tags": ["categories", "performance"],
                    })

            # 5. Confidence distribution
            result = await db.execute(
                select(Prediction.confidence)
                .where(Prediction.confidence.isnot(None))
            )
            confidences = [c for (c,) in result.all() if c is not None]
            if confidences:
                avg_conf = sum(confidences) / len(confidences)
                high_conf = sum(1 for c in confidences if c > 0.8 or c < 0.2)
                mid_conf = sum(1 for c in confidences if 0.4 <= c <= 0.6)

                scratchpad_entries.append({
                    "title": "Confidence Distribution",
                    "content": (
                        f"Total predictions: {len(confidences)}\n"
                        f"Average confidence: {avg_conf:.2f}\n"
                        f"Extreme (>80% or <20%): {high_conf} ({high_conf/len(confidences):.0%})\n"
                        f"Uncertain (40-60%): {mid_conf} ({mid_conf/len(confidences):.0%})"
                    ),
                    "category": "analysis",
                    "priority": "low",
                    "tags": ["confidence", "distribution"],
                })
                actions.append(f"Confidence distribution: avg={avg_conf:.2f}, extreme={high_conf}, uncertain={mid_conf}")

            # 6. Pattern detection from scored predictions
            if scored_preds >= 5:
                patterns_found = await self._detect_patterns(db)
                actions.append(f"Pattern detection: {len(patterns_found)} patterns found/updated")

        summary = f"Strategy analysis: {scored_preds} scored predictions, {len(scratchpad_entries)} insights generated"
        return {
            "summary": summary,
            "actions": actions,
            "scratchpad_entries": scratchpad_entries,
        }

    @staticmethod
    async def _detect_patterns(db) -> list[str]:
        """Detect recurring patterns from scored predictions and save to PredictionPattern table.

        Patterns detected:
        1. Tool outperformance — tool X beats ensemble in category Y
        2. Sentiment divergence — large sentiment-market gap predicts correction
        3. Multi-market agreement — cross-platform consensus is more accurate
        4. Confidence calibration — systematic over/under confidence in categories
        5. Time horizon bias — short-term predictions are better/worse calibrated
        """
        patterns_found = []

        # Load all scored predictions with their signals
        result = await db.execute(
            select(Prediction, PredictionScore, Source)
            .join(PredictionScore, PredictionScore.prediction_id == Prediction.id)
            .join(Source, Prediction.source_id == Source.id)
            .where(Source.actual_outcome.isnot(None))
        )
        scored = result.all()
        if len(scored) < 5:
            return patterns_found

        # --- Pattern 1: Tool outperformance by category ---
        # For each tool, compute Brier score per category vs ensemble
        tool_cat_scores = defaultdict(lambda: defaultdict(list))
        ensemble_cat_scores = defaultdict(list)
        for pred, score, source in scored:
            cat = source.category or "general"
            ensemble_cat_scores[cat].append(score.brier_score)
            tool_outputs = (pred.data_signals or {}).get("tool_outputs", {})
            actual = 1.0 if source.actual_outcome == "yes" else 0.0
            for tool_name, tool_data in tool_outputs.items():
                tool_brier = (tool_data["probability"] - actual) ** 2
                tool_cat_scores[tool_name][cat].append(tool_brier)

        for tool_name, cat_scores in tool_cat_scores.items():
            for cat, scores in cat_scores.items():
                if len(scores) < 3:
                    continue
                tool_avg = sum(scores) / len(scores)
                ens_avg = sum(ensemble_cat_scores[cat]) / len(ensemble_cat_scores[cat])
                if tool_avg < ens_avg - 0.05:  # tool beats ensemble by 0.05+
                    pattern_name = f"tool_outperforms_{tool_name}_{cat}"
                    await _upsert_pattern(db,
                        name=pattern_name,
                        pattern_type="tool_interaction",
                        description=f"{tool_name} outperforms ensemble in {cat} (Brier {tool_avg:.3f} vs {ens_avg:.3f})",
                        condition={"tool": tool_name, "category": cat, "tool_brier": round(tool_avg, 4), "ensemble_brier": round(ens_avg, 4)},
                        times_seen=len(scores),
                        times_correct=sum(1 for s in scores if s < ens_avg),
                        category=cat,
                        discovered_by="strategy_optimizer",
                    )
                    patterns_found.append(pattern_name)

        # --- Pattern 2: Sentiment divergence predicts correction ---
        high_div_briers = []
        low_div_briers = []
        for pred, score, source in scored:
            signals = (pred.data_signals or {}).get("tool_outputs", {})
            market_prob = source.current_market_probability
            if market_prob is None:
                continue
            # Check if sentiment divergence tool was used
            sent_div = signals.get("sentiment_divergence", {})
            if sent_div:
                sent_prob = sent_div.get("probability", market_prob)
                divergence = abs(sent_prob - market_prob)
                if divergence > 0.15:
                    high_div_briers.append(score.brier_score)
                else:
                    low_div_briers.append(score.brier_score)

        if len(high_div_briers) >= 3 and len(low_div_briers) >= 3:
            high_avg = sum(high_div_briers) / len(high_div_briers)
            low_avg = sum(low_div_briers) / len(low_div_briers)
            if high_avg < low_avg:  # high divergence = better predictions (sentiment adds signal)
                await _upsert_pattern(db,
                    name="sentiment_divergence_signal",
                    pattern_type="signal_pattern",
                    description=f"High sentiment-market divergence (>15%) improves predictions (Brier {high_avg:.3f} vs {low_avg:.3f})",
                    condition={"type": "sentiment_divergence", "threshold": 0.15, "direction": "above"},
                    times_seen=len(high_div_briers) + len(low_div_briers),
                    times_correct=len(high_div_briers),
                    category=None,
                    discovered_by="strategy_optimizer",
                )
                patterns_found.append("sentiment_divergence_signal")

        # --- Pattern 3: Multi-market agreement improves accuracy ---
        multi_briers = []
        single_briers = []
        for pred, score, source in scored:
            tools = (pred.data_signals or {}).get("tools_used", [])
            if "multi_market_ensemble" in tools:
                multi_briers.append(score.brier_score)
            else:
                single_briers.append(score.brier_score)

        if len(multi_briers) >= 3 and len(single_briers) >= 3:
            multi_avg = sum(multi_briers) / len(multi_briers)
            single_avg = sum(single_briers) / len(single_briers)
            better = "multi" if multi_avg < single_avg else "single"
            await _upsert_pattern(db,
                name="multi_market_agreement",
                pattern_type="signal_pattern",
                description=f"Cross-platform agreement: multi-market Brier {multi_avg:.3f} vs single {single_avg:.3f} ({better} is better)",
                condition={"type": "multi_market", "multi_brier": round(multi_avg, 4), "single_brier": round(single_avg, 4)},
                times_seen=len(multi_briers) + len(single_briers),
                times_correct=len(multi_briers) if better == "multi" else len(single_briers),
                category=None,
                discovered_by="strategy_optimizer",
            )
            patterns_found.append("multi_market_agreement")

        # --- Pattern 4: Time horizon calibration bias ---
        horizon_scores = defaultdict(list)
        for pred, score, source in scored:
            horizon_scores[pred.time_horizon or "medium"].append(
                (pred.confidence, 1.0 if source.actual_outcome == "yes" else 0.0, score.brier_score)
            )

        for horizon, entries in horizon_scores.items():
            if len(entries) < 3:
                continue
            avg_conf = sum(e[0] for e in entries) / len(entries)
            avg_actual = sum(e[1] for e in entries) / len(entries)
            avg_brier = sum(e[2] for e in entries) / len(entries)
            bias = avg_conf - avg_actual  # positive = overconfident
            if abs(bias) > 0.1:
                direction = "overconfident" if bias > 0 else "underconfident"
                await _upsert_pattern(db,
                    name=f"calibration_bias_{horizon}",
                    pattern_type="calibration",
                    description=f"{horizon}-term predictions are {direction} by {abs(bias):.2f} (avg conf {avg_conf:.2f}, actual rate {avg_actual:.2f}, Brier {avg_brier:.3f})",
                    condition={"horizon": horizon, "bias": round(bias, 4), "direction": direction},
                    times_seen=len(entries),
                    times_correct=sum(1 for e in entries if abs(e[0] - e[1]) < 0.2),
                    category=None,
                    discovered_by="strategy_optimizer",
                )
                patterns_found.append(f"calibration_bias_{horizon}")

        # --- Pattern 5: Category-specific bias ---
        for cat, entries in ensemble_cat_scores.items():
            if len(entries) < 5:
                continue
            cat_avg = sum(entries) / len(entries)
            overall_avg = sum(s.brier_score for _, s, _ in scored) / len(scored)
            if cat_avg > overall_avg + 0.05:  # category is worse than average
                await _upsert_pattern(db,
                    name=f"weak_category_{cat}",
                    pattern_type="category_bias",
                    description=f"Category '{cat}' underperforms (Brier {cat_avg:.3f} vs overall {overall_avg:.3f})",
                    condition={"category": cat, "category_brier": round(cat_avg, 4), "overall_brier": round(overall_avg, 4)},
                    times_seen=len(entries),
                    times_correct=sum(1 for b in entries if b < 0.25),
                    category=cat,
                    discovered_by="strategy_optimizer",
                )
                patterns_found.append(f"weak_category_{cat}")

        await db.commit()
        return patterns_found


async def _upsert_pattern(db, *, name: str, pattern_type: str, description: str,
                          condition: dict, times_seen: int, times_correct: int,
                          category: str | None, discovered_by: str):
    """Create or update a prediction pattern."""
    existing = await db.execute(
        select(PredictionPattern).where(PredictionPattern.name == name)
    )
    pattern = existing.scalar_one_or_none()

    accuracy = times_correct / times_seen if times_seen > 0 else None
    now = datetime.now(timezone.utc)

    if pattern:
        pattern.description = description
        pattern.condition = condition
        pattern.times_seen = times_seen
        pattern.times_correct = times_correct
        pattern.accuracy = accuracy
        pattern.version += 1
        pattern.updated_at = now
        # Auto-validate patterns with enough data and good accuracy
        if times_seen >= 10 and accuracy and accuracy >= 0.6 and pattern.status == "candidate":
            pattern.status = "validated"
            pattern.validated_at = now
        elif times_seen >= 10 and accuracy and accuracy < 0.4:
            pattern.status = "rejected"
    else:
        pattern = PredictionPattern(
            name=name,
            pattern_type=pattern_type,
            description=description,
            condition=condition,
            times_seen=times_seen,
            times_correct=times_correct,
            accuracy=accuracy,
            status="candidate",
            discovered_by=discovered_by,
            category=category,
        )
        db.add(pattern)
