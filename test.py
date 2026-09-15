import marimo

__generated_with = "0.24.0"
app = marimo.App()


@app.cell
def _():
    import nflreadpy as nfl
    import polars as pl
    from polars import col as c
    import marimo as mo

    SeasonSelector = int | list[int] | bool | None

    def import_rosters(seasons: SeasonSelector = None) -> pl.DataFrame:
        """Import player roster data."""
        return nfl.load_rosters(seasons=seasons)


    def import_injuries(seasons: SeasonSelector = None) -> pl.DataFrame:
        """Import player injury data."""
        return nfl.load_injuries(seasons=seasons)


    def import_teams() -> pl.DataFrame:
        """Import league team metadata."""
        return nfl.load_teams()



    def import_schedules(seasons: SeasonSelector = True) -> pl.DataFrame:
        """Import game schedules."""
        return nfl.load_schedules(seasons=seasons)



    def import_team_stats(
        seasons: SeasonSelector = None,
    ) -> pl.DataFrame:
        """Import team statistics."""
        return nfl.load_team_stats(
            seasons=seasons,
        )



    def import_player_stats(
        seasons: SeasonSelector = None,
    ) -> pl.DataFrame:
        """Import player statistics."""
        return nfl.load_player_stats(
            seasons=seasons,
        )


    # max_season = nfl.load_schedules().select(pl.col("season").max()).item()
    # stats_max_season = (
    #     nfl.load_team_stats(summary_level="reg").select(pl.col("season").max()).item()
    # )

    # # Fetch last 4 seasons of stats
    # stats_seasons = list(range(stats_max_season - 3, stats_max_season + 1))

    # # LazyFrames
    # rosters_lf = nfl.load_rosters()
    # injuries_lf = nfl.load_injuries()
    # teams_lf = nfl.load_teams()
    # schedules_lf = nfl.load_schedules(seasons=max_season)
    # team_stats_lf = nfl.load_team_stats(seasons=stats_seasons)
    # player_stats_lf = nfl.load_player_stats(seasons=stats_seasons)
    return import_team_stats, mo


@app.cell
def _(import_team_stats):
    df = import_team_stats(2025)
    return (df,)


@app.cell
def _(df, mo):
    mo.ui.table(df, max_columns=None)
    return


if __name__ == "__main__":
    app.run()
