# Fixtures

Fixed input data for development, prompt tuning, and testing.

Set `USE_LIVE_DATA = False` in `config.py` to use fixtures.
Set `USE_LIVE_DATA = True` for real sessions and the Day 30 demo.

## Scenarios

| File | Scenario | Purpose |
|---|---|---|
| `normal_day.json` | Semiconductor chain green, VIX stable, no major signals | Baseline agent development |

## Adding new scenarios

Each fixture represents a deliberately constructed scenario.
Name files after the scenario, not after a date.

Planned fixtures for Day 15 prompt tuning:
- `vix_spike.json` — VIX above 25, equities mixed
- `chain_divergence.json` — AVGO up, NVDA and TSM down
- `black_swan_active.json` — geopolitical shock, VIX above 30