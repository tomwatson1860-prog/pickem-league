#!/usr/bin/env python3
"""Ditkatron Thoughts updater for the family pick'em site (index.html in this repo).

Only the Ditkatron Thoughts data (window.__PK_THOUGHTS in index.html) is ever changed. Everything
else on the site stays as it is.

Data sources
  * NFL schedule, scores and betting lines: nflverse games.csv (github.com/nflverse/nfldata).
  * Family picks, Weeks 1-6: window.__PK_DATA embedded in index.html.
  * Family picks, Week 7 on: tools/ditkatron/league_picks.json, a cache of picks for FINISHED
    games only, topped up each run from rows copied out of the league pick sheet.

Privacy rule: picks are only ever read for games that are final. Picks for games that have not
finished are dropped on input and never cached, summarised or published.

Commands
  need     print the earliest week whose finished games still need picks from the pick sheet
  prep     merge new pick rows, build the Thoughts data and a fact summary for writing the take
  publish  add Ditkatron's paragraphs and write them into index.html
"""
import argparse, csv, json, re, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
CT = ZoneInfo('America/Chicago')
BOT = 'Ditkatron 9000'
SEASON = '2026'
HERE = Path(__file__).resolve().parent
CACHE = HERE / 'league_picks.json'
NICK = dict(ARI='Cardinals', ATL='Falcons', BAL='Ravens', BUF='Bills', CAR='Panthers', CHI='Bears', CIN='Bengals', CLE='Browns', DAL='Cowboys', DEN='Broncos', DET='Lions', GB='Packers', HOU='Texans', IND='Colts', JAX='Jaguars', KC='Chiefs', LA='Rams', LAC='Chargers', LV='Raiders', MIA='Dolphins', MIN='Vikings', NE='Patriots', NO='Saints', NYG='Giants', NYJ='Jets', PHI='Eagles', PIT='Steelers', SEA='Seahawks', SF='49ers', TB='Buccaneers', TEN='Titans', WAS='Commanders')
NORTH = ['Bears', 'Lions', 'Packers', 'Vikings']
W = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen']
ORD = ['', 'first', 'second', 'third', 'fourth']
THOUGHTS_RE = re.compile(r'(<script>window\.__PK_THOUGHTS = )(.*?)(;</script>)', re.S)
DATA_RE = re.compile(r'<script>window\.__PK_DATA = (\{.*?\});</script>', re.S)


# ---------------- loading ----------------
def load_nfl(path):
    games = []
    for r in csv.DictReader(open(path, newline='')):
        if r['season'] != SEASON or r['game_type'] != 'REG':
            continue
        k = datetime.strptime(r['gameday'] + ' ' + r['gametime'], '%Y-%m-%d %H:%M').replace(tzinfo=ET)
        g = {'week': int(r['week']), 'away': NICK[r['away_team']], 'home': NICK[r['home_team']], 'kick': k,
             'div': r['div_game'] == '1', 'final': r['away_score'] != '' and r['home_score'] != '',
             'ml_a': r['away_moneyline'], 'ml_h': r['home_moneyline'], 'spread': r['spread_line'], 'row': r}
        if g['final']:
            g['sa'], g['sh'] = int(r['away_score']), int(r['home_score'])
            g['winner'] = g['away'] if g['sa'] > g['sh'] else g['home'] if g['sh'] > g['sa'] else 'TIE'
        games.append(g)
    games.sort(key=lambda g: (g['week'], g['kick']))  # stable: same-time games keep nflverse order
    return games


def load_site(path):
    m = DATA_RE.search(Path(path).read_text())
    if not m:
        sys.exit('index.html: window.__PK_DATA not found')
    return json.loads(m.group(1))


def load_cache():
    return json.loads(CACHE.read_text()) if CACHE.exists() else {'about': '', 'picks': []}


def by_team(games):
    """(week, team) -> game"""
    idx = {}
    for g in games:
        idx[(g['week'], g['away'])] = g
        idx[(g['week'], g['home'])] = g
    return idx


