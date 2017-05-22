#!/usr/bin/python

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

# Change the following paths as appropriate on your system
config_file = "rbsync.cfg"
secrets_file = "secrets.yaml"
rhythmdb_default = expanduser('~/.local/share/rhythmbox/rhythmdb.xml')

debug = False


class SyncRB():

    secrets = None
    config = None

    def __init__(self):
        if self.secrets is None:
            self.load_secrets(secrets_file)

        if self.config is None:
            self.load_config(config_file)

        self.username = self.secrets['username']
        password_hash = self.secrets['password_hash']

        API_KEY = self.secrets['api_key']
        API_SECRET = self.secrets['api_secret']

        self.network = pylast.LastFMNetwork(
            api_key=API_KEY, api_secret=API_SECRET,
            username=self.username, password_hash=password_hash)

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
                tzlocal.get_localzone()).strftime("%Y-%m-%d %H:%M:%S (%Z)")

    def load_secrets(self, secrets_file):
        if os.path.isfile(secrets_file):
            import yaml  # pip install pyyaml
            with open(secrets_file, "r") as f:  # see example_test_pylast.yaml
                self.secrets = yaml.load(f)
            if debug:
                print("Loaded secrets from secrets.yaml")
        else:
            self.secrets = {}
            try:
                self.secrets["username"] = \
                    os.environ['PYLAST_USERNAME'].strip()
                self.secrets["password_hash"] = \
                    os.environ['PYLAST_PASSWORD_HASH'].strip()
                #  password_hash = pylast.md5('password')
                self.secrets["api_key"] = os.environ['PYLAST_API_KEY'].strip()
                self.secrets["api_secret"] = \
                    os.environ['PYLAST_API_SECRET'].strip()
                if debug:
                    print("Loaded secrets from environment variables")
            except KeyError:
                print("Missing environment variables: PYLAST_USERNAME etc.")

    def load_config(self, config_file):
        config = configparser.ConfigParser()
        self.config = {}
        if os.path.isfile(config_file):
            config.read_file(open(config_file))
            self.config['last_update'] = config['Sync']['last_update'] \
                if 'last_update' in config['Sync'] else "0"
            self.config['limit'] = config['Sync']['limit'] \
                if 'limit' in config['Sync'] else "500"
            self.config['rhythmdb'] = config['Sync']['rhythmdb'] \
                if 'rhythmdb' in config['Sync'] \
                else rhythmdb_default
        else:
            self.config['last_update'] = '0'
            self.config['limit'] = 500
            self.config['rhythmdb'] = rhythmdb_default
        print("Updating with scrobbles since ",
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
                print("Updated configuration file")

    def get_recent_tracks(self):
        recent_tracks = self.network.get_user(self.username).get_recent_tracks(
                limit=int(self.config['limit']),
                time_from=self.config['last_update'],
                time_to=self.timestamp)
        return recent_tracks

    def match_scrobbles(self, tracklist):
        for c, track in enumerate(tracklist, 1):
            artist = track.track.artist
            title = track.track.title
            album = track.album
            timestamp = track.timestamp
            if debug:
                print(str(artist) + ' - ' + str(title) +
                      ' {' + str(album) + '} @ ' + str(timestamp))
            xpath_query = '//entry[@type="song"]/title[lower(text())="' \
                + str(title).lower() + '"]/../artist[lower(text())="' \
                + str(artist).lower() + '"]/../album[lower(text())="' \
                + str(album).lower() + '"]/..'
            matches = self.db_root.xpath(
                    xpath_query,
                    extensions={(None, 'lower'): (lambda c, a: a[0].lower())})
            if len(matches) >= 1:
                #  If there are multiples of the song, use the first instance
                el_playcount = matches[0].find('play-count')
                el_temp = etree.Element('play-count')
                if el_playcount is not None:
                    el_temp.text = str(int(el_playcount.text) + 1)
                    matches[0].replace(el_playcount, el_temp)
                else:
                    el_temp.text = "1"
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
                print('\033[92m' + '✓ ' + '\033[00m' + str(artist)
                      + ' - ' + str(album) + ' - ' + str(title)
                      + ' {{' + playcount + '}}')
            else:
                print('\033[91m' + 'x ' + '\033[00m' + 'No Match: '
                      + str(artist) + ' - ' + str(album) + ' - ' + str(title))
        rhythmdb_backup = self.config['rhythmdb'] + '.backup-' + sync.timestamp
        shutil.copy2(self.config['rhythmdb'], rhythmdb_backup)
        self.db.write(self.config['rhythmdb'])


if __name__ == '__main__':
    sync = SyncRB()

    recents = sync.get_recent_tracks()
    sync.match_scrobbles(recents)
    sync.save_config(config_file)
