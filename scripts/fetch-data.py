import marimo

__generated_with = "0.23.9"
app = marimo.App()


@app.cell
def _():
    import polars as pl
    import nflreadpy as nfl
    from pathlib import Path

    return Path, nfl, pl


@app.cell
def _(Path):
    OUTPUT_DIR = Path(__file__).parent.parent / "data"

    OUTPUT_DIR.mkdir(exist_ok=True)
    return (OUTPUT_DIR,)


@app.cell
def _(nfl, pl):
    print("Fetching Team Stats Data...")

    team_stats_df: pl.DataFrame = nfl.load_team_stats(summary_level="reg")

    print(f"  Loaded {team_stats_df.shape[0]} rows × {team_stats_df.shape[1]} columns")
    print(f"  Columns: {team_stats_df.columns}")
    return (team_stats_df,)


@app.cell
def _(OUTPUT_DIR, team_stats_df: "pl.DataFrame"):
    team_stats_curr_season_file_loc = OUTPUT_DIR / "team-stats-curr-season.parquet"

    team_stats_df.write_parquet(str(team_stats_curr_season_file_loc), compression="snappy")

    print(f"  Saved to {team_stats_curr_season_file_loc}")
    print("Done.")
    return


if __name__ == "__main__":
    app.run()