def family_picks(site, cache, games):
    """All family picks for FINAL games: list of dicts {week, game(obj), player, pick}."""
    idx = by_team(games)
    out = []
    for p in site['picks']:  # Weeks 1-6 from the site's own data
        if p['week'] >= 7 or p['player'].strip() == BOT:
            continue
        g = idx.get((p['week'], p['pick']))
        if g and g['final']:
            out.append({'week': p['week'], 'g': g, 'player': p['player'].strip(), 'pick': p['pick']})
    for p in cache['picks']:
        g = idx.get((p['week'], p['pick']))
        if g and g['final'] and p['player'].strip() != BOT:
            out.append({'week': p['week'], 'g': g, 'player': p['player'].strip(), 'pick': p['pick']})
    seen, uniq = set(), []
    for p in out:  # one pick per player per game
        k = (p['week'], id(p['g']), p['player'])
        if k not in seen:
            seen.add(k); uniq.append(p)
    return uniq


# ---------------- helpers ----------------
def prob(g):
    try:
        a, h = float(g['ml_a']), float(g['ml_h'])
    except (TypeError, ValueError):
        return None
    imp = lambda m: 100 / (m + 100) if m > 0 else -m / (-m + 100)
    a, h = imp(a), imp(h)
    return a / (a + h), h / (a + h)


def rs(v): return f"{v[0]}–{v[1]}" + (f"–{v[2]}" if v[2] else '')
def names(xs): return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' and ' + xs[-1]
def nb(t): return t.replace('–', '–⁠')  # keep "4–2" on one line
def kick_str(g): return g['kick'].strftime('%a ') + g['kick'].strftime('%I:%M %p').lstrip('0')
def is_thanksgiving(d): return d.month == 11 and d.weekday() == 3 and 22 <= d.day <= 28


def when_str(g):
    d = g['kick']
    if is_thanksgiving(d): return 'Thanksgiving'
    if d.month == 12 and d.day == 25: return 'Christmas Day'
    return f"{d.strftime('%a')}{' night' if d.hour >= 19 else ''}, {d.strftime('%b')} {d.day}"


def tv_name(g):
    d = g['kick']
    if d.hour >= 19 and not is_thanksgiving(d):
        return {0: 'Monday Night Football', 3: 'Thursday Night Football', 6: 'Sunday Night Football'}.get(d.weekday())
    return None


def records(games, upto=None):
    rec = defaultdict(lambda: [0, 0, 0])
    for g in games:
        if not g['final'] or (upto and g['kick'] > upto): continue
        if g['winner'] == 'TIE': rec[g['away']][2] += 1; rec[g['home']][2] += 1
        else:
            rec[g['winner']][0] += 1
            rec[g['away'] if g['winner'] == g['home'] else g['home']][1] += 1
    return rec


# ---------------- need ----------------
def cmd_need(a):
    games = load_nfl(a.nfl)
    cache = load_cache()
    have = {(p['week'], p['pick']) for p in cache['picks']}
    weeks = sorted({g['week'] for g in games if g['week'] >= 7 and g['final']
                    and (g['week'], g['away']) not in have and (g['week'], g['home']) not in have})
    print(weeks[0] if weeks else 'none')


# ---------------- prep ----------------
def merge_new(new_path, games, cache):
    """Add sheet rows [week, game, player, pick] for FINAL games to the cache. Rows for games that
    are not final are dropped here and never stored."""
    rows = json.loads(Path(new_path).read_text())
    if isinstance(rows, dict): rows = rows.get('values', [])
    idx = by_team(games)
    keep = {(p['week'], p['player'], p['pick']) for p in cache['picks']}
    known = {(p['week'], p['player'], id(idx.get((p['week'], p['pick'])))) for p in cache['picks']}
    added = dropped = 0
    for r in rows:
        if len(r) < 4 or not str(r[0]).strip().isdigit(): continue
        week, game, player, pick = int(r[0]), int(r[1]), str(r[2]).strip(), str(r[3]).strip()
        g = idx.get((week, pick))
        if not g or not g['final'] or player == BOT or not player:
            dropped += 1; continue
        if (week, player, id(g)) in known or (week, player, pick) in keep: continue
        cache['picks'].append({'week': week, 'game': game, 'player': player, 'pick': pick})
        known.add((week, player, id(g))); added += 1
    cache['picks'].sort(key=lambda p: (p['week'], p['game'], p['player']))
    cache['about'] = ('Family picks for finished games, Week 7 on, copied from the league pick sheet. '
                      'Picks for games that have not finished are never stored here.')
    return added, dropped


