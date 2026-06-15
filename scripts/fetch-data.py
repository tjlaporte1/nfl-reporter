import polars as pl
import nflreadpy as nfl
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

print("Fetching Team Stats Data...")

team_stats_df: pl.DataFrame = nfl.load_team_stats(summary_level="reg")

print(f"  Loaded {team_stats_df.shape[0]} rows × {team_stats_df.shape[1]} columns")
print(f"  Columns: {team_stats_df.columns}")

team_stats_curr_season_file_loc = OUTPUT_DIR / "team-stats-curr-season.parquet"
team_stats_df.write_parquet(str(team_stats_curr_season_file_loc), compression="snappy")

print(f"  Saved to {team_stats_curr_season_file_loc}")
print("Done.")