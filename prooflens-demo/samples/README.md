# Samples

A few generated placeholder images plus `labels.csv` so `python compare.py samples`
runs out of the box. These are flat synthetic images — fine for exercising the
deterministic checks and the bake-off plumbing, but **not** representative of real
proof photos.

To run a meaningful bake-off, drop your own images here (or in any folder) and add
a `labels.csv`:

```csv
filename,label
my_meeting.jpg,good
photo_of_screen.jpg,bad
poster.jpg,bad
```

- `good` = a genuine in-person meeting photo
- `bad`  = screen photo / designed graphic / meme / no people / irrelevant

Then: `python compare.py <folder>`