def build(a):
    now = datetime.fromisoformat(a.now.replace('Z', '+00:00')) if a.now else datetime.now(timezone.utc)
    games = load_nfl(a.nfl)
    site = load_site(a.site)
    cache = load_cache()
    added = dropped = 0
    if a.new:
        added, dropped = merge_new(a.new, games, cache)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0) + '\n')
    players = [p['player'].strip() for p in sorted(site['players'], key=lambda r: r.get('order', 0)) if p['player'].strip() != BOT]
    picks = family_picks(site, cache, games)

    weeks = sorted({g['week'] for g in games})
    wk_games = {w: [g for g in games if g['week'] == w] for w in weeks}
    complete = [w for w in weeks if all(g['final'] for g in wk_games[w])]
    pending = [w for w in weeks if w not in complete]
    cur = pending[0] if pending else None
    last = max([w for w in complete if cur is None or w < cur], default=None)
    if last is None:
        sys.exit('No finished week yet.')
    # make sure finished weeks have picks: warn if a finished week has none (sheet rows not copied)
    pick_weeks = Counter(p['week'] for p in picks)
    missing = [w for w in complete if pick_weeks[w] == 0]

    # ---------- league ----------
    wk = defaultdict(lambda: [0, 0])
    for p in picks:
        w = p['g']['winner']
        if w == 'TIE': continue
        wk[(p['week'], p['player'])][0 if p['pick'] == w else 1] += 1
    done = [w for w in complete if w <= last]
    tot = {pl: [sum(wk[(w, pl)][0] for w in done), sum(wk[(w, pl)][1] for w in done)] for pl in players}
    order = sorted(players, key=lambda pl: (-tot[pl][0], tot[pl][1]))
    race = {pl: [] for pl in players}; cum = {pl: 0 for pl in players}; leaders = []
    for w in done:
        for pl in players: cum[pl] += wk[(w, pl)][0]
        top = max(cum.values())
        for pl in players: race[pl].append(top - cum[pl])
        leaders.append([pl for pl in players if cum[pl] == top])
    weekly = []
    for w in done:
        decided = sum(1 for g in wk_games[w] if g['winner'] != 'TIE')
        best = max(wk[(w, pl)][0] for pl in players)
        weekly.append({'week': w, 'score': best, 'of': decided, 'who': [pl for pl in players if wk[(w, pl)][0] == best]})
    top_counts = Counter(pl for x in weekly for pl in x['who'])
    most_tops = max(top_counts.values()); most_tops_who = [pl for pl in players if top_counts[pl] == most_tops]
    avg = [(x['week'], sum(wk[(x['week'], pl)][0] for pl in players) / len(players), x['of']) for x in weekly]
    tough = min(avg, key=lambda t: t[1] / t[2])
    best_week = max(((wk[(w, pl)][0], wk[(w, pl)][1], w, pl) for w in done for pl in players), key=lambda t: (t[0] - t[1], t[0]))
    by_game = defaultdict(list)
    for p in picks: by_game[id(p['g'])].append(p)
    gobj = {id(g): g for g in games}
    un = [0, 0]; crowd = {pl: [0, 0] for pl in players}; lone = []
    for k, ps in by_game.items():
        g = gobj[k]
        if g['winner'] == 'TIE' or g['week'] > last: continue
        if len(ps) >= len(players) and len({p['pick'] for p in ps}) == 1:
            un[0 if ps[0]['pick'] == g['winner'] else 1] += 1
        if len(ps) >= 6:
            for p in ps:
                share = sum(1 for q in ps if q['pick'] == p['pick']) / len(ps)
                if share <= 1 / 3: crowd[p['player']][0 if p['pick'] == g['winner'] else 1] += 1
                if share * len(ps) == 1: lone.append((g['week'], p['player'], p['pick'], g))
    crowd_rows = sorted(({'player': pl, 'w': v[0], 'l': v[1]} for pl, v in crowd.items()), key=lambda r: (-r['w'], r['l']))

    # ---------- NFL ----------
    rec = records(games)
    fav = [0, 0]
    for g in games:
        pr = g['final'] and g['winner'] != 'TIE' and prob(g)
        if pr and pr[0] != pr[1]:
            fav[0 if (pr[0] > pr[1]) == (g['winner'] == g['away']) else 1] += 1
    cur_games = wk_games.get(cur, [])
    cur_final = [g for g in cur_games if g['final']]
    ref_games = cur_final if cur_final else wk_games[last]
    ref_week = cur if cur_final else last
    upsets = []
    for g in ref_games:
        pr = prob(g)
        if not pr or g['winner'] == 'TIE': continue
        wp = pr[0] if g['winner'] == g['away'] else pr[1]
        loser = g['home'] if g['winner'] == g['away'] else g['away']
        upsets.append((wp, g['winner'], loser, max(g['sa'], g['sh']), min(g['sa'], g['sh']), g))
    upsets.sort(key=lambda u: u[0])
    lines = []
    for g in cur_games:
        pr = prob(g)
        ap = round(100 * pr[0]) if pr else 50
        lines.append({'away': g['away'], 'home': g['home'], 'away_pct': ap, 'home_pct': 100 - ap,
                      'away_rec': rs(rec[g['away']]), 'home_rec': rs(rec[g['home']]), 'div': g['div'], 'site': '',
                      'kick': kick_str(g), 'final': [g['sa'], g['sh']] if g['final'] else None})
    open_games = [g for g in cur_games if g['kick'] > now and not g['final']]
    playing = {t for g in cur_games for t in (g['away'], g['home'])}
    byes = sorted(set(NICK.values()) - playing) if cur else []

    facts = []
    if upsets:
        u = upsets[0]
        if u[0] < 0.5:
            facts.append({'big': f"{u[3]}–{u[4]}", 'label': f"{u[1]} over the {u[2]}",
                          'detail': f"Week {ref_week}'s biggest upset{' so far' if ref_week == cur else ''}: the {u[2]} were {round(100 * (1 - u[0]))}% favorites"})
        else:
            facts.append({'big': f"{len(upsets)}–0", 'label': f"favorites in Week {ref_week}{' so far' if ref_week == cur else ''}",
                          'detail': 'No upsets: every betting favorite has won'})
    def pct_of(g):
        pr = prob(g); return (max(pr) if pr else 0.5, pr)
    if open_games:
        fg = max(open_games, key=lambda g: pct_of(g)[0]); pr = prob(fg)
        if pr:
            ft, fo = (fg['away'], fg['home']) if pr[0] > pr[1] else (fg['home'], fg['away'])
            facts.append({'big': f"{round(100 * max(pr))}%", 'label': f"{ft} to beat the {fo}",
                          'detail': f"Week {cur}'s biggest favorite ({rs(rec[ft])} against {rs(rec[fo])})"})
        cg = min(open_games, key=lambda g: abs(pct_of(g)[0] - 0.5)); pr = prob(cg)
        if pr and cg is not fg:
            hi, lo = round(100 * max(pr)), 100 - round(100 * max(pr))
            facts.append({'big': f"{hi}/{lo}", 'label': f"{cg['away']} at {cg['home']}", 'detail': 'The closest game still to play'})
        ng = min(open_games, key=lambda g: g['kick'])
        day = ng['kick'].strftime('%A'); night = ng['kick'].hour >= 19
        facts.append({'big': ng['kick'].strftime('%I:%M %p').lstrip('0'), 'label': f"{ng['away']} at {ng['home']}",
                      'detail': f"Next kickoff: {'Thanksgiving' if is_thanksgiving(ng['kick']) else day}{' night' if night and not is_thanksgiving(ng['kick']) else ''} (Eastern time)"})
    if len(facts) < 4 and fav[0] + fav[1]:
        facts.append({'big': f"{fav[0]}–{fav[1]}", 'label': 'favorites this season', 'detail': f"Betting favorites have won {round(100 * fav[0] / (fav[0] + fav[1]))}% of decided games"})
    facts = facts[:4]

    # ---------- Chicago Bears ----------
    north = sorted(NORTH, key=lambda t: (-(rec[t][0] + rec[t][2] / 2) / max(1, sum(rec[t])), -rec[t][0]))
    bpos = north.index('Bears') + 1
    leader = north[0] if north[0] != 'Bears' else north[1]
    gb = ((rec[north[0]][0] - rec['Bears'][0]) + (rec['Bears'][1] - rec[north[0]][1])) / 2
    gba = ((rec['Bears'][0] - rec[leader][0]) + (rec[leader][1] - rec['Bears'][1])) / 2 if north[0] == 'Bears' else 0
    half = lambda x: (str(int(x)) if x >= 1 else '') + ('½' if x % 1 else '') if x else '0'
    bg = [g for g in games if 'Bears' in (g['away'], g['home'])]
    season, results, nxt = [], [], None
    for wkn in range(1, 19):
        g = next((x for x in bg if x['week'] == wkn), None)
        if not g: season.append({'week': wkn, 'bye': True}); continue
        home = g['home'] == 'Bears'; opp = g['away'] if home else g['home']
        s = {'week': wkn, 'opp': opp, 'home': home, 'div': g['div']}
        if g['final']:
            us, them = (g['sh'], g['sa']) if home else (g['sa'], g['sh'])
            s.update(res='W' if us > them else 'L' if us < them else 'T', score=f"{us}–{them}"); results.append((s, g, us, them))
        else:
            s['when'] = 'In progress' if g['kick'] <= now else when_str(g)
            if nxt is None:
                pr = prob(g)
                nxt = dict(s, g=g, pct=round(100 * (pr[1] if home else pr[0])) if pr else None)
                s['next'] = True
                if nxt['pct'] is not None: s['pct'] = nxt['pct']
        season.append(s)
    bfacts = []
    if nxt:
        g = nxt['g']; tv = tv_name(g)
        vs = f"Bears {'vs' if nxt['home'] else 'at'} the {nxt['opp']}"
        if nxt['pct'] is not None:
            sp = abs(float(g['spread'] or 0))
            line = (f"The betting line makes Chicago {sp:g}-point {'favorites' if nxt['pct'] > 50 else 'underdogs'}, about a {nxt['pct']}% chance to win."
                    if sp else f"The betting line gives Chicago about a {nxt['pct']}% chance to win.")
            when_txt = (f"{tv}, {g['kick'].strftime('%b')}\u00a0" if tv else f"{g['kick'].strftime('%a %b')}\u00a0") + f"{g['kick'].day} at {g['kick'].strftime('%I:%M %p').lstrip('0')} ET."
            bfacts.append({'big': f"{nxt['pct']}%", 'label': vs, 'detail': when_txt + ' ' + line})
        else:
            bfacts.append({'big': when_str(g), 'label': vs, 'detail': 'Betting line not posted yet.'})
    if results:
        ls, lg, lus, lthem = results[-1]
        streak = 0
        for s, *_ in reversed(results):
            if s['res'] != ls['res']: break
            streak += 1
        last5 = sum(1 for s, *_ in results[-5:] if s['res'] == 'W')
        where = 'at Soldier Field' if ls['home'] else f"at the {ls['opp']}"
        word = {'W': ('over', 'wins'), 'L': ('fall to', 'losses'), 'T': ('tie', 'ties')}[ls['res']]
        tail = f"{W[streak].capitalize()} straight {word[1]}" if streak > 1 else ('A win' if ls['res'] == 'W' else 'A loss' if ls['res'] == 'L' else 'A tie')
        if len(results) >= 5: tail += f", {W[last5]} of the last five."
        else: tail += '.'
        bfacts.append({'big': f"{lus}–{lthem}", 'label': f"Bears {word[0]} the {ls['opp']}", 'detail': f"Week {ls['week']} {where}. {tail}"})
    losses = [s['opp'] for s, *_ in results if s['res'] == 'L']
    div_l = [o for o in losses if o in NORTH]
    div_note = (f" {'Both' if len(losses) == 2 else 'All ' + W[len(losses)]} Bears losses came in the division." if losses and len(div_l) == len(losses) and len(losses) > 1 else '')
    standings = 'NFC North: ' + ', '.join(f"{t} {rs(rec[t])}" for t in north) + '.'
    if north[0] == 'Bears':
        bfacts.append({'big': half(gba) if gba else 'Tied', 'label': f"game{'s' if gba != 1 else ''} ahead of the {leader}" if gba else 'for first in the NFC North', 'detail': standings + div_note})
    else:
        bfacts.append({'big': half(gb), 'label': f"game{'s' if gb != 1 else ''} behind the {north[0]}", 'detail': standings + div_note})
    bkeys = [k for k, ps in by_game.items() if 'Bears' in (gobj[k]['away'], gobj[k]['home'])]
    on_b = sum(1 for k in bkeys for p in by_game[k] if p['pick'] == 'Bears')
    all_b = sum(len(by_game[k]) for k in bkeys)
    doubt = sorted((k for k in bkeys if any(p['pick'] != 'Bears' for p in by_game[k])), key=lambda k: gobj[k]['week'])
    if not bkeys:
        dtxt = ''
    elif not doubt:
        dtxt = 'Everyone has taken Chicago in every Bears game.'
    elif len(doubt) == 1:
        k = doubt[0]; g = gobj[k]; bel = [p['player'] for p in by_game[k] if p['pick'] == 'Bears']
        opp = g['away'] if g['home'] == 'Bears' else g['home']; s = next(x for x in season if x['week'] == g['week'])
        if bel:
            dtxt = f"Everyone took Chicago every week except Week {g['week']}, when only {names(bel)} backed them against the {opp}. The Bears {'won' if s['res'] == 'W' else 'lost'} {s['score']}."
        else:
            dtxt = f"Everyone took Chicago every week except Week {g['week']}, when nobody did. The Bears {'won' if s['res'] == 'W' else 'lost'} {s['score']} against the {opp}."
    else:
        right = sum(1 for k in bkeys for p in by_game[k] if p['pick'] == gobj[k]['winner'])
        dtxt = f"The whole family took Chicago in {W[len(bkeys) - len(doubt)]} of {W[len(bkeys)]} Bears games. Family record picking Bears games: {right}–{all_b - right}."
    if bkeys:
        bfacts.append({'big': f"{on_b} of {all_b}", 'label': 'family picks on the Bears', 'detail': dtxt})
    bears = {'record': rs(rec['Bears']), 'place': f"{ORD[bpos].capitalize()} in the NFC North",
             'next': (f"Next: {'vs' if nxt['home'] else 'at'} the {nxt['opp']}, {nxt['when']}" if nxt else 'Regular season complete'),
             'season': season, 'facts': bfacts}

    # ---------- page data ----------
    nowct = now.astimezone(CT)
    phase = (f"Week {cur} {'in progress' if cur_final else 'preview'}" if cur else 'Regular season complete')
    pulse = [
      {'big': f"{un[0]}–{un[1]}", 'label': f"When all {W[len(players)]} agreed", 'detail': f"{round(100 * un[0] / max(1, un[0] + un[1]))}% of unanimous picks won"},
      {'big': f"Week {tough[0]}", 'label': 'Toughest week', 'detail': f"Family average {tough[1]:.1f} of {tough[2]} right"},
      {'big': f"{best_week[0]}–{best_week[1]}", 'label': 'Best single week', 'detail': f"{best_week[3]}, Week {best_week[2]}"},
      {'big': str(most_tops), 'label': 'Most weekly top scores', 'detail': names(most_tops_who)},
    ]
    for f in facts + bfacts: f['detail'] = nb(f['detail'])
    page = {'written': f"Updated {nowct.strftime('%A, %b')} {nowct.day}, {nowct.year} · {phase}",
            'take': [], 'facts': facts, 'bears': bears, 'byes': names(byes) if byes else '', 'lines': lines,
            'lines_title': f"Week {cur} at a glance" if cur else f"Week {last} final scores",
            'pulse_note': f"Weeks 1–{last}, every finished game.",
            'race': {'weeks': done, 'series': [{'player': pl, 'back': race[pl]} for pl in order], 'highlight': order[:3]},
            'weekly': weekly, 'pulse': pulse, 'crowd': crowd_rows,
            'sources': f"NFL records, schedule and betting lines: nflverse (github.com/nflverse/nfldata), {nowct.strftime('%b')} {nowct.day}, {nowct.year}. League numbers: the league workbook (Weeks 1–6) and the league pick sheet (Week 7 on)."}

    # ---------- summary for writing the take (finished games only) ----------
    S = []
    S.append(f"# Ditkatron Thoughts fact sheet: {nowct.strftime('%A %b %d, %Y %I:%M %p')} Central")
    S.append(f"Phase: {phase}. Finished weeks: 1–{last}. Picks only from FINISHED games appear below; never mention or guess anyone's pick for a game that has not finished.")
    if missing: S.append(f"WARNING: no family picks found for finished week(s) {missing}. Copy those rows from the pick sheet and run prep again before publishing.")
    S.append(f"Pick rows merged this run: {added} added, {dropped} skipped (not final, Ditkatron, or unknown team).")
    S.append('\n## Standings through Week %d' % last)
    prev_tot = {pl: [sum(wk[(w, pl)][0] for w in done[:-1]), 0] for pl in players}
    prev_order = sorted(players, key=lambda pl: -prev_tot[pl][0])
    rank = lambda o, pl, t: 1 + sum(1 for q in o if t[q][0] > t[pl][0])
    lead_w = tot[order[0]][0]
    for pl in order:
        S.append(f"- {pl}: {tot[pl][0]}–{tot[pl][1]}, {'leader' if tot[pl][0] == lead_w else str(lead_w - tot[pl][0]) + ' back'}; Week {last}: {wk[(last, pl)][0]}–{wk[(last, pl)][1]}; rank was {rank(prev_order, pl, prev_tot)} after Week {done[-2] if len(done) > 1 else '-'}")
    S.append(f"Leaders by week: " + '; '.join(f"Wk {w}: {names(ls)}" for w, ls in zip(done, leaders)))
    S.append(f"Week {last} top score: {names(weekly[-1]['who'])} at {weekly[-1]['score']}–{weekly[-1]['of'] - weekly[-1]['score']}.")
    S.append(f"Weekly top-score counts: " + ', '.join(f"{pl} {top_counts[pl]}" for pl in order if top_counts[pl]))
    S.append(f"Going against the crowd (picks made by a third or fewer): " + ', '.join(f"{r['player']} {r['w']}–{r['l']}" for r in crowd_rows))
    S.append(f"Unanimous picks: {un[0]}–{un[1]}. Toughest week: {tough[0]}. Best single week: {best_week[3]}, Week {best_week[2]} ({best_week[0]}–{best_week[1]}).")
    def game_line(g):
        pr = prob(g); fv = ''
        if pr: fv = f"; betting favorite {g['away'] if pr[0] > pr[1] else g['home']} {round(100 * max(pr))}%"
        return f"{g['away']} {g['sa']}, {g['home']} {g['sh']}{fv}"
    for w, label in ([(last, f"Week {last} results")] + ([(cur, f"Week {cur} finished games so far")] if cur_final else [])):
        S.append(f"\n## {label}")
        for g in wk_games[w]:
            if not g['final']: continue
            ps = by_game.get(id(g), [])
            right = [p['player'] for p in ps if p['pick'] == g['winner']]
            wrong = [p['player'] for p in ps if p['pick'] != g['winner']]
            S.append(f"- {game_line(g)}. Family: {len(right)} right, {len(wrong)} wrong" + (f"; missed: {names(wrong)}" if 0 < len(wrong) <= 3 else '') + (f"; got it: {names(right)}" if 0 < len(right) <= 3 else ''))
        if w == cur:
            S.append('Week %d records so far: ' % cur + ', '.join(f"{pl} {wk[(cur, pl)][0]}–{wk[(cur, pl)][1]}" for pl in players))
    if open_games:
        S.append(f"\n## Week {cur} games still to play (no picks are visible for these; do not mention any)")
        for g in open_games:
            pr = prob(g)
            S.append(f"- {kick_str(g)} ET: {g['away']} ({rs(rec[g['away']])}) at {g['home']} ({rs(rec[g['home']])})" + (f"; {g['away'] if pr[0] > pr[1] else g['home']} {round(100 * max(pr))}% favorite" if pr else '') + (' [division]' if g['div'] else ''))
    if byes: S.append(f"On bye: {names(byes)}.")
    S.append('\n## NFL notes')
    unbeaten = [t for t, v in rec.items() if v[1] == 0 and v[2] == 0]
    winless = [t for t, v in rec.items() if v[0] == 0]
    S.append(f"Unbeaten: {', '.join(f'{t} {rs(rec[t])}' for t in unbeaten) or 'none'}. Winless: {', '.join(f'{t} {rs(rec[t])}' for t in winless) or 'none'}. Favorites this season: {fav[0]}–{fav[1]}.")
    for f in facts: S.append(f"- Tile: {f['big']} | {f['label']} | {f['detail']}")
    S.append('\n## Chicago Bears')
    S.append(f"{bears['record']}, {bears['place']}. {bears['next']}.")
    for f in bfacts: S.append(f"- {f['big']} | {f['label']} | {f['detail']}")
    if a.roast:
        R = a.roast
        if R in players:
            S.append(f"\n## {R} (running bit: they have been complaining about Ditkatron)")
            S.append(f"Record {tot[R][0]}–{tot[R][1]}, rank {rank(order, R, tot)} of {len(players)}, {lead_w - tot[R][0]} back of first. Weeks led: {sum(1 for ls in leaders if R in ls)} (" + ', '.join(f'Wk {w}' for w, ls in zip(done, leaders) if R in ls) + ').')
            S.append(f"Weekly records: " + ', '.join(f"Wk {w} {wk[(w, R)][0]}–{wk[(w, R)][1]}" for w in done) + (f"; Week {cur} so far {wk[(cur, R)][0]}–{wk[(cur, R)][1]}" if cur_final else '') + '.')
            S.append(f"Weekly top scores: {top_counts[R]}. Against the crowd: {crowd[R][0]}–{crowd[R][1]}.")
            mine = [x for x in lone if x[1] == R and x[0] >= max(1, last - 2)]
            if mine:
                S.append('Lone-wolf picks (only one in the family) in recent weeks: ' + '; '.join(f"Wk {w} {pk} ({'won' if g['winner'] == pk else 'lost'}, {g['away']} {g['sa']}–{g['home']} {g['sh']})" for w, _, pk, g in mine))
    S.append('\n## Last published take (do not repeat its jokes)')
    old = THOUGHTS_RE.search(Path(a.site).read_text())
    if old:
        try:
            for p in json.loads(old.group(2)).get('take', []): S.append(f"> {p}")
        except json.JSONDecodeError:
            pass
    Path(a.out).write_text(json.dumps(page, ensure_ascii=False, indent=1))
    Path(a.summary).write_text('\n'.join(S) + '\n')
    print('\n'.join(S))


