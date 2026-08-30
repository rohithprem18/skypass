"""Conflict resolution: choosing which overlapping passes to actually observe.

A single-aperture ground station can track one object at a time, and needs a
setup gap between consecutive targets to slew and reconfigure. Selecting the
best subset of mutually compatible passes is therefore *weighted interval
scheduling*, which has an exact O(n log n) dynamic program -- no metaheuristic
and no MILP solver required.

This module provides that exact algorithm plus the baselines it is measured
against: the heuristics a human operator actually uses, a brute-force optimum
for verification on small instances, and a genetic algorithm standing in for the
metaheuristics common in the operator-side tasking literature.
"""
from __future__ import annotations

import bisect
import datetime as dt
import random
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

from .passes import Pass


@dataclass
class Schedule:
    """A conflict-free observation timetable."""

    selected: List[Pass] = field(default_factory=list)
    algorithm: str = ""
    objective: float = 0.0
    runtime_s: float = 0.0
    n_candidates: int = 0

    @property
    def count(self) -> int:
        return len(self.selected)

    def is_feasible(self, gap_min: float) -> bool:
        gap = dt.timedelta(minutes=gap_min)
        s = sorted(self.selected, key=lambda p: p.aos)
        return all(s[i + 1].aos - s[i].los >= gap for i in range(len(s) - 1))

    def to_dict(self) -> dict:
        return {"algorithm": self.algorithm, "objective": round(self.objective, 4),
                "count": self.count, "runtime_s": round(self.runtime_s, 4),
                "n_candidates": self.n_candidates,
                "passes": [p.to_dict() for p in self.selected]}


def _prepare(passes: Sequence[Pass]) -> List[Pass]:
    """Sort by finish time -- the precondition of the dynamic program."""
    return sorted(passes, key=lambda p: (p.los, p.aos))


def compatibility_index(ordered: Sequence[Pass], gap_min: float) -> List[int]:
    """``p(j)``: index of the latest pass that can precede ``ordered[j]``.

    Returns -1 when no earlier pass is compatible. O(n log n) via binary search
    on the (already sorted) finish times.
    """
    gap = dt.timedelta(minutes=gap_min)
    ends = [p.los for p in ordered]
    return [bisect.bisect_right(ends, p.aos - gap) - 1 for p in ordered]


# ---------------------------------------------------------------------------
# Exact dynamic program -- the SkyPass scheduler
# ---------------------------------------------------------------------------
def optimal_schedule(passes: Sequence[Pass], gap_min: float = 0.0) -> Schedule:
    """Maximum-value conflict-free subset, exactly, in O(n log n).

    Standard weighted-interval-scheduling recurrence
    (Kleinberg and Tardos, *Algorithm Design*, Sec. 6.1):

        OPT[j] = max( OPT[j-1],  v_j + OPT[p(j)+1] )

    with a one-based ``OPT`` so that ``OPT[0] = 0`` absorbs ``p(j) = -1``.
    """
    t0 = time.perf_counter()
    ordered = _prepare(passes)
    n = len(ordered)
    if n == 0:
        return Schedule([], "dp-optimal", 0.0, time.perf_counter() - t0, 0)

    p_idx = compatibility_index(ordered, gap_min)
    val = [p.value for p in ordered]

    opt = [0.0] * (n + 1)
    for j in range(1, n + 1):
        take = val[j - 1] + opt[p_idx[j - 1] + 1]
        opt[j] = take if take > opt[j - 1] else opt[j - 1]

    chosen: List[Pass] = []
    j = n
    while j > 0:
        take = val[j - 1] + opt[p_idx[j - 1] + 1]
        if take >= opt[j - 1] - 1e-12 and take > 0.0:
            chosen.append(ordered[j - 1])
            j = p_idx[j - 1] + 1
        else:
            j -= 1
    chosen.reverse()
    return Schedule(chosen, "dp-optimal", opt[n], time.perf_counter() - t0, n)


# ---------------------------------------------------------------------------
# Capacity-constrained exact scheduling
# ---------------------------------------------------------------------------
def observing_night(p: Pass, lon_deg: float) -> dt.date:
    """The observing night a pass belongs to, in local solar time.

    Shifting by the longitude equivalent and then back by 12 h puts an evening
    and the small hours that follow it into the *same* night, which is how an
    observer actually budgets a session.
    """
    local = p.tca + dt.timedelta(hours=lon_deg / 15.0)
    return (local - dt.timedelta(hours=12)).date()


