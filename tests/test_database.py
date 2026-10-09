import pytest

from hltv_bot.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / 'bot.db'))


def test_template_is_copied_on_first_start(tmp_path):
    template = Database(str(tmp_path / 'template.db'))
    template.update_valid_teams({'FaZe', 'Vitality'})

    db = Database(str(tmp_path / 'data' / 'bot.db'), str(tmp_path / 'template.db'))
    assert db.get_valid_teams() == {'FaZe', 'Vitality'}


def test_favorites_are_case_insensitive(db):
    assert db.add_favorite(1, 'FaZe')
    assert not db.add_favorite(1, 'faze')
    assert db.get_favorites(1) == ['FaZe']
    assert db.remove_favorite(1, 'FAZE') == 'FaZe'
    assert db.get_favorites(1) == []
    assert db.remove_favorite(1, 'FaZe') is None


def test_registered_users_without_favorites_are_known(db):
    db.register_user(1)
    db.add_favorite(2, 'BIG')
    assert db.get_all_users() == {1, 2}
    assert db.get_all_users_with_favorites() == {2}


def test_min_stars_default_and_update(db):
    assert db.get_min_stars(1) == 1
    db.register_user(1)
    db.set_min_stars(1, 3)
    db.register_user(1)  # must not reset the setting
    assert db.get_min_stars(1) == 3


def test_team_update_merges_and_fixes_case(db):
    db.update_valid_teams({'FaZe', 'faze academy'})
    db.update_valid_teams({'FAZE Academy'})  # partial scrape must not drop FaZe
    assert db.get_valid_teams() == {'FaZe', 'FAZE Academy'}


def test_notifications(db):
    assert not db.was_notification_sent(1, '42', 'result')
    db.mark_notification_sent(1, '42', 'result')
    assert db.was_notification_sent(1, '42', 'result')
    db.prune_notifications(days=30)  # recent entry survives
    assert db.was_notification_sent(1, '42', 'result')
