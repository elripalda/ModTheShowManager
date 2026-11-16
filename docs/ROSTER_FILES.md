# Roster files

**Teams & Rosters › Import / Export** reads and writes rosters as JSON. Export a team to see a full example, or
start from **Save a Sample File to Edit**.

```json
{
  "format": "modtheshow-roster",
  "teams": [
    {
      "team": "New York Yankees",
      "rename": {"city": "Gotham", "name": "Knights", "short": "GTH"},
      "replace": true,
      "players": [
        {"first": "Babe", "last": "Ruth", "pos": "RF", "number": 3, "bats": "L", "throws": "L",
         "height": "6'2", "overall": 99,
         "ratings": {"contact_vs_r": 112, "power_vs_r": 125, "discipline": 110}},
        {"first": "Waite", "last": "Hoyt", "pos": "SP", "number": 12, "throws": "R",
         "ratings": {"stamina": 99, "bb_per_9": 90}}
      ]
    }
  ]
}
```

## Teams

| Key | What it does |
| --- | --- |
| `team` | Which team: full name, nickname or abbreviation (`"New York Yankees"`, `"Yankees"`, `"NYY"`). |
| `rename` | Optional new `city`, `name` and `short`. |
| `replace` | `true` sends everyone on the team who isn't in the file to free agency first. Leave it out to add to the team. |
| `players` | The players, in order. The first five pitchers are the rotation, the sixth is the closer, the rest the bullpen. |

A team holds 30 pitchers and 65 position players at most.

## Players

Only `last` is required for a new player. Leave anything else out and it keeps its value.

| Key | Values |
| --- | --- |
| `id` | The game's player id. Exports include it; with it a player is found even after a rename. |
| `first`, `last` | Up to 15 letters each. |
| `pos` | `P` (or `SP`, `RP`, `CP`), `C`, `1B`, `2B`, `3B`, `SS`, `LF`, `CF`, `RF`. |
| `number` | 0 to 99. |
| `bats` | `R`, `L` or `S`. |
| `throws` | `R` or `L`. |
| `height` | `"6'2"` or inches (`74`). |
| `overall` | 0 to 125. 99 is the normal top. |
| `ratings` | See below. 0 to 125 each. |
| `gear` | Item numbers per slot, as an export shows them. |
| `like` | A player's name. Copies his whole look (face, hair, skin, build). |

Hitter ratings: `contact_vs_l`, `contact_vs_r`, `power_vs_l`, `power_vs_r`, `vision`, `discipline`, `clutch`,
`bunting`, `speed`, `stealing`, `arm_strength`, `arm_accuracy`, `fielding`, `reaction`, `durability`, `blocking`,
`potential`.

Pitcher ratings: `stamina`, `pitching_clutch`, `h_per_9`, `hr_per_9`, `k_per_9`, `bb_per_9`, plus `speed`,
`arm_strength`, `arm_accuracy`, `fielding`, `reaction`, `durability`, `potential`.

Gear slots: `bat`, `bat_grip`, `batting_gloves`, `glove`, `cleats`, `elbow_guard`, `shin_guard`, `wrist_guard`,
`sleeve`, `eyewear`, `catcher_mask`, `chest_protector`, `leg_guards`.

## How players are matched

1. By `id`, when the file has one.
2. By exact first and last name. The game's legends are in there as free agents (Ruth, Gehrig, Mays and so on), so
   a classic roster that names them gets the real ones, scanned faces and all.
3. Anyone else is new. The manager takes a spare player with a built face (a free agent first, then the low
   minors), renames him and sets what the file says. New players never land on a scanned head.

After an import, lineups with a hole are filled for you: the best fit at each position, the best bat left over at
DH, batting order from the best hitter down. Nothing is written until you press **Save to My Mod**.

## Having an AI write one

Give it this page and ask for what you want ("the 1998 Yankees, 25 players, ratings out of 99 with stars up to
110"). Check the names fit in 15 letters and the team name matches one in the game.