def _capacity_dp(ordered: List[Pass], gap_min: float, capacity: int):
    """Exact weighted interval scheduling under a cardinality budget.

    Adds one dimension to the classic recurrence:

        OPT[j][k] = max( OPT[j-1][k],  v_j + OPT[p(j)+1][k-1] )

    "at most ``capacity`` observations" is what makes weather-awareness matter:
    with unlimited capacity a planner simply observes everything and never has
    to choose between a clear pass and a cloudy one. Runs in O(nK) after the
    O(n log n) sort, so a night's worth of passes is still solved instantly.
    """
    n = len(ordered)
    if n == 0 or capacity <= 0:
        return [], 0.0
    k_max = min(capacity, n)
    p_idx = compatibility_index(ordered, gap_min)
    val = [p.value for p in ordered]

    # opt[j][k] with j in 0..n, k in 0..k_max
    opt = [[0.0] * (k_max + 1) for _ in range(n + 1)]
    for j in range(1, n + 1):
        vj = val[j - 1]
        pj = p_idx[j - 1] + 1
        row, prev = opt[j], opt[j - 1]
        row[0] = 0.0
        for k in range(1, k_max + 1):
            take = vj + opt[pj][k - 1]
            row[k] = take if take > prev[k] else prev[k]

    chosen: List[Pass] = []
    j, k = n, k_max
    while j > 0 and k > 0:
        vj = val[j - 1]
        pj = p_idx[j - 1] + 1
        take = vj + opt[pj][k - 1]
        # opt[j][k] = max(opt[j-1][k], take), so item j-1 is in an optimal
        # solution exactly when taking it is strictly better than skipping it.
        if vj > 0.0 and take > opt[j - 1][k] + 1e-12:
            chosen.append(ordered[j - 1])
            j, k = pj, k - 1
        else:
            j -= 1
    chosen.reverse()
    return chosen, opt[n][k_max]


def capacity_schedule(passes: Sequence[Pass], gap_min: float = 0.0,
                      capacity: Optional[int] = None,
                      per_night: bool = False,
                      lon_deg: float = 0.0) -> Schedule:
    """Optimal timetable subject to an observing-capacity budget.

    ``capacity=None`` reduces exactly to :func:`optimal_schedule`.
    ``per_night=True`` applies the budget to each observing night separately.
    Nights are disjoint in time, so solving them independently is still exact.
    """
    t0 = time.perf_counter()
    if capacity is None:
        s = optimal_schedule(passes, gap_min)
        s.algorithm = "dp-optimal"
        return s

    groups: dict = {}
    if per_night:
        for p in passes:
            groups.setdefault(observing_night(p, lon_deg), []).append(p)
    else:
        groups[None] = list(passes)

    chosen: List[Pass] = []
    total = 0.0
    for g in groups.values():
        sel, v = _capacity_dp(_prepare(g), gap_min, capacity)
        chosen.extend(sel)
        total += v
    chosen.sort(key=lambda p: p.aos)
    label = f"dp-capacity-{capacity}" + ("-per-night" if per_night else "")
    return Schedule(chosen, label, total, time.perf_counter() - t0, len(passes))


