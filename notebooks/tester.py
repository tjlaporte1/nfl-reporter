import marimo

__generated_with = "0.23.9"
app = marimo.App()


@app.cell
def _(nfl, pl):
    max_season = nfl.load_schedules().select(pl.col("season").max()).item()
    stats_max_season = (
        nfl.load_team_stats(summary_level="reg").select(pl.col("season").max()).item()
    )
    print(f"  Max season: {max_season}")
    print(f"  Max stats season: {stats_max_season}")

    # Fetch last 4 seasons of stats
    stats_seasons = list(range(stats_max_season - 3, stats_max_season + 1))
    print(f"  Seasons to fetch: {stats_seasons}")


    # Fetch and save teams
    print("Fetching teams...")

    teams_df = nfl.load_teams()

    # Fetch and save latest schedule
    print("Fetching schedules...")

    schedules_df = nfl.load_schedules(seasons=max_season)

    # Fetch and save team stats
    print("Fetching team stats data...")

    team_stats_df = nfl.load_team_stats(seasons=stats_seasons)

    # Fetch and save player stats
    print("Fetching player stats data...")
    player_stats_df = nfl.load_player_stats(seasons=stats_seasons)

    print("Done.")
    return


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import nflreadpy as nfl

    return nfl, pl


if __name__ == "__main__":
    app.run()
