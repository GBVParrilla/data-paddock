/** Plain-language definitions for every bit of F1 jargon the site uses. One place, reused everywhere. */
export const GLOSSARY: Record<string, { term: string; def: string }> = {
  DNF: { term: 'DNF', def: 'Did not finish: the car retired before the chequered flag.' },
  DNS: { term: 'DNS', def: 'Did not start: the car was entered but never took the start.' },
  DSQ: { term: 'DSQ', def: 'Disqualified: removed from the results by the stewards.' },
  NC: { term: 'NC', def: 'Not classified: still running at the end, but covered less than 90% of the winner\'s distance.' },
  lapped: { term: 'Lapped', def: 'Finished one or more laps behind the winner, who passed them on track.' },
  VSC: { term: 'Virtual Safety Car', def: 'Every car must slow to a set pace while marshals work. Pit stops under it cost much less time than usual.' },
  SC: { term: 'Safety Car', def: 'A real car leads the field at reduced speed and the gaps between cars close up. A cheap moment to pit.' },
  red: { term: 'Red flag', def: 'The session is stopped and cars return to the pit lane. Teams may change tyres while they wait.' },
  stint: { term: 'Stint', def: 'The laps a driver does on one set of tyres, between pit stops.' },
  compound: { term: 'Compound', def: 'The tyre type. Soft is fastest but wears quickest; hard lasts longest but is slower. Intermediate and wet tyres are for rain.' },
  undercut: { term: 'Undercut', def: 'Pitting before a rival so your fresh tyres gain enough time to come out ahead once they stop too.' },
  overcut: { term: 'Overcut', def: 'Staying out longer than a rival and using the clear track to come out ahead after your own stop.' },
  longrun: { term: 'Long run', def: 'Several laps in a row on race-like fuel in practice. The average lap shows race pace better than one fast lap.' },
  Q: { term: 'Q1, Q2, Q3', def: 'Qualifying\'s three knockout segments. The slowest cars drop out after Q1 and Q2; the top ten fight for pole in Q3.' },
  SQ: { term: 'Sprint qualifying', def: 'A shorter qualifying session (SQ1, SQ2, SQ3) that sets the grid for the Saturday sprint.' },
  sprint: { term: 'Sprint', def: 'A short race of about a third of the distance, with points for the top eight.' },
  pole: { term: 'Pole position', def: 'First place on the grid, earned by the fastest lap in the final qualifying segment.' },
  sector: { term: 'Sector', def: 'The lap is timed in three parts. Comparing sectors shows where on track a driver is quick or slow.' },
  purple: { term: 'Sector colours', def: 'Purple: the fastest of anyone. Green: top quarter of the field. Yellow: middle half. Red: bottom quarter.' },
  reference: { term: 'Reference lap', def: 'The fastest lap of the session. Each corner shows the time a driver\'s best lap gained (left) or lost (right) against it.' },
  stationary: { term: 'Stationary time', def: 'How long the car stood still while the tyres were changed. The timing feed doesn\'t publish it for every race, so pit-lane time is shown instead.' },
  pitlane: { term: 'Pit-lane time', def: 'From pit entry to pit exit, including the stop itself. Around 20 seconds at most tracks.' },
  tracklimits: { term: 'Track limits', def: 'All four wheels over the white line. The lap time is deleted, and repeat offences bring penalties.' },
  grid: { term: 'Grid penalty', def: 'A drop down the starting order, usually for using too many engine parts or a rules breach.' },
  standin: { term: 'Stand-in', def: 'A driver racing for a team that isn\'t their usual one, covering for an injured or absent driver.' },
  interpretation: { term: 'Interpretation', def: 'Analysis written from the data. It is an informed reading of what happened, not a certainty.' },
}

/** Only real jargon is underlined (REVIEW_ROUND2 A6). Everything else in GLOSSARY renders as plain text. */
export const UNDERLINED = new Set(['VSC', 'SC', 'red', 'DNF', 'DNS', 'DSQ', 'NC', 'lapped', 'undercut', 'overcut', 'stint', 'compound', 'longrun', 'Q', 'SQ', 'standin', 'interpretation'])
