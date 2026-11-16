# Designing your own scorebug

A scorebug is not one picture. It is a stack of small pieces the game places, tints and fills in while it runs.
You design it by changing those pieces, not by painting a finished bug.

## What it is made of

| Piece | What the game does with it |
| --- | --- |
| Frame | The plate behind everything. A flat texture, stretched to size. |
| Team rows | One template, used twice. The game paints it the team's colour and drops in the logo, abbreviation and score. |
| Info block | Inning, bases, count, outs. Each is a switch with one look per state (0, 1, 2 outs; eight base states). |
| Batter and pitcher bars | Tall sheets that slide up from behind the bug. Only the part above it shows. |
| Pop-ups | Player card, home run, strikeout, the between-innings block. They fade or slide in on a cue. |

Text is never part of a picture. Names, scores and the count are text boxes filled in live, drawn in a game font.

## The quick way

1. **Scoreboards › Layout**, pick Theme 1. Start from **Styles › Wide Top Bar** or the stock bug.
2. Set a moment in the **Game** row: teams, score, inning, count, outs, runners. Type any team's abbreviation
   and its real logo and colour come up. Check the awkward cases: 11 runs, a full count, bases loaded, two outs.
3. Click a piece and use **Colour**, **Opacity**, **Move**, **Size**, **Hide**. Click a text box for its font,
   size and alignment.
4. Open the pop-ups one at a time and play the animations, so you see what slides over what.
5. **Save as Style…** to keep it. **Save to My Mod**, Apply, and look at it in a game.

## From Photoshop

Work on a 1920 x 1080 canvas, which is the size the game lays out on. Paste a screenshot of a real game
underneath so you can judge size against the field.

- **One layer per piece.** Frame, row plate, score box, base diamond, out light and so on. No text, no logos,
  no team colours baked in: the game adds those.
- **Paint tintable pieces in white and greys.** The game multiplies a texture by the piece's colour, so white
  takes the colour exactly and grey takes it darker. A piece you paint in colour keeps that colour everywhere.
- **Keep the transparency.** Export each layer as a PNG with alpha, trimmed to the piece.
- **Match the size of what you replace**, or a clean multiple of it (2x is fine and looks sharper). The
  **Its textures** list shows every texture the overlay draws.
- **States are separate art.** An out light needs an off and an on. A base needs empty and occupied.

Then in the sandbox: click the piece, **Replace PNG**, pick your export. Move and resize until the preview matches
your mockup, and set the fonts.

For lettering, **Import Font…** takes a `.ttf` or `.otf` and draws it into the game in place of one of its fonts.

## Building one from nothing

A design file describes a scorebug as data. The manager compiles it into the game's own format, so the game draws
it and fills it in like one of its own. Nothing of the stock bug is left on screen.

```json
{"name": "MTS_Mine", "size": [700, 46], "pieces": [
  {"box": [0, 0, 700, 46], "color": "#0c0c0c", "opacity": 88},
  {"text": "^d0^", "data": ["AWAY_TEAM TEAM_PROF SHORT_NAME"], "at": [14, 5, 80, 36], "size": 30, "align": "left"},
  {"text": "^d0^", "data": ["SCORER AWAY_SCORE"], "at": [96, 5, 54, 36], "size": 30, "color": "#ffd24a"},
  {"logo": "home", "kind": 2, "at": [640, 3, 40, 40]},
  {"team": "home", "at": [186, 0, 150, 46], "opacity": 70},
  {"switch": "IG IS_BOTTOM", "at": [354, 5, 50, 36], "looks": [
    [{"text": "TOP", "at": [0, 0, 50, 36], "size": 22}],
    [{"text": "BOT", "at": [0, 0, 50, 36], "size": 22}]]},
  {"text": "^d0^ OUT", "data": ["SCORER OUTS"], "at": [584, 5, 104, 36], "size": 26, "align": "right"}]}
```

| Piece | What it draws |
| --- | --- |
| `box` | A filled rectangle. |
| `image` | A picture: one of the theme pack's textures by name, or a PNG of your own by its file name. |
| `text` | Words. `^d0^`, `^d1^` are live values, one query each in `data`. Without `data` the words are fixed. |
| `logo` | A team's logo, `"away"` or `"home"`, from one of the game's five logo sets (`kind` 1 to 5). |
| `team` | A box in the team's colour. |
| `tint` | A group whose boxes and images take the team's colour: white takes it exactly, grey takes it darker. Text and logos inside keep their own. `"shade": 1` uses the club's second colour. |
| `switch` | One look per value of a query: look 0 when it answers 0, look 1 for 1, and so on. |
| `group` | Pieces kept together, optionally clipped to the group's box. |

Positions are `[x, y, width, height]` inside the parent, in screen pixels. `font` is a game font number, `size` is
in pixels, `align` is left, centre or right. Add `"x"` and `"y"` at the top to place the bug on screen. The data
you can show is listed in [Game data for a scorebug](SCOREBUG_DATA.md).

`"bars": true` at the top keeps the game's batter and pitcher bars, rising from the design's top edge.

`"team_colors": {"HOU": "#eb6e1f"}` at the top gives a club a colour of your own. It replaces the game's colour
for that club everywhere the design uses `team` or `tint`, whichever side the club is on.

