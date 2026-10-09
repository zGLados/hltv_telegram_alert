from hltv_bot.bot import parse_team_list, split_message


def test_parse_team_list():
    assert parse_team_list('FaZe, Navi\nG2\n\n , BIG') == ['FaZe', 'Navi', 'G2', 'BIG']


def test_split_message_respects_limit_and_blocks():
    blocks = [f'<b>match {i}</b>\n' + 'x' * 50 for i in range(20)]
    chunks = split_message('\n\n'.join(blocks), limit=200)
    assert all(len(c) <= 200 for c in chunks)
    assert '\n\n'.join(chunks) == '\n\n'.join(blocks)
    assert split_message('short') == ['short']
