# Game data for a scorebug

A piece of a design shows live data by naming a query, in the game's own words. Use them in `"data"` for text and
in `"switch"` to pick a look. They are written without the outer brackets: `SCORER OUTS`, `BoxScore HITS [ 0 ]`.

The game's text uses 3,281 different queries. These are the ones a scorebug is likely to want. The first group
is proven in play. The others come from other screens of the game and have not all been tried in a scorebug.

## The game in progress

Used by the scorebug itself, so these answer during play.

| Query |
| --- |
| `SCORER AWAY_SCORE` |
| `SCORER HOME_SCORE` |
| `SCORER INNING` |
| `SCORER OUTS` |
| `SCORER BALLS` |
| `SCORER STRIKES` |
| `SCORER PITCH_CLOCK` |
| `IG BALLS` |
| `IG STRIKES` |
| `IG IS_BOTTOM` |
| `SCOREBAR INNING_STR [ 0 ]` |
| `SCOREBAR INNING_STR [ 1 ]` |
| `SCOREBAR OUT_TAB` |
| `SCOREBAR 1ST_BASE_TAB` |
| `SCOREBAR 2ND_BASE_TAB` |
| `SCOREBAR 3RD_BASE_TAB` |
| `AWAY_TEAM TEAM_PROF SHORT_NAME` |
| `HOME_TEAM TEAM_PROF SHORT_NAME` |
| `AWAY_TEAM_ID` |
| `HOME_TEAM_ID` |

## Batter and pitcher

From the batter and pitcher bars.

| Query |
| --- |
| `CURRENT_BATTER GAME_STATS AT_BATS` |
| `CURRENT_BATTER GAME_STATS BASE_ON_BALLS` |
| `CURRENT_BATTER GAME_STATS HITS` |
| `CURRENT_BATTER GAME_STATS RBI` |
| `CURRENT_BATTER PLAYER_NUM` |
| `CURRENT_BATTER PROFILE` |
| `CURRENT_BATTER SEASON_STATS AVG` |
| `CURRENT_BATTER SEASON_STATS HR` |
| `CURRENT_BATTER SEASON_STATS RBI` |
| `CURRENT_BATTER SEASON_STATS STOLEN_BASES` |
| `CURRENT_BATTER SEASON_STATS TPA` |
| `CURRENT_PITCHER PLAYER_NUM` |
| `CURRENT_PITCHER PROFILE CONFIDENCE` |
| `CURRENT_PITCHER PROFILE ENERGY` |
| `CURRENT_PITCHER SEASON_STATS P_AVG_RHB` |
| `PITCH_BAT_STATS BD_HEADER` |
| `PITCH_BAT_STATS PITCH_COUNT` |
| `PITCH_BAT_STATS PITCH_COUNT_BALLS` |
| `PITCH_BAT_STATS PITCH_COUNT_STRIKES` |
| `PITCH_BAT_STATS PULL_TYPE` |
| `SCOREBAR BATTER_BAR_EXIT_VELO` |
| `SCOREBAR BATTER_BAR_INFO` |
| `SCOREBAR BATTER_BAR_NAME [ 0 ]` |
| `SCOREBAR BATTER_BAR_NAME [ 1 ]` |
| `SCOREBAR BATTER_LINEUP_INDEX` |
| `SCOREBAR BATTER_STATS` |
| `SCOREBAR PITCHES_IN_INNING [ 0 ]` |
| `SCOREBAR PITCHES_IN_INNING [ 1 ]` |
| `SCOREBAR PITCHES_IN_INNING [ 2 ]` |

## Line score

From the box score screen: runs by inning, hits and errors. Team 0 is away, 1 is home; innings count from 0.

| Query |
| --- |
| `BoxScore INNING_VAL [ 0 , 0 ]` |
| `BoxScore INNING_VAL [ 1 , 8 ]` |
| `BoxScore INNING_STR [ 0 ]` |
| `BoxScore HITS [ 0 ]` |
| `BoxScore HITS [ 1 ]` |
| `BoxScore ERRORS [ 0 ]` |
| `BoxScore ERRORS [ 1 ]` |
| `BoxScore DATE_STR` |

