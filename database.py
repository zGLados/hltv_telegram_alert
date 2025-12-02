import sqlite3
from typing import List, Set
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialisiere die Datenbank mit notwendigen Tabellen"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Table for user favorites
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    user_id INTEGER,
                    team_name TEXT,
                    PRIMARY KEY (user_id, team_name)
                )
            ''')
            
            # Table for already sent notifications
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications_sent (
                    user_id INTEGER,
                    match_id TEXT,
                    notification_type TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, match_id, notification_type)
                )
            ''')
            
            conn.commit()
            logger.info("Datenbank initialisiert")

    def add_favorite(self, user_id: int, team_name: str) -> bool:
        """Add a favorite team"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT OR IGNORE INTO favorites (user_id, team_name) VALUES (?, ?)',
                    (user_id, team_name)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error adding favorite: {e}")
            return False

    def remove_favorite(self, user_id: int, team_name: str) -> bool:
        """Remove a favorite team"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'DELETE FROM favorites WHERE user_id = ? AND team_name = ?',
                    (user_id, team_name)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error removing favorite: {e}")
            return False

    def get_favorites(self, user_id: int) -> List[str]:
        """Hole alle Favoriten eines Benutzers"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT team_name FROM favorites WHERE user_id = ? ORDER BY team_name',
                    (user_id,)
                )
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error retrieving users: {e}")
            return []

    def get_all_users_with_favorites(self) -> Set[int]:
        """Hole alle User-IDs, die Favoriten haben"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT user_id FROM favorites')
                return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error retrieving users: {e}")
            return set()

    def mark_notification_sent(self, user_id: int, match_id: str, notification_type: str):
        """Mark a notification as sent"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT OR IGNORE INTO notifications_sent (user_id, match_id, notification_type) VALUES (?, ?, ?)',
                    (user_id, match_id, notification_type)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error marking notification: {e}")

    def was_notification_sent(self, user_id: int, match_id: str, notification_type: str) -> bool:
        """Check if a notification was already sent"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT 1 FROM notifications_sent WHERE user_id = ? AND match_id = ? AND notification_type = ?',
                    (user_id, match_id, notification_type)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking notification: {e}")
            return False
