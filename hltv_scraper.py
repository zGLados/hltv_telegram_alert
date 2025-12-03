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
        self._time = time
        self.stars = stars
        self.score = score
        self.status = status
        self._match_url = None
        self._scraper = None
    
    @property
    def time(self) -> Optional[datetime]:
        """Lazy load match time from match page if not set"""
        if self._time is None and self._match_url and self._scraper:
            logger.info(f"Lazy loading datetime for match {self.match_id}...")
            self._time = self._scraper._get_match_datetime_from_page(self._match_url)
        return self._time
    
    @time.setter
    def time(self, value):
        self._time = value
    
    def get_match_url(self) -> str:
        """Get the full HLTV match URL"""
        if self._match_url:
            return f"{HLTV_BASE_URL}{self._match_url}"
        return f"{HLTV_BASE_URL}/matches/{self.match_id}"
    
    def format_for_telegram(self) -> str:
        """Format match for Telegram with HTML markup and link"""
        url = self.get_match_url()
        
        # Star rating using white star (☆)
        stars_display = "☆" * self.stars if self.stars > 0 else "No rating"
        
        if self.score:
            # Finished match
            return (
                f'<a href="{url}">{self.team1} vs {self.team2}</a>\n'
                f'Result: {self.score}\n'
                f'Rating: {stars_display}\n'
                f'@ {self.event}'
            )
        elif self.time:
            # Upcoming match with time
            date_str = self.time.strftime("%d %b")
            time_str = self.time.strftime("%H:%M UTC")
            return (
                f'<a href="{url}">{self.team1} vs {self.team2}</a>\n'
                f'Rating: {stars_display}\n'
                f'{date_str} {time_str} @ {self.event}'
            )
        else:
            # No time available
            return (
                f'<a href="{url}">{self.team1} vs {self.team2}</a>\n'
                f'Rating: {stars_display}\n'
                f'@ {self.event}'
            )

    def __str__(self):
        if self.score:
            return f"{self.team1} vs {self.team2} - {self.score}\n📍 {self.event}"
        elif self.time:
            date_str = self.time.strftime("%d.%m.%Y")
            time_str = self.time.strftime("%H:%M")
            return f"{self.team1} vs {self.team2}\n📅 {date_str} | ⏰ {time_str}\n📍 {self.event}"
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
        self._datetime_cache = {}  # Cache for match datetimes to avoid duplicate requests
        self._matches_cache = None  # Cache for all matches
        self._matches_cache_time = None  # Timestamp of last cache update
        self._cache_duration = 1800  # Cache duration in seconds (30 minutes)

    def _rate_limit(self):
        """Rate limiting to avoid overloading HLTV"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._request_delay:
            time.sleep(self._request_delay - time_since_last)
        self._last_request_time = time.time()
    
    def preload_match_datetimes(self, matches: List[Match], max_matches: int = 20):
        """Eagerly load datetimes for a list of matches to populate cache
        
        Args:
            matches: List of matches to load datetimes for
            max_matches: Maximum number of matches to load (to avoid too many requests)
        """
        logger.info(f"Preloading datetimes for up to {max_matches} matches...")
        loaded = 0
        for match in matches[:max_matches]:
            if match._match_url and match._time is None:
                # Access .time property to trigger lazy loading
                _ = match.time
                loaded += 1
        logger.info(f"Preloaded {loaded} match datetimes")

    def search_team(self, team_name: str) -> bool:
        """Check if a team exists - simplified version that accepts all teams"""
        # Simply accept all team names without web scraping
        # The actual validation happens when matches are fetched
        # This prevents unnecessary API calls and potential rate limiting
        
        team_name_lower = team_name.lower()
        
        # Store in cache for consistency
        self._team_cache.add(team_name_lower)
        
        logger.info(f"Team '{team_name}' accepted")
        return True

    def get_todays_matches(self, min_stars: int = 0, use_cache: bool = True) -> List[Match]:
        """Get today's matches from HLTV - only returns truly upcoming matches
        
        Args:
            min_stars: Minimum star rating for matches
            use_cache: If True, use cached matches if available and not expired
        """
        # Check if we can use cache
        if use_cache and self._matches_cache is not None and self._matches_cache_time is not None:
            cache_age = time.time() - self._matches_cache_time
            if cache_age < self._cache_duration:
                logger.info(f"Using cached matches (age: {int(cache_age)}s / {self._cache_duration}s)")
                # Filter by min_stars from cache
                return [m for m in self._matches_cache if m.stars >= min_stars]
        
        # Fetch fresh matches
        try:
            self._rate_limit()
            # Don't use date parameter as HLTV shows same matches on multiple days
            # Just get the main matches page
            response = self.session.get(HLTV_MATCHES_URL, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            matches = []
            current_date = datetime.now().date()
            
            # Find all match containers
            all_divs = soup.find_all('div', class_=True)
            
            for div in all_divs:
                classes = div.get('class', [])
                
                # Check for match container
                if 'match' in classes and len(classes) <= 3:
                    try:
                        match = self._parse_match_container(div, current_date)
                        if match:
                            matches.append(match)
                    except Exception as e:
                        logger.error(f"Error parsing a match: {e}")
                        continue
            
            # Remove duplicates based on match_id
            seen_ids = set()
            unique_matches = []
            for match in matches:
                if match.match_id not in seen_ids:
                    seen_ids.add(match.match_id)
                    unique_matches.append(match)
            
            logger.info(f"Found {len(unique_matches)} unique matches (filtered {len(matches) - len(unique_matches)} duplicates)")
            
            # Update cache
            self._matches_cache = unique_matches
            self._matches_cache_time = time.time()
            logger.info(f"Updated matches cache with {len(unique_matches)} matches")
            
            # Filter by min_stars
            return [m for m in unique_matches if m.stars >= min_stars]
            
        except Exception as e:
            logger.error(f"Error fetching matches: {e}")
            return []
    
    def get_matches_for_date(self, date: datetime.date, min_stars: int = 0) -> List[Match]:
        """Get matches for a specific date from HLTV"""
        try:
            self._rate_limit()
            # Use HLTV's date parameter to get matches for specific date
            url = f"{HLTV_MATCHES_URL}?selectedDate={date}"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            matches = []
            
            # Find all match containers
            # Since we're using the date parameter, all matches on this page are for this date
            all_divs = soup.find_all('div', class_=True)
            
            for div in all_divs:
                classes = div.get('class', [])
                
                # Check for match container (simple match div with few classes)
                if 'match' in classes and len(classes) <= 3:
                    try:
                        # Pass the date we know this match is for
                        match = self._parse_match_container(div, date)
                        if match and match.stars >= min_stars:
                            matches.append(match)
                    except Exception as e:
                        logger.error(f"Error parsing a match: {e}")
                        continue
            
            # Remove duplicates based on match_id, team1, team2, and time
            seen = {}
            unique_matches = []
            for match in matches:
                # Use match_id as primary key, with teams and time as fallback
                key = (match.match_id, match.team1, match.team2, match.time)
                if key not in seen:
                    seen[key] = True
                    unique_matches.append(match)
            
            logger.info(f"Found {len(unique_matches)} unique matches for {date} (filtered {len(matches) - len(unique_matches)} duplicates)")
            return unique_matches
            
        except Exception as e:
            logger.error(f"Error fetching matches for {date}: {e}")
            return []

    def _get_match_datetime_from_page(self, match_url: str) -> Optional[datetime]:
        """Fetch the match page and extract the actual datetime from countdown or data attributes"""
        # Check cache first
        if match_url in self._datetime_cache:
            logger.debug(f"Using cached datetime for {match_url}")
            return self._datetime_cache[match_url]
        
        try:
            self._rate_limit()
            # match_url is the full path like /matches/2388091/mouz-vs-parivision-starladder-budapest-major-2025
            full_url = f"https://www.hltv.org{match_url}"
            response = self.session.get(full_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Look for Unix timestamp in data-unix attribute
            unix_elements = soup.find_all(attrs={'data-unix': True})
            if unix_elements:
                unix_timestamp = int(unix_elements[0]['data-unix'])
                # Unix timestamp is in milliseconds
                match_datetime = datetime.fromtimestamp(unix_timestamp / 1000)
                logger.debug(f"Match {match_url}: Found datetime from Unix timestamp: {match_datetime}")
                # Cache the result
                self._datetime_cache[match_url] = match_datetime
                return match_datetime
            
            # Fallback: Look for time element with datetime attribute
            time_elem = soup.find('div', class_='time')
            if time_elem:
                unix_attr = time_elem.get('data-unix')
                if unix_attr:
                    unix_timestamp = int(unix_attr)
                    match_datetime = datetime.fromtimestamp(unix_timestamp / 1000)
                    logger.debug(f"Match {match_url}: Found datetime from time element: {match_datetime}")
                    # Cache the result
                    self._datetime_cache[match_url] = match_datetime
                    return match_datetime
            
            logger.warning(f"Match {match_url}: Could not find datetime on match page")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching match page {match_url}: {e}")
            return None

    def _parse_match_container(self, container, match_date: datetime.date = None) -> Optional[Match]:
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
            
            # Create match object with match_url stored for lazy datetime fetching
            match = Match(
                match_id=match_id,
                team1=team1_name,
                team2=team2_name,
                event=event,
                time=None,  # Will be set lazily when needed
                stars=stars,
                status=status
            )
            
            # Store the URL in a custom attribute for lazy fetching
            match._match_url = match_url
            match._scraper = self  # Reference to scraper for lazy fetching
            
            return match
            
        except Exception as e:
            logger.error(f"Error parsing match container: {e}")
            return None

    def _parse_date_header(self, date_text: str) -> datetime.date:
        """Parse HLTV date header (e.g., 'Today', 'Tomorrow', 'Wednesday 4th of December 2025')"""
        try:
            date_text = date_text.lower().strip()
            today = datetime.now().date()
            
            if 'today' in date_text:
                return today
            elif 'tomorrow' in date_text:
                return today + timedelta(days=1)
            else:
                # Try to parse specific date formats from HLTV
                # Format: "Wednesday 4th of December 2025" or similar
                # Extract day, month, year using regex
                import re
                
                # Try to find day number (1-31)
                day_match = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', date_text)
                
                # Try to find month name
                months = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                month_num = None
                for month_name, month_val in months.items():
                    if month_name in date_text:
                        month_num = month_val
                        break
                
                # Try to find year (2024, 2025, etc.)
                year_match = re.search(r'\b(20\d{2})\b', date_text)
                
                if day_match and month_num and year_match:
                    day = int(day_match.group(1))
                    year = int(year_match.group(1))
                    parsed_date = datetime(year, month_num, day).date()
                    logger.info(f"Parsed date '{date_text}' as {parsed_date}")
                    return parsed_date
                
                # If we can't parse it, assume it's tomorrow
                logger.warning(f"Could not parse date '{date_text}', assuming tomorrow")
                return today + timedelta(days=1)
        except Exception as e:
            logger.error(f"Error parsing date header '{date_text}': {e}")
            return datetime.now().date()

    def _parse_time(self, time_str: str, match_date: datetime.date = None) -> Optional[datetime]:
        """Parse time string from HLTV and intelligently determine the date"""
        try:
            # If no date provided, use today
            if match_date is None:
                match_date = datetime.now().date()
            
            # Format: "19:00"
            if ':' in time_str:
                hour, minute = map(int, time_str.split(':'))
                match_time = datetime.combine(match_date, datetime.min.time())
                match_time = match_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # If the match time is in the past (earlier today), assume it's tomorrow
                now = datetime.now()
                if match_time < now and match_date == now.date():
                    match_time = match_time + timedelta(days=1)
                    logger.debug(f"Match time {time_str} is in the past, moving to tomorrow: {match_time}")
                
                return match_time
        except Exception as e:
            logger.error(f"Error parsing time '{time_str}': {e}")
        return None

    def get_recent_results(self, hours: int = 24) -> List[Match]:
        """Get recent results (approximately last 24 hours, no exact date filtering available)"""
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
            # Match ID and URL
            match_link = container.find('a', class_='a-reset')
            if not match_link:
                return None
            
            match_url = match_link.get('href', '')
            match_id = match_url.split('/')[-2] if match_url else None
            
            if not match_id:
                return None
            
            # Teams - they're in divs with class 'team'
            team_divs = container.find_all('div', class_='team')
            if len(team_divs) < 2:
                return None
            
            team1_name = team_divs[0].text.strip()
            team2_name = team_divs[1].text.strip()
            
            # Score - in td with class 'result-score'
            result_score_td = container.find('td', class_='result-score')
            if result_score_td:
                # Extract score from spans
                score_spans = result_score_td.find_all('span')
                if len(score_spans) >= 2:
                    score1 = score_spans[0].text.strip()
                    score2 = score_spans[1].text.strip()
                    score = f"{score1}-{score2}"
                else:
                    score = result_score_td.text.strip().replace('\n', '').replace(' ', '')
            else:
                score = "0-0"
            
            # Event - in span with class 'event-name'
            event_span = container.find('span', class_='event-name')
            event = event_span.text.strip() if event_span else "Unknown Event"
            
            # Stars - count i tags with class 'fa-star'
            stars = 0
            star_divs = container.find_all('i', class_='fa-star')
            stars = len(star_divs)
            
            match = Match(
                match_id=match_id,
                team1=team1_name,
                team2=team2_name,
                event=event,
                time=None,
                stars=stars,
                score=score,
                status="finished"
            )
            
            # Store match URL for link generation
            match._match_url = match_url
            match._scraper = self
            
            return match
            
        except Exception as e:
            logger.error(f"Error parsing result container: {e}")
            return None
