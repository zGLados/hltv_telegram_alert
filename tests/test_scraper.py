import json
from datetime import datetime, timedelta, timezone

import pytest
from bs4 import BeautifulSoup

from hltv_bot.database import Database
from hltv_bot.scraper import HLTVScraper, Match

# Minimal HTML mirroring the HLTV structures the parser relies on.
MATCHES_HTML = '''
<div class="match">
  <a href="/matches/2380001/faze-vs-natus-vincere-iem-cologne-2026">
    <div class="match-event" data-event-headline="IEM Cologne 2026">IEM Cologne 2026</div>
    <div class="match-time" data-unix="1791561600000">18:00</div>
    <div class="match-team"><div class="match-teamname">FaZe</div></div>
    <div class="match-team"><div class="match-teamname">Natus Vincere</div></div>
    <div class="match-rating">
      <i class="fa fa-star"></i><i class="fa fa-star"></i><i class="fa fa-star faded"></i>
    </div>
  </a>
</div>
<div class="match">
  <a href="/matches/2380001/faze-vs-natus-vincere-iem-cologne-2026"></a>
  <div class="match-team"><div class="match-teamname">FaZe</div></div>
  <div class="match-team"><div class="match-teamname">Natus Vincere</div></div>
</div>
<div class="match">
  <a href="/matches/2380002/big-vs-mouz-cct-season-3">
    <div class="match-team"><div class="match-teamname">BIG</div></div>
    <div class="match-team"><div class="match-teamname">MOUZ</div></div>
    <div class="match-rating matchLive"></div>
  </a>
</div>
<div class="match"><a href="/news/123/not-a-match">x</a></div>
'''

RESULTS_HTML = '''
<div class="big-results">
  <div class="result-con">
    <a class="a-reset" href="/matches/2370001/g2-vs-vitality-blast-premier">
      <div class="team">G2</div><div class="team">Vitality</div><i class="fa fa-star"></i></a>
  </div>
  <div class="result-con">
    <a class="a-reset" href="/matches/2360000/faze-vs-mouz-last-week">
      <div class="team">FaZe</div><div class="team">MOUZ</div><i class="fa fa-star"></i></a>
  </div>
</div>
<div class="result-con" data-zonedgrouping-entry-unix="%d">
  <a class="a-reset" href="/matches/2370001/g2-vs-vitality-blast-premier">
    <div class="team">G2</div>
    <td class="result-score"><span>2</span> - <span>1</span></td>
    <div class="team">Vitality</div>
    <span class="event-name">BLAST Premier</span>
    <i class="fa fa-star"></i>
  </a>
</div>
<div class="result-con" data-zonedgrouping-entry-unix="1000000000000">
  <a class="a-reset" href="/matches/2370000/old-vs-match-some-event">
    <div class="team">Old</div><div class="team">Match</div>
  </a>
</div>
'''


def soup(text):
    return BeautifulSoup(text, 'lxml')


def test_parse_matches_page():
    matches = HLTVScraper.parse_matches_page(soup(MATCHES_HTML))
    assert [m.match_id for m in matches] == ['2380001', '2380002']  # deduplicated

    faze = matches[0]
    assert (faze.team1, faze.team2, faze.stars, faze.status) == ('FaZe', 'Natus Vincere', 2, 'upcoming')
    assert faze.event == 'IEM Cologne 2026'  # from data-event-headline
    assert faze.time == datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)

    big = matches[1]
    assert (big.stars, big.time) == (0, None)
    assert big.event == 'Cct Season 3'  # fallback: derived from the URL slug
    # HLTV puts "matchLive" on every rating element, it must not mean live
    assert not big.is_live


def test_is_live_means_kickoff_passed():
    now = datetime.now(timezone.utc)
    assert Match('1', 'A', 'B', 'E', 1, time=now - timedelta(minutes=5)).is_live
    assert not Match('1', 'A', 'B', 'E', 1, time=now + timedelta(minutes=5)).is_live
    assert not Match('1', 'A', 'B', 'E', 1, time=now - timedelta(minutes=5), status='finished').is_live


def test_parse_results_page_and_age_filter():
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    results = HLTVScraper.parse_results_page(soup(RESULTS_HTML % now_ms))
    # featured duplicate merged (gets the timestamp), untimed old featured result dropped
    assert [r.match_id for r in results] == ['2370001', '2370000']
    g2 = results[0]
    assert g2.time is not None
    assert (g2.match_id, g2.team1, g2.team2, g2.score, g2.event, g2.stars) == (
        '2370001', 'G2', 'Vitality', '2-1', 'BLAST Premier', 1)

    scraper = HLTVScraper()
    scraper._get = lambda url, timeout=15: soup(RESULTS_HTML % now_ms)
    assert [r.match_id for r in scraper.get_recent_results(hours=24)] == ['2370001']


