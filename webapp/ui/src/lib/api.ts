import type { Plan, Settings, Station, TrackPoint } from '../types';

function query(s: Settings): string {
  const q = new URLSearchParams();
  if (s.lat.trim() && s.lon.trim()) { q.set('lat', s.lat); q.set('lon', s.lon); }
  else q.set('station', s.station);
  q.set('days', s.days);
  q.set('mode', s.mode);
  q.set('mask', s.mask);
  q.set('capacity', s.capacity);
  q.set('weather', s.weather ? '1' : '0');
  return q.toString();
}

export async function fetchStations(): Promise<Station[]> {
  const r = await fetch('/api/stations');
  if (!r.ok) throw new Error('Could not load stations');
  return (await r.json()).stations;
}

export async function fetchPlan(s: Settings, signal?: AbortSignal): Promise<Plan> {
  const r = await fetch('/api/plan?' + query(s), { signal });
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || data.error || 'Planning failed');
  return data as Plan;
}

/** The elevation profile of one pass, fetched only when it is opened. */
export async function fetchTrack(s: Settings, norad: number, aos: string,
                                 los?: string): Promise<TrackPoint[]> {
  const q = new URLSearchParams(query(s));
  q.set('norad', String(norad));
  q.set('aos', aos);
  if (los) q.set('los', los);
  const r = await fetch('/api/track?' + q.toString());
  if (!r.ok) throw new Error('Could not load track');
  return (await r.json()).track as TrackPoint[];
}

export const icsUrl = (s: Settings): string => '/api/ics?' + query(s);
