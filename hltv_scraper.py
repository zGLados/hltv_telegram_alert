"""Scraper for HLTV.org (upcoming matches, results, team rankings).

Requests use curl_cffi with impersonate='chrome' (plain python-requests got
HTTP 403). Keep curl_cffi's default headers; don't set a custom User-Agent.

All methods here do blocking network I/O. The bot calls them via
`asyncio.to_thread`, so this class is written to be thread-safe: every HTTP
request goes through `_get`, which serialises requests and enforces the rate
limit.
"""
import html
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Set, Tuple

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from config import (
    HLTV_BASE_URL, HLTV_MATCHES_URL, HLTV_RANKING_URL, HLTV_RESULTS_URL,
    MATCH_CACHE_SECONDS, REQUEST_DELAY, TZ,
)

logger = logging.getLogger(__name__)

MATCH_URL_RE = re.compile(r'^/matches/(\d+)/')


@dataclass
class Match:
    """An HLTV match: upcoming/live (no score) or finished (with score)."""
    match_id: str
    team1: str
    team2: str
    event: str
    stars: int
    url_path: str = ''
    time: Optional[datetime] = None  # timezone-aware (UTC) kick-off / finish time
    score: Optional[str] = None
    status: str = 'upcoming'  # upcoming | finished

    @property
    def is_live(self) -> bool:
        """Kick-off has passed but the match is still in the match list.

        HLTV's own "matchLive" class is on every rating element, so it can't
        be used to detect live matches."""
        return (self.status != 'finished' and self.time is not None
                and self.time <= datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {'match_id': self.match_id, 'team1': self.team1, 'team2': self.team2,
                'event': self.event, 'stars': self.stars, 'url_path': self.url_path,
                'time': self.time.isoformat() if self.time else None,
                'score': self.score, 'status': self.status}

    @classmethod
    def from_dict(cls, data: dict) -> 'Match':
        data = dict(data)
        data['time'] = datetime.fromisoformat(data['time']) if data.get('time') else None
        return cls(**data)

    @property
    def url(self) -> str:
        return f"{HLTV_BASE_URL}{self.url_path or f'/matches/{self.match_id}'}"

    @property
    def local_time(self) -> Optional[datetime]:
        return self.time.astimezone(TZ) if self.time else None

    def has_team(self, team_name: str) -> bool:
        """Exact (case-insensitive) team match. Substring matching would make
        'BIG' also match 'BIG EQUIPA'."""
        name = team_name.casefold()
        return name in (self.team1.casefold(), self.team2.casefold())

    def format_for_telegram(self) -> str:
        """HTML snippet for Telegram (all scraped text is escaped)."""
        title = f'<a href="{html.escape(self.url)}">{html.escape(self.team1)} vs {html.escape(self.team2)}</a>'
        stars = '☆' * self.stars if self.stars > 0 else 'No rating'
        event = html.escape(self.event)
        lines = [title]
        if self.score:
            lines.append(f'Result: {html.escape(self.score)}')
        if self.is_live:
            lines.append('🔴 LIVE')
        lines.append(f'Rating: {stars}')
        local = self.local_time
        if local and not self.score:
            lines.append(f'{local.strftime("%d %b %H:%M %Z")} @ {event}')
        else:
            lines.append(f'@ {event}')
        return '\n'.join(lines)


def _from_unix_ms(value) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


class HLTVScraper:
    def __init__(self, db=None, cache_file: Optional[str] = None):
        self.db = db  # used to persist and validate team names
        self.cache_file = cache_file  # JSON snapshot of the match list
        self.session = curl_requests.Session(impersonate='chrome')

        self._request_lock = threading.Lock()
        self._last_request_time = 0.0

        self._matches_cache: Optional[List[Match]] = None
        self._matches_cache_time = 0.0
        self._datetime_cache: Dict[str, datetime] = {}  # url_path -> kick-off time
        self._load_cache_file()

    # --- HTTP -------------------------------------------------------------------

    def _get(self, url: str, timeout: int = 15) -> BeautifulSoup:
        """Rate-limited, serialised GET. Raises on HTTP errors."""
        with self._request_lock:
            wait = REQUEST_DELAY - (time.monotonic() - self._last_request_time)
            if wait > 0:
                time.sleep(wait)
            try:
                response = self.session.get(url, timeout=timeout, allow_redirects=True)
            finally:
                self._last_request_time = time.monotonic()
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')

    @property
    def matches_fetched_at(self) -> float:
        """Unix time of the last successful match-list fetch (0 = never)."""
        return self._matches_cache_time

    # --- Upcoming matches -----------------------------------------------------------

    def get_upcoming_matches(self, min_stars: int = 0, use_cache: bool = True) -> List[Match]:
        """Upcoming and live matches from /matches, filtered by star rating.

        Returns an empty list if HLTV can't be reached and nothing is cached.
        """
        cache_fresh = (time.time() - self._matches_cache_time) < MATCH_CACHE_SECONDS
        if not (use_cache and self._matches_cache is not None and cache_fresh):
            try:
                soup = self._get(HLTV_MATCHES_URL)
                self._matches_cache = self.parse_matches_page(soup)
                self._matches_cache_time = time.time()
                for match in self._matches_cache:
                    if match.time is None:
                        match.time = self._datetime_cache.get(match.url_path)
                logger.info(f"Fetched {len(self._matches_cache)} upcoming matches")
                self._save_cache_file()
            except Exception as e:
                logger.error(f"Error fetching matches: {e}")
                if self._matches_cache is None:
                    return []
                logger.info("Serving stale match cache")
        return [m for m in self._matches_cache if m.stars >= min_stars]

    # --- Match snapshot file ------------------------------------------------------
    # The last successful match list is kept on disk so a restart (or a day on
    # which HLTV blocks us) still has data to answer /today and the summary.

    def _save_cache_file(self):
        if not self.cache_file or self._matches_cache is None:
            return
        data = {
            'fetched_at': datetime.fromtimestamp(self._matches_cache_time, timezone.utc).isoformat(),
            'starred_count': sum(1 for m in self._matches_cache if m.stars >= 1),
            'matches': [m.to_dict() for m in self._matches_cache],
        }
        tmp = f'{self.cache_file}.tmp'
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.cache_file)  # atomic: never leave a half-written file
        except OSError as e:
            logger.error(f"Could not write match snapshot {self.cache_file}: {e}")

    def _load_cache_file(self):
        if not self.cache_file or not os.path.exists(self.cache_file):
            return
        try:
            with open(self.cache_file, encoding='utf-8') as f:
                data = json.load(f)
            fetched_at = datetime.fromisoformat(data['fetched_at'])
            # Drop matches that must be over by now (kick-off more than 6 h ago)
            stale = datetime.now(timezone.utc) - timedelta(hours=6)
            matches = [Match.from_dict(m) for m in data['matches']]
            self._matches_cache = [m for m in matches if m.time is None or m.time >= stale]
            self._matches_cache_time = fetched_at.timestamp()
            logger.info(f"Loaded {len(self._matches_cache)} matches from snapshot "
                        f"{self.cache_file} (fetched {fetched_at:%Y-%m-%d %H:%M} UTC)")
        except Exception as e:
            logger.error(f"Ignoring unreadable match snapshot {self.cache_file}: {e}")

    @classmethod
    def parse_matches_page(cls, soup: BeautifulSoup) -> List[Match]:
        matches, seen = [], set()
        # Containers without both team names (TBD fixtures) are skipped
        for div in soup.find_all('div', class_='match'):
            try:
                match = cls._parse_match_container(div)
            except Exception as e:
                logger.error(f"Error parsing match container: {e}")
                continue
            if match and match.match_id not in seen:
                seen.add(match.match_id)
                matches.append(match)
        return matches

    @staticmethod
    def _parse_match_container(container) -> Optional[Match]:
        link = container.find('a', href=MATCH_URL_RE)
        if not link:
            return None
        url_path = link['href']
        match_id = MATCH_URL_RE.match(url_path).group(1)

        team_divs = container.find_all('div', class_='match-team')
        if len(team_divs) < 2:
            return None
        names = [d.find('div', class_='match-teamname') for d in team_divs[:2]]
        if not all(names):
            return None
        team1, team2 = (n.get_text(strip=True) for n in names)
        if not team1 or not team2:
            return None

        stars = 0
        rating = container.find('div', class_='match-rating')
        if rating:
            stars = sum(1 for s in rating.find_all('i', class_='fa-star')
                        if 'faded' not in s.get('class', []))

        # Kick-off time, if the list page carries it (saves a match-page request)
        unix_elem = container.find(attrs={'data-unix': True})
        kickoff = _from_unix_ms(unix_elem['data-unix']) if unix_elem else None

        event_elem = container.find(attrs={'data-event-headline': True})
        event = (event_elem['data-event-headline'].strip() if event_elem
                 else HLTVScraper._event_from_slug(url_path, team1, team2))

        return Match(
            match_id=match_id, team1=team1, team2=team2, event=event,
            stars=stars, url_path=url_path, time=kickoff,
        )

    @staticmethod
    def _event_from_slug(url_path: str, team1: str, team2: str) -> str:
        """Fallback: derive the event name from /matches/<id>/<team1>-vs-<team2>-<event>."""
        parts = url_path.split('/')
        if len(parts) < 4 or not parts[3]:
            return 'Unknown Event'
        slug = parts[3]
        t1 = team1.lower().replace(' ', '-').replace('.', '')
        t2 = team2.lower().replace(' ', '-').replace('.', '')
        for prefix in (f'{t1}-vs-{t2}-', f'{t2}-vs-{t1}-'):
            if slug.startswith(prefix):
                slug = slug[len(prefix):]
                break
        return slug.replace('-', ' ').title()

    # --- Kick-off times -----------------------------------------------------------

    def resolve_times(self, matches: Iterable[Match], limit: Optional[int] = None) -> int:
        """Fill in missing kick-off times by fetching match pages (cached per URL).

        Returns the number of match pages fetched.
        """
        fetched = 0
        for match in matches:
            if match.time is not None or not match.url_path:
                continue
            if match.url_path in self._datetime_cache:
                match.time = self._datetime_cache[match.url_path]
                continue
            if limit is not None and fetched >= limit:
                break
            match.time = self._fetch_match_time(match.url_path)
            fetched += 1
        return fetched

    def _fetch_match_time(self, url_path: str) -> Optional[datetime]:
        try:
            soup = self._get(f"{HLTV_BASE_URL}{url_path}", timeout=10)
        except Exception as e:
            logger.error(f"Error fetching match page {url_path}: {e}")
            return None
        elem = soup.find(attrs={'data-unix': True})
        kickoff = _from_unix_ms(elem['data-unix']) if elem else None
        if kickoff:
            self._datetime_cache[url_path] = kickoff
        else:
            logger.warning(f"No kick-off time found on {url_path}")
        return kickoff

    def prune_time_cache(self):
        """Drop cached kick-off times of matches that are no longer listed."""
        if self._matches_cache is None:
            return
        listed = {m.url_path for m in self._matches_cache}
        for key in list(self._datetime_cache):
            if key not in listed:
                del self._datetime_cache[key]

    # --- Results ------------------------------------------------------------------

    def get_recent_results(self, hours: int = 24, limit: int = 50) -> List[Match]:
        """Recently finished matches from /results, at most `hours` old.

        Results without a timestamp (only possible if HLTV drops the attribute
        entirely) are kept, so the bot degrades to "newest `limit` results".
        """
        try:
            soup = self._get(HLTV_RESULTS_URL, timeout=10)
        except Exception as e:
            logger.error(f"Error fetching results: {e}")
            return []
        results = self.parse_results_page(soup)[:limit]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [r for r in results if r.time is None or r.time >= cutoff]

    @classmethod
    def parse_results_page(cls, soup: BeautifulSoup) -> List[Match]:
        results: List[Match] = []
        seen: Dict[str, Match] = {}
        for container in soup.find_all('div', class_='result-con'):
            try:
                result = cls._parse_result_container(container)
            except Exception as e:
                logger.error(f"Error parsing result container: {e}")
                continue
            if not result:
                continue
            # The "featured results" block at the top has no timestamps and
            # repeats matches from the main list: the main-list entry wins.
            previous = seen.get(result.match_id)
            if previous:
                if result.time and previous.time is None:
                    results[results.index(previous)] = result
                    seen[result.match_id] = result
                continue
            seen[result.match_id] = result
            results.append(result)
        # Featured results that are older than the main list stay untimed;
        # drop them unless the page has no timestamps at all.
        if any(r.time for r in results):
            results = [r for r in results if r.time]
        return results

    @staticmethod
    def _parse_result_container(container) -> Optional[Match]:
        link = container.find('a', class_='a-reset')
        url_path = link.get('href', '') if link else ''
        m = MATCH_URL_RE.match(url_path)
        if not m:
            return None

        team_divs = container.find_all('div', class_='team')
        if len(team_divs) < 2:
            return None
        team1 = team_divs[0].get_text(strip=True)
        team2 = team_divs[1].get_text(strip=True)

        score = '0-0'
        score_td = container.find('td', class_='result-score')
        if score_td:
            spans = score_td.find_all('span')
            if len(spans) >= 2:
                score = f"{spans[0].get_text(strip=True)}-{spans[1].get_text(strip=True)}"
            else:
                score = re.sub(r'\s+', '', score_td.get_text())

        event_span = container.find('span', class_='event-name')
        event = event_span.get_text(strip=True) if event_span else 'Unknown Event'

        return Match(
            match_id=m.group(1), team1=team1, team2=team2, event=event,
            stars=len(container.find_all('i', class_='fa-star')),
            url_path=url_path,
            time=_from_unix_ms(container.get('data-zonedgrouping-entry-unix')),
            score=score, status='finished',
        )

    # --- Teams --------------------------------------------------------------------

    def refresh_teams(self) -> Set[str]:
        """Scrape team names (world ranking + current matches) and merge them
        into the database. Returns the names found in this run."""
        teams: Set[str] = set()

        # /ranking/teams redirects to the latest weekly ranking
        rankings_url = HLTV_RANKING_URL
        try:
            soup = self._get(rankings_url)
            names = soup.select('div.ranked-team span.name') or soup.select('span.name')
            teams.update(n.get_text(strip=True) for n in names)
            logger.info(f"Found {len(teams)} teams on {rankings_url}")
        except Exception as e:
            logger.warning(f"Could not load rankings ({rankings_url}): {e}")

        # Also add teams from the match list to catch new / unranked teams
        for match in self.get_upcoming_matches():
            teams.update((match.team1, match.team2))

        teams.discard('')
        teams.discard('TBD')
        if teams and self.db:
            self.db.update_valid_teams(teams)
        return teams

    def search_team(self, team_name: str) -> Tuple[bool, str]:
        """Validate a user-supplied team name against the known-team list.

        Returns (True, canonical_name) or (False, input). Matching order:
        exact (case-insensitive) → unique prefix → unique substring. Ambiguous
        input is rejected rather than guessed.
        """
        name = team_name.strip()
        query = name.casefold()
        if not (2 <= len(query) <= 30) or query.isdigit():
            return False, name

        known = sorted(self.db.get_valid_teams()) if self.db else []
        if not known:
            logger.error(f"No known teams in database, cannot validate '{name}'")
            return False, name

        for team in known:
            if team.casefold() == query:
                return True, team
        for candidates in (
            [t for t in known if t.casefold().startswith(query)],
            [t for t in known if query in t.casefold()],
        ):
            if len(candidates) == 1:
                return True, candidates[0]
            if candidates:
                logger.info(f"'{name}' is ambiguous: {candidates[:5]}")
                return False, name
        return False, name

    def suggest_teams(self, team_name: str, limit: int = 5) -> List[str]:
        """Known teams containing the input, for "did you mean" hints."""
        query = team_name.strip().casefold()
        if len(query) < 2 or not self.db:
            return []
        return sorted(t for t in self.db.get_valid_teams() if query in t.casefold())[:limit]
