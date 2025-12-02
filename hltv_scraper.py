import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import re
import time
from config import HLTV_BASE_URL, HLTV_MATCHES_URL, HLTV_RESULTS_URL, HEADERS

logger = logging.getLogger(__name__)


class Match:
    """Repräsentiert ein HLTV Match"""
    def __init__(self, match_id: str, team1: str, team2: str, 
                 event: str, time: Optional[datetime], stars: int, 
                 score: Optional[str] = None, status: str = "upcoming"):
        self.match_id = match_id
        self.team1 = team1
        self.team2 = team2
        self.event = event
        self.time = time
        self.stars = stars
        self.score = score
        self.status = status

    def __str__(self):
        if self.score:
            return f"{self.team1} vs {self.team2} - {self.score}\n📍 {self.event}"
        elif self.time:
            time_str = self.time.strftime("%H:%M")
            return f"{self.team1} vs {self.team2}\n⏰ {time_str} | 📍 {self.event}"
        else:
            return f"{self.team1} vs {self.team2}\n📍 {self.event}"

    def has_team(self, team_name: str) -> bool:
        """Prüfe ob ein Team in diesem Match spielt"""
        team_name_lower = team_name.lower()
        return (team_name_lower in self.team1.lower() or 
                team_name_lower in self.team2.lower())


class HLTVScraper:
    """Scraper für HLTV.org"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._team_cache = set()  # Cache für gefundene Teams
        self._last_request_time = 0
        self._request_delay = 2  # Sekunden zwischen Requests

    def _rate_limit(self):
        """Rate limiting um HLTV nicht zu überlasten"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._request_delay:
            time.sleep(self._request_delay - time_since_last)
        self._last_request_time = time.time()

    def search_team(self, team_name: str) -> bool:
        """Prüfe ob ein Team auf HLTV existiert"""
        try:
            self._rate_limit()
            # Suche auf der Teams-Seite
            search_url = f"{HLTV_BASE_URL}/search?term={team_name}"
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Suche nach Team-Ergebnissen
            team_results = soup.find_all('a', href=re.compile(r'/team/\d+/'))
            
            if team_results:
                # Speichere gefundene Teams im Cache
                for result in team_results:
                    team_text = result.get_text(strip=True)
                    if team_text:
                        self._team_cache.add(team_text.lower())
                
                # Prüfe ob der gesuchte Name in den Ergebnissen ist
                team_name_lower = team_name.lower()
                for result in team_results:
                    result_name = result.get_text(strip=True).lower()
                    if team_name_lower in result_name or result_name in team_name_lower:
                        logger.info(f"Team '{team_name}' found on HLTV")
                        return True
            
            logger.info(f"Team '{team_name}' not found on HLTV")
            return False
            
        except Exception as e:
            logger.error(f"Error searching for team '{team_name}': {e}")
            # Bei Fehler erlauben wir das Team trotzdem (z.B. bei Netzwerkproblemen)
            return True

    def get_todays_matches(self, min_stars: int = 0) -> List[Match]:
        """Hole die heutigen Matches von HLTV"""
        try:
            self._rate_limit()
            response = self.session.get(HLTV_MATCHES_URL, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            matches = []
            
            # Finde alle Match-Container für heute
            match_containers = soup.find_all('div', class_='upcomingMatch')
            
            for container in match_containers:
                try:
                    match = self._parse_match_container(container)
                    if match and match.stars >= min_stars:
                        matches.append(match)
                except Exception as e:
                    logger.error(f"Fehler beim Parsen eines Matches: {e}")
                    continue
            
            logger.info(f"{len(matches)} Matches für heute gefunden")
            return matches
            
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Matches: {e}")
            return []

    def _parse_match_container(self, container) -> Optional[Match]:
        """Parse einen Match-Container"""
        try:
            # Match ID
            match_link = container.find('a', class_='match')
            if not match_link:
                return None
            
            match_id = match_link.get('href', '').split('/')[-2]
            
            # Teams
            team_divs = container.find_all('div', class_='matchTeam')
            if len(team_divs) < 2:
                return None
            
            team1 = team_divs[0].find('div', class_='matchTeamName')
            team2 = team_divs[1].find('div', class_='matchTeamName')
            
            if not team1 or not team2:
                return None
            
            team1_name = team1.text.strip()
            team2_name = team2.text.strip()
            
            # Event
            event_div = container.find('div', class_='matchEventName')
            event = event_div.text.strip() if event_div else "Unknown Event"
            
            # Zeit
            time_div = container.find('div', class_='matchTime')
            match_time = None
            if time_div:
                time_str = time_div.text.strip()
                match_time = self._parse_time(time_str)
            
            # Sterne (Wichtigkeit)
            stars = 0
            star_divs = container.find_all('i', class_='fa-star')
            stars = len([s for s in star_divs if 'fa-star' in s.get('class', [])])
            
            return Match(
                match_id=match_id,
                team1=team1_name,
                team2=team2_name,
                event=event,
                time=match_time,
                stars=stars
            )
            
        except Exception as e:
            logger.error(f"Fehler beim Parsen des Match-Containers: {e}")
            return None

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """Parse Zeit-String von HLTV"""
        try:
            # Format: "19:00"
            if ':' in time_str:
                hour, minute = map(int, time_str.split(':'))
                now = datetime.now()
                match_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return match_time
        except Exception as e:
            logger.error(f"Fehler beim Parsen der Zeit '{time_str}': {e}")
        return None

    def get_recent_results(self, hours: int = 24) -> List[Match]:
        """Hole die neuesten Ergebnisse der letzten X Stunden"""
        try:
            self._rate_limit()
            response = self.session.get(HLTV_RESULTS_URL, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            results = []
            
            # Finde alle Result-Container
            result_containers = soup.find_all('div', class_='result-con')
            
            for container in result_containers[:20]:  # Limitiere auf die neuesten 20
                try:
                    result = self._parse_result_container(container)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Fehler beim Parsen eines Ergebnisses: {e}")
                    continue
            
            logger.info(f"{len(results)} Ergebnisse gefunden")
            return results
            
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Ergebnisse: {e}")
            return []

    def _parse_result_container(self, container) -> Optional[Match]:
        """Parse einen Result-Container"""
        try:
            # Match ID
            match_link = container.find('a', class_='a-reset')
            if not match_link:
                return None
            
            match_id = match_link.get('href', '').split('/')[-2]
            
            # Teams
            team_divs = container.find_all('div', class_='team')
            if len(team_divs) < 2:
                return None
            
            team1_name = team_divs[0].text.strip()
            team2_name = team_divs[1].text.strip()
            
            # Score
            result_score = container.find('div', class_='result-score')
            score = result_score.text.strip() if result_score else "0-0"
            
            # Event
            event_div = container.find('div', class_='event-name')
            event = event_div.text.strip() if event_div else "Unknown Event"
            
            # Sterne
            stars = 0
            star_divs = container.find_all('i', class_='fa-star')
            stars = len([s for s in star_divs if 'fa-star' in s.get('class', [])])
            
            return Match(
                match_id=match_id,
                team1=team1_name,
                team2=team2_name,
                event=event,
                time=None,
                stars=stars,
                score=score,
                status="finished"
            )
            
        except Exception as e:
            logger.error(f"Fehler beim Parsen des Result-Containers: {e}")
            return None
