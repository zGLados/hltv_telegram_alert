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
            
            # Tabelle für Benutzer-Favoriten
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    user_id INTEGER,
                    team_name TEXT,
                    PRIMARY KEY (user_id, team_name)
                )
            ''')
            
            # Tabelle für bereits gesendete Benachrichtigungen
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
        """Füge ein Favoriten-Team hinzu"""
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
            logger.error(f"Fehler beim Hinzufügen von Favorit: {e}")
            return False

    def remove_favorite(self, user_id: int, team_name: str) -> bool:
        """Entferne ein Favoriten-Team"""
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
            logger.error(f"Fehler beim Entfernen von Favorit: {e}")
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
            logger.error(f"Fehler beim Abrufen von Favoriten: {e}")
            return []

    def get_all_users_with_favorites(self) -> Set[int]:
        """Hole alle User-IDs, die Favoriten haben"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT user_id FROM favorites')
                return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Fehler beim Abrufen von Benutzern: {e}")
            return set()

    def mark_notification_sent(self, user_id: int, match_id: str, notification_type: str):
        """Markiere eine Benachrichtigung als gesendet"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT OR IGNORE INTO notifications_sent (user_id, match_id, notification_type) VALUES (?, ?, ?)',
                    (user_id, match_id, notification_type)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Fehler beim Markieren der Benachrichtigung: {e}")

    def was_notification_sent(self, user_id: int, match_id: str, notification_type: str) -> bool:
        """Prüfe ob eine Benachrichtigung bereits gesendet wurde"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT 1 FROM notifications_sent WHERE user_id = ? AND match_id = ? AND notification_type = ?',
                    (user_id, match_id, notification_type)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Fehler beim Prüfen der Benachrichtigung: {e}")
            return False
