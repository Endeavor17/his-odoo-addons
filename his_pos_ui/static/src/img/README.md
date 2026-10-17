# Wallpapers

One per point of sale, named for the theme that loads it.

| File | Theme | Subject |
|---|---|---|
| `copy_center.webp` | `copy_center` | the copier / reprography counter |
| `restaurant.webp` | `restaurant` | plated service |
| `cafeteria.webp` | `cafeteria` | espresso being pulled |

WebP, 678 × 452 (restaurant 720 × 404), about 30 KB each. They are
decorative: no alt text, and no information is carried by them that is not
also written on the screen.

**Source and licence: not recorded.** The files arrived with the adopted POS
theme (commit 05297db) without a note of where they come from. Before the next
release, record each photograph's source and licence here, or replace it with
a photograph HIS owns. At 678 px they are also upscaled on a 1440 px screen;
a 1600 px export at the same weight budget (about 150 KB in WebP) would be
sharp.

The HIS logo shown in the till's bar is his_theme's
(`his_theme/static/img/his_logo_white.png`), not this module's.

**A missing file is not a failure.** `tokens.scss` sets `--his-wallpaper-color`
alongside `--his-wallpaper`, so an absent image degrades to the theme's deep
tone and the entry screen still looks deliberate rather than broken.

The scrim is applied in CSS (`login.scss`), not baked into the image. Export a
clean photograph; do not pre-darken it.
