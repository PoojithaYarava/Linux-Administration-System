-- Reference schema. The API creates these tables with IF NOT EXISTS at startup.
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS system_metrics (
  id INTEGER PRIMARY KEY,
  timestamp TEXT NOT NULL,
  cpu_usage REAL NOT NULL,
  memory_usage REAL NOT NULL,
  disk_usage REAL NOT NULL,
  network_received INTEGER NOT NULL,
  network_sent INTEGER NOT NULL,
  load_average REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS processes (
  id INTEGER PRIMARY KEY,
  timestamp TEXT NOT NULL,
  pid INTEGER NOT NULL,
  process_name TEXT NOT NULL,
  cpu_usage REAL NOT NULL,
  memory_usage REAL NOT NULL,
  status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS services (
  id INTEGER PRIMARY KEY,
  service_name TEXT NOT NULL,
  status TEXT NOT NULL,
  enabled INTEGER NOT NULL,
  checked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS logs (
  id INTEGER PRIMARY KEY,
  timestamp TEXT NOT NULL,
  source TEXT NOT NULL,
  severity TEXT NOT NULL,
  message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY,
  timestamp TEXT NOT NULL,
  alert_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  message TEXT NOT NULL,
  status TEXT NOT NULL,
  source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  action_type TEXT NOT NULL,
  target TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  executed_at TEXT,
  status TEXT NOT NULL,
  result TEXT
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  action TEXT NOT NULL,
  target TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  result TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
