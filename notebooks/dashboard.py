# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "marimo",
#   "polars",
#   "pyarrow",
#   "plotly",
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
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl

    return (pl,)


@app.cell
def data_url(pl):
    BASE_DATA_URL = "https://raw.githubusercontent.com/tjlaporte1/nfl-reporter/main/data/"

    teams_df = pl.read_parquet(f"{BASE_DATA_URL}{"teams.parquet"}")
    schedules_df = pl.read_parquet(f"{BASE_DATA_URL}{"schedules.parquet"}")
    team_stats_df = pl.read_parquet(f"{BASE_DATA_URL}{"team-stats.parquet"}")
    player_stats_df = pl.read_parquet(f"{BASE_DATA_URL}{"player-stats.parquet"}")
    rosters_df = pl.read_parquet(f"{BASE_DATA_URL}{"rosters.parquet"}")
    injuries_df = pl.read_parquet(f"{BASE_DATA_URL}{"injuries.parquet"}")
    return (team_stats_df,)


@app.cell
def _(team_stats_df):
    team_stats_df
    return


if __name__ == "__main__":
    app.run()
