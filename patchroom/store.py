"""Transactional local state. Local users can edit this database; it is not a trust boundary."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


TRANSITIONS = {
    'reported': {'needs_information', 'reproducing'},
    'needs_information': {'reported'},
    'reproducing': {'reproduced', 'not_reproduced', 'reproduction_error'},
    'not_reproduced': {'reproducing', 'needs_information'},
    'reproduction_error': {'reproducing', 'needs_information'},
    'reproduced': {'patching'},
    'patching': {'verifying'},
    'verifying': {'patching', 'awaiting_human_review'},
    'awaiting_human_review': {'accepted', 'rejected', 'patching'},
    'accepted': {'patching'},
    'rejected': {'patching'},
}


class Store:
    def __init__(self, work):
        self.work = Path(work).resolve()
        self.work.mkdir(parents=True, exist_ok=True)
        self.db = self.work / 'patchroom.sqlite3'
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL, at TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY, case_id TEXT NOT NULL,
                    operation TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL,
                    owner_pid INTEGER NOT NULL, created_at TEXT NOT NULL, result TEXT);
                CREATE TABLE IF NOT EXISTS proposals(case_id TEXT NOT NULL, id TEXT NOT NULL,
                    data TEXT NOT NULL, PRIMARY KEY(case_id,id));
                CREATE TABLE IF NOT EXISTS handoffs(case_id TEXT NOT NULL, event_id TEXT NOT NULL,
                    data TEXT NOT NULL, PRIMARY KEY(case_id,event_id));
                PRAGMA user_version=1;
            ''')

    def connect(self):
        db = sqlite3.connect(str(self.db), timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, case_id, db=None):
        if db is None:
            with self.connect() as connection:
                return self.get(case_id, connection)
        row = db.execute('SELECT data FROM cases WHERE id=?', (case_id,)).fetchone()
        if row is None:
            raise ValueError('unknown case: ' + case_id)
        return json.loads(row['data'])

    def put(self, db, case):
        db.execute('UPDATE cases SET data=? WHERE id=?', (json.dumps(case), case['id']))

    def event(self, db, case_id, kind, data):
        db.execute('INSERT INTO events(case_id,at,kind,data) VALUES(?,?,?,?)',
                   (case_id, now(), kind, json.dumps(data)))

    def transition(self, db, case, target, reason):
        previous = case['status']
        if target not in TRANSITIONS.get(previous, set()):
            raise ValueError('invalid transition: ' + previous + ' -> ' + target)
        case['status'] = target
        self.event(db, case['id'], 'state_changed',
                   {'from': previous, 'to': target, 'reason': reason})

    def proposals(self, case_id, db=None):
        if db is None:
            with self.connect() as connection:
                return self.proposals(case_id, connection)
        return [json.loads(row['data']) for row in db.execute(
            'SELECT data FROM proposals WHERE case_id=? ORDER BY id', (case_id,))]

    def save_proposal(self, db, case_id, proposal):
        db.execute('INSERT OR REPLACE INTO proposals(case_id,id,data) VALUES(?,?,?)',
                   (case_id, proposal['id'], json.dumps(proposal)))

    def timeline(self, case_id):
        self.get(case_id)
        with self.connect() as db:
            return [dict(seq=r['seq'], at=r['at'], kind=r['kind'], data=json.loads(r['data']))
                    for r in db.execute('SELECT * FROM events WHERE case_id=? ORDER BY seq', (case_id,))]