def budget_schedule(passes: Sequence[Pass], gap_min: float,
                    per_night_cap: int, total_budget: int,
                    lon_deg: float = 0.0) -> Schedule:
    """Exact schedule under BOTH a nightly cap and a total budget.

    This is the realistic small-station model, and the two limits do different
    work. The nightly cap says the station cannot cram a month of observing into
    one night. The total budget says it does not have to go out every night ---
    and being free to *skip* a night is precisely the decision a weather
    forecast informs. A nightly quota alone forces the station out regardless of
    the sky, which removes the choice weather-awareness exists to make.

    The problem separates exactly. Observing nights are disjoint in time, so for
    night $i$ let $V_i[j]$ be the optimal value obtainable there using at most
    $j$ observations, computed by :func:`_capacity_dp`. Allocating the budget
    across nights is then a knapsack over the $V_i$:

        W[i][b] = max_{0 <= j <= min(cap, b)}  V_i[j] + W[i-1][b-j]

    Both stages are exact, so their composition is exact. Total cost is
    O(sum_i n_i C + N B C), trivial at station scale.
    """
    t0 = time.perf_counter()
    items = list(passes)
    if not items or total_budget <= 0 or per_night_cap <= 0:
        return Schedule([], "dp-budget", 0.0, time.perf_counter() - t0,
                        len(items))

    nights: dict = {}
    for p in items:
        nights.setdefault(observing_night(p, lon_deg), []).append(p)
    keys = sorted(nights)
    cap = per_night_cap

    # Per-night value curves and the selections behind them.
    values, picks = [], []
    for k in keys:
        ordered = _prepare(nights[k])
        vs, ps = [0.0], [[]]
        for j in range(1, cap + 1):
            sel, v = _capacity_dp(ordered, gap_min, j)
            vs.append(v)
            ps.append(sel)
        values.append(vs)
        picks.append(ps)

    # Knapsack across nights.
    n_nights = len(keys)
    b_max = min(total_budget, cap * n_nights)
    neg = float("-inf")
    w = [[neg] * (b_max + 1) for _ in range(n_nights + 1)]
    w[0][0] = 0.0
    for i in range(1, n_nights + 1):
        vi = values[i - 1]
        for b in range(b_max + 1):
            best = neg
            for j in range(0, min(cap, b) + 1):
                prev = w[i - 1][b - j]
                if prev == neg:
                    continue
                cand = prev + vi[j]
                if cand > best:
                    best = cand
            w[i][b] = best

    # Best total value over any spend up to the budget.
    b_star, best_val = 0, 0.0
    for b in range(b_max + 1):
        if w[n_nights][b] > best_val:
            best_val, b_star = w[n_nights][b], b

    chosen: List[Pass] = []
    b = b_star
    for i in range(n_nights, 0, -1):
        vi = values[i - 1]
        for j in range(0, min(cap, b) + 1):
            prev = w[i - 1][b - j]
            if prev == neg:
                continue
            if abs(prev + vi[j] - w[i][b]) < 1e-12:
                chosen.extend(picks[i - 1][j])
                b -= j
                break
    chosen.sort(key=lambda p: p.aos)
    return Schedule(chosen, f"dp-budget-{per_night_cap}x{total_budget}",
                    best_val, time.perf_counter() - t0, len(items))


def greedy_budget(passes: Sequence[Pass], gap_min: float, per_night_cap: int,
                  total_budget: int, key: Callable[[Pass], float],
                  label: str, lon_deg: float = 0.0) -> Schedule:
    """Greedy counterpart of :func:`budget_schedule`, for baselines."""
    t0 = time.perf_counter()
    gap = dt.timedelta(minutes=gap_min)
    per_night: dict = {}
    chosen: List[Pass] = []
    for p in sorted(passes, key=key, reverse=True):
        if len(chosen) >= total_budget:
            break
        night = observing_night(p, lon_deg)
        taken = per_night.setdefault(night, [])
        if len(taken) >= per_night_cap:
            continue
        if all(not (p.aos < q.los + gap and q.aos < p.los + gap) for q in taken):
            taken.append(p)
            chosen.append(p)
    chosen.sort(key=lambda p: p.aos)
    return Schedule(chosen, label, sum(p.value for p in chosen),
                    time.perf_counter() - t0, len(passes))


def brute_force_budget(passes: Sequence[Pass], gap_min: float,
                       per_night_cap: int, total_budget: int,
                       lon_deg: float = 0.0, max_n: int = 18) -> Schedule:
    """Exhaustive reference for the two-level budgeted problem."""
    t0 = time.perf_counter()
    items = list(passes)
    n = len(items)
    if n > max_n:
        raise ValueError(f"brute force refused for n={n} (> {max_n})")
    gap = dt.timedelta(minutes=gap_min)
    best_val, best_mask = 0.0, 0
    for mask in range(1 << n):
        sel = [items[i] for i in range(n) if mask >> i & 1]
        if len(sel) > total_budget:
            continue
        per_night: dict = {}
        for p in sel:
            per_night.setdefault(observing_night(p, lon_deg), []).append(p)
        if any(len(v) > per_night_cap for v in per_night.values()):
            continue
        sel.sort(key=lambda p: p.aos)
        if any(sel[i + 1].aos - sel[i].los < gap for i in range(len(sel) - 1)):
            continue
        v = sum(p.value for p in sel)
        if v > best_val:
            best_val, best_mask = v, mask
    chosen = [items[i] for i in range(n) if best_mask >> i & 1]
    chosen.sort(key=lambda p: p.aos)
    return Schedule(chosen, "brute-force-budget", best_val,
                    time.perf_counter() - t0, n)


