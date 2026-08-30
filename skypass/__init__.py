"""SkyPass -- weather-aware integrated satellite transit planning.

Public surface::

    from skypass import plan, GROUND_STATIONS
    result = plan(GROUND_STATIONS["chennai"], days=7)
    print(result.summary())
"""
from .config import (DEFAULT_SITE, GROUND_STATIONS, PlannerConfig, ScoreWeights,
                     Site)
from .passes import Pass, Tracker, find_passes, find_passes_dense
from .pipeline import PlanResult, load_catalogue, plan, propagate_all
from .scheduler import (Schedule, brute_force_optimal, genetic_schedule,
                        greedy_max_elevation, optimal_schedule)
from .scoring import MODE_OPTICAL, MODE_RADIO, score_pass

__version__ = "1.0.0"

__all__ = [
    "DEFAULT_SITE", "GROUND_STATIONS", "PlannerConfig", "ScoreWeights", "Site",
    "Pass", "Tracker", "find_passes", "find_passes_dense",
    "PlanResult", "load_catalogue", "plan", "propagate_all",
    "Schedule", "brute_force_optimal", "genetic_schedule",
    "greedy_max_elevation", "optimal_schedule",
    "MODE_OPTICAL", "MODE_RADIO", "score_pass", "__version__",
]
