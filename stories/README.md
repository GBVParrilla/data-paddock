# Story corrections

Every story on the site is written by Claude when the session's data is processed and stored in the
database. **This folder holds the human corrections.** A file here replaces the AI text for one story;
the AI version is kept untouched underneath.

## Fixing a story (the easy way)

1. Open the story on the site with `?editor=1` at the end of the URL (flag issues link there already).
2. Click **Edit**. GitHub opens a new file here, prefilled with the AI text.
3. Change the text, optionally fill in `note:` (shown on the site as the reason), and commit.
4. The site rebuilds in a few minutes and shows your version, marked "corrected by the editor".

To go back to the AI story, click **Revert to AI** (or just delete the file).

## File layout

`stories/<year>/<round>-<event>/<session>/<driver>.md`, for example
`stories/2026/01-australian-grand-prix/race/leclerc.md`. Also:

- `.../weekend/<driver>.md` for the weekend arc
- `.../<session>/compare-<driver>-vs-<driver>.md` for a teammate head-to-head
- `<year>/season/driver-<driver>.md` and `<year>/season/team-<team>.md` for season stories

```markdown
---
ai_generated_at: 2026-03-08T10:12:44
note: He pitted on lap 21, not 23
---

## Recap

Corrected recap…

## Analysis

Corrected strategy analysis (driver session stories only; leave the section out to keep the AI's)…
```

If Claude later rewrites a story because its data changed, a correction made against the older version
is flagged in editor mode so you can check it still applies. Corrections to session stories also feed
into that driver's weekend arc the next time the arc is written.