## Scorebug moments

Home runs, strikeouts, speed, the end of an inning.

| Query |
| --- |
| `SCOREBAR BENCH_PLAYER [ 0 ]` |
| `SCOREBAR BENCH_PLAYER_HAND [ 0 ]` |
| `SCOREBAR CALLOUT_TYPE` |
| `SCOREBAR DOUBLEPLAY_STR` |
| `SCOREBAR END_OF_INNING_STRING [ 0 ]` |
| `SCOREBAR END_OF_INNING_STRING [ 1 ]` |
| `SCOREBAR END_OF_INNING_STRING` |
| `SCOREBAR HITTER_TYPE` |
| `SCOREBAR HOMERUN_STR [ 1 ]` |
| `SCOREBAR HOMERUN_STR [ 2 ]` |
| `SCOREBAR HR_COUNT` |
| `SCOREBAR HR_COUNT_SUBSCRIPT` |
| `SCOREBAR HR_COUNT_TEXT` |
| `SCOREBAR HR_DIST` |
| `SCOREBAR HR_EXIT_VELOCITY` |
| `SCOREBAR INTERACTIVE_PROMPT` |
| `SCOREBAR LINEUP_CITY` |
| `SCOREBAR LINEUP_NAME` |
| `SCOREBAR MAX_ATTENDANCE` |
| `SCOREBAR NOTABLE_STR` |
| `SCOREBAR ON_DECK_NOTABLE` |
| `SCOREBAR ON_DECK_TEXT` |
| `SCOREBAR PLAYGO_PROGRESS` |
| `SCOREBAR PLAYGO_STATUS` |
| `SCOREBAR PRESTEXT [ 0 ]` |
| `SCOREBAR PRESTEXT [ 1 ]` |
| `SCOREBAR PRESTEXT [ 2 ]` |
| `SCOREBAR PRESTEXT [ 3 ]` |
| `SCOREBAR PRESTEXT [ 4 ]` |
| `SCOREBAR PREVIOUS_SCORE [ 0 ]` |
| `SCOREBAR PREVIOUS_SCORE [ 1 ]` |
| `SCOREBAR RAID_OUTS_LEFT` |
| `SCOREBAR SPEED` |
| `SCOREBAR STANDINGS_NOTABLE` |
| `SCOREBAR STANDINGS_TEXT` |
| `SCOREBAR STANDINGS_TITLE` |
| `SCOREBAR STOLEN_BASE_LEAD_RUNNER_NAME` |
| `SCOREBAR STOLEN_BASE_LEAD_RUNNER_VALUE` |
| `SCOREBAR STRIKEOUT_STR [ 0 ]` |
| `SCOREBAR STRIKEOUT_STR [ 1 ]` |

## Logos and team colour

`{"logo": "away", "kind": 2}` draws that team's logo. Kinds 1 to 5 are the game's five logo sets: wordmark, flat
primary, large 3D, tile, large flat. `{"team": "home"}` fills a box with the team's colour.

| Query | Answer |
|---|---|
| `UI CAP_TEAM_CLR [ AWAY_TEAM_ID ]` | The colour of the uniform that team has on. Add `, 1` for its second colour |
| `UI ACTUAL_TEAM_CLR [ HOME_TEAM_ID , 0 ]` | The club's own colour, whatever it wears. `1` for its second |
| `TEAM_UI IS_CITY_CONNECT_ACTIVE [ AWAY_TEAM_ID ]` | 1 while that team wears City Connect |
| `CAP_CLR_BRIGHTNESS_TAB [ HOME_TEAM_ID ]` | 1 when that team's colour is a light one |
| `HAS_CAP_LOGO [ AWAY_TEAM_ID ]` | 1 when the team has a cap logo to show |
| `AWAY_TEAM TEAM_PROF TEAM_INX` | The club's number, 0 to 29 |

`OFF_TEAM_ID` and `DEF_TEAM_ID` stand for the team batting and the team in the field.

## Finding more

Every query the manager can name is in `src/modtheshow/assets/querynames.txt`, one word per line. A query only
compiles when all its words are in that list.