# ---------------- publish ----------------
def cmd_publish(a):
    page = json.loads(Path(a.base).read_text())
    take = json.loads(Path(a.take).read_text())
    paras = take['paragraphs'] if isinstance(take, dict) else take
    paras = [p.strip() for p in paras if p and p.strip()]
    problems = []
    if not 3 <= len(paras) <= 6: problems.append(f'need 3-6 paragraphs, got {len(paras)}')
    for p in paras:
        if len(p) > 900: problems.append('a paragraph is over 900 characters')
        if re.search(r'https?://|token=|\b\d{3}[-. )]\s?\d{3}[-. ]\d{4}\b|@', p): problems.append('a paragraph has a link, token, phone number or email: ' + p[:60])
    if problems:
        sys.exit('publish refused: ' + '; '.join(problems))
    page['take'] = paras
    html = Path(a.site).read_text()
    blob = json.dumps(page, ensure_ascii=False, indent=1).replace('</', '<\\/')
    new, n = THOUGHTS_RE.subn(lambda m: m.group(1) + blob + m.group(3), html, count=1)
    if n != 1:
        sys.exit('publish refused: window.__PK_THOUGHTS not found in index.html')
    Path(a.site).write_text(new)
    print(f"index.html updated: {len(paras)} paragraphs, {len(page['facts'])} NFL tiles, {len(page['bears']['facts'])} Bears tiles, {len(page['lines'])} games.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    n = sub.add_parser('need'); n.add_argument('--nfl', required=True)
    p = sub.add_parser('prep')
    p.add_argument('--site', required=True); p.add_argument('--nfl', required=True)
    p.add_argument('--new', help='JSON list of pick-sheet rows [week, game, player, pick]')
    p.add_argument('--now', help='ISO time, default now'); p.add_argument('--roast', default='Michael & Katie')
    p.add_argument('--out', default='thoughts_base.json'); p.add_argument('--summary', default='thoughts_summary.md')
    u = sub.add_parser('publish')
    u.add_argument('--site', required=True); u.add_argument('--base', default='thoughts_base.json'); u.add_argument('--take', required=True)
    a = ap.parse_args()
    {'need': cmd_need, 'prep': build, 'publish': cmd_publish}[a.cmd](a)


if __name__ == '__main__':
    main()
