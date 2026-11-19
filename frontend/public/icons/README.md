# App Icons

The NeuralCanvas mark is a copper **N** traced across a triangulated mesh face shown in
perspective, on a graphite tile. `favicon.svg` is the source; every raster here is generated
from it.

| File                   | Size          | Used by                                  |
| ---------------------- | ------------- | ---------------------------------------- |
| `favicon.svg`          | vector        | Modern browsers (preferred)              |
| `favicon.ico`          | 16, 32, 48 px | Fallback for browsers without SVG icons  |
| `favicon.png`          | 32 px         | PNG fallback                             |
| `apple-touch-icon.png` | 180 px        | iOS home screen (full-bleed, no corners) |

These paths are referenced from the `head()` links in `src/routes/__root.tsx`.

## Regenerating

Requires `rsvg-convert` (librsvg) and ImageMagick. Run from this directory:

```sh
for s in 16 32 48; do rsvg-convert -w $s -h $s favicon.svg -o /tmp/f$s.png; done
cp /tmp/f32.png favicon.png
magick /tmp/f16.png /tmp/f32.png /tmp/f48.png favicon.ico

# Apple touch icon: square, no rounded tile or border (iOS applies its own mask)
sed -e 's|<rect x="1" y="1" width="62" height="62" rx="14"|<rect width="64" height="64"|' \
    -e '/stroke-opacity=".35"/d' favicon.svg > /tmp/apple.svg
rsvg-convert -w 180 -h 180 /tmp/apple.svg -o apple-touch-icon.png
```
