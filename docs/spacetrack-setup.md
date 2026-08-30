# Enabling the historical-element-set experiments

Two results need element sets as they existed in the past, which only
[Space-Track.org](https://www.space-track.org/) provides for recent years.
CelesTrak serves current elements only, and its historical archive stops at
2004-12-31 by law (US PL 108-136 Sec. 913).

## 1. Get a free account

Register at <https://www.space-track.org/auth/createAccount>. Approval is
usually immediate.

## 2. Provide the credentials

Either export them for the session:

```bash
export SPACETRACK_USER='you@example.com'
export SPACETRACK_PASS='your-password'
```

On Windows PowerShell:

```powershell
$env:SPACETRACK_USER = 'you@example.com'
$env:SPACETRACK_PASS = 'your-password'
```

Or create a file named `.spacetrack` in the project root:

```
user=you@example.com
pass=your-password
```

`.spacetrack` is git-ignored. Credentials are never written to any result file,
log, or figure.

## 3. Run the two experiments

```bash
# Element-set ageing: how prediction degrades with epoch age
python experiments/exp8_tle_age.py --objects 60 --days 60

# Retrospective evaluation with epoch-correct elements, removing the
# back-propagation error rather than arguing it is common-mode
python experiments/exp4_weather_value.py --days 60 --limit 300 \
    --historical-tle --tag _histtle

python experiments/make_tables.py
python experiments/make_figures.py
cd paper && tectonic -X compile skypass.tex
```

Both scripts degrade gracefully: without credentials `exp8` records a skip and
`exp4 --historical-tle` warns and falls back to back-propagated elements, so the
paper still builds.

## Rate limits

Space-Track asks for fewer than 30 requests/minute and 300/hour, and asks that
queries be batched rather than looped per object. `skypass/spacetrack.py`
enforces a 2.5 s minimum interval, batches all objects into single queries, and
caches every response under `cache/spacetrack/`, so re-runs cost no requests.
