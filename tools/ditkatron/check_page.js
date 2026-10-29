// Render check for the Ditkatron Thoughts tab: node tools/ditkatron/check_page.js index.html [shot-prefix]
// Loads the page offline (the league sheet's web app is blocked), opens the tab on a desktop and a
// phone screen, and exits non-zero if anything is wrong.
const { chromium, devices } = require('playwright');
const path = require('path');
(async () => {
  const file = path.resolve(process.argv[2] || 'index.html');
  const shot = process.argv[3];
  const b = await chromium.launch();
  let bad = 0;
  for (const [label, opts] of [['desktop', { viewport: { width: 1440, height: 1000 } }], ['phone', devices['iPhone 13']]]) {
    const c = await b.newContext(opts); const p = await c.newPage(); const errs = [];
    p.on('pageerror', (e) => errs.push(e.message));
    await p.route('https://script.google.com/**', (r) => r.fulfill({ status: 503, body: '' }));
    await p.goto('file://' + file); await p.waitForTimeout(1200);
    await p.evaluate(() => { window.SpookyMusic && SpookyMusic.stop(); });
    await p.click('#tab-insights'); await p.waitForTimeout(700);
    const r = await p.evaluate(() => {
      const T = window.__PK_THOUGHTS || {};
      const q = (s) => document.querySelectorAll(s).length;
      return { paras: q('#dk-paras p'), want: (T.take || []).length, facts: q('#dk-factgrid .dk-fact'), bears: !document.getElementById('dk-bears').hidden,
        chips: q('.dk-bg'), lines: q('.dk-line'), race: q('#dk-race-chart svg'), written: document.getElementById('dk-written').textContent,
        sw: document.documentElement.scrollWidth, w: innerWidth };
    });
    const ok = !errs.length && r.paras > 0 && r.paras === r.want && r.facts > 0 && r.bears && r.chips === 18 && r.race === 1 && r.sw <= r.w;
    if (!ok) bad++;
    console.log((ok ? 'OK   ' : 'FAIL ') + label + ' ' + JSON.stringify(r) + (errs.length ? ' errors=' + JSON.stringify(errs) : ''));
    if (shot) {
      await p.evaluate(() => document.getElementById('dk-take').scrollIntoView());
      await p.screenshot({ path: shot + '_' + label + '.png' });
    }
    await c.close();
  }
  await b.close();
  process.exit(bad ? 1 : 0);
})();
