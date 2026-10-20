import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useTitle } from '../hooks/useTitle'

function Item({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="mt-8 scroll-mt-20">
      <h2 className="h2 !text-[18px]">{title}</h2>
      <div className="prose mt-2 space-y-2.5">{children}</div>
    </section>
  )
}

/** How every computed number on the site is made (REVIEW_ROUND3, Workstream H). The figures match the code:
 * narratives/debrief.py, narratives/facts.py, analysis/strategy.py and analysis/turns.py. */
export function MethodsPage() {
  useTitle('How the numbers are made')
  return (
    <div className="wrap pt-8 max-w-3xl">
      <h1 className="h-feature">How the numbers are made</h1>
      <p className="t2 mt-3 text-[15px] leading-relaxed">
        Every number on Data Paddock is computed from public timing data: OpenF1 for laps, stints, pit stops, positions,
        race control and car positions, and Jolpica for results and qualifying. Nothing is estimated by hand. This page
        explains what each computed figure means and when the site leaves one out.
      </p>

      <Item id="stories" title="Stories and the debrief">
        <p>Claude, an AI model, writes the short story under each headline (Essential) from a fact sheet the code builds for that
          driver and session. Before it is published, code checks every number, name and claim in it against the fact sheet: a story
          that fails is rewritten, and if it still fails, a story written by code from the same facts is published instead.
          Each page says which kind you are reading.</p>
        <p>Expert shows the debrief instead: tables and three numbered findings, all computed in code. A dash means the
          timing data doesn't have that value, and the note under the table says why.</p>
      </Item>

      <Item id="fuel" title="Fuel-corrected pace">
        <p>A car gets faster as it burns fuel, by about 0.03s a lap. To compare stints and drivers fairly, each lap gets that
          time back for every lap of fuel already burned: lap time + 0.03s × (lap number − 1). Every lap is then compared as
          if it carried the fuel of lap 1.</p>
        <p>Only clean laps count: not lap 1, not a lap into or out of the pits, not a lap under a Safety Car, Virtual Safety
          Car or red flag (or the lap after), and not a lap more than 4% slower than the stint's best (traffic, a mistake).
          A stint needs at least 3 clean laps for an average.</p>
      </Item>

      <Item id="degradation" title="Degradation (fade per lap)">
        <p>How much slower each lap got through a stint, allowing for fuel: the slope of a straight line through the stint's clean
          laps against laps into the stint, with the 0.03s a lap of fuel added back. +0.040s means each lap was 0.04s slower than the
          one before on the same fuel. It needs at least 6 clean laps.</p>
      </Item>

      <Item id="teammate" title="Pace against the teammate on the same tyre">
        <p>The difference between the driver's fuel-corrected average on a stint and his teammate's fuel-corrected average over
          all of the teammate's clean laps on the same tyre in that race. Minus means the driver was quicker. The teammate is the
          one he had that weekend, from the entry list, so a stand-in is compared with the car beside him.</p>
      </Item>

      <Item id="stops" title="Pit stops: places and timing">
        <p><strong>Places</strong>: his position on the lap before he stopped, against his position once every car that was within
          3 places of him had made its own stop (within 25 laps). "P10 to P11 (−1)" means the stop cost him one place once
          everyone had stopped.</p>
        <p><strong>Timing</strong>: a stop up to 3 laps before a Safety Car or Virtual Safety Car is "just before" (the unlucky
          case: cars that waited then stopped for less time); a stop under one is "during" (a cheap stop); a stop up to 3 laps
          after one ended is "just after" (the cheap stop was missed).</p>
        <p><strong>Pit lane and stationary</strong>: pit-lane time is from the pit entry line to the exit line. Stationary time
          is how long the car stood still, when the feed publishes it.</p>
      </Item>

      <Item id="qualifying" title="Qualifying: cut lines and gaps">
        <p>The margin to the cut line is the gap to the first car knocked out (when he went through, shown as +) or to the last
          car through (when he went out, shown as −), in that segment. The gap to his teammate compares their best times in the
          same segment.</p>
      </Item>

      <Item id="ranks" title="Sector ranks and their colours">
        <p>Each driver's best time in each of the three sectors, ranked among everyone who set a time in that sector.
          Purple is the fastest of all, green the top quarter, yellow the middle half and red the bottom quarter. A rank is
          never given out of fewer than 3.</p>
      </Item>

      <Item id="corners" title="Corner times and their colours">
        <p>Each corner owns a stretch of track, from halfway after the previous corner to halfway before the next, so the corners
          add up to the lap. The time through each stretch comes from the car's position data on the driver's best lap, anchored
          on where that lap crosses the start/finish line. Corners are ranked across every driver in the session and coloured
          like sectors, so exactly one driver is purple at each corner.</p>
        <p>A lap whose position data is broken is never coloured: the trace must take the official lap time to within a second,
          have no gap over 2.5s and stay on the track; and no corner may be more than 1.5s (or 20% of the corner's time) off the
          session's reference lap. When a driver's best lap fails, a lap within 1% of it is used instead, or the map shows his
          sectors only, with a note.</p>
      </Item>

      <Item id="long-runs" title="Practice: long runs">
        <p>A long run is a stint of several laps on one tyre. Its pace is ranked against other drivers' long runs on the same tyre
          only when at least 3 drivers ran 5 laps or more on it, and the number of laps is shown beside it. Practice pace is a guide
          only: teams don't publish fuel loads or engine modes.</p>
      </Item>

      <p className="t3 text-[13px] mt-10"><Link to="/races" className="underline underline-offset-2 hover:text-[var(--text)]">Back to the races</Link></p>
    </div>
  )
}
