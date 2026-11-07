# Seasonal themes

The site can dress up for a season (Halloween, Thanksgiving, and so on). Every theme works the same way:
one script near the top of `index.html` adds a class to `<html>` (for example `class="halloween"`), and
everything that belongs to the theme is switched on only while that class is there. With no class, the
site is the plain everyday look.

**Halloween is the blueprint.** It has been taken off the schedule, but all of its pieces are still in
`index.html`, so it can be previewed, reused next October, or copied as the starting point for a new theme.

## Turning a theme on and off

The schedule is the `SCHEDULE` list in the first `<script>` of `index.html`:

```js
var SCHEDULE=[
  ["thanksgiving","2026-11-16T05:00:00Z","2026-12-01T12:00:00Z"]
];
```

Each row is `[class, start, end]`, with times in UTC: the start is included and the end is not. Central
time is UTC−5 in summer and UTC−6 in winter, so midnight Central on Nov 16 is `2026-11-16T06:00:00Z`.
The first matching row wins.

- **Take a theme down:** delete its row. Its code stays dormant.
- **Bring Halloween back:** add a row such as `["halloween","2027-10-01T05:00:00Z","2027-11-02T05:00:00Z"]`.
- **Preview without scheduling:** add `?theme=halloween`, `?theme=thanksgiving` or `?theme=plain` to the
  address. A new theme's class name has to be added to that `?theme=` pattern in the same script.

## Anatomy of a theme (Halloween as the example)

Each piece is optional, and each one is keyed off the `<html>` class. Halloween uses the prefix `hw-`
and Thanksgiving uses `tg-`; a new theme should pick its own short prefix.

| Piece | Where it is in `index.html` | Halloween |
|---|---|---|
| **Schedule and preview** | first `<script>` in `<head>`: `SCHEDULE` and the `?theme=` pattern | not scheduled; `?theme=halloween` |
| **Tab and home-screen icons** | same script, `ic` object: `[32×32 favicon, 180×180 apple-touch icon]` as base64 PNGs (opaque, no transparency) | Halloween icon set |
| **Browser bar colour** | same script, `tc` object: `[light, dark]` | `#130e1d` for both |
| **Colours** | CSS block `Halloween (blueprint theme …)`: `html:root.halloween { --color-bg … }` redefines the site's colour tokens, so every card, chart and table follows | one night-time palette whatever the visitor's light/dark setting |
| **Show/hide helper** | `.hw-only { display: none; }` and `html.halloween .hw-only { display: block; }` | anything marked `hw-only` appears only in the theme |
| **Decorations in the page** | `hw-only` elements right after `<body>`: `hw-music` button, `hw-sky` (flying bats), `hw-web`, `hw-moon`, `hw-bats` | inline SVG only, no outside images |
| **Occasional visitors** | script `Halloween extras on the full-screen bats layer` (CSS: `lightning and occasional visitors`) | lightning, a ghost, a spider, glowing eyes, a witch; test by hand with `window.hwSpooky` |
| **Music** | songs are synthesized in the `SpookyMusic` engine (no audio files); the `Seasonal music` script's `CFG` lists each theme's songs, button label and the key that remembers "music off" on a device | `bach`, `stalker`, `lake` |
| **Ditkatron artwork** | images in `img/` (`ditkatron_bust/full/face.webp`), listed in `window.__DKX`; CSS block `Ditkatron 9000 in the Halloween theme`; the `T` table in the `Ditkatron 9000 artwork` script sets eye positions, his tagline and speech bubble, and which sky layer he rises in | portrait on the Thoughts card, face on the standings, rises with the lightning |
| **Small touches** | e.g. the Bears corner uses `html.halloween` to pick its dark colours | |

Thanksgiving adds one piece Halloween doesn't have: a `tg-only` card in the page (`tg-heritage`) with
holiday history and the holiday's games.

## Making a new theme

1. Choose a class name and prefix (for example `christmas` and `xm-`).
2. Copy the Halloween pieces you want, renaming `halloween`/`hw-` to the new names: the colour block, the
   show/hide helper, the decorations, and optionally the visitors script, a `CFG` entry for music, and a
   `__DKX` / `T` entry for Ditkatron artwork.
3. Add the class to the `ic` and `tc` objects and to the `?theme=` pattern.
4. Preview with `?theme=<name>` on a phone and a computer, in light and dark mode, and with reduced motion
   turned on (animations must stop).
5. Add a `SCHEDULE` row when it should go live.

## Rules every theme follows

- Everything is served from the site itself: inline SVG, `data:` icons, files in `img/`, synthesized
  music. Nothing loads from another server.
- Animations respect the visitor's reduced-motion setting and pause while the tab is hidden.
- Music never starts until the browser allows it, and the corner button turns it off for good on that device.
- The daily Ditkatron Thoughts task never touches theme code.
