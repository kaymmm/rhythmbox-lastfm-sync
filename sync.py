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

# Rhythmbox Library Sync w/LastFM
# v2.0.0
# 2022-02-04

from datetime import datetime
import inspect
from getpass import getpass
import logging
from lxml import etree
import os
import pylast
import shutil
import time
import tzlocal
import webbrowser
import yaml

# Change the following paths as appropriate on your system
# Get the script directory
filename = inspect.getframeinfo(inspect.currentframe()).filename
SCRIPT_DIR = os.path.dirname(os.path.abspath(filename))
# default rhythmbox database location:
RHYTHMBOX_DB = os.path.expanduser('~/.local/share/rhythmbox/rhythmdb.xml')
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'rbsync.yaml')
SECRETS_FILE = os.path.join(SCRIPT_DIR, 'secrets.yaml')
# LIBREFM_SESSION_KEY_FILE = os.path.join(SCRIPT_DIR, 'session_key.librefm')

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

class SyncRB():

    secrets = None
    config = None

    def __init__(self,
                 secrets_file=SECRETS_FILE,
                 config_file=CONFIG_FILE
                 ):
        if self.secrets is None:
            self.load_secrets(secrets_file)

        if self.config is None:
            self.load_config(config_file)

        if os.path.isfile(self.config['rhythmdb']):
            self.db = etree.parse(self.config['rhythmdb'])
            self.db_root = self.db.getroot()

    def local_timestamp(self, strtimestamp):
        return datetime.fromtimestamp(
                float(strtimestamp),
                tzlocal.get_localzone()).strftime('%Y-%m-%d %H:%M:%S (%Z)')

    def load_secrets(self, secrets_file):
        if os.path.isfile(secrets_file):
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
            sys.exit('Fatal error. Cannot continue.')

    def load_config(self, config_file):
        try:
            if os.path.isfile(config_file):
                with open(config_file, 'r') as f:
                    logging.debug('Configuration file opened: ' + config_file)
                    self.config = yaml.load(f, Loader=yaml.SafeLoader)
            else:
                logging.error('The configuration file does not exist at ' + config_file)
            logging.info('Last successful sync was {0}'.format(
                self.local_timestamp(self.config['last_update'])))
        except Exception as err:
            logging.error('There was an error loading the configuration file: {0}'.format(err))
            sys.exit('Fatal error. Exiting.')
        if not self.config:
            logging.error('Configuration not parsed correctly')
            logging.error('  make sure you have a "rbsync.yaml" file configured.')
            sys.exit('Fatal error. Exiting.')
        else:
            logging.debug('Configuration file parsed.')
            if 'rhythmdb' in self.config:
                self.config['rhythmdb'] = os.path.expanduser(self.config['rhythmdb'])
            else:
                self.config['rhythmdb'] = RHYTHMBOX_DB
        logging.debug('Configuration:')
        logging.debug(self.config)

    def save_config(self, config_file):
        try:
            with open(config_file, 'w+') as f:
                self.config['last_update'] = str(int(datetime.timestamp(datetime.now())))
                yaml.dump(self.config, f, default_flow_style = False)
        except Exception as err:
            logging.error('There was an error saving the configuration file: {0}'.format(err))
        logging.debug('Updated configuration file.')

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
            sys.exit('Fatal Error. Cannot conect to last.fm')

    def last_session(self, key_file):
        if not os.path.exists(key_file):
            skg = pylast.SessionKeyGenerator(self.network)
            url = skg.get_web_auth_url()

            print(
                "Please authorize the scrobbler "
                "to scrobble to your account: %s\n" % url)
            webbrowser.open(url)

            while True:
                try:
                    session_key = skg.get_web_auth_session_key(url)
                    fp = open(key_file, "w")
                    fp.write(session_key)
                    fp.close()
                    break
                except pylast.WSError:
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

    def xpath_matches(self, artist, title, album):
        xp_query = '//entry[@type=\"song\"]'
        if title is not None:
            xp_query += '/title[lower(text())=$title]/..'
        if artist is not None:
            xp_query += '/artist[lower(text())=$artist]/..'
        if album is not None and album != 'music' and album != '[unknown album]':  # 'music' == empty
            xp_query += '/album[lower(text())=$album]/..'
            matches = self.db_root.xpath(
                xp_query,
                title = title.lower(),
                artist = artist.lower(),
                album = album.lower(),
                extensions={(None, 'lower'): (lambda c, a: a[0].lower())})
        else:
            matches = self.db_root.xpath(
                xp_query,
                title = title.lower(),
                artist = artist.lower(),
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
                    + ' {{' + playcount + '}}' + ' [Played: ' + self.local_timestamp(track['timestamp']) + ']')
            else:
                logging.info('\033[91m' + 'x ' + '\033[00m' + track['artist'] + ' - '
                      + track['album'] + ' - ' + track['title'] + ' [Played: ' + self.local_timestamp(track['timestamp']) + ']')
        return num_matches

    def write_db(self):
        if self.config['backup']:
            rhythmdb_backup = self.config['rhythmdb'] + '.backup-' + self.config['last_update']
        shutil.copy2(self.config['rhythmdb'], rhythmdb_backup)
        self.db.write(self.config['rhythmdb'])

def sync_lastfm(secrets_file=SECRETS_FILE,
                config_file=CONFIG_FILE):
    sync = SyncRB(secrets_file,config_file)
    sync.load_lastfm_network()
    recents = sync.get_recent_tracks()
    if sync.match_scrobbles(recents) > 0:
        sync.write_db()
    sync.save_config(CONFIG_FILE)


if __name__ == '__main__':
    sync_lastfm()
