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

__generated_with = "0.23.11"
app = marimo.App(
    width="medium",
    app_title="NFL Reporter",
    layout_file="layouts/dashboard.grid.json",
)


@app.cell
def _(c, max_season, max_week, mo, teams_lf):
    league_logo_src = teams_lf.select(c.team_league_logo).unique().collect().head(1).item()  # ty:ignore[unresolved-attribute]
    leage_logo = mo.image(src=league_logo_src, width=120, alt="")

    title_stack = mo.hstack(
        [
            leage_logo,
            mo.md(f"""
    # NFL Reporter - {str(max_season)} Season
    """),
        ],
        justify="start",
        align="center",
        gap=2,
    )

    tabs = mo.ui.tabs(
        {
            "League": mo.md("_League overview coming soon_"),
            "My Team": mo.md("_Team stats coming soon_"),
            "Players": mo.md("_Player stats coming soon_"),
            "Injuries": mo.md("_Injury report coming soon_"),
        },
        lazy=True,
    )

    week_num_stack = mo.hstack([mo.md(f"_Week {max_week}_")],justify="end", align="center")

    header_stack = mo.hstack(
        [title_stack, tabs, week_num_stack], justify="space-between", align="center",)

    header_stack
    return (tabs,)


@app.cell
def _(injuries_lf, mo, player_stats_lf, tabs, team_stats_lf):
    if "League" in tabs.value:
        # The League page will eventually show league-wide EPA trends,
        # standings, and win/loss summaries.
        page_content = mo.vstack(
            [
                mo.md("# 🏈 League Overview"),
                mo.md("_League-wide charts go here_"),
            ]
        )

    elif "Teams" in tabs.value:
        # The Teams page will show per-team stats with a dropdown to
        # filter by team. For now we show the raw DataFrame as a table.
        #
        # .head(10) limits the table to the first 10 rows so the page
        # doesn't get overwhelming during development.
        page_content = mo.vstack(
            [
                mo.md("# 📊 Team Stats"),
                mo.ui.table(team_stats_lf.head(10).collect()),  # ty:ignore[invalid-argument-type]
            ]
        )

    elif "Players" in tabs.value:
        page_content = mo.vstack(
            [
                mo.md("# 🏃 Player Stats"),
                mo.ui.dataframe(player_stats_lf.head(10).collect()),  # ty:ignore[invalid-argument-type]
            ]
        )

    elif "Injuries" in tabs.value:
        page_content = mo.vstack(
            [
                mo.md("# 🩹 Injury Report"),
                mo.ui.table(injuries_lf.head(10).collect()),  # type: ignore
            ]
        )

    else:
        # Fallback — shown briefly on first load before nav_tabs.value
        # is set, or if something unexpected happens.
        page_content = mo.md("_Select a page from the sidebar_")
    return


@app.cell
def _(max_week):
    max_week
    return


@app.cell
def _():
    import marimo as mo
    import polars as pl
    from polars import col as c
    import nflreadpy as nfl

    return c, mo, nfl, pl


@app.cell
def _(c, nfl, pl):
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
        injuries_lf,
        max_season,
        max_week,
        player_stats_lf,
        schedules_lf,
        team_stats_lf,
        teams_lf,
    )


@app.cell
def _(mo, schedules_lf):
    df = schedules_lf.collect()

    mo.ui.dataframe(df)
    return


@app.cell
def _(teams_lf):
    team_options = (
        teams_lf.select("team_name")
        .unique()
        .sort("team_name")
        .collect()
        .get_column("team_name")  # ty:ignore[unresolved-attribute]
        .to_list()
    )
    return (team_options,)


@app.cell
def _(mo, team_options):
    team_dropdown = mo.ui.dropdown(
        options=team_options,
        value=team_options[0],
        label="Select a team:",
    )
    team_dropdown
    return (team_dropdown,)


@app.cell
def _():
    return


@app.cell
def _(mo, pl, schedules_lf):
    week_options = (
        schedules_lf
        .filter(pl.col("season") == 2026)
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
    return week_dropdown, week_options


@app.cell
def _(week_options):
    week_options
    return


@app.cell
def _(week_dropdown):
    week_dropdown
    return


@app.cell
def _(pl, schedules_lf):
    _lf = (
        schedules_lf.select(
            [
                "week",
                "game_type",
                "gameday",
                "weekday",
                "gametime",
                "away_team",
                "away_score",
                "home_team",
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

    schedules_display = _lf.select([
            "week",
            "game_type",
            "matchup",
            "date_display",
            "weekday",
            "time_display",
            "status",
            "stadium",
        ])
    return (schedules_display,)


@app.cell
def _(max_season, mo, pl, schedules_display, week_dropdown):
    _schedule_collected = schedules_display.collect()

    selected_week = week_dropdown.value      # e.g. "Week 3" or "All Weeks"

    # Filter the already-collected DataFrame based on the selection.
    # Because _schedule_collected is a regular DataFrame (not LazyFrame),
    # we use .filter() directly — no need to .collect() again.
    if selected_week == "All Weeks":
        _filtered = _schedule_collected      # no filter, show everything
    else:
        # Extract the integer from "Week 3" → 3
        # int(selected_week.split(" ")[1]) splits "Week 3" into ["Week", "3"]
        # and converts "3" to the integer 3.
        week_num = int(selected_week.split(" ")[1])
        _filtered = _schedule_collected.filter(pl.col("week") == week_num)

    # ── Build the final tab layout ─────────────────────────────────────────────
    # mo.vstack stacks: header → controls → table (top to bottom)
    schedule_content = mo.vstack([

        # Header section
        mo.md(f"## {max_season} Season Schedule"),
        mo.md("Game times shown in Eastern Time. Scores shown for completed games."),

        # Dropdown filter — sits above the table
        mo.hstack([
            week_dropdown,
            # Show a small count of how many games are displayed
            mo.md(f"**{len(_filtered)} games**"),
        ], align="center", gap=1),

        mo.md("---"),

        # The table itself — mo.ui.table() renders a Polars DataFrame
        # as an interactive, sortable table.
        # pagination=True adds page controls so it doesn't scroll forever.
        mo.ui.table(
            _filtered,
            pagination=False,
            show_column_summaries=False,
            show_data_types=False,
            selection=None
        ),
    ])

    schedule_content
    return


@app.cell
def _(pl, team_dropdown, teams_lf):
    selected_team = team_dropdown.value
    filtered_df = teams_lf.filter(pl.col("team_name") == selected_team).collect()

    filtered_df
    return


if __name__ == "__main__":
    app.run()
