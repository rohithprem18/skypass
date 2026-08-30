import { useEffect, useRef, useState } from 'react';

/* What to say while a plan is being built.
 *
 * A full catalogue over a long horizon takes ten seconds or more, which is
 * long enough that a static label reads as a hung button. The phrases below
 * follow the real order of the pipeline, and an elapsed counter runs alongside
 * them so the wait is visibly progressing rather than merely animated.
 *
 * The rotation is timed, not tracked: the planner does its work in one request
 * and does not report which stage it is in, so these are a description of the
 * job rather than telemetry from it. The elapsed seconds are real.
 */

export const PLANNING_PHRASES = [
  'Loading element sets',
  'Propagating orbits',
  'Finding horizon crossings',
  'Checking sunlight and shadow',
  'Reading the cloud forecast',
  'Resolving overlapping passes',
  'Building the schedule',
] as const;

const STEP_MS = 1900;

export interface PlanningStatus {
  phrase: string;
  seconds: number;
}

export function usePlanningStatus(busy: boolean): PlanningStatus {
  const [tick, setTick] = useState(0);
  const started = useRef(0);

  useEffect(() => {
    if (!busy) { setTick(0); return; }
    started.current = Date.now();
    setTick(0);
    const id = setInterval(() => setTick(Date.now() - started.current), 250);
    return () => clearInterval(id);
  }, [busy]);

  // Hold on the last phrase rather than looping: cycling back to "loading
  // element sets" after twelve seconds would suggest it had started over.
  const i = Math.min(PLANNING_PHRASES.length - 1, Math.floor(tick / STEP_MS));
  return {
    phrase: PLANNING_PHRASES[i] ?? PLANNING_PHRASES[0],
    seconds: Math.floor(tick / 1000),
  };
}