def greedy_capacity(passes: Sequence[Pass], gap_min: float, capacity: int,
                    key: Callable[[Pass], float], label: str,
                    per_night: bool = False, lon_deg: float = 0.0) -> Schedule:
    """Greedy counterpart of :func:`capacity_schedule`, for baselines."""
    t0 = time.perf_counter()
    gap = dt.timedelta(minutes=gap_min)
    groups: dict = {}
    if per_night:
        for p in passes:
            groups.setdefault(observing_night(p, lon_deg), []).append(p)
    else:
        groups[None] = list(passes)
    chosen: List[Pass] = []
    for g in groups.values():
        taken: List[Pass] = []
        for p in sorted(g, key=key, reverse=True):
            if len(taken) >= capacity:
                break
            if all(not (p.aos < q.los + gap and q.aos < p.los + gap)
                   for q in taken):
                taken.append(p)
        chosen.extend(taken)
    chosen.sort(key=lambda p: p.aos)
    return Schedule(chosen, label, sum(p.value for p in chosen),
                    time.perf_counter() - t0, len(passes))


def brute_force_capacity(passes: Sequence[Pass], gap_min: float, capacity: int,
                         max_n: int = 20) -> Schedule:
    """Exhaustive reference for the capacity-constrained problem."""
    t0 = time.perf_counter()
    items = list(passes)
    n = len(items)
    if n > max_n:
        raise ValueError(f"brute force refused for n={n} (> {max_n})")
    gap = dt.timedelta(minutes=gap_min)
    best_val, best_mask = 0.0, 0
    for mask in range(1 << n):
        if bin(mask).count("1") > capacity:
            continue
        sel = [items[i] for i in range(n) if mask >> i & 1]
        sel.sort(key=lambda p: p.aos)
        if any(sel[i + 1].aos - sel[i].los < gap for i in range(len(sel) - 1)):
            continue
        v = sum(p.value for p in sel)
        if v > best_val:
            best_val, best_mask = v, mask
    chosen = [items[i] for i in range(n) if best_mask >> i & 1]
    chosen.sort(key=lambda p: p.aos)
    return Schedule(chosen, "brute-force-capacity", best_val,
                    time.perf_counter() - t0, n)


# ---------------------------------------------------------------------------
# Heuristic baselines
# ---------------------------------------------------------------------------
def _greedy(passes: Sequence[Pass], gap_min: float, key: Callable[[Pass], float],
            label: str, reverse: bool = True) -> Schedule:
    t0 = time.perf_counter()
    gap = dt.timedelta(minutes=gap_min)
    chosen: List[Pass] = []
    for p in sorted(passes, key=key, reverse=reverse):
        ok = True
        for q in chosen:
            if p.aos < q.los + gap and q.aos < p.los + gap:
                ok = False
                break
        if ok:
            chosen.append(p)
    chosen.sort(key=lambda p: p.aos)
    return Schedule(chosen, label, sum(p.value for p in chosen),
                    time.perf_counter() - t0, len(passes))


def greedy_earliest_finish(passes: Sequence[Pass], gap_min: float = 0.0) -> Schedule:
    """Classic unweighted interval scheduling: maximises *count*, not value."""
    return _greedy(passes, gap_min, key=lambda p: p.los, label="greedy-earliest-finish",
                   reverse=False)


def greedy_highest_value(passes: Sequence[Pass], gap_min: float = 0.0) -> Schedule:
    """Take the most valuable compatible pass first."""
    return _greedy(passes, gap_min, key=lambda p: p.value, label="greedy-highest-value")


def greedy_max_elevation(passes: Sequence[Pass], gap_min: float = 0.0) -> Schedule:
    """The rule of thumb an operator uses by hand: chase the highest culmination."""
    return _greedy(passes, gap_min, key=lambda p: p.el_max_deg,
                   label="greedy-max-elevation")


def greedy_longest_duration(passes: Sequence[Pass], gap_min: float = 0.0) -> Schedule:
    """Chase the longest contact window (the usual radio-operator rule)."""
    return _greedy(passes, gap_min, key=lambda p: p.duration_s,
                   label="greedy-longest-duration")