A PNG of your own is drawn at whatever size its piece is, so export it large and let the piece set the size. Inside
a `tint` group it takes the team's colour, so paint a plate in white and keep its gloss and rim as a second picture
outside the group. A design can carry twelve pictures. Each one takes the place of an equipment brand mark in the
theme's pack, which the scorebug never draws. Paths that are not full ones are looked for beside the design file.

`"enter"` on a piece brings it in when the scorebug first appears:
`{"from": [-60, 0], "fade": true, "frames": 20, "delay": 4}` starts it 60 pixels to the left and clear, and moves
and fades it into place over 20 frames after waiting 4. The game runs 60 frames a second.

You don't have to write the file by hand. **Styles › New Blank Design** starts one in the sandbox, and so do
**Classic Line** (one line of text along the bottom), **Line Score** (runs by inning, hits and errors),
**Team Tiles** (each club on a tile of its own colour, sliding in), **Glass Tiles** (rounded glass plates drawn
from pictures that come with the manager) and **Night Strip** (a thin strip along the top). In a design the right-hand column changes to **Layers**, **Chosen piece** and **Rule and motion**:

- **+ Box, + Text, + Logo, + Team Colour, + Image** add a piece. **+ Image** takes a PNG of your own. **Copy**
  and **Delete** act on the chosen one.
- For text, **Font** picks one of the game's fonts and **Import Font…** draws another font into the game in its
  place.
- **Layers** lists every piece, back to front, nested the way they are grouped. **Move Back** and **Move
  Forward** change what covers what. Double-click a layer to name it.
- **Drag a piece** on the screen to move it, the way you would a layer. Dragging the background still moves the
  whole scorebug. **Line it up** snaps the chosen piece to the left, centre, right, top, middle or bottom of what
  it sits in.
- **Colours of the design** shows every colour the design uses. Click one to change it everywhere: yellow scores
  to red in one go.
- **Rule** draws a piece only while something is true: pick the data, then "is", "is at least" and so on, and a
  number. An out light is a dot with the rule *SCORER OUTS is at least 1*. A lit base is a diamond with the rule
  *SCOREBAR 1ST_BASE_TAB is 1*.
- Pick a piece from the list or click it on the screen. **Chosen piece** sets its place and size, colour and
  opacity, and for text its words, the data it shows, its size and alignment.
- The last box under **Rule and motion** sets how the piece arrives: fade in, or slide in from a side. Play it from the
  Animation row, under **Design: entrance**.
- **Team Colours…** gives clubs a colour of your own: `HOU=#eb6e1f, SD=#ffc425`. Type a club in the Game row to
  see it.
- Type `^d0^` in the words where a live value goes and pick the data for it. For two values use `^d0^` and `^d1^`
  and separate the two queries with `;`.
- Drag the red box to place the whole bug.
- **Save Design…** writes the file. **Save to My Mod** and **Save as Style…** work as they do for any layout.

- A rule can ask two things, joined by **and** or **or**: *balls is 3* and *strikes is 2* is a full count.
- A piece with a rule and a motion arrives each time its rule comes true. That is how **Night Strip** drops its
  FULL COUNT tag.

A new piece goes into the group you have chosen. In the file a rule is
`"when": {"data": "SCORER OUTS", "is": ">=", "value": 2}` on any piece, two rules are
`"when": {"all": [rule, rule]}` (or `"any"`), and `"name"` is what the layer is called. A font imported for a
design is remembered in it as `"fonts": {"25": "Bebas Neue"}` and goes into the mod when the design is saved. **Styles › Open a Design File…** loads one.

An AI can write a design file for you: [Making a scorebug with an AI](SCOREBUG_AI.md) has the block to paste
and what to ask for.

## What a mockup needs if you hand it over

A flat picture is enough to copy a layout: where things sit, how big, what colour. To build it properly send:

- the mockup at 1920 x 1080, on a game screenshot;
- the pieces as separate PNGs, named for what they are;
- the font files;
- each state drawn once: outs, bases, top and bottom of the inning;
- a note on what should move, and from where (the batter bar drops from the top edge, the score rolls up).

## Not possible yet

- **Mixing the two.** A design replaces the whole scorebug. Adding one new piece to a stock bug, or keeping the
  stock batter bar under a design, is next.
- **More motion.** A piece can arrive, at the start or when its rule comes true. Leaving, looping and a number
  rolling over are not built.
- **More than twelve pictures.** A design's own art borrows textures the scorebug never draws, and there are
  twelve of them.
- **Pop-ups dropping down.** The bars and cards are built to rise from behind the bug. On a top bar they still
  rise, so the bar has to sit low enough to leave them room.
- **Transitions.** The wipes between plays are Bink videos (`CROSS/MOVIES/PRESENTATION/THEMEn/*.BK2`), not
  layouts. Replacing them means encoding a video, which the manager does not do.
- **Per-uniform colours.** A design can give a club its own colour, but tying a look to a City Connect or
  throwback uniform is not worked out. The preview still takes the game's colours from a table.

Starting lineups, the pre-game matchup, due up and the lower thirds are layouts like the scorebug
(`NSW/UI/GAME/PRES/PRESOSDSn`). They open in the same sandbox, without their lists filled in.
