# Wallpapers

One per point of sale, named for the theme that loads it.

| File | Theme | Subject |
|---|---|---|
| `copy_center.webp` | `copy_center` | the copier / reprography counter |
| `restaurant.webp` | `restaurant` | plated service |
| `cafeteria.webp` | `cafeteria` | espresso being pulled |

Long edge 1920px, WebP. They are decorative: no alt text, and no information is
carried by them that is not also written on the screen.

**A missing file is not a failure.** `tokens.scss` sets `--his-wallpaper-color`
alongside `--his-wallpaper`, so an absent image degrades to the theme's deep
tone and the entry screen still looks deliberate rather than broken. That is
the state the repository ships in today — the photographs are not committed.

The scrim is applied in CSS (`login.scss`), not baked into the image. Export a
clean photograph; do not pre-darken it.
