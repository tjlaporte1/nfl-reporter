# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "marimo",
#   "polars",
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
    import nflreadpy as nfl
    import urllib.request
    import io

    return io, nfl, pl, urllib


@app.cell
def _(nfl):
    nfl.load_injuries()
    return


@app.cell
def _(nfl, pl):
    max_season = nfl.load_team_stats(summary_level="reg").select(pl.col("season").max()).item()
    seasons = list(range(max_season - 3, max_season + 1))

    print(seasons)
    return


@app.cell
def data_url(io, pl, urllib):
    BASE_DATA_URL = "https://raw.githubusercontent.com/tjlaporte1/nfl-reporter/main/data/"

    def load_parquet(filename: str) -> pl.DataFrame:
        """
        Fetches a parquet file from the GitHub data folder and returns
        it as a Polars DataFrame.

        filename: just the filename, e.g. "team-stats.parquet"
        """
        url = BASE_DATA_URL + filename
        with urllib.request.urlopen(url) as response:
            raw_bytes = response.read()
        return pl.read_parquet(io.BytesIO(raw_bytes))

    return


if __name__ == "__main__":
    app.run()
