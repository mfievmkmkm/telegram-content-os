import os
import sqlite3
from datetime import datetime


class Database:
    def __init__(self, path: str, timezone):
        self.path, self.timezone = path, timezone

    def connect(self):
        folder = os.path.dirname(self.path)
        if folder: os.makedirs(folder, exist_ok=True)
        db = sqlite3.connect(self.path); db.row_factory = sqlite3.Row
        return db

    def init(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS drafts(
              id INTEGER PRIMARY KEY AUTOINCREMENT,channel_key TEXT NOT NULL,format_key TEXT NOT NULL,
              text TEXT NOT NULL,hook_score INTEGER NOT NULL,source_title TEXT,source_url TEXT,
              source_hash TEXT,status TEXT NOT NULL DEFAULT 'review',scheduled_at TEXT,created_at TEXT NOT NULL,
              published_at TEXT,published_message_id INTEGER);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_source ON drafts(channel_key,source_hash)
              WHERE source_hash IS NOT NULL;
            CREATE TABLE IF NOT EXISTS video_jobs(
              id INTEGER PRIMARY KEY AUTOINCREMENT,draft_id INTEGER NOT NULL,payload TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'ready',result_url TEXT,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS channel_posts(
              id INTEGER PRIMARY KEY AUTOINCREMENT,channel_key TEXT NOT NULL,source_channel TEXT NOT NULL,
              source_role TEXT NOT NULL,telegram_post_id INTEGER NOT NULL,text TEXT NOT NULL,
              views INTEGER,posted_at TEXT,imported_at TEXT NOT NULL,
              UNIQUE(source_channel,telegram_post_id));
            CREATE TABLE IF NOT EXISTS post_metrics(
              id INTEGER PRIMARY KEY AUTOINCREMENT,draft_id INTEGER NOT NULL,views INTEGER NOT NULL DEFAULT 0,
              reactions INTEGER NOT NULL DEFAULT 0,forwards INTEGER NOT NULL DEFAULT 0,
              engagement REAL NOT NULL DEFAULT 0,captured_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS match_jobs(
              id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT,source_type TEXT NOT NULL,
              source_ref TEXT NOT NULL,player_ref TEXT NOT NULL,analysis_mode TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'queued',progress INTEGER NOT NULL DEFAULT 0,
              result_url TEXT,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            """)
            columns={row[1] for row in db.execute("PRAGMA table_info(drafts)")}
            if "published_message_id" not in columns:
                db.execute("ALTER TABLE drafts ADD COLUMN published_message_id INTEGER")

    def set(self, key, value):
        with self.connect() as db:
            db.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def get(self, key):
        with self.connect() as db: row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def used_hashes(self, channel_key):
        with self.connect() as db:
            return {r[0] for r in db.execute("SELECT source_hash FROM drafts WHERE channel_key=? AND source_hash IS NOT NULL", (channel_key,))}

    def save_draft(self, channel_key, format_key, text, hook_score, title="", url="", source_hash=None):
        with self.connect() as db:
            cur = db.execute("INSERT INTO drafts(channel_key,format_key,text,hook_score,source_title,source_url,source_hash,created_at) VALUES(?,?,?,?,?,?,?,?)",
                             (channel_key,format_key,text,hook_score,title,url,source_hash,datetime.now(self.timezone).isoformat()))
            return cur.lastrowid

    def draft(self, draft_id):
        with self.connect() as db: return db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()

    def update(self, draft_id, **fields):
        allowed = {"text","hook_score","status","scheduled_at","published_at","published_message_id"}; clean = {k:v for k,v in fields.items() if k in allowed}
        if clean:
            with self.connect() as db: db.execute(f"UPDATE drafts SET {','.join(f'{k}=?' for k in clean)} WHERE id=?", (*clean.values(),draft_id))

    def scheduled(self, now):
        with self.connect() as db:
            return db.execute("SELECT * FROM drafts WHERE status='scheduled' AND scheduled_at<=?", (now,)).fetchall()

    def save_video_job(self, draft_id, payload):
        with self.connect() as db:
            cur=db.execute("INSERT INTO video_jobs(draft_id,payload,created_at) VALUES(?,?,?)",
                           (draft_id,payload,datetime.now(self.timezone).isoformat()))
            return cur.lastrowid

    def save_channel_post(self, channel_key, source_channel, source_role, post_id, text, views=None, posted_at=None):
        with self.connect() as db:
            cur=db.execute("INSERT OR IGNORE INTO channel_posts(channel_key,source_channel,source_role,telegram_post_id,text,views,posted_at,imported_at) VALUES(?,?,?,?,?,?,?,?)",
                           (channel_key,source_channel,source_role,post_id,text,views,posted_at,datetime.now(self.timezone).isoformat()))
            return bool(cur.rowcount)

    def style_examples(self, channel_key, limit=6):
        with self.connect() as db:
            return db.execute("SELECT text FROM channel_posts WHERE channel_key=? AND source_role='own' ORDER BY telegram_post_id DESC LIMIT ?",(channel_key,limit)).fetchall()

    def radar_posts(self, channel_key, limit=8):
        with self.connect() as db:
            return db.execute("SELECT text FROM channel_posts WHERE channel_key=? AND source_role='radar' ORDER BY telegram_post_id DESC LIMIT ?",(channel_key,limit)).fetchall()

    def import_counts(self):
        with self.connect() as db:
            return db.execute("SELECT source_channel,source_role,COUNT(*) count FROM channel_posts GROUP BY source_channel,source_role").fetchall()

    def published_for_metrics(self, limit=100):
        with self.connect() as db:
            return db.execute("SELECT * FROM drafts WHERE status='published' AND published_message_id IS NOT NULL ORDER BY published_at DESC LIMIT ?",(limit,)).fetchall()

    def save_metrics(self,draft_id,views,reactions,forwards):
        engagement=((reactions+forwards*2)/views*100) if views else 0
        with self.connect() as db:
            db.execute("INSERT INTO post_metrics(draft_id,views,reactions,forwards,engagement,captured_at) VALUES(?,?,?,?,?,?)",
                       (draft_id,views,reactions,forwards,engagement,datetime.now(self.timezone).isoformat()))

    def analytics_summary(self, limit=10):
        with self.connect() as db:
            return db.execute("""SELECT d.id,d.channel_key,d.format_key,d.hook_score,d.text,m.views,m.reactions,m.forwards,m.engagement
              FROM drafts d JOIN post_metrics m ON m.id=(SELECT id FROM post_metrics WHERE draft_id=d.id ORDER BY captured_at DESC LIMIT 1)
              ORDER BY m.engagement DESC,m.views DESC LIMIT ?""",(limit,)).fetchall()

    def save_match_job(self,source_type,source_ref,player_ref,analysis_mode):
        now=datetime.now(self.timezone).isoformat()
        with self.connect() as db:
            cur=db.execute("INSERT INTO match_jobs(source_type,source_ref,player_ref,analysis_mode,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                           (source_type,source_ref,player_ref,analysis_mode,now,now))
            return cur.lastrowid

    def update_match_job(self,job_id,**fields):
        allowed={"external_id","status","progress","result_url","error"}; clean={k:v for k,v in fields.items() if k in allowed}
        clean["updated_at"]=datetime.now(self.timezone).isoformat()
        with self.connect() as db:
            db.execute(f"UPDATE match_jobs SET {','.join(f'{k}=?' for k in clean)} WHERE id=?",(*clean.values(),job_id))

    def match_job(self,job_id):
        with self.connect() as db: return db.execute("SELECT * FROM match_jobs WHERE id=?",(job_id,)).fetchone()
