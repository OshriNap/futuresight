"""LLM-guided evolution advisor — uses local Ollama to propose targeted mutations.

Instead of blind Gaussian noise, the advisor analyzes fitness history and parameter
performance to suggest which parameters to mutate and in which direction.
Falls back gracefully to random mutation if Ollama is unavailable.

Two modes:
1. **Guided mutation** (qwen2.5-coder:7b via Ollama) — fast, per-candidate: "given these
   results, propose 3-5 parameter changes as JSON"
2. **Meta-analysis** (Claude Code scheduled task) — the backend exposes evolution state via
   GET /api/evolution/meta-analysis-context, a Claude Code task analyzes it with a strong
   cloud model, then POSTs guidance back via POST /api/evolution/meta-analysis-guidance
"""

import json
import logging

import httpx

from app.evolution.defaults import DEFAULT_GENOME, MUTATION_RANGES

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:7b"
TIMEOUT = 60  # seconds


async def _call_ollama(prompt: str, system: str = "") -> str | None:
    """Call local Ollama qwen2.5-coder and return the response text. Returns None on failure."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
    except Exception as e:
        logger.warning(f"Ollama call failed: {e}")
        return None


def _build_param_summary(genome_data: dict, fitness: float | None) -> str:
    """Build a compact summary of genome parameters grouped by tool."""
    groups: dict[str, list[str]] = {}
    for key, val in sorted(genome_data.items()):
        prefix = key.split(".")[0]
        default = DEFAULT_GENOME.get(key)
        delta = ""
        if default is not None and val != default:
            delta = f" (default={default}, delta={val - default:+.4f})"
        groups.setdefault(prefix, []).append(f"  {key} = {val}{delta}")

    lines = []
    for group, params in groups.items():
        lines.append(f"[{group}]")
        lines.extend(params)

    fitness_str = f"Brier score (fitness): {fitness:.4f}" if fitness is not None else "Fitness: not yet measured"
    return fitness_str + "\n\n" + "\n".join(lines)


def _build_history_summary(history: list[dict]) -> str:
    """Build a compact summary of recent evolution history."""
    if not history:
        return "No evolution history yet."

    lines = []
    for run in history[:10]:
        line = f"Gen {run['generation']}: "
        if run.get("champion_fitness") is not None:
            line += f"champion_brier={run['champion_fitness']:.4f}"
        line += f" created={run.get('candidates_created', 0)}"
        line += f" retired={run.get('candidates_retired', 0)}"
        line += f" promoted={run.get('candidates_promoted', 0)}"
        lines.append(line)

    return "\n".join(lines)


def _build_retired_summary(retired_genomes: list[dict]) -> str:
    """Summarize what mutations retired candidates tried (to avoid repeating failures)."""
    if not retired_genomes:
        return "No retired candidates yet."

    lines = []
    for g in retired_genomes[:5]:
        diffs = []
        data = g.get("genome_data", {})
        for key, val in data.items():
            default = DEFAULT_GENOME.get(key)
            if default is not None and val != default:
                diffs.append(f"{key}: {default}->{val}")
        if diffs:
            fitness_str = f"brier={g['fitness']:.4f}" if g.get("fitness") is not None else "unscored"
            lines.append(f"  Gen {g.get('generation', '?')} ({fitness_str}): {', '.join(diffs[:6])}")

    return "\n".join(lines) if lines else "No informative retired candidates."


GUIDED_MUTATION_SYSTEM = """You are an optimization advisor for a prediction system. You analyze parameter performance and suggest targeted mutations to improve prediction accuracy (lower Brier score = better).

