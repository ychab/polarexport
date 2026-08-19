# AccessLink vs the Polar account export

`polarexport night` pulls from the Polar AccessLink v3 API. Polar also offers a full account export
from flow.polar.com (`polar-user-data-export.zip`) — a much larger, much slower artifact (it can take
over a week to be delivered) that carries more than the API exposes. This is the boundary between the
two, not a list of bugs: AccessLink structurally cannot return some of this data, and this tool cannot
either.

It was written from an audit of a real account export (243 MB, 4 881 files, night-relevant history
from 2023-07-18 to 2026-08-05) against the local `data/` store on 2026-08-19.

## History

AccessLink v3 retains only the last 28 days of sleep, nightly-recharge and SleepWise data (v4 would
give 90 — still not history). The account export in the audit covered three years. `polarexport`
works around this by accumulating every fetched night in `data/` and never discarding it — run the
tool regularly and your local history grows even though Polar's API window never moves. But a night
that ages out of the 28-day window *before* it was ever fetched is gone for good; there is no way to
retrieve it later through AccessLink.

## Baselines

The account export ships per-user baselines Polar computes from months of history:
`sleepScoreBaseline`, `remScoreBaseline`, `n3ScoreBaseline`, `continuityScoreBaseline`,
`efficiencyScoreBaseline`, `groupSolidityScoreBaseline`, `longInterruptionsScoreBaseline`,
`groupRefreshScoreBaseline`, `sleepTimeAverageMinutes`, and on the Nightly Recharge side
`meanBaselineRri`, `sdBaselineRri`, `meanBaselineRmssd`, `sdBaselineRmssd`,
`meanBaselineRespirationInterval`, `sdBaselineRespirationInterval`.

AccessLink returns **none** of them. Without a baseline, a value like "83 ms RMSSD" or a "-5.4 ANS
charge" can only be read as a raw number — an agent has to derive its own baseline from the export's
own history window instead of asking Polar what normal looks like for this specific person.

## Sleep-score components

AccessLink's `sleep` payload gives 3 of roughly 10 sub-scores: `group_duration_score`,
`group_solidity_score`, `group_regeneration_score`. The account export adds `continuityScore`,
`efficiencyScore`, `remScore`, `n3Score`, `longInterruptionsScore`, `sleepTimeOwnTargetScore`,
`sleepTimeRecommendationScore`, and `scoreRate`.

## Interruption counts

AccessLink gives interruption *duration* only: `short_interruption_duration`,
`long_interruption_duration`. The account export also gives `totalCount`, `shortCount`, `longCount` —
36 interruptions packed into 34 minutes reads very differently from 5 interruptions in the same span,
and duration alone cannot distinguish the two.

## Sleep efficiency, span and type

`efficiencyPercent`, `sleepSpan`, `asleepDuration`, `sleepType` (e.g. `SLEEP_PLUS_STAGES`), and the
`feedback` code are account-export only. Efficiency is derivable from `sleep_start_time` /
`sleep_end_time` and the stage totals already in `nights.json`, so nothing is truly lost here — it
just is not handed over pre-computed.

## Hypnogram and skin-temperature resolution

AccessLink's hypnogram is minute-keyed with numeric stage codes; the account export is 30-second
state changes with named states (`NONREM2`, `NONREM3`, `REM`, `WAKE`). Skin temperature is similar:
AccessLink returns one nightly aggregate (`skin_temperature.celsius` / `.deviation` in `nights.json`),
while the account export carries roughly 100 samples per night at 5-minute spacing, plus
`sensorLocation` and skin-contact interval records that AccessLink does not expose at all.

## Per-cycle sleep detail

AccessLink gives `sleep_cycles` as a count. The account export has the full array of individual
cycles.

## PPI / beat-to-beat raw samples

The account export includes dozens of `ppi_samples_*` files (beat-to-beat interval data). There is no
AccessLink endpoint for this at all — Nightly Recharge's `beat_to_beat_avg` is the closest AccessLink
gets, and it is a nightly average, not the underlying samples.

## Out of scope

Scraping flow.polar.com or importing the account export are both explicitly out of scope for
`polarexport` — the tool's value is fetching *fresh* data in seconds rather than waiting on Polar's
export pipeline. An account-export importer is a legitimate idea but a separate one, worth its own
discussion before any code gets written.
