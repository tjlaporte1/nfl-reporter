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

    return mo, nfl, pl, urllib


@app.cell
def _(nfl, pl):
    nfl.load_depth_charts().filter(pl.col("team") == "PHI")
    # _df.filter(pl.col("player_id") == "00-0023459")
    return


@app.cell
def data_url():
    DATA_URL = (
        "https://raw.githubusercontent.com/"
        "YOUR_GITHUB_USERNAME/YOUR_REPO_NAME/"
        "main/data/team_stats_2025.json"
    )
    return (DATA_URL,)


@app.cell
def _(DATA_URL, mo, pl, urllib):
    try:
        with urllib.request.urlopen(DATA_URL) as response:
            raw_bytes = response.read()

        df = pl.read_json(raw_bytes)

        mo_status = mo.callout(
            mo.md(f"✅ **Data loaded successfully** — {df.shape[0]} rows, {df.shape[1]} columns"),
            kind="success",
        )

    except Exception as e:
        # If loading fails, df is set to an empty DataFrame so downstream
        # cells don't crash — they'll just show empty charts.
        df = pl.DataFrame()
        mo_status = mo.callout(
            mo.md(f"❌ **Could not load data:** `{e}`\n\nCheck that the DATA_URL in Cell 3 points to your repo."),
            kind="danger",
        )
    return (mo_status,)


@app.cell
def _(mo_status):
    mo_status
    return


if __name__ == "__main__":
    app.run()
