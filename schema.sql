-- =============================================================================
-- Clash Royale Crawler — Database Schema (SQLite / libSQL / Turso)
-- =============================================================================

CREATE TABLE IF NOT EXISTS players (
  tag TEXT PRIMARY KEY,
  name TEXT,
  clan_tag TEXT,
  clan_name TEXT,
  trophies INTEGER,
  best_trophies INTEGER,
  exp_level INTEGER,
  arena_id INTEGER,
  battle_count INTEGER,
  wins INTEGER,
  losses INTEGER,
  three_crown_wins INTEGER,
  donations INTEGER,
  donations_received INTEGER,
  last_seen_api TEXT,
  last_battle_time TEXT,
  activity_status TEXT DEFAULT 'unknown',
  activity_score INTEGER DEFAULT 0,
  discovered_from TEXT,
  discovery_depth INTEGER DEFAULT 0,
  last_profile_scan_at TEXT,
  last_battlelog_scan_at TEXT,
  next_scan_at TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_players_next_scan   ON players(next_scan_at);
CREATE INDEX IF NOT EXISTS idx_players_activity    ON players(activity_status, activity_score);
CREATE INDEX IF NOT EXISTS idx_players_clan        ON players(clan_tag);

CREATE TABLE IF NOT EXISTS clans (
  tag TEXT PRIMARY KEY,
  name TEXT,
  location_id INTEGER,
  members INTEGER,
  clan_score INTEGER,
  required_trophies INTEGER,
  last_members_scan_at TEXT,
  next_members_scan_at TEXT,
  discovered_from TEXT,
  discovery_depth INTEGER DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clans_next_scan ON clans(next_members_scan_at);

CREATE TABLE IF NOT EXISTS player_queue (
  tag TEXT PRIMARY KEY,
  priority INTEGER DEFAULT 50,
  source TEXT,
  depth INTEGER DEFAULT 0,
  attempts INTEGER DEFAULT 0,
  next_try_at TEXT DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_player_queue_next
  ON player_queue(priority DESC, next_try_at);

CREATE TABLE IF NOT EXISTS clan_queue (
  tag TEXT PRIMARY KEY,
  priority INTEGER DEFAULT 50,
  source TEXT,
  depth INTEGER DEFAULT 0,
  attempts INTEGER DEFAULT 0,
  next_try_at TEXT DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clan_queue_next
  ON clan_queue(priority DESC, next_try_at);

CREATE TABLE IF NOT EXISTS battle_summaries (
  battle_id TEXT PRIMARY KEY,
  battle_time TEXT,
  battle_type TEXT,
  game_mode TEXT,
  player_tag TEXT,
  opponent_tag TEXT,
  player_crowns INTEGER,
  opponent_crowns INTEGER,
  result TEXT,
  player_deck_hash TEXT,
  opponent_deck_hash TEXT,
  raw_r2_key TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_battle_player ON battle_summaries(player_tag);
CREATE INDEX IF NOT EXISTS idx_battle_time   ON battle_summaries(battle_time);

CREATE TABLE IF NOT EXISTS crawl_stats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  stat_key TEXT,
  stat_value TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
