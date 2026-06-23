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

__generated_with = "0.23.9"
app = marimo.App(
    width="medium",
    app_title="NFL Reporter",
    layout_file="layouts/dashboard.grid.json",
)


@app.cell
def _(mo, stats_max_season):
    mo.md(f"# NFL Reporter - {str(stats_max_season)} Season")
    return


app._unparsable_cell(
    r"""
    mo.nav_menu(
        {"/league": "Leage",
        /}
    )
    """,
    name="_"
)


@app.cell
def _():
    import marimo as mo
    import polars as pl
    from polars import col as c
    import nflreadpy as nfl

    return c, mo, nfl, pl


@app.cell
def _(c, mo, teams_lf):
    league_logo = teams_lf.select(c.team_league_logo).unique().collect().head(1).item()
    mo.image(src=league_logo,width=120, alt="")
    return


@app.cell
def _(nfl, pl):
    max_season = nfl.load_schedules().select(pl.col("season").max()).item()
    stats_max_season = (
        nfl.load_team_stats(summary_level="reg").select(pl.col("season").max()).item()
    )

    # Fetch last 4 seasons of stats
    stats_seasons = list(range(stats_max_season - 3, stats_max_season + 1))

    # LazyFrames
    rosters_lf = nfl.load_rosters().lazy()
    injury_lf = nfl.load_injuries().lazy()
    teams_lf = nfl.load_teams().lazy()
    schedules_lf = nfl.load_schedules(seasons=max_season).lazy()
    team_stats_lf = nfl.load_team_stats(seasons=stats_seasons).lazy()
    player_stats_lf = nfl.load_player_stats(seasons=stats_seasons).lazy()
    return stats_max_season, teams_lf


@app.cell
def _(teams_lf):
    team_options = (
        teams_lf.select("team_name")
        .unique()
        .sort("team_name")
        .collect()
        .get_column("team_name")  # ty:ignore[unresolved-attribute]
        .to_list()
    )  # ty:ignore[unresolved-attribute]
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
def _(pl, team_dropdown, teams_lf):
    selected_team = team_dropdown.value
    filtered_df = teams_lf.filter(pl.col("team_name") == selected_team).collect()

    filtered_df
    return


if __name__ == "__main__":
    app.run()
