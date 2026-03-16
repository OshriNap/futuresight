"""Default genome parameters — all current hardcoded values extracted into one place.

Each parameter has a default value, min, max, and mutation sigma (std dev for Gaussian noise).
Tools read from genome_params with fallback to these defaults, so the system is
backwards-compatible: None genome = current behavior.
"""

# All tunable parameters with their current (default) values
DEFAULT_GENOME: dict = {
    # --- base_rate_tool ---
    "base_rate.weight": 0.15,
    "base_rate.politics_yes_rate": 0.42,
    "base_rate.politics_efficiency": 0.85,
    "base_rate.geopolitics_yes_rate": 0.38,
    "base_rate.geopolitics_efficiency": 0.80,
    "base_rate.technology_yes_rate": 0.35,
    "base_rate.technology_efficiency": 0.75,
    "base_rate.economy_yes_rate": 0.40,
    "base_rate.economy_efficiency": 0.82,
    "base_rate.finance_yes_rate": 0.45,
    "base_rate.finance_efficiency": 0.80,
    "base_rate.climate_yes_rate": 0.30,
    "base_rate.climate_efficiency": 0.70,
    "base_rate.health_yes_rate": 0.35,
    "base_rate.health_efficiency": 0.75,
    "base_rate.general_yes_rate": 0.40,
    "base_rate.general_efficiency": 0.80,

    # --- contrarian ---
    "contrarian.extreme_low": 0.60,       # (0.0, 0.05) range
    "contrarian.low": 0.75,               # (0.05, 0.15) range
    "contrarian.moderate_low": 0.90,      # (0.15, 0.30) range
    "contrarian.neutral": 1.00,           # (0.30, 0.70) range
    "contrarian.moderate_high": 0.90,     # (0.70, 0.85) range
    "contrarian.high": 0.75,             # (0.85, 0.95) range
    "contrarian.extreme_high": 0.60,      # (0.95, 1.0) range

    # --- llm_reasoner ---
    "llm.market_weight_base": 3.0,
    "llm.market_weight_time_scale": 2.0,
    "llm.multi_market_weight_base": 2.0,
    "llm.trend_adjustment": 0.3,
    "llm.sentiment_adjustment": 0.1,

    # --- nli_tool ---
    "nli.adjustment_scale": 0.15,
    "nli.headline_cap": 15,

    # --- historical_analogy ---
    "historical.blend_weight": 0.20,
    "historical.deadline_yes_rate": 0.35,
    "historical.country_action_yes_rate": 0.40,
    "historical.tech_milestone_yes_rate": 0.30,
    "historical.political_outcome_yes_rate": 0.45,
    "historical.crisis_yes_rate": 0.20,
    "historical.regulation_yes_rate": 0.30,
    "historical.price_target_yes_rate": 0.40,

    # --- sentiment_divergence ---
    "sentiment.divergence_threshold": 0.3,
    "sentiment.correction_factor": 0.04,

    # --- ensemble (tool_registry) ---
    "ensemble.extremize_max": 0.35,
    "ensemble.variance_divisor": 0.06,
    "ensemble.category_bonus": 0.2,
    "ensemble.performance_weight": 0.3,

    # --- extrapolation ---
    "extrapolation.ses_alpha": 0.3,
    "extrapolation.holt_alpha": 0.3,
    "extrapolation.holt_beta": 0.1,
    "extrapolation.ma_window": 5,
    "extrapolation.reversion_speed": 0.3,

    # --- graph_context ---
    "graph.causes_mult": 1.0,
    "graph.amplifies_mult": 0.7,
    "graph.correlates_mult": 0.5,
    "graph.precedes_mult": 0.3,
    "graph.mitigates_mult": -0.7,
    "graph.resolved_scale": 0.1,
    "graph.unresolved_scale": 0.05,
}


