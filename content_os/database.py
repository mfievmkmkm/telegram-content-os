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
              views INTEGER,reactions INTEGER DEFAULT 0,forwards INTEGER DEFAULT 0,media_kind TEXT,media_ref TEXT,
              posted_at TEXT,imported_at TEXT NOT NULL,
              UNIQUE(source_channel,telegram_post_id));
            CREATE TABLE IF NOT EXISTS post_metrics(
              id INTEGER PRIMARY KEY AUTOINCREMENT,draft_id INTEGER NOT NULL,views INTEGER NOT NULL DEFAULT 0,
              reactions INTEGER NOT NULL DEFAULT 0,forwards INTEGER NOT NULL DEFAULT 0,
              engagement REAL NOT NULL DEFAULT 0,captured_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS match_jobs(
              id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT,source_type TEXT NOT NULL,
              source_ref TEXT NOT NULL,player_ref TEXT NOT NULL,analysis_mode TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'queued',progress INTEGER NOT NULL DEFAULT 0,
              result_url TEXT,error TEXT,metrics_json TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS players(
              id INTEGER PRIMARY KEY AUTOINCREMENT,display_name TEXT NOT NULL,birth_year INTEGER,
              position TEXT,strong_foot TEXT,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS player_matches(
              player_id INTEGER NOT NULL,match_job_id INTEGER NOT NULL,created_at TEXT NOT NULL,
              PRIMARY KEY(player_id,match_job_id));
            CREATE TABLE IF NOT EXISTS service_orders(
              id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,username TEXT,
              offer_key TEXT NOT NULL,brief TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'new',
              created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS funnel_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,event_type TEXT NOT NULL,
              source TEXT,offer_key TEXT,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS course_notes(
              id INTEGER PRIMARY KEY AUTOINCREMENT,source_channel TEXT NOT NULL,message_id INTEGER NOT NULL,
              text TEXT NOT NULL,posted_at TEXT,imported_at TEXT NOT NULL,UNIQUE(source_channel,message_id));
            """)
            columns={row[1] for row in db.execute("PRAGMA table_info(drafts)")}
            if "published_message_id" not in columns:
                db.execute("ALTER TABLE drafts ADD COLUMN published_message_id INTEGER")
            post_columns={row[1] for row in db.execute("PRAGMA table_info(channel_posts)")}
            for name,declaration in {"reactions":"INTEGER DEFAULT 0","forwards":"INTEGER DEFAULT 0","media_kind":"TEXT","media_ref":"TEXT"}.items():
                if name not in post_columns: db.execute(f"ALTER TABLE channel_posts ADD COLUMN {name} {declaration}")
            match_columns={row[1] for row in db.execute("PRAGMA table_info(match_jobs)")}
            if "metrics_json" not in match_columns: db.execute("ALTER TABLE match_jobs ADD COLUMN metrics_json TEXT")

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

    def future_scheduled(self, now, limit=30):
        with self.connect() as db:
            return db.execute("SELECT * FROM drafts WHERE status='scheduled' AND scheduled_at>? ORDER BY scheduled_at LIMIT ?",(now,limit)).fetchall()

    def save_video_job(self, draft_id, payload):
        with self.connect() as db:
            cur=db.execute("INSERT INTO video_jobs(draft_id,payload,created_at) VALUES(?,?,?)",
                           (draft_id,payload,datetime.now(self.timezone).isoformat()))
            return cur.lastrowid

    def save_channel_post(self,channel_key,source_channel,source_role,post_id,text,views=None,posted_at=None,
                          reactions=0,forwards=0,media_kind=None,media_ref=None):
        with self.connect() as db:
            cur=db.execute("INSERT OR IGNORE INTO channel_posts(channel_key,source_channel,source_role,telegram_post_id,text,views,reactions,forwards,media_kind,media_ref,posted_at,imported_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                           (channel_key,source_channel,source_role,post_id,text,views,reactions,forwards,media_kind,media_ref,posted_at,datetime.now(self.timezone).isoformat()))
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

    def editorial_insights(self,channel_key):
        with self.connect() as db:
            rows=db.execute("""SELECT d.format_key,AVG(m.engagement) avg_er,COUNT(*) samples
              FROM drafts d JOIN post_metrics m ON m.id=(SELECT id FROM post_metrics WHERE draft_id=d.id ORDER BY captured_at DESC LIMIT 1)
              WHERE d.channel_key=? GROUP BY d.format_key HAVING COUNT(*)>=2 ORDER BY avg_er DESC LIMIT 3""",(channel_key,)).fetchall()
        return [{"format_key":row["format_key"],"avg_er":row["avg_er"],"samples":row["samples"]} for row in rows]

    def save_match_job(self,source_type,source_ref,player_ref,analysis_mode):
        now=datetime.now(self.timezone).isoformat()
        with self.connect() as db:
            cur=db.execute("INSERT INTO match_jobs(source_type,source_ref,player_ref,analysis_mode,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                           (source_type,source_ref,player_ref,analysis_mode,now,now))
            return cur.lastrowid

    def update_match_job(self,job_id,**fields):
        allowed={"external_id","status","progress","result_url","error","metrics_json"}; clean={k:v for k,v in fields.items() if k in allowed}
        clean["updated_at"]=datetime.now(self.timezone).isoformat()
        with self.connect() as db:
            db.execute(f"UPDATE match_jobs SET {','.join(f'{k}=?' for k in clean)} WHERE id=?",(*clean.values(),job_id))

    def match_job(self,job_id):
        with self.connect() as db: return db.execute("SELECT * FROM match_jobs WHERE id=?",(job_id,)).fetchone()

    def save_player(self,display_name,birth_year=None,position="",strong_foot=""):
        with self.connect() as db:
            cur=db.execute("INSERT INTO players(display_name,birth_year,position,strong_foot,created_at) VALUES(?,?,?,?,?)",
                           (display_name,birth_year,position,strong_foot,datetime.now(self.timezone).isoformat())); return cur.lastrowid

    def players(self):
        with self.connect() as db: return db.execute("SELECT * FROM players ORDER BY id DESC").fetchall()

    def link_player_match(self,player_id,match_job_id):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO player_matches(player_id,match_job_id,created_at) VALUES(?,?,?)",
                       (player_id,match_job_id,datetime.now(self.timezone).isoformat()))

    def player_report(self,player_id):
        with self.connect() as db:
            player=db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone()
            matches=db.execute("SELECT j.* FROM match_jobs j JOIN player_matches p ON p.match_job_id=j.id WHERE p.player_id=? ORDER BY j.created_at",(player_id,)).fetchall()
        return player,matches

    def save_service_order(self,user_id,username,offer_key,brief):
        with self.connect() as db:
            cur=db.execute("INSERT INTO service_orders(user_id,username,offer_key,brief,created_at) VALUES(?,?,?,?,?)",
                           (user_id,username,offer_key,brief,datetime.now(self.timezone).isoformat()))
            return cur.lastrowid

    def service_orders(self,status="new",limit=30):
        with self.connect() as db:
            return db.execute("SELECT * FROM service_orders WHERE status=? ORDER BY id DESC LIMIT ?",(status,limit)).fetchall()

    def service_order(self,order_id):
        with self.connect() as db: return db.execute("SELECT * FROM service_orders WHERE id=?",(order_id,)).fetchone()

    def update_service_order(self,order_id,status):
        with self.connect() as db: db.execute("UPDATE service_orders SET status=? WHERE id=?",(status,order_id))

    def save_funnel_event(self,user_id,event_type,source="",offer_key=""):
        with self.connect() as db: db.execute("INSERT INTO funnel_events(user_id,event_type,source,offer_key,created_at) VALUES(?,?,?,?,?)",
          (user_id,event_type,source,offer_key,datetime.now(self.timezone).isoformat()))

    def funnel_events(self,limit=5000):
        with self.connect() as db: return db.execute("SELECT * FROM funnel_events ORDER BY id DESC LIMIT ?",(limit,)).fetchall()

    def save_course_note(self,source_channel,message_id,text,posted_at=None):
        with self.connect() as db:
            cur=db.execute("INSERT OR IGNORE INTO course_notes(source_channel,message_id,text,posted_at,imported_at) VALUES(?,?,?,?,?)",
              (source_channel,message_id,text,posted_at,datetime.now(self.timezone).isoformat())); return bool(cur.rowcount)

    def course_snippets(self,limit=12):
        with self.connect() as db: return db.execute("SELECT text,source_channel FROM course_notes ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
