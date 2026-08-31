export interface Pass {
  name: string;
  norad_id: number;
  aos: string;
  tca: string;
  los: string;
  duration_s: number;
  el_max: number;
  az_aos: number;
  az_tca: number;
  az_los: number;
  dir_aos: string;
  dir_tca: string;
  dir_los: string;
  range_km: number;
  magnitude: number | null;
  cloud: number | null;
  score: number;
  priority: number;
  night: string;
  track: TrackPoint[];
  /** True when the scheduler kept this pass. */
  selected: boolean;
  /** Scheduled passes whose slot this one wanted; empty when it won. */
  conflicts: Conflict[];
  /** Share of the pass spent out of Earth's umbra, 0..1. */
  sunlit: number | null;
  /** Solar elevation at culmination, degrees. Negative after sunset. */
  sun_elev: number | null;
  phase_deg: number | null;
  /** Assigned client-side so the next pass can be identified cheaply. */
  __id?: number;
}

export interface Conflict { norad_id: number; name: string; aos: string }

export interface TrackPoint { az: number; el: number; t: string }

export interface Funnel {
  catalogue: number;
  geometric: number;
  sunlit: number;
  dark: number;
  bright: number;
  clear: number;
  candidates: number;
  scheduled: number;
}

export interface NightSummary {
  night: string;
  passes: number;
  selected: number;
  cloud: number | null;
  best_el: number;
  best_score: number;
  verdict: 'best' | 'good' | 'skip';
}

export interface HourCloud { t: string; cloud: number }
export interface Interval { from: string; to: string }
export interface Crossing { t: string; falling: boolean }

export interface Plan {
  site: { name: string; lat: number; lon: number; alt: number; mask: number };
  window: { from: string; to: string; days: number };
  mode: 'optical' | 'radio';
  weather_used: boolean;
  capacity: number;
  funnel: Funnel;
  runtime_s: number;
  propagations: number;
  passes: Pass[];
  if_clear: Pass[];
  candidates: Pass[];
  nights: NightSummary[];
  hourly: HourCloud[];
  twilight: Record<string, Crossing[]>;
  /** Nested intervals per twilight phase: day, civil, nautical, astronomical. */
  bands: Record<string, Interval[]>;
  darkness: Interval[];
  setup_gap_min: number;
  blocked_by_weather: number;
  mean_cloud: number | null;
  generated: string;
}

export interface Station {
  key: string; name: string; lat: number; lon: number; alt: number;
}

export interface Settings {
  station: string;
  lat: string;
  lon: string;
  days: string;
  mode: 'optical' | 'radio';
  mask: string;
  capacity: string;
  weather: boolean;
}

export type View =
  | 'overview' | 'planner' | 'passes' | 'weather' | 'schedule';