# ---------------------------------------------------------------------------
# Reference solvers
# ---------------------------------------------------------------------------
def brute_force_optimal(passes: Sequence[Pass], gap_min: float = 0.0,
                        max_n: int = 22) -> Schedule:
    """Exhaustive search over all subsets. Verification only; O(2^n)."""
    t0 = time.perf_counter()
    items = list(passes)
    n = len(items)
    if n > max_n:
        raise ValueError(f"brute force refused for n={n} (> {max_n})")
    gap = dt.timedelta(minutes=gap_min)

    best_val, best_set = 0.0, 0
    for mask in range(1 << n):
        sel = [items[i] for i in range(n) if mask >> i & 1]
        sel.sort(key=lambda p: p.aos)
        if any(sel[i + 1].aos - sel[i].los < gap for i in range(len(sel) - 1)):
            continue
        v = sum(p.value for p in sel)
        if v > best_val:
            best_val, best_set = v, mask
    chosen = [items[i] for i in range(n) if best_set >> i & 1]
    chosen.sort(key=lambda p: p.aos)
    return Schedule(chosen, "brute-force", best_val, time.perf_counter() - t0, n)


def genetic_schedule(passes: Sequence[Pass], gap_min: float = 0.0,
                     population: int = 120, generations: int = 250,
                     mutation_rate: float = 0.15, elite: int = 4,
                     seed: int = 0) -> Schedule:
    """Order-based genetic algorithm, standing in for the metaheuristic family.

    A chromosome is a permutation of candidate passes; it is decoded by walking
    the permutation and accepting each pass that is still compatible. This is
    the representation most commonly used in satellite-tasking GA papers, and it
    is included to show what such a solver costs on a problem that has an exact
    polynomial algorithm.
    """
    t0 = time.perf_counter()
    rng = random.Random(seed)
    items = list(passes)
    n = len(items)
    if n == 0:
        return Schedule([], "genetic", 0.0, time.perf_counter() - t0, 0)
    gap = dt.timedelta(minutes=gap_min)

    def decode(order: List[int]):
        chosen: List[Pass] = []
        for i in order:
            p = items[i]
            if all(not (p.aos < q.los + gap and q.aos < p.los + gap) for q in chosen):
                chosen.append(p)
        return chosen, sum(p.value for p in chosen)

    pop = []
    for _ in range(population):
        g = list(range(n))
        rng.shuffle(g)
        pop.append(g)
    # Seed one individual with the value-greedy order to give the GA a fair start.
    pop[0] = sorted(range(n), key=lambda i: -items[i].value)

    scored = [(decode(g)[1], g) for g in pop]
    scored.sort(key=lambda x: -x[0])

    for _ in range(generations):
        nxt = [g for _, g in scored[:elite]]
        while len(nxt) < population:
            a = max(rng.sample(scored, 3), key=lambda x: x[0])[1]
            b = max(rng.sample(scored, 3), key=lambda x: x[0])[1]
            child = _order_crossover(a, b, rng)
            if rng.random() < mutation_rate:
                i, j = rng.randrange(n), rng.randrange(n)
                child[i], child[j] = child[j], child[i]
            nxt.append(child)
        scored = [(decode(g)[1], g) for g in nxt]
        scored.sort(key=lambda x: -x[0])

    best_val, best_g = scored[0]
    chosen, _ = decode(best_g)
    chosen.sort(key=lambda p: p.aos)
    return Schedule(chosen, "genetic", best_val, time.perf_counter() - t0, n)


def _order_crossover(a: List[int], b: List[int], rng: random.Random) -> List[int]:
    """Davis order crossover (OX1)."""
    n = len(a)
    if n < 2:
        return list(a)
    i, j = sorted(rng.sample(range(n), 2))
    child = [None] * n
    child[i:j + 1] = a[i:j + 1]
    taken = set(a[i:j + 1])
    k = (j + 1) % n
    for x in b[j + 1:] + b[:j + 1]:
        if x not in taken:
            child[k] = x
            taken.add(x)
            k = (k + 1) % n
    return [x for x in child]


ALGORITHMS = {
    "dp-optimal": optimal_schedule,
    "greedy-highest-value": greedy_highest_value,
    "greedy-max-elevation": greedy_max_elevation,
    "greedy-longest-duration": greedy_longest_duration,
    "greedy-earliest-finish": greedy_earliest_finish,
    "genetic": genetic_schedule,
}