def test_has_team_is_exact():
    match = Match('1', 'BIG EQUIPA', 'Sprout', 'Event', 1)
    assert match.has_team('big equipa')
    assert not match.has_team('BIG')


def test_format_escapes_html():
    match = Match('1', '<b>evil</b>', 'A&B', 'Cup <3', 0, url_path='/matches/1/x')
    text = match.format_for_telegram()
    assert '&lt;b&gt;evil&lt;/b&gt;' in text and 'A&amp;B' in text and 'Cup &lt;3' in text
    assert 'No rating' in text


@pytest.fixture
def scraper(tmp_path):
    db = Database(str(tmp_path / 'bot.db'))
    db.update_valid_teams({'FaZe', 'FaZe Academy', 'Vitality', 'BIG', 'BIG EQUIPA', 'MOUZ'})
    return HLTVScraper(db)


@pytest.mark.parametrize('query, expected', [
    ('faze', (True, 'FaZe')),        # exact beats prefix
    ('vita', (True, 'Vitality')),    # unique prefix
    ('equipa', (True, 'BIG EQUIPA')),  # unique substring
    ('big', (True, 'BIG')),
    ('fa', (False, 'fa')),           # ambiguous prefix
    ('x', (False, 'x')),             # too short
    ('1234', (False, '1234')),       # digits only
    ('Astralis', (False, 'Astralis')),
])
def test_search_team(scraper, query, expected):
    assert scraper.search_team(query) == expected


def test_suggest_teams(scraper):
    assert scraper.suggest_teams('faz') == ['FaZe', 'FaZe Academy']


def test_resolve_times_uses_cache_and_limit(scraper):
    calls = []

    def fake_fetch(url_path):
        calls.append(url_path)
        t = datetime(2026, 1, 1, tzinfo=timezone.utc)
        scraper._datetime_cache[url_path] = t
        return t

    scraper._fetch_match_time = fake_fetch
    matches = [Match(str(i), 'A', 'B', 'E', 1, url_path=f'/matches/{i}/x') for i in range(3)]
    assert scraper.resolve_times(matches, limit=2) == 2
    assert matches[2].time is None
    again = [Match('0', 'A', 'B', 'E', 1, url_path='/matches/0/x')]
    assert scraper.resolve_times(again) == 0 and again[0].time is not None
    assert len(calls) == 2


def test_snapshot_file_roundtrip(tmp_path):
    cache_file = str(tmp_path / 'match_cache.json')
    scraper = HLTVScraper(cache_file=cache_file)
    scraper._get = lambda url, timeout=15: soup(MATCHES_HTML)
    assert len(scraper.get_upcoming_matches()) == 2

    data = json.loads(open(cache_file).read())
    assert data['starred_count'] == 1 and len(data['matches']) == 2

    # A new instance (= bot restart) serves the snapshot without any request
    restarted = HLTVScraper(cache_file=cache_file)
    restarted._get = lambda url, timeout=15: pytest.fail('should use the snapshot')
    loaded = restarted.get_upcoming_matches()
    assert loaded == scraper.get_upcoming_matches()


def test_snapshot_drops_finished_matches_and_survives_garbage(tmp_path):
    cache_file = tmp_path / 'match_cache.json'
    old = Match('1', 'A', 'B', 'E', 1, time=datetime.now(timezone.utc) - timedelta(hours=7))
    new = Match('2', 'C', 'D', 'E', 1, time=datetime.now(timezone.utc) + timedelta(hours=1))
    cache_file.write_text(json.dumps({'fetched_at': datetime.now(timezone.utc).isoformat(),
                                      'matches': [old.to_dict(), new.to_dict()]}))
    assert [m.match_id for m in HLTVScraper(cache_file=str(cache_file)).get_upcoming_matches()] == ['2']

    cache_file.write_text('{not json')
    broken = HLTVScraper(cache_file=str(cache_file))
    broken._get = lambda url, timeout=15: (_ for _ in ()).throw(RuntimeError('403'))
    assert broken.get_upcoming_matches() == []


def test_failed_fetch_keeps_previous_data(tmp_path):
    scraper = HLTVScraper()
    scraper._get = lambda url, timeout=15: soup(MATCHES_HTML)
    first = scraper.get_upcoming_matches()
    fetched_at = scraper.matches_fetched_at

    def blocked(url, timeout=15):
        raise RuntimeError('403 Forbidden')
    scraper._get = blocked
    assert scraper.get_upcoming_matches(use_cache=False) == first
    assert scraper.matches_fetched_at == fetched_at
