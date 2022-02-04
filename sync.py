#!/usr/bin/env python3

"""
Copyright 2017-2022 Keith Miyake

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

import pylast
import shutil
import os
from datetime import datetime
from lxml import etree
import configparser
import logging
import inspect

# Change the following paths as appropriate on your system
# CONFIG_DIR = script directory
filename = inspect.getframeinfo(inspect.currentframe()).filename
CONFIG_DIR = os.path.dirname(os.path.abspath(filename))
# default rhythmbox database location:
RHYTHMBOX_DB = os.path.expanduser('~/.local/share/rhythmbox/rhythmdb.xml')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'rbsync.cfg')
SECRETS_FILE = os.path.join(CONFIG_DIR, 'secrets.yaml')
# LIBREFM_SESSION_KEY_FILE = os.path.join(CONFIG_DIR, 'session_key.librefm')

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

class SyncRB():

    secrets = None
    config = None

    def __init__(self,
                 secrets_file=SECRETS_FILE,
                 config_file=CONFIG_FILE,
                 database_file=RHYTHMBOX_DB):
        if self.secrets is None:
            self.load_secrets(secrets_file)

        if self.config is None:
            self.load_config(config_file, database_file)

        if os.path.isfile(self.config['rhythmdb']):
            self.db = etree.parse(self.config['rhythmdb'])
            self.db_root = self.db.getroot()

    def local_timestamp(self, strtimestamp):
        import tzlocal
        return datetime.fromtimestamp(
                float(strtimestamp),
                tzlocal.get_localzone()).strftime('%Y-%m-%d %H:%M:%S (%Z)')

    def load_secrets(self, secrets_file):
        if os.path.isfile(secrets_file):
            import yaml
            with open(secrets_file, 'r') as f:
                self.secrets = yaml.load(f, Loader=yaml.SafeLoader)
                if not self.secrets:
                    logging.warning('secrets.yaml could not be loaded; creating new file.')
                    self.create_secrets(secrets_file)
                else:
                    logging.debug('secrets.yaml loaded')
        else:
            logging.info('Login information does not exist. Please enter your Last.fm login info.')
            self.create_secrets(secrets_file)

    def create_secrets(self, secrets_file):
        import yaml
        from getpass import getpass
        self.secrets = {}
        try:
            self.secrets['last_username'] = \
                input("Enter last.fm username: ").strip()
            self.secrets['last_password_hash'] = \
                pylast.md5(getpass(prompt='Enter last.fm password: ').strip())
            self.secrets['last_api_key'] = \
                input("Enter last.fm api key: ").strip()
            self.secrets['last_api_secret'] = \
                input("Enter last.fm api secret: ").strip()
            with open(secrets_file, 'w+') as f:
                yaml.dump(self.secrets, f, default_flow_style=False)
            logging.debug('Saved secrets to secrets.yaml')
        except Exception as err:
            logging.error('There was an error saving the secrets: {0}'.format(err))

    def load_config(self, config_file, database_file):
        config = configparser.ConfigParser()
        self.config = {}
        if os.path.isfile(config_file):
            config.read_file(open(config_file))
            self.config['last_update'] = config['Sync']['last_update'] \
                if 'last_update' in config['Sync'] else '0'
            self.config['limit'] = config['Sync']['limit'] \
                if 'limit' in config['Sync'] else '500'
            self.config['backup'] = config['Sync'].getboolean('backup') \
                if 'backup' in config['Sync'] else True
            if database_file is not None:
                self.config['rhythmdb'] = config['Sync']['rhythmdb'] \
                    if 'rhythmdb' in config['Sync'] \
                    else database_file
            else:
                self.config['rhythmdb'] = RHYTHMBOX_DB
        else:
            self.config['last_update'] = '0'
            self.config['limit'] = '500'
            self.config['rhythmdb'] = RHYTHMBOX_DB
            self.config['backup'] = True
        logging.info('Last successful sync was {0}'.format(
              self.local_timestamp(self.config['last_update'])))

    def save_config(self, config_file):
        if self.config is not None:
            config = configparser.ConfigParser()
            config['Sync'] = {}
            config['Sync']['backup'] = str(self.config['backup'])
            config['Sync']['last_update'] = str(int(datetime.timestamp(datetime.now())))
            config['Sync']['limit'] = self.config['limit']
            config['Sync']['rhythmdb'] = self.config['rhythmdb']
            with open(config_file, 'w') as configfile:
                config.write(configfile)
            logging.debug('Updated configuration file')

    def load_lastfm_network(self):
        try:
            self.network = pylast.LastFMNetwork(
                api_key=self.secrets['last_api_key'],
                api_secret=self.secrets['last_api_secret'],
                username=self.secrets['last_username'],
                password_hash=self.secrets['last_password_hash'])
            self.network.enable_rate_limit()
            # self.libre_session(LIBREFM_SESSION_KEY_FILE)
            return 1
        except (pylast.NetworkError, pylast.MalformedResponseError) as e:
            logging.error('Could not connect to last.fm: {0}'.format(e))
            return 0

    def last_session(self, key_file):
        if not os.path.exists(key_file):
            skg = pylast.SessionKeyGenerator(self.network)
            url = skg.get_web_auth_url()

            print(
                "Please authorize the scrobbler "
                "to scrobble to your account: %s\n" % url)
            import webbrowser
            webbrowser.open(url)

            while True:
                try:
                    session_key = skg.get_web_auth_session_key(url)
                    fp = open(key_file, "w")
                    fp.write(session_key)
                    fp.close()
                    break
                except pylast.WSError:
                    import time
                    time.sleep(1)
        else:
            session_key = open(key_file).read()
        self.network.session_key = session_key

    def pylast_to_dict(self, track_list):
        return_list = []
        for c, track in enumerate(track_list, 1):
            return_list.insert(0, {
                'artist': str(track.track.artist),
                'title': str(track.track.title),
                'timestamp': track.timestamp,
                'album': str(track.album)})
        return return_list

    def get_recent_tracks(self):
        all_recents = []
        num_tracks = 1
        limit = int(self.config['limit'])
        time_start = int(self.config['last_update'])
        time_end = datetime.timestamp(datetime.now())
        while num_tracks > 0 and time_start < time_end:
            try:
                logging.debug(
                    'Pulling tracks starting at {0} and ending at {1} ({2} - {3})'
                    .format(
                            datetime.fromtimestamp(time_start),
                            datetime.fromtimestamp(time_end),
                            time_start,
                            time_end
                    )
                )
                recents = self.network.get_user(
                    self.secrets['last_username']).get_recent_tracks(
                        time_from=time_start,
                        time_to=time_end
                    )
            except (pylast.NetworkError, pylast.MalformedResponseError, pylast.WSError) as e:
                logging.error(
                        'Could not get recent tracks from Last.fm: {0}'
                        .format(e))
                break

            recents_clean = self.pylast_to_dict(recents)

            num_tracks = len(recents)
            if num_tracks > 0:
                all_recents.extend(recents_clean)
                time_end = int(min([x['timestamp'] for x in recents_clean])) - 1

            logging.info(
                    'Retrieved {0} tracks.'
                    .format(
                            len(recents),
                            time_end
                    )
            )
        return all_recents

    def xpath_escape(self, s):
        # make sure that " and ' are properly matched since xpath is wonko
        # https://www.examplefiles.net/cs/234056
        if '"' in s and "'" in s:
            return 'concat(%s)' % ", '""',".join('"%s"' % x for x in s.split('"'))
        elif '"' in s:
            return "'%s'" % s
        return '"%s"' % s

    def xpath_matches(self, artist, title, album):
        xp_query = '//entry[@type=\"song\"]'
        if title is not None:
            xp_query += '/title[lower(text())=' + self.xpath_escape(title.lower()) + ']/..'
        if artist is not None:
            xp_query += '/artist[lower(text())=' + self.xpath_escape(artist.lower()) + ']/..'
        if album is not None and album != 'music' and album != '[unknown album]':  # 'music' == empty
            xp_query += '/album[lower(text())=' + self.xpath_escape(album.lower()) + ']/..'
        logging.debug('\n->Query: ' + xp_query)
        matches = self.db_root.xpath(
            xp_query,
            extensions={(None, 'lower'): (lambda c, a: a[0].lower())})
        return matches

    def match_scrobbles(self, tracklist):
        num_matches = 0
        for c, track in enumerate(tracklist, 1):
            timestamp = track['timestamp']
            matches = self.xpath_matches(
                track['artist'],
                track['title'],
                track['album'])
            if len(matches) >= 1:
                #  If there are multiples of the song, use the first instance
                el_playcount = matches[0].find('play-count')
                el_temp = etree.Element('play-count')
                if el_playcount is not None:
                    el_temp.text = str(int(el_playcount.text) + 1)
                    matches[0].replace(el_playcount, el_temp)
                else:
                    el_temp.text = '1'
                    matches[0].append(el_temp)
                playcount = el_temp.text

                el_lastplayed = matches[0].find('last-played')
                el_temp = etree.Element('last-played')
                if el_lastplayed is not None:
                    lastplayed = int(el_lastplayed.text)
                    el_temp.text = timestamp
                    if lastplayed < int(timestamp):
                        matches[0].replace(el_lastplayed, el_temp)
                else:
                    el_temp.text = timestamp
                    matches[0].append(el_temp)
                num_matches += 1
                logging.info('\033[92m' + '✓ ' + '\033[00m' + track['artist']
                      + ' - ' + track['album'] + ' - ' + track['title']
                      + ' {{' + playcount + '}}')
            else:
                logging.info('\033[91m' + 'x ' + '\033[00m' + track['artist'] + ' - '
                      + track['album'] + ' - ' + track['title'])
        return num_matches

    def write_db(self):
        if self.config['backup']:
            rhythmdb_backup = self.config['rhythmdb'] + '.backup-' + self.config['last_update']
        shutil.copy2(self.config['rhythmdb'], rhythmdb_backup)
        self.db.write(self.config['rhythmdb'])


if __name__ == '__main__':
    sync = SyncRB(secrets_file=SECRETS_FILE,
                  config_file=CONFIG_FILE)
    sync.load_lastfm_network()

    recents = sync.get_recent_tracks()
    if sync.match_scrobbles(recents) > 0:
        sync.write_db()
    sync.save_config(CONFIG_FILE)
