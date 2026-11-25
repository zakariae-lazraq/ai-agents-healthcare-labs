# Data dictionary — Lab 3 teaching cohort (synthetic)

| Variable | Unit | Training range | Impossible (blocked) |
|---|---|---|---|
| age | years | 30–79 | < 0 or > 120 |
| sex | male / female | — | other values |
| systolic_bp | mmHg | 90–200 | < 50 or > 300 |
| cholesterol (total) | mg/dL | 120–400 | < 50 or > 1000; 1.5–15 looks like mmol/L |
| max_heart_rate | bpm | 70–205 | < 30 or > 250 |
| smoker | yes / no | — | — |
| diabetes | yes / no | — | — |
| event_10y | 0 / 1 | outcome | — |
