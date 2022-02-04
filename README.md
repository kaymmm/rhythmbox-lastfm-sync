# Rhythmbox Sync from LastFM (easily tweaked for LibreFM etc.)

This is project developed for myself to pull external scrobbles to LastFM into the Rhythmbox playcount. If anyone else finds it useful they're welcome to try it out.

It works by connecting to the LastFM api and pulling your recently scrobbled songs. Hopefully those scrobbles came from a music player using the songs from your Rhythmbox library (e.g., on your phone), otherwise it won't be able to find a match. It then edits your Rhythmbox database and updates the playcount accordingly.

**Note:** Sometimes the matching doesn't work. I've been tweaking the script to try handling cases when they appear, but some may still escape matching.
 
## Installation

1. This is tested on linux/gnu, based on my own computer setup; not sure if it'll work on other OS, but you can try it by editing `sync.py` with the appropriate directory structure. All commands assume linux/gnu, edit as appropriate on your own OS.
2. Requires python3. Not sure what version exactly, but you need a version with configparser built in (or to install it through pip)
3. `git clone` the repo; `cd` to the repo directory.
4. `pip install -r requirements.txt`
5. create `rbsync.cfg`; you can use `sample_config.cfg` as a template (e.g., `cp sample_config.cfg rbsync.cfg`)
6. locate your `rhythmdb.xml` database file, probably in `~/.local/share/rhythmbox/rhythmdb.xml`
7. edit `rbsync.cfg` (or you can use the default values):
  a. backup: boolean whether to backup the rhythmbox database file before editing it
  b. limit: maximum number of items to pull from LastFM
  c. rhythmdb: the path you located in step (4)
  d. last_update: the epoch time you want to start syncing from
    - you can get the epoch time using something like: `> date +%s -d'Jan 1, 2020 03:30:00'`
    - by default, the epoch time is 0; feel free to leave this alone and it'll just pull your entire LastFM history (up to `limit` items)
8. set up a LastFM developer account (search it on the internet; too lazy to look it up myself)
9. from ^^ get the api key and api secret; write it down or keep the window open
  a. the first time you run sync, it'll prompt you for your username, password, and the api key/secret, all of which are required to log in and access your play history
10. make sure that `sync.py` is executable: `> chmod u+x sync.py`
11. run it! e.g., `> ./sync.py`; you probably want to quit Rhythmbox before you sync so that your changes register correctly. though it might update automatically?
12. while it's running, it should output what's going on as it syncs files, along with a check/'x' corresponding to the sync status. 'x' usually means that for whatever reason, the artist/title wasn't found in your library.
13. after running, it should create a `secrets.yaml` file adjacent to `rbsync.cfg`. don't share or git-sync this since it'll store your LastFM api key and password hash (rainbow table attacks?)
14. if you said yes to backup, it'll create a `rhythmdb.xml.backup-(date)` file adjacent to your original rhythmdb.xml file. **Note**: it won't clean old versions, so if you run it often, you'll spam backup files that can get quite large. suggest cleaning out old backups periodically.
15. if you don't want all the info output, edit `sync.py` l37 and change `logging.INFO` to something else, probably `logging.WARNING` so you'll still see actual warnings or errors.

## To-Do/known bugs

- [X] Some files don't sync correctly. It has something to do with the format of artist/title/album but needs to be confirmed across a broader test set.
  - [x] items without an album or "[unknown album]" [seems to be fixed]
  - [x] albums with quotes or apostrophes (e.g., 7", what's going on; one or the other works but not both at the same time) [seems to be fixed]
- [ ] Change config and secrets files to XML to reduce dependencies; can't remember why I did it the way I did, but that was not a clever design choice.
- [ ] update the test suite and actually complete it
- [X] Move config directories to a more sensible location
- [ ] Code cleanup
- [X] Create this readme

## LICENSE

see `LICENSE` (it's GPLv3)
