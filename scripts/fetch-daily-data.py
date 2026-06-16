# Fetch and save NFL daily data (rosters, injuries) to parquet files
import polars as pl
import nflreadpy as nfl
from pathlib import Path

# Setup output directory
OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

# Determine seasons to fetch
print("Finding the season...")

max_season = (
    nfl.load_schedules().select(pl.col("season").max()).item()
)
stats_max_season = (
    nfl.load_team_stats(summary_level="reg").select(pl.col("season").max()).item()
)
print(f"  Max season: {max_season}")
print(f"  Max stats season: {stats_max_season}")

# Fetch last 4 seasons of stats
stats_seasons = list(range(stats_max_season - 3, stats_max_season + 1))
print(f"  Seasons to fetch: {stats_seasons}")

# Fetch and save rosters
print("Fetching rosters...")

rosters_df = nfl.load_rosters()
rosters_file_loc = OUTPUT_DIR / "rosters.parquet"
rosters_df.write_parquet(str(rosters_file_loc), compression="snappy")
print(f"  Saved to {rosters_file_loc}")

# Fetch and save injury list
print("Fetching injury list...")

injury_df = nfl.load_injuries()
injury_file_loc = OUTPUT_DIR / "injuries.parquet"
injury_df.write_parquet(str(injury_file_loc), compression="snappy")
print(f"  Saved to {injury_file_loc}")

print("Done.")