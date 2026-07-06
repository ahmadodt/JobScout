CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT NOT NULL,
    date_posted TEXT,
    date_collected TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'relevant', 'ignored', 'applied')),
    score INTEGER,
    score_reason TEXT,
    score_source TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_date_collected ON jobs(date_collected);

CREATE TABLE IF NOT EXISTS company_watchlist (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    careers_url TEXT,
    added_at TEXT DEFAULT (datetime('now')),
    active INTEGER DEFAULT 1
);
