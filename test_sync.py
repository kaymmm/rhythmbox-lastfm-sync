import pytest
from sync import SyncRB


@pytest.fixture
def test_sync():
    return SyncRB()


@pytest.fixture
def test_sync_empty():
    return SyncRB(secrets_file='test_secrets.yaml',
                  config_file='test_config.cfg')


def test_load_secrets(test_sync_empty):
    assert test_sync_empty.secrets['username'] == 'dummy'
    assert test_sync_empty.secrets['password_hash'] == \
        '00000000000000000000000000000000'
    assert test_sync_empty.secrets['api_key'] == \
        '00000000000000000000000000000000'
    assert test_sync_empty.secrets['api_secret'] == \
        '00000000000000000000000000000000'


def test_load_config(test_sync_empty):
    assert test_sync_empty.config['last_update'] == '0'
    assert test_sync_empty.config['limit'] == '500'
    # assert test_sync_empty.config['rhythmdb'] == '.xml'


def test_local_timestamp(test_sync_empty):
    assert test_sync_empty.local_timestamp(0) == '1969-12-31 16:00:00 (PST)'
    assert test_sync_empty.local_timestamp(1500000000) == \
        '2017-07-13 19:40:00 (PDT)'


def test_load_lastfm_network(test_sync):
    # test_sync = SyncRB(secrets_file='test_secrets.yaml') # Should FAIL
    assert test_sync.load_lastfm_network() == 1


def test_get_recent_tracks(test_sync):
    test_sync.load_lastfm_network()
    recents = test_sync.get_recent_tracks()
    assert recents is not None


@pytest.mark.skipif(not pytest.config.getoption("--dumprecent"),
                    reason="need option --dumprecent to run.")
def test_dump_recent_tracks(test_sync):
    test_sync.load_lastfm_network()
    recents = test_sync.get_recent_tracks()
    test_sync.dump_recent_tracks(recents)


def test_xpath_escape(test_sync_empty):
    assert test_sync_empty.xpath_escape('ab "cd" e&f\'g <:>') \
            == "ab &quot;cd&quot; e&amp;f'g &lt;:&gt;"


def test_read_recents(test_sync_empty):
    test_list = test_sync_empty.read_recent_tracks()
    assert test_list is not None


@pytest.mark.match
def test_match_scrobbles(test_sync_empty):
    recents = test_sync_empty.read_recent_tracks()
    matches = test_sync_empty.match_scrobbles(recents)
    print("Number of matches: " + str(matches))
    assert matches > 0
