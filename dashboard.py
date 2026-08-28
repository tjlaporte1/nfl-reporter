# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "marimo",
#   "polars",
#   "pyarrow",
#   "plotly",
#    "nflreadpy",
# ]
# ///

# ─────────────────────────────────────────────────────────────────────────────
# HOW MARIMO WORKS — read this before looking at the code
#
# Marimo is a "reactive" notebook. Instead of running cells top-to-bottom
# like Jupyter, marimo watches which variables each cell uses and defines.
# When a variable changes, every cell that depends on it re-runs automatically.
#
# Think of it like a spreadsheet: change one cell, and everything that
# references it updates instantly.
#
# Each cell in this file is separated by the `@app.cell` decorator.
# The function name inside doesn't matter — marimo uses the return value
# and the function's arguments to figure out the dependency graph.
#
# Example:
#   @app.cell
#   def __(mo):           ← this cell USES `mo` (declared in another cell)
#       x = mo.md("hi")  ← defines `x`
#       return (x,)       ← makes `x` available to other cells
# ─────────────────────────────────────────────────────────────────────────────

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="NFL Reporter")


@app.cell
def _(c, max_season, max_week, mo, teams_lf):
    league_logo_src = teams_lf.select(c.team_league_logo).unique().collect().head(1).item()
    leage_logo = mo.image(src=league_logo_src, width=50, alt="")

    title_stack = mo.hstack(
        [
            leage_logo,
            mo.md(f"""
    ### NFL Reporter - {str(max_season)}"""),
        ],
        justify="start",
        align="center",
        gap=2,
    )

    tabs = mo.ui.tabs(
        {
            "League": mo.md("_Schedule & Stats_"),
            "My Team": mo.md("_Team stats coming soon_"),
            "Players": mo.md("_Player stats coming soon_"),
            "Injuries": mo.md("_Injury report coming soon_"),
        },
        lazy=True,
    )

    week_num_stack = mo.hstack([mo.md(f"_Week {max_week}_")], justify="end", align="center")

    header_stack = mo.Html(
        f"""<div style="width: 100%;">
            {mo.vstack(
                [
                    mo.hstack(
                        [title_stack, week_num_stack],
                        justify="space-between",
                        align="center",
                    ),
                    mo.hstack(
                        [tabs],
                        justify="center",
                        align="center",
                    ),
                ],
                align="stretch",
            ).text}
        </div>"""
    )

    header_stack
    return (tabs,)


@app.cell
def _(page_content):
    page_content
    return


@app.cell
def _(injuries_lf, mo, player_stats_lf, schedule_content, tabs, team_stats_lf):
    if "League" in tabs.value:
        # The League page will eventually show league-wide EPA trends,
        # standings, and win/loss summaries.
        page_content = mo.vstack(
            [
                schedule_content
            ]
        )

    elif "My Team" in tabs.value:
        # The My Team page will show per-team stats with a dropdown to
        # filter by team. For now we show the raw DataFrame as a table.
        #
        # .head(10) limits the table to the first 10 rows so the page
        # doesn't get overwhelming during development.
        page_content = mo.vstack(
            [
                mo.md("# 📊 Team Stats"),
                mo.ui.table(team_stats_lf.head(10).collect()),
            ]
        )

    elif "Players" in tabs.value:
        page_content = mo.vstack(
            [
                mo.md("# 🏃 Player Stats"),
                mo.ui.dataframe(player_stats_lf.head(10).collect()),
            ]
        )

    elif "Injuries" in tabs.value:
        page_content = mo.vstack(
            [
                mo.md("# 🩹 Injury Report"),
                mo.ui.table(injuries_lf.head(10).collect()),
            ]
        )

    else:
        # Fallback — shown briefly on first load before nav_tabs.value
        # is set, or if something unexpected happens.
        page_content = mo.md("_Select a page from the sidebar_")
    return (page_content,)


@app.cell
def _():
    import marimo as mo
    import nflreadpy as nfl
    import polars as pl
    from polars import col as c

    max_season = nfl.load_schedules().select(pl.col("season").max()).item()
    stats_max_season = (
        nfl.load_team_stats(summary_level="reg").select(pl.col("season").max()).item()
    )

    # Fetch last 4 seasons of stats
    stats_seasons = list(range(stats_max_season - 3, stats_max_season + 1))

    # LazyFrames
    rosters_lf = nfl.load_rosters().lazy()
    injuries_lf = nfl.load_injuries().lazy()
    teams_lf = nfl.load_teams().lazy()
    schedules_lf = nfl.load_schedules(seasons=max_season).lazy()
    team_stats_lf = nfl.load_team_stats(seasons=stats_seasons).lazy()
    player_stats_lf = nfl.load_player_stats(seasons=stats_seasons).lazy()

    max_week = (
        schedules_lf.filter(c.home_score.is_not_null())
        .select(c.week.max())
        .collect()
        .item()  # ty:ignore[unresolved-attribute]
    )

    max_week = int(max_week) if max_week is not None else 0
    return (
        c,
        injuries_lf,
        max_season,
        max_week,
        mo,
        pl,
        player_stats_lf,
        schedules_lf,
        team_stats_lf,
        teams_lf,
    )


@app.cell
def _(team_dropdown):
    team_dropdown
    return


