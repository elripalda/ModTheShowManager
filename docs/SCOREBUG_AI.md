# Making a scorebug with an AI

A design file is plain text, so any chat AI can write one. Give it the rules below, describe what you want, save
the answer as a `.json` file and open it from **Styles › Open a Design File…**. Then fix the details by hand in the
sandbox: drag pieces, change colours, swap fonts.

## What to paste first

Copy this whole block into the chat before you describe your scorebug.

```text
You are writing a scorebug design file for Mod the Show Manager (MLB The Show 26). Answer with one JSON object and
nothing else.

Shape:
{"name": "MTS_<OneWord>", "size": [width, height], "x": left, "y": top, "bars": false, "pieces": [ ... ]}

The screen is 1920 x 1080. "x" and "y" place the design's top-left corner. Every piece has "at": [x, y, width,
height], measured inside whatever it sits in. Pieces are drawn in order, so later ones cover earlier ones.

Pieces:
- {"box": [x, y, w, h], "color": "#rrggbb", "opacity": 0-100}                  a filled rectangle
- {"text": "WORDS", "at": [...], "size": px, "color": "#rrggbb", "align": "left|centre|right", "font": 25}
- {"text": "^d0^", "data": ["QUERY"], "at": [...]}                             live text, one query per ^dN^
- {"logo": "away|home", "kind": 2, "at": [...]}                                the club's logo (kind 1-5)
- {"team": "away|home", "at": [...], "opacity": 0-100}                         a box in the club's colour
- {"tint": "away|home", "at": [...], "group": [pieces]}                        boxes/images inside take the colour
- {"group": [pieces], "at": [...], "clip": true|false}                         pieces kept together
- {"image": "file.png", "at": [...]}                                           a picture beside the design file

Any piece may add:
- "name": "what it is"                                                         shown in the layers list
- "when": {"data": "QUERY", "is": "==|!=|>|>=|<|<=", "value": N}                 drawn only while true
- "when": {"all": [rule, rule]} or {"any": [rule, rule]}                       and / or
- "enter": {"from": [dx, dy], "frames": 20, "delay": 0}                        slides and fades in (60 frames = 1 s)

Queries you may use (write them exactly):
AWAY_TEAM TEAM_PROF SHORT_NAME, HOME_TEAM TEAM_PROF SHORT_NAME, SCORER AWAY_SCORE, SCORER HOME_SCORE,
SCOREBAR INNING_STR [ 0 ] (the number), SCOREBAR INNING_STR [ 1 ] (like "6TH"), IG IS_BOTTOM (0 top, 1 bottom),
IG BALLS, IG STRIKES, SCORER OUTS, SCOREBAR 1ST_BASE_TAB, SCOREBAR 2ND_BASE_TAB, SCOREBAR 3RD_BASE_TAB (1 when a
runner is on), CURRENT_BATTER SEASON_STATS AVG, BoxScore HITS [ 0 ], BoxScore HITS [ 1 ], BoxScore ERRORS [ 0 ],
BoxScore ERRORS [ 1 ], BoxScore INNING_VAL [ team , inning ] (team 0 away, 1 home; inning from 0).

Rules:
- Whole numbers only for positions and sizes.
- Fonts are game font numbers: 25 is a bold upright sans, 37 is heavy slanted digits, 23 is a slanted sans.
- Give every text a box wider than its longest value (scores reach two digits, club names four letters).
- Leave at least 6 pixels between pieces that should not touch.
- An "on" light is a second piece on top of the "off" one, with a "when" rule.
- Do not invent queries, piece types or keys.
```

## Then describe it

Say what a designer would say. The more of these you pin down, the less you fix afterwards:

- **Where it sits and how big.** "A strip 760 wide and 44 tall, centred along the top, 44 from the top edge."
- **What it shows.** "Both clubs with logos and scores, the inning with an arrow for top or bottom, the three bases,
  balls and strikes, outs as two dots."
- **The look.** "Flat black at 85% with a thin white line on top. Scores in yellow. Club names in white."
- **Team colour.** "Each club's name sits on a box of its own colour."
- **What changes.** "The first-base diamond turns yellow when a runner is on. Show FULL COUNT under the strip
  when it is 3-2."
- **Motion.** "The whole strip fades in. The FULL COUNT tag drops down 14 pixels as it appears."

A prompt that works:

```text
Make a 1970s broadcast scorebug: one line of white text on a black bar at the bottom, 700 x 46, centred, 60 above
the bottom edge. Left to right: away club, away score in yellow, a thin divider, home club, home score in yellow,
a divider, TOP or BOT and the inning number, a divider, three small squares for the bases in a diamond that turn
yellow with a runner on, balls-strikes, and "N OUT". Nothing moves.
```

## Fixing what comes back

- **It will not open.** The sandbox says which piece or query it does not know. Paste that message back to the AI.
- **Things overlap or sit off-centre.** Drag them, or pick the piece and use **Line it up**.
- **A colour is wrong everywhere.** Click its swatch under **Colours of the design**.
- **A number is cut off.** Widen its box (**W**) rather than shrinking the text.
- **Check the hard cases** in the Game row: 11 runs, a 12th inning, a full count, bases loaded, two outs.

## Pictures and fonts of your own

Ask the AI for pieces like `{"image": "plate.png", "at": [0, 0, 280, 68]}` and put `plate.png` in the same folder
as the design file. Paint plates white if they should take a team's colour (put them in a `tint` group) and keep
gloss or a rim as a second picture on top. For lettering, pick the text in the sandbox and use **Import Font…**.

More on every piece: [Designing your own scorebug](SCOREBUG_DESIGN.md). All the data:
[Game data for a scorebug](SCOREBUG_DATA.md).
