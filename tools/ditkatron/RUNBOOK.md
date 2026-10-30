# Ditkatron Thoughts: daily update

A scheduled task runs this every morning. It changes only the Ditkatron Thoughts data in
`index.html` (`window.__PK_THOUGHTS`) and the cache `tools/ditkatron/league_picks.json`. Nothing
else on the site is touched.

## Rules
- Picks are used only for games that are **final**. Never mention, hint at or guess anyone's pick
  for a game that has not finished. The site keeps picks hidden until kickoff.
- No phone numbers, emails, private player links or tokens anywhere in the repo or the take.
- Ditkatron 9000 is the commentator, not a player: his picks are never counted or shown.
- The take never says or hints who Ditkatron is picking, or who he thinks will win, in a game that
  has not finished ("Ditkatron likes X", "Ditkatron is taking X"). His picks live in the pick sheet
  and are secret until kickoff. He can cheer for da Bears as a fan and quote the betting line.

## Steps
1. `GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/nflverse/nfldata /tmp/nfldata`
2. `python3 tools/ditkatron/thoughts.py need --nfl /tmp/nfldata/data/games.csv`
   prints the first week (7 or later) whose finished games are not in the cache yet, or `none`.
3. If it printed a week N: read the pick sheet's `Picks` tab, column A, find the rows with
   Week >= N, read columns A:D for those rows (Week, Game, Player, Pick) and save them as a JSON
   list of rows to `/tmp/new_picks.json`. Rows for unfinished games are dropped by the script.
4. `python3 tools/ditkatron/thoughts.py prep --site index.html --nfl /tmp/nfldata/data/games.csv
   [--new /tmp/new_picks.json] --out /tmp/thoughts_base.json --summary /tmp/thoughts_summary.md`
   prints the fact sheet. If it warns about a finished week with no picks, fix step 3 first.
5. Write Ditkatron's take from the fact sheet only: 4-5 short paragraphs in his voice, saved as
   `{"paragraphs": [...]}` in `/tmp/take.json`.
6. `python3 tools/ditkatron/thoughts.py publish --site index.html --base /tmp/thoughts_base.json --take /tmp/take.json`
7. Check the page renders (Ditkatron Thoughts tab, no script errors, no sideways scroll on a
   phone), check `git diff --stat` shows only `index.html` and the cache, then commit and push.
