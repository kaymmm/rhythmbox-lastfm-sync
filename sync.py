#!/usr/bin/env python3

"""
Copyright 2017 Keith Miyake

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
from os.path import expanduser
import time
from lxml import etree
import configparser
# from xml.sax.saxutils import escape

current_dir = os.path.dirname(os.path.realpath(__file__))
# Change the following paths as appropriate on your system
config_file_default = current_dir + '/rbsync.cfg'
secrets_file_default = current_dir + '/secrets.yaml'
rhythmdb_default = expanduser('~/.local/share/rhythmbox/rhythmdb.xml')
recents_test_file = current_dir + '/recents_test.txt'

debug = False


class SyncRB():

    secrets = None
    config = None

    def __init__(self,
                 secrets_file=secrets_file_default,
                 config_file=config_file_default,
                 database_file=rhythmdb_default):
        if self.secrets is None:
            self.load_secrets(secrets_file)

        if self.config is None:
            self.load_config(config_file, database_file)

        self.username = self.secrets['username']
        self.password_hash = self.secrets['password_hash']

        self.API_KEY = self.secrets['api_key']
        self.API_SECRET = self.secrets['api_secret']

        self.last_update = self.config['last_update']
        self.timestamp = str(int(time.time()))

        if os.path.isfile(self.config['rhythmdb']):
            self.db = etree.parse(self.config['rhythmdb'])
            self.db_root = self.db.getroot()

    def local_timestamp(self, strtimestamp):
        from datetime import datetime
        import tzlocal  # pip install tzlocal
        return datetime.fromtimestamp(
                float(strtimestamp),
                tzlocal.get_localzone()).strftime('%Y-%m-%d %H:%M:%S (%Z)')

    def load_secrets(self, secrets_file):
        if os.path.isfile(secrets_file):
            import yaml  # pip install pyyaml
            with open(secrets_file, 'r') as f:  # see example_test_pylast.yaml
                self.secrets = yaml.load(f, Loader=yaml.SafeLoader)
                if not self.secrets:
                    if debug:
                        print('secrets.yaml does not contain necessary variables')
                    self.create_secrets(secrets_file)
                else:
                    if debug:
                        print('secrets.yaml loaded')
        else:
            self.create_secrets(secrets_file)

    def create_secrets(self, secrets_file):
        import yaml  # pip install pyyaml
        from getpass import getpass
        self.secrets = {}
        try:
            self.secrets['username'] = \
                input("Enter LastFM username: ").strip()
            self.secrets['password_hash'] = \
                pylast.md5(getpass(prompt='Enter LastFM password: ').strip())
            self.secrets['api_key'] = \
                input("Enter LastFM API Key: ").strip()
            self.secrets['api_secret'] = \
                getpass(prompt='Enter LastFM API Secret: ').strip()
            if debug:
                from pprint import pprint
                pprint(self.secrets)
            with open(secrets_file, 'w+') as f:
                yaml.dump(self.secrets, f, default_flow_style=False)
            if debug:
                print('Added secrets to secrets.yaml')
        except Exception as err:
            print('There was an error saving the secrets.yaml file: %s' % Exception)

    def load_config(self, config_file, database_file):
        config = configparser.ConfigParser()
        self.config = {}
        if os.path.isfile(config_file):
            config.read_file(open(config_file))
            self.config['last_update'] = config['Sync']['last_update'] \
                if 'last_update' in config['Sync'] else '0'
            self.config['limit'] = config['Sync']['limit'] \
                if 'limit' in config['Sync'] else '500'
            if database_file is not None:
                self.config['rhythmdb'] = config['Sync']['rhythmdb'] \
                    if 'rhythmdb' in config['Sync'] \
                    else database_file
            else:
                self.config['rhythmdb'] = rhythmdb_default
        else:
            self.config['last_update'] = '0'
            self.config['limit'] = '500'
            self.config['rhythmdb'] = rhythmdb_default
        print('Updating with scrobbles since ',
              self.local_timestamp(self.config['last_update']))

    def save_config(self, config_file):
        if self.config is not None:
            config = configparser.ConfigParser()
            config['Sync'] = {}
            config['Sync']['last_update'] = self.timestamp
            config['Sync']['limit'] = self.config['limit']
            config['Sync']['rhythmdb'] = self.config['rhythmdb']
            with open(config_file, 'w') as configfile:
                config.write(configfile)
            if debug:
                print('Updated configuration file')

    def load_lastfm_network(self):
        self.network = pylast.LastFMNetwork(
            api_key=self.API_KEY, api_secret=self.API_SECRET,
            username=self.username, password_hash=self.password_hash)
        return 1

    def pylast_to_dict(self, track_list):
        return_list = []
        for c, track in enumerate(track_list, 1):
            return_list.insert(0, {
                'artist': str(track.track.artist),
                'title': str(track.track.title),
                'album': str(track.album),
                'timestamp': track.timestamp})
        # if debug:
        #     print('Saving recent track list to ' + recents_test_file)
        #     self.dump_recent_tracks(return_list)
        return return_list

    def get_recent_tracks(self):
        recent_tracks = self.network.get_user(self.username).get_recent_tracks(
                limit=int(self.config['limit']),
                time_from=self.config['last_update'],
                time_to=self.timestamp)
        return self.pylast_to_dict(recent_tracks)

    def dump_recent_tracks(self, recents):
        import json
        with open(recents_test_file, 'w') as f:
            json.dump(recents, f, indent=2)

    def read_recent_tracks(self):
        import ast
        ret_val = None
        if os.path.isfile(recents_test_file):
            with open(recents_test_file, 'r') as f:
                g = f.read()
            ret_val = ast.literal_eval(g)
        return ret_val

    def xpath_escape(self, s):
        # x = escape(s)
        x = s.replace('"', '&quot;')
        return x

    def xpath_matches(self, artist, title, album):
        xp_query = '//entry[@type=\"song\"]'
        if title is not None:
            xp_query += '/title[lower(text())=\"%s\"]/..' % \
                    self.xpath_escape(title.lower())
        if artist is not None:
            xp_query += '/artist[lower(text())=\"%s\"]/..' % \
                    self.xpath_escape(artist.lower())
        if album is not None and album != 'music':  # 'music' == empty
            xp_query += '/album[lower(text())=\"%s\"]/..' % \
                    self.xpath_escape(album.lower())
        matches = self.db_root.xpath(
            xp_query,
            extensions={(None, 'lower'): (lambda c, a: a[0].lower())})
        if debug:
            print('\n->Query: ' + xp_query)
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
                print('\033[92m' + '✓ ' + '\033[00m' + track['artist']
                      + ' - ' + track['album'] + ' - ' + track['title']
                      + ' {{' + playcount + '}}')
            else:
                print('\033[91m' + 'x ' + '\033[00m' + track['artist'] + ' - '
                      + track['album'] + ' - ' + track['title'])
        return num_matches

    def write_db(self):
        rhythmdb_backup = self.config['rhythmdb'] + '.backup-' + self.timestamp
        shutil.copy2(self.config['rhythmdb'], rhythmdb_backup)
        self.db.write(self.config['rhythmdb'])


if __name__ == '__main__':
    sync = SyncRB(secrets_file=secrets_file_default,
                  config_file=config_file_default)
    sync.load_lastfm_network()

    recents = sync.get_recent_tracks()
    if sync.match_scrobbles(recents) > 0:
        sync.write_db()
    sync.save_config(config_file_default)
