/* Measured results, transcribed from paper/generated/numbers.tex.
 *
 * These are findings, not live state: they came from experiment runs over
 * fixed archived inputs and do not change when the planner runs. Every value
 * here has a macro of the same meaning in the paper, so the interface and the
 * publication cannot disagree. Update this file only when the experiments are
 * re-run and numbers.tex changes.
 */

export const WEATHER = {
  /** Clear-sky yield gain under a tight across-night budget (\TightGainClear). */
  budgetGain: 55.0,
  /** Same planner constrained to a fixed nightly quota (\QuotaGainEV). */
  quotaGain: -1.5,
  /** Clear-sky share of observations, weather-blind (\BudgetBlindClearRate). */
  blindClearRate: 13.9,
  /** Clear-sky share under the tight budget (\TightClearRate). */
  clearRate: 28.1,
  /** Cloud varies this much more between nights than within one (\BtwWthRatio). */
  betweenWithinRatio: 2.2,
  /** Pass quality varies this much within a night (\BaseSkew). */
  passSkew: 1.8,
} as const;

export const PROPAGATION = {
  /** Fewer SGP4 calls than dense stepping (\CallReduction). */
  reduction: 23.7,
  naiveCalls: 54_864_000,     // \CallsDense
  fastCalls: 2_311_148,       // \CallsFast
  recall: 99.78,              // \Recall
  missed: 4,                  // \Missed
  /** Mean culmination agreement with Skyfield, seconds (\SkyfieldTca). */
  meanError: 0.055,
  worstError: 0.293,          // \SkyfieldTcaMax
  catalogue: 635,             // \NCatalogue
  passes: 1801,               // \NPasses
} as const;

export const SCHEDULER = {
  exactDp: 100.0,             // \DPOptimalPct
  greedyValue: 99.95,         // \GreedyValuePct
  greedyElevation: 95.39,     // \GreedyElevPct
  greedyElevationWorst: 9.4,  // \GreedyElevMin
  genetic: 99.67,             // \GAPct
  geneticCost: 38_922,        // \GASlowdown
  trials: 2000,               // \SchedTrials
  /** 100,000 intervals scheduled in this many ms (\DPBigMs / \DPBigN). */
  bigN: 100_000,
  bigMs: 285.3,
} as const;

/** Heidke skill of the cloud forecast by lead time in days (exp3, Table). */
export const FORECAST = {
  skillByLead: [0.378, 0.347, 0.289, 0.289, 0.191, 0.145, 0.176, 0.114],
  persistence: 0.206,         // \HssPersistence
  day1: 0.347,                // \HssOne
  day3: 0.289,                // \HssThree
  day7: 0.114,                // \HssSeven
} as const;

export const TLE_AGE = {
  fresh: 0.05,                // \AgeDayOne  (< 1 day)
  week: 4.3,                  // \AgeWeek
  fortnight: 16.2,            // \AgeFortnight
  month: 75.3,                // \AgeMonth
  comparisons: 33_223,        // \AgeComparisons
  objects: 60,                // \AgeObjects
} as const;

export const ELEMENTS = {
  meanError: 0.55,            // \EpochMean
  medianError: 0.42,          // \EpochMedian
  underOneSecond: 90.2,       // \EpochUnderOne
  p90: 0.95,                  // \EpochPninety
  worst: 13.04,               // \EpochMax
} as const;

export const SCALE = {
  objects: 635,               // \ScaleObjects
  days: 7,                    // \ScaleDays
  passes: 12_438,             // \ScalePasses
  seconds: 104.4,             // \ScaleSeconds
  scheduleMs: 2.1,            // \ScaleSchedMs
} as const;

/** How many nights ahead the forecast still beats naive persistence. */
export const confidentDays = (): number =>
  FORECAST.skillByLead.filter((s) => s > FORECAST.persistence).length - 1;

export interface Experiment {
  id: string;
  title: string;
  method: string;
  findings: [string, string][];
}

/** The experiment index, in the order the paper reports them. */
export const EXPERIMENTS: Experiment[] = [
  {
    id: '01',
    title: 'Pass extraction',
    method: 'Adaptive horizon-crossing detection against dense reference stepping',
    findings: [['Recall', `${PROPAGATION.recall}%`],
               ['Propagator calls', `${PROPAGATION.reduction}× fewer`]],
  },
  {
    id: '02',
    title: 'Element-set error',
    method: 'Historical epoch validation against independent element sets',
    findings: [['Mean error', `${ELEMENTS.meanError} s`],
               ['Under one second', `${ELEMENTS.underOneSecond}%`]],
  },
  {
    id: '03',
    title: 'Forecast skill',
    method: 'Cloud forecast verified against ERA5 reanalysis, 60 days, 7 sites',
    findings: [['Heidke skill', `${FORECAST.day1} → ${FORECAST.day7}`],
               ['Beats persistence to', `day ${confidentDays()}`]],
  },
  {
    id: '04',
    title: 'Weather value',
    method: 'Retrospective scheduling with and without the forecast',
    findings: [['Across-night budget', `+${WEATHER.budgetGain}%`],
               ['Fixed nightly quota', `${WEATHER.quotaGain}%`]],
  },
  {
    id: '05',
    title: 'Conflict resolution',
    method: 'Exact dynamic programming against exhaustive search and baselines',
    findings: [['Optimal', `${SCHEDULER.trials.toLocaleString()}/${SCHEDULER.trials.toLocaleString()} instances`],
               ['Genetic algorithm', `${SCHEDULER.genetic}% at ${SCHEDULER.geneticCost.toLocaleString()}× cost`]],
  },
  {
    id: '06',
    title: 'End-to-end pipeline',
    method: 'Full catalogue propagated, scored, scheduled and exported',
    findings: [['Catalogue', `${SCALE.objects} objects, ${SCALE.days} days`],
               ['Runtime', `${SCALE.seconds} s`]],
  },
  {
    id: '07',
    title: 'Cloud structure',
    method: 'Variance decomposition of the cloud field within and between nights',
    findings: [['Between vs within night', `${WEATHER.betweenWithinRatio}×`],
               ['Pass-quality spread', `${WEATHER.passSkew}×`]],
  },
  {
    id: '08',
    title: 'Element-set ageing',
    method: 'Aged elements compared against fresh reference orbits',
    findings: [['Fresh to one month', `${TLE_AGE.fresh} s → ${TLE_AGE.month} s`],
               ['Comparisons', TLE_AGE.comparisons.toLocaleString()]],
  },
];
