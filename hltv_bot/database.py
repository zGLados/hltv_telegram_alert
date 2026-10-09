"""SQLite persistence: users, favourite teams, sent notifications and the known-team list."""
import logging
import os
import shutil
import sqlite3
from contextlib import contextmanager
from typing import Iterable, List, Optional, Set

logger = logging.getLogger(__name__)

DEFAULT_MIN_STARS = 1


class Database:
    def __init__(self, db_path: str, template_path: Optional[str] = None):
        self.db_path = db_path
        self._init_from_template(template_path)
        self._init_schema()

    @contextmanager
    def _connect(self):
        """Open a connection, commit on success, always close."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_from_template(self, template_path: Optional[str]):
        """On first start copy the shipped template DB (pre-loaded team list)."""
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if (template_path and not os.path.exists(self.db_path)
                and os.path.exists(template_path)
                and os.path.abspath(template_path) != os.path.abspath(self.db_path)):
            shutil.copyfile(template_path, self.db_path)
            logger.info(f"Initialised database from template {template_path}")

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS favorites (
                    user_id INTEGER,
                    team_name TEXT,
                    PRIMARY KEY (user_id, team_name)
                );

                -- One row per known user (created on /start or any setting change)
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    min_stars INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS notifications_sent (
                    user_id INTEGER,
                    match_id TEXT,
                    notification_type TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, match_id, notification_type)
                );

                CREATE TABLE IF NOT EXISTS valid_teams (
                    team_name TEXT PRIMARY KEY,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
        logger.info("Database initialised")

    # --- Users ----------------------------------------------------------------

    def register_user(self, user_id: int):
        """Make sure the user exists so they receive the daily summary."""
        with self._connect() as conn:
            conn.execute(
                'INSERT OR IGNORE INTO user_settings (user_id, min_stars) VALUES (?, ?)',
                (user_id, DEFAULT_MIN_STARS)
            )

    def get_all_users(self) -> Set[int]:
        """All users that ever interacted with the bot (registered or with favourites)."""
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT user_id FROM user_settings UNION SELECT user_id FROM favorites'
            ).fetchall()
        return {row[0] for row in rows}

    def get_all_users_with_favorites(self) -> Set[int]:
        with self._connect() as conn:
            rows = conn.execute('SELECT DISTINCT user_id FROM favorites').fetchall()
        return {row[0] for row in rows}

    def set_min_stars(self, user_id: int, min_stars: int):
        with self._connect() as conn:
            conn.execute(
                'INSERT INTO user_settings (user_id, min_stars) VALUES (?, ?) '
                'ON CONFLICT(user_id) DO UPDATE SET min_stars = excluded.min_stars',
                (user_id, min_stars)
            )

    def get_min_stars(self, user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT min_stars FROM user_settings WHERE user_id = ?', (user_id,)
            ).fetchone()
        return row[0] if row else DEFAULT_MIN_STARS

    # --- Favourites -------------------------------------------------------------

    def add_favorite(self, user_id: int, team_name: str) -> bool:
        """Add a favourite. Returns False if it already exists (case-insensitive)."""
        with self._connect() as conn:
            exists = conn.execute(
                'SELECT 1 FROM favorites WHERE user_id = ? AND team_name = ? COLLATE NOCASE',
                (user_id, team_name)
            ).fetchone()
            if exists:
                return False
            conn.execute(
                'INSERT INTO favorites (user_id, team_name) VALUES (?, ?)',
                (user_id, team_name)
            )
        return True

    def remove_favorite(self, user_id: int, team_name: str) -> Optional[str]:
        """Remove a favourite (case-insensitive). Returns the stored name, or None."""
        with self._connect() as conn:
            row = conn.execute(
                'SELECT team_name FROM favorites WHERE user_id = ? AND team_name = ? COLLATE NOCASE',
                (user_id, team_name)
            ).fetchone()
            if not row:
                return None
            conn.execute(
                'DELETE FROM favorites WHERE user_id = ? AND team_name = ?',
                (user_id, row[0])
            )
        return row[0]

    def get_favorites(self, user_id: int) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT team_name FROM favorites WHERE user_id = ? ORDER BY team_name COLLATE NOCASE',
                (user_id,)
            ).fetchall()
        return [row[0] for row in rows]

    # --- Notifications ----------------------------------------------------------

    def mark_notification_sent(self, user_id: int, match_id: str, notification_type: str):
        with self._connect() as conn:
            conn.execute(
                'INSERT OR IGNORE INTO notifications_sent (user_id, match_id, notification_type) '
                'VALUES (?, ?, ?)',
                (user_id, match_id, notification_type)
            )

    def was_notification_sent(self, user_id: int, match_id: str, notification_type: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT 1 FROM notifications_sent '
                'WHERE user_id = ? AND match_id = ? AND notification_type = ?',
                (user_id, match_id, notification_type)
            ).fetchone()
        return row is not None

    def prune_notifications(self, days: int = 30):
        """Forget sent notifications older than `days` (keeps the table small)."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM notifications_sent WHERE sent_at < datetime('now', ?)",
                (f'-{days} days',)
            )

    # --- Known teams --------------------------------------------------------------

    def update_valid_teams(self, teams: Iterable[str]):
        """Merge scraped team names into the known-team list.

        Teams are only added, never removed: a partial scrape (e.g. rankings page
        blocked, only the match list worked) must not shrink the list. If a team
        already exists with different capitalisation, the new spelling wins.
        """
        teams = [t for t in teams if t]
        with self._connect() as conn:
            for team in teams:
                conn.execute('DELETE FROM valid_teams WHERE team_name = ? COLLATE NOCASE', (team,))
                conn.execute('INSERT INTO valid_teams (team_name) VALUES (?)', (team,))
        logger.info(f"Merged {len(teams)} teams into the team list")

    def get_valid_teams(self) -> Set[str]:
        with self._connect() as conn:
            rows = conn.execute('SELECT team_name FROM valid_teams').fetchall()
        return {row[0] for row in rows}
