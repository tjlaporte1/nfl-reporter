# Fetch and save NFL data (teams, schedules, and stats) to parquet files
import polars as pl
import nflreadpy as nfl
from pathlib import Path

# Setup output directory
OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)


# Determine seasons to fetch
print("Finding the season...")

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
teams_file_loc = OUTPUT_DIR / "teams.parquet"
teams_df.write_parquet(str(teams_file_loc), compression="snappy")
print(f"  Saved to {teams_file_loc}")

# Fetch and save latest schedule
print("Fetching schedules...")

schedules_df = nfl.load_schedules(seasons=max_season)
schedules_file_loc = OUTPUT_DIR / "schedules.parquet"
schedules_df.write_parquet(str(schedules_file_loc), compression="snappy")
print(f"  Saved to {schedules_file_loc}")

# Fetch and save team stats
print("Fetching team stats data...")

team_stats_df = nfl.load_team_stats(seasons=stats_seasons)
team_stats_file_loc = OUTPUT_DIR / "team-stats.parquet"
team_stats_df.write_parquet(str(team_stats_file_loc), compression="snappy")
print(f"  Saved to {team_stats_file_loc}")

# Fetch and save player stats
print("Fetching player stats data...")
player_stats_df = nfl.load_player_stats(seasons=stats_seasons)
player_stats_file_loc = OUTPUT_DIR / "player-stats.parquet"
player_stats_df.write_parquet(str(player_stats_file_loc), compression="snappy")
print(f"  Saved to {player_stats_file_loc}")

print("Done.")
