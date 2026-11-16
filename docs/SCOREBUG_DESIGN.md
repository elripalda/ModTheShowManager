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
- **Match the size of what you replace**, or a clean multiple of it (2x is fine and looks sharper). The strip
  under the preview shows every texture and its size.
- **States are separate art.** An out light needs an off and an on. A base needs empty and occupied.

Then in the sandbox: click the piece, **Replace PNG**, pick your export. Move and resize until the preview matches
your mockup, and set the fonts.

For lettering, **Import Font…** takes a `.ttf` or `.otf` and draws it into the game in place of one of its fonts.

## What a mockup needs if you hand it over

A flat picture is enough to copy a layout: where things sit, how big, what colour. To build it properly send:

- the mockup at 1920 x 1080, on a game screenshot;
- the pieces as separate PNGs, named for what they are;
- the font files;
- each state drawn once: outs, bases, top and bottom of the inning;
- a note on what should move, and from where (the batter bar drops from the top edge, the score rolls up).

## Not possible yet

- **New pieces.** You can change, move, hide and repaint what a theme has, and a template can be copied and
  reshaped (the Split Bar's mirrored home side is a second copy of the team row). A piece built from nothing,
  with its own text and data, is next.
- **Pop-ups dropping down.** The bars and cards are built to rise from behind the bug. On a top bar they still
  rise, so the bar has to sit low enough to leave them room.
- **Transitions.** The wipes between plays are Bink videos (`CROSS/MOVIES/PRESENTATION/THEMEn/*.BK2`), not
  layouts. Replacing them means encoding a video, which the manager does not do.
- **Per-uniform colours.** The preview takes a team's colour from a table. Tying a look to a City Connect or
  throwback uniform is not worked out.

Starting lineups, the pre-game matchup, due up and the lower thirds are layouts like the scorebug
(`NSW/UI/GAME/PRES/PRESOSDSn`). They open in the same sandbox, without their lists filled in.
