import requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import re
import time
from config import HLTV_BASE_URL, HLTV_MATCHES_URL, HLTV_RESULTS_URL, HEADERS

logger = logging.getLogger(__name__)


class Match:
    """Represents an HLTV Match"""
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
        """Check if a team is playing in this match"""
        team_name_lower = team_name.lower()
        return (team_name_lower in self.team1.lower() or 
                team_name_lower in self.team2.lower())


class HLTVScraper:
    """Scraper for HLTV.org"""
    
    def __init__(self):
        # Create scraper with enhanced browser properties
        self.session = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            },
            delay=10  # Initial delay for Cloudflare challenge
        )
        self.session.headers.update(HEADERS)
        self._team_cache = set()  # Cache for found teams
        self._last_request_time = 0
        self._request_delay = 3  # Increase delay to 3 seconds

    def _rate_limit(self):
        """Rate limiting to avoid overloading HLTV"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._request_delay:
            time.sleep(self._request_delay - time_since_last)
        self._last_request_time = time.time()

    def search_team(self, team_name: str) -> bool:
        """Check if a team exists on HLTV"""
        try:
            self._rate_limit()
            # Search on the teams page
            search_url = f"{HLTV_BASE_URL}/search?term={team_name}"
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Search for team results
            team_results = soup.find_all('a', href=re.compile(r'/team/\d+/'))
            
            if team_results:
                # Store found teams in cache
                for result in team_results:
                    team_text = result.get_text(strip=True)
                    if team_text:
                        self._team_cache.add(team_text.lower())
                
                # Check if the searched name is in the results
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
            # On error, allow the team anyway (e.g., network issues)
            return True

    def get_todays_matches(self, min_stars: int = 0) -> List[Match]:
        """Get today's matches from HLTV"""
        try:
            self._rate_limit()
            response = self.session.get(HLTV_MATCHES_URL, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            matches = []
            
            # Find all match containers (new structure)
            match_containers = soup.find_all('div', class_='match')
            
            for container in match_containers:
                try:
                    match = self._parse_match_container(container)
                    if match and match.stars >= min_stars:
                        matches.append(match)
                except Exception as e:
                    logger.error(f"Error parsing a match: {e}")
                    continue
            
            logger.info(f"Found {len(matches)} matches for today")
            return matches
            
        except Exception as e:
            logger.error(f"Error fetching matches: {e}")
            return []

    def _parse_match_container(self, container) -> Optional[Match]:
        """Parse a match container (new HLTV structure)"""
        try:
            # Match ID and event name from URL
            match_link = container.find('a', href=re.compile(r'/matches/\d+/'))
            if not match_link:
                return None
            
            match_url = match_link.get('href', '')
            match_parts = match_url.split('/')
            if len(match_parts) < 3:
                return None
            
            match_id = match_parts[2]
            
            # Teams
            team_divs = container.find_all('div', class_='match-team')
            if len(team_divs) < 2:
                return None
            
            team1_elem = team_divs[0].find('div', class_='match-teamname')
            team2_elem = team_divs[1].find('div', class_='match-teamname')
            
            if not team1_elem or not team2_elem:
                return None
            
            team1_name = team1_elem.get_text(strip=True)
            team2_name = team2_elem.get_text(strip=True)
            
            if not team1_name or not team2_name:
                return None
            
            # Extract event name from URL and remove team names
            # URL format: /matches/ID/team1-vs-team2-event-name
            event = "Unknown Event"
            if len(match_parts) > 3:
                url_slug = match_parts[3]
                # Remove team names from the slug (they appear at the beginning)
                # Convert team names to lowercase and replace spaces with hyphens
                team1_slug = team1_name.lower().replace(' ', '-').replace('.', '')
                team2_slug = team2_name.lower().replace(' ', '-').replace('.', '')
                
                # Remove "team1-vs-team2-" pattern from the beginning
                event_slug = url_slug
                for pattern in [f"{team1_slug}-vs-{team2_slug}-", f"{team2_slug}-vs-{team1_slug}-"]:
                    if event_slug.startswith(pattern):
                        event_slug = event_slug[len(pattern):]
                        break
                
                # Clean up and format the event name
                event = event_slug.replace('-', ' ').title()
            
            # Time
            time_div = container.find('div', class_='match-time')
            match_time = None
            if time_div:
                time_str = time_div.get_text(strip=True)
                match_time = self._parse_time(time_str)
            
            # Stars (importance) - count only non-faded stars
            stars = 0
            star_container = container.find('div', class_='match-rating')
            if star_container:
                star_icons = star_container.find_all('i', class_='fa-star')
                # Count only stars without 'faded' class
                stars = len([s for s in star_icons if 'faded' not in s.get('class', [])])
            
            # Check status (live match?)
            status = "upcoming"
            if star_container and 'matchLive' in star_container.get('class', []):
                status = "live"
            
            return Match(
                match_id=match_id,
                team1=team1_name,
                team2=team2_name,
                event=event,
                time=match_time,
                stars=stars,
                status=status
            )
            
        except Exception as e:
            logger.error(f"Error parsing match container: {e}")
            return None

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """Parse time string from HLTV"""
        try:
            # Format: "19:00"
            if ':' in time_str:
                hour, minute = map(int, time_str.split(':'))
                now = datetime.now()
                match_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return match_time
        except Exception as e:
            logger.error(f"Error parsing time '{time_str}': {e}")
        return None

    def get_recent_results(self, hours: int = 24) -> List[Match]:
        """Get recent results from the last X hours"""
        try:
            self._rate_limit()
            response = self.session.get(HLTV_RESULTS_URL, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            results = []
            
            # Find all result containers
            result_containers = soup.find_all('div', class_='result-con')
            
            for container in result_containers[:20]:  # Limit to newest 20
                try:
                    result = self._parse_result_container(container)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error parsing a result: {e}")
                    continue
            
            logger.info(f"Found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error fetching results: {e}")
            return []

    def _parse_result_container(self, container) -> Optional[Match]:
        """Parse a result container"""
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
            
            # Stars
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
            logger.error(f"Error parsing result container: {e}")
            return None