Rules:
- Output ONLY valid JSON, no markdown fences, no explanation
- Suggest 3-5 parameter changes
- Each change: {"param": "param.name", "value": float, "reason": "brief reason"}
- Stay within allowed ranges
- Avoid repeating mutations that already failed (see retired candidates)
- Focus on parameters where you see the most room for improvement"""


async def propose_guided_mutations(
    champion_data: dict,
    champion_fitness: float | None,
    history: list[dict],
    retired_genomes: list[dict] | None = None,
) -> list[dict] | None:
    """Ask local Ollama qwen2.5-coder to propose targeted parameter mutations.

    Returns:
        List of {"param": str, "value": float, "reason": str} or None if unavailable
    """
    param_summary = _build_param_summary(champion_data, champion_fitness)
    history_summary = _build_history_summary(history)
    retired_summary = _build_retired_summary(retired_genomes or [])

    ranges_str = "\n".join(
        f"  {k}: min={v[0]}, max={v[1]}"
        for k, v in sorted(MUTATION_RANGES.items())
    )

    prompt = f"""Current champion genome:
{param_summary}

Evolution history (recent):
{history_summary}

Retired candidates (failed mutations to avoid):
{retired_summary}

Parameter ranges:
{ranges_str}

Propose 3-5 parameter changes to create a candidate that might beat the champion.
Output JSON array: [{{"param": "name", "value": number, "reason": "why"}}]"""

    response = await _call_ollama(prompt, system=GUIDED_MUTATION_SYSTEM)
    if not response:
        return None

    return _parse_mutations(response, champion_data)


def _parse_mutations(response: str, champion_data: dict) -> list[dict] | None:
    """Parse and validate LLM-proposed mutations."""
    text = response.strip()

    # Handle markdown code fences
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                text = part
                break

    try:
        mutations = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                mutations = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM mutations: {text[:200]}")
                return None
        else:
            logger.warning(f"No JSON array in LLM response: {text[:200]}")
            return None

    if not isinstance(mutations, list):
        return None

    valid = []
    for m in mutations:
        if not isinstance(m, dict):
            continue
        param = m.get("param", "")
        value = m.get("value")
        if param not in MUTATION_RANGES or value is None:
            continue
        try:
            value = float(value)
        except (ValueError, TypeError):
            continue

        min_val, max_val, _ = MUTATION_RANGES[param]
        value = max(min_val, min(max_val, value))

        if isinstance(DEFAULT_GENOME.get(param), int):
            value = int(round(value))
        else:
            value = round(value, 6)

        valid.append({
            "param": param,
            "value": value,
            "reason": str(m.get("reason", ""))[:200],
        })

    return valid if valid else None


def apply_guided_mutations(champion_data: dict, mutations: list[dict]) -> dict:
    """Apply LLM-proposed mutations to champion genome data.

    Returns new genome_data dict.
    """
    data = dict(champion_data)
    for m in mutations:
        param = m["param"]
        if param in data:
            data[param] = m["value"]
    return data


def build_meta_analysis_context(
    champion_data: dict,
    champion_fitness: float | None,
    all_genomes: list[dict],
    history: list[dict],
) -> dict:
    """Build context payload for Claude Code scheduled task to analyze.

    The backend doesn't call cloud LLMs directly — instead it prepares
    the data, and a Claude Code scheduled task fetches it via
    GET /api/evolution/meta-analysis-context, reasons about it, then
    POSTs guidance back via POST /api/evolution/meta-analysis-guidance.
    """
    param_summary = _build_param_summary(champion_data, champion_fitness)

    # Build genome lineage
    genome_lineage = []
    for g in all_genomes[:20]:
        diffs = {}
        data = g.get("genome_data", {})
        for key, val in data.items():
            default = DEFAULT_GENOME.get(key)
            if default is not None and abs(val - default) > 0.001:
                diffs[key] = round(val, 6)

        genome_lineage.append({
            "generation": g.get("generation"),
            "status": g.get("status"),
            "fitness": round(g["fitness"], 6) if g.get("fitness") is not None else None,
            "mutations_from_default": diffs,
        })

    return {
        "champion": {
            "fitness": round(champion_fitness, 6) if champion_fitness is not None else None,
            "genome_data": champion_data,
            "param_summary": param_summary,
        },
        "genome_lineage": genome_lineage,
        "evolution_history": history[:20],
        "mutation_ranges": {k: {"min": v[0], "max": v[1], "sigma": v[2]} for k, v in MUTATION_RANGES.items()},
        "defaults": DEFAULT_GENOME,
    }