@app.cell
def _(c, mo, schedules_lf, teams_lf):
    team_map = {
        row[1]: row[0]
        for row in teams_lf.select(["team_abbr", "team_name"]).sort("team_name").collect().rows()
    }

    # Prepend "All Teams" as the default option
    team_options = ["All Teams"] + list(team_map.keys())

    team_dropdown = mo.ui.dropdown(
        options=team_options,
        value="All Teams",
        label="Team",
    )

    week_options = (
        schedules_lf
        .select("week")
        .unique()
        .sort("week")
        .collect()
        .to_series()
        .to_list()
    )

    week_options = ["All Weeks"] + [f"Week {w}" for w in week_options]

    week_dropdown = mo.ui.dropdown(
        options=week_options,
        value="All Weeks",
        label="Filter by Week",
    )

    game_types = (
        schedules_lf
        .select(
            c.game_type.replace(
                {
                    "REG": "Regular Season",
                    "WC": "Wild Card",
                    "DIV": "Divisional",
                    "CON": "Conference Championship",
                    "SB": "Super Bowl",
                }
            ).alias("game_type")
        )
        .unique()
        .sort("game_type")
        .collect()
        .to_series()
        .to_list()
    )

    game_type_options = ["All"] + game_types

    game_type_dropdown = mo.ui.dropdown(
        options=game_type_options,
        value="All",
        label="Filter by Game Type",
    )

    return game_type_dropdown, team_dropdown, team_map, week_dropdown


@app.cell
def _(
    game_type_dropdown,
    max_season,
    mo,
    pl,
    schedules_lf,
    team_dropdown,
    team_map,
    week_dropdown,
):
    _lf = (
        schedules_lf.select(
            [
                "week",
                "game_type",
                "away_team",
                "home_team",
                "gameday",
                "weekday",
                "gametime",
                "away_score",
                "home_score",
                "stadium",
            ]
        )
        .sort(["week", "gameday", "gametime"])
        .with_columns(
            pl.when(pl.col("away_score").is_not_null())
            .then(
                pl.col("away_team")
                + "  "
                + pl.col("away_score").cast(pl.Utf8)
                + "  -  "
                + pl.col("home_score").cast(pl.Utf8)
                + "  "
                + pl.col("home_team")
            )
            .otherwise(pl.col("away_team") + " @ " + pl.col("home_team"))
            .alias("matchup"),
            pl.col("game_type")
            .replace(
                {
                    "REG": "Regular Season",
                    "WC": "Wild Card",
                    "DIV": "Divisional",
                    "CON": "Conference Championship",
                    "SB": "Super Bowl",
                }
            )
            .alias("game_type"),
        )
        .with_columns(
            pl.when(pl.col("away_score").is_not_null())
            .then(pl.lit("Final"))
            .otherwise(pl.lit("Upcoming"))
            .alias("status"),
            pl.col("gameday")
            .str.strptime(pl.Date, "%Y-%m-%d")  # parse "2025-09-07" → Date
            .dt.strftime("%b %-d, %Y")  # format → "Sep 7, 2025"
            .alias("date_display"),
            # gametime can be null for some games, so we handle that safely
            pl.when(pl.col("gametime").is_not_null())
            .then(
                pl.col("gametime")
                .str.strptime(pl.Time, "%H:%M")  # parse "13:00" → Time
                .dt.strftime("%-I:%M %p")  # format → "1:00 PM"
                + " ET"
            )
            .otherwise(pl.lit("TBD"))
            .alias("time_display"),
        )
    )

    schedules_display = _lf.select(
        [
            "week",
            "game_type",
            "away_team",
            "home_team",
            "matchup",
            "date_display",
            "weekday",
            "time_display",
            "status",
            "stadium",
        ]
    ).collect()

    selected_week = week_dropdown.value  # e.g. "Week 3" or "All Weeks"
    selected_team = team_dropdown.value  # e.g. "Philadelphia Eagles" or "All Teams"
    selected_game_type = game_type_dropdown.value

    # Filter the already-collected DataFrame based on the selection.
    # Because _schedule_collected is a regular DataFrame (not LazyFrame),
    # we use .filter() directly — no need to .collect() again.
    if selected_week == "All Weeks":
        _filtered = schedules_display  # no filter, show everything
    else:
        # Extract the integer from "Week 3" → 3
        # int(selected_week.split(" ")[1]) splits "Week 3" into ["Week", "3"]
        # and converts "3" to the integer 3.
        week_num = int(selected_week.split(" ")[1])
        _filtered = schedules_display.filter(pl.col("week") == week_num)  # type: ignore

    if selected_game_type != "All":
        _filtered = _filtered.filter(pl.col("game_type") == selected_game_type)

    if selected_team != "All Teams":
        team_abbr = team_map[selected_team]  # "Philadelphia Eagles" → "PHI"
        _filtered = _filtered.filter(
            (pl.col("away_team") == team_abbr)  # PHI is the away team, OR
            | (pl.col("home_team") == team_abbr)  # PHI is the home team
        )

    # ── Build the final tab layout ─────────────────────────────────────────────
    # mo.vstack stacks: header → controls → table (top to bottom)
    _display_cols = [
        "week",
        "game_type",
        "matchup",
        "date_display",
        "weekday",
        "time_display",
        "status",
        "stadium",
    ]

    schedule_content = mo.vstack(
        [
            # Header section
            mo.md(f"### {max_season} Season Schedule"),
            mo.md("Game times shown in Eastern Time. Scores shown for completed games."),
            # Dropdown filter — sits above the table
            mo.hstack(
                [
                    week_dropdown,
                    game_type_dropdown,
                    team_dropdown,
                    mo.md(f"**{len(_filtered)} games**"),
                ],
                align="center",
                gap=1,
            ),
            mo.md("---"),
            # The table itself — mo.ui.table() renders a Polars DataFrame
            # as an interactive, sortable table.
            # pagination=True adds page controls so it doesn't scroll forever.
            mo.ui.table(
                _filtered.select(_display_cols),  # type: ignore
                pagination=False,
                show_column_summaries=False,
                show_data_types=False,
                selection=None,
            ),
        ]
    )
    return (schedule_content,)


if __name__ == "__main__":
    app.run()
