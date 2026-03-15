---
name: analyze-sentiment
description: Run batch sentiment analysis on collected sources using local RTX 2060 GPU. Use when user wants to score news/reddit sources with sentiment, check GPU status, or analyze sentiment trends.
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, WebFetch
argument-hint: "[platform|stats|install-deps] [--force] [--limit N]"
---

# Batch Sentiment Analysis (Local GPU)

Run sentiment analysis on collected sources using the local RTX 2060 SUPER (8GB VRAM) with
`cardiffnlp/twitter-roberta-base-sentiment-latest` via HuggingFace transformers.

## Arguments

Parse `$ARGUMENTS` for these modes:

| Argument | Action |
|----------|--------|
| *(empty)* | Run sentiment on all unscored sources |
| `gdelt` / `reddit` / `polymarket` | Run on specific platform only |
| `stats` | Show sentiment score distribution and coverage |
| `install-deps` | Install torch + transformers into the backend venv |
| `--force` | Re-analyze sources that already have scores |
| `--limit N` | Max sources to process (default 500) |

## Step-by-step

### 1. Pre-flight checks

Before running analysis, verify the environment:

```bash
# Check GPU is available
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null
```

If GPU is not detected, warn the user and ask if they want to proceed on CPU (much slower).

```bash
# Check dependencies are installed
cd /home/oshrin/projects/future_prediction/backend && python -c "import torch; import transformers; print(f'torch={torch.__version__}, cuda={torch.cuda.is_available()}, transformers={transformers.__version__}')" 2>&1
```

If imports fail, tell the user to run `/analyze-sentiment install-deps` first.

### 2. Handle `install-deps` mode

If the user passed `install-deps`:

```bash
cd /home/oshrin/projects/future_prediction/backend
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install transformers
```

Then verify:
```bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}')"
```

Stop here after install — do not run analysis.

### 3. Handle `stats` mode

If the user passed `stats`, query the database directly:

```bash
cd /home/oshrin/projects/future_prediction/backend
python -c "
import asyncio, json
from sqlalchemy import select, func
from app.database import async_session
from app.models.source import Source

async def stats():
    async with async_session() as db:
        # Total sources
        total = (await db.execute(select(func.count(Source.id)))).scalar()

        # Sources with sentiment
        result = await db.execute(select(Source).limit(5000))
        sources = result.scalars().all()

        with_sentiment = 0
        sentiments = {'positive': 0, 'negative': 0, 'neutral': 0}
        scores = []
        by_platform = {}

        for s in sources:
            raw = s.raw_data or {}
            plat = s.platform
            if plat not in by_platform:
                by_platform[plat] = {'total': 0, 'scored': 0}
            by_platform[plat]['total'] += 1

            if 'sentiment' in raw:
                with_sentiment += 1
                by_platform[plat]['scored'] += 1
                scores.append(raw['sentiment'])
                label = raw.get('sentiment_label', 'neutral')
                sentiments[label] = sentiments.get(label, 0) + 1

        print(f'Total sources: {total}')
        print(f'With sentiment: {with_sentiment} ({with_sentiment/max(total,1)*100:.1f}%)')
        print(f'Without sentiment: {total - with_sentiment}')
        print()
        print('By platform:')
        for p, c in sorted(by_platform.items()):
            print(f'  {p}: {c[\"scored\"]}/{c[\"total\"]} scored')
        print()
        print('Label distribution:')
        for label, count in sorted(sentiments.items()):
            print(f'  {label}: {count}')
        if scores:
            print()
            avg = sum(scores) / len(scores)
            print(f'Avg sentiment: {avg:+.3f}')
            print(f'Range: [{min(scores):+.3f}, {max(scores):+.3f}]')

asyncio.run(stats())
"
```

Stop here after showing stats.

### 4. Run batch analysis

For the main analysis mode, call the API endpoint:

```bash
# Determine parameters from arguments
# platform: gdelt, reddit, or empty for all
# force: true if --force was passed
# limit: number if --limit N was passed
curl -s -X POST "http://localhost:8000/api/meta/analyze-sentiment?platform=${PLATFORM}&force=${FORCE}" | python -m json.tool
```

If the API is not running, fall back to running the task directly:

```bash
cd /home/oshrin/projects/future_prediction/backend
python -c "
import asyncio
from app.tasks.sentiment_tasks import analyze_sentiment
result = asyncio.run(analyze_sentiment(platform=${PLATFORM_OR_NONE}, batch_size=32, limit=${LIMIT}, force=${FORCE}))
print(result)
"
```

### 5. Post-analysis summary

After analysis completes, run the `stats` query (step 3) to show the updated sentiment coverage. Highlight:
- How many new sources were scored
- GPU vs CPU was used
- Any errors or warnings