# Mutation ranges: (min, max, sigma) for each parameter
# sigma is the standard deviation for Gaussian mutation
MUTATION_RANGES: dict[str, tuple[float, float, float]] = {
    # base_rate
    "base_rate.weight": (0.05, 0.40, 0.03),
    "base_rate.politics_yes_rate": (0.20, 0.65, 0.04),
    "base_rate.politics_efficiency": (0.50, 0.98, 0.05),
    "base_rate.geopolitics_yes_rate": (0.20, 0.60, 0.04),
    "base_rate.geopolitics_efficiency": (0.50, 0.95, 0.05),
    "base_rate.technology_yes_rate": (0.15, 0.55, 0.04),
    "base_rate.technology_efficiency": (0.45, 0.95, 0.05),
    "base_rate.economy_yes_rate": (0.20, 0.60, 0.04),
    "base_rate.economy_efficiency": (0.50, 0.95, 0.05),
    "base_rate.finance_yes_rate": (0.25, 0.65, 0.04),
    "base_rate.finance_efficiency": (0.50, 0.95, 0.05),
    "base_rate.climate_yes_rate": (0.10, 0.50, 0.04),
    "base_rate.climate_efficiency": (0.40, 0.90, 0.05),
    "base_rate.health_yes_rate": (0.15, 0.55, 0.04),
    "base_rate.health_efficiency": (0.45, 0.95, 0.05),
    "base_rate.general_yes_rate": (0.20, 0.60, 0.04),
    "base_rate.general_efficiency": (0.50, 0.95, 0.05),

    # contrarian
    "contrarian.extreme_low": (0.30, 0.85, 0.06),
    "contrarian.low": (0.50, 0.95, 0.05),
    "contrarian.moderate_low": (0.75, 1.0, 0.03),
    "contrarian.neutral": (0.95, 1.05, 0.01),
    "contrarian.moderate_high": (0.75, 1.0, 0.03),
    "contrarian.high": (0.50, 0.95, 0.05),
    "contrarian.extreme_high": (0.30, 0.85, 0.06),

    # llm_reasoner
    "llm.market_weight_base": (1.0, 6.0, 0.4),
    "llm.market_weight_time_scale": (0.5, 4.0, 0.3),
    "llm.multi_market_weight_base": (0.5, 4.0, 0.3),
    "llm.trend_adjustment": (0.05, 0.6, 0.05),
    "llm.sentiment_adjustment": (0.02, 0.25, 0.03),

    # nli
    "nli.adjustment_scale": (0.05, 0.30, 0.03),
    "nli.headline_cap": (5, 30, 3),

    # historical_analogy
    "historical.blend_weight": (0.05, 0.45, 0.04),
    "historical.deadline_yes_rate": (0.15, 0.55, 0.04),
    "historical.country_action_yes_rate": (0.20, 0.60, 0.04),
    "historical.tech_milestone_yes_rate": (0.10, 0.50, 0.04),
    "historical.political_outcome_yes_rate": (0.25, 0.65, 0.04),
    "historical.crisis_yes_rate": (0.05, 0.40, 0.04),
    "historical.regulation_yes_rate": (0.10, 0.50, 0.04),
    "historical.price_target_yes_rate": (0.20, 0.60, 0.04),

    # sentiment_divergence
    "sentiment.divergence_threshold": (0.10, 0.60, 0.05),
    "sentiment.correction_factor": (0.01, 0.10, 0.01),

    # ensemble
    "ensemble.extremize_max": (0.10, 0.60, 0.05),
    "ensemble.variance_divisor": (0.02, 0.15, 0.02),
    "ensemble.category_bonus": (0.05, 0.40, 0.04),
    "ensemble.performance_weight": (0.10, 0.50, 0.04),

    # extrapolation
    "extrapolation.ses_alpha": (0.05, 0.70, 0.05),
    "extrapolation.holt_alpha": (0.05, 0.70, 0.05),
    "extrapolation.holt_beta": (0.01, 0.40, 0.03),
    "extrapolation.ma_window": (2, 15, 2),
    "extrapolation.reversion_speed": (0.05, 0.70, 0.05),

    # graph_context
    "graph.causes_mult": (0.5, 1.5, 0.1),
    "graph.amplifies_mult": (0.3, 1.2, 0.08),
    "graph.correlates_mult": (0.1, 0.9, 0.08),
    "graph.precedes_mult": (0.05, 0.7, 0.06),
    "graph.mitigates_mult": (-1.2, -0.3, 0.08),
    "graph.resolved_scale": (0.03, 0.25, 0.03),
    "graph.unresolved_scale": (0.01, 0.15, 0.02),
}


# Default NLI reframing strategies with weights
DEFAULT_REFRAMES: dict = {
    "baseline": {
        "template": "This suggests that: {question}",
        "weight": 1.0,
    },
    "duplicate": {
        "template": "{question}. {question}",
        "weight": 0.0,  # Disabled by default, evolution can enable
    },
    "elaborate": {
        "template": "{question} In other words, will {question_short}?",
        "weight": 0.0,
    },
    "negate_check": {
        "template": "This contradicts: {question}",
        "weight": 0.0,
    },
    "category_context": {
        "template": "In {category}: {question}",
        "weight": 0.0,
    },
}
