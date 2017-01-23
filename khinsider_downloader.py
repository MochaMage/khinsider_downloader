#!/usr/bin/python3
# _*_ coding:utf-8 _*_

import shutil
import requests
import re
import os
import sys
import string
import _pickle as pickle
import codecs
from bs4 import BeautifulSoup
from mutagen import id3
from mutagen.mp3 import MP3
import sqlite3

LAST_FM_URL = "http://ws.audioscrobbler.com/2.0"


def getSoup(url):
    page = requests.get(url)
    removeRe = re.compile(r"^</td>\s*$", re.MULTILINE)
    page_soup = BeautifulSoup(re.sub(removeRe, b'', str(page.content)), "html.parser")
    center = page_soup.find(**{'class': 'contentpaneopen'})

    return center


def getCleanAlbumName(album_name):
    clean_album_name = re.search(r"^(.*)\s\(.*$", album_name)
    if clean_album_name:
        return clean_album_name.group(1)
    return album_name


def getCleanSongTitle(song, regex):
    # Make the title of a song easier to read
    # Most stuff uploaded to KHI use the same
    # format so for most cases, the default
    # regex will suffice. If it doesn't match the
    # default of whatever regex expression was passed
    # to the script, just use the original title.
    searcher = re.search(regex, song[0])
    title = ""

    if(searcher):
        title = searcher.group(1)
    else:
        print("Bad regex, using file name for title")
        try:
            title = re.search("(.*)\.mp3", song[0]).group(1)
        except:
            print("Unable to parse title of file, is this an MP3 file?")

    return string.capwords(title.replace("-", " "))


def checkForSongCache(album_name, song_cache_location):
    # Find if this directory and song source URL file exists,
    # otherwise, use selenium to get the song sources.
    songs = []
    if os.path.exists(song_cache_location):
        with open(song_cache_location, "rb") as f:
            songs = pickle.load(f)
            return songs
    return False


def getSongList(soup):
    tbody = soup.find('table', **{'id': 'songlist'})
    songs = []
    # Get the links to the song pages and save to song_links
    song_links = tbody.findAll('tr')[1:-1]

    for tr in song_links:
        song_res = requests.get("{0}{1}".format("https://downloads.khinsider.com", tr.find('a')['href']))
        song_soup = BeautifulSoup(song_res.content, "html.parser")
        song_url = song_soup.audio['src']
        print("Adding '{0}' to song list".format(u"{0}".format(song_url)))

        songs.append((tr.a.text, song_url))
    return songs


def createSongCache(songs, album_name, song_cache_location):
    # Create directory to store songs in.
    # if directory exists, just keep going.
    try:
        os.mkdir(album_name)
    except OSError:
        pass

    # Save the songs list to disk so that if we want to download again, selenium won't be required.
    with open(song_cache_location, "wb") as f:
        pickle.dump(songs, f)


def searchLastFm(album_name):
    # Use last.fm to get the album artwork, if it can find it.

    found_album_artist = ""
    found_album_name = ""

    found_cover_data = None
    found_cover_mime = ""
    found_image_url = ""

    db = createConnection("config.db")
    api_key = getLastFmApiKey(db)

    params = {'api_key': api_key,
              'format': 'json',
              'method': 'album.search',
              'album': album_name,
              'limit': 1}

    res = requests.get(LAST_FM_URL, params=params)

    # Use the most relevant result and find its largest album album art file location
    if int(res.json()['results']['opensearch:totalResults']) > 0:
        album_match = res.json()['results']['albummatches']['album'][0]
        images = album_match['image']
        found_album_artist = album_match['artist']
        found_album_name = album_match['name']

        # Really, last.fm? You give me a JSON map
        # but can't be bothered to make the sizes
        # the keys?!
        for image in images:
            if image['size'] == 'extralarge':
                found_image_url = image['#text']

        return (found_album_name, found_album_artist, found_image_url)

    return False


def downloadSong(album_name, title, song):
    # Disgusting hack around unicode characters in filenames
    filename = '{0}/{1}.mp3'.format(album_name, title).replace("\\", "")
    if os.path.exists(filename):
        return filename
    else:
        # Try to fetch the song from the server
        res = requests.get(song[1], stream=True)
        print(u"Downloading '{0}'".format(filename))

        if res.status_code == 200:
            # Write the song to a file on disk
            with open(filename, "xb") as f:
                res.raw.decode_content = True
                shutil.copyfileobj(res.raw, f)
                return filename
        else:
            return False


def editMp3Details(filename, title, album_name, track_number,
                   use_lastfm = False, lastfm_cover_url = "",
                   lastfm_album_artist = "", lastfm_album_name = ""):
    # Edit the new file with ID3 data
    # to make songs somewhat easier to track.
    song = MP3(filename)
    song.tags['TIT2'] = id3.TIT2(encoding=id3.Encoding.UTF8, text=[title])
    song.tags['TRCK'] = id3.TRCK(encoding=id3.Encoding.UTF8, text=[track_number])
    song.tags['TALB'] = id3.TALB(encoding=id3.Encoding.UTF8, text=[album_name])

    if use_lastfm:
        found_cover_data = None
        if lastfm_cover_url:
            img_res = requests.get(lastfm_cover_url, stream=True)
            found_cover_mime = img_res.headers['Content-Type']
            img_res.raw.decode_content = True
            found_cover_data = img_res.raw.read()

        if found_cover_data is not None:
            song.tags.add(id3.APIC(data=found_cover_data, mime=found_cover_mime, type=id3.PictureType.COVER_FRONT))
        if lastfm_album_artist:
            song.tags['TPE1'] = id3.TPE1(encoding=id3.Encoding.UTF8, text=[lastfm_album_artist])
        if lastfm_album_name:
            song.tags['TALB'] = id3.TALB(encoding=id3.Encoding.UTF8, text=[lastfm_album_name])

    song.save()


def createConnection(db_file):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    db = sqlite3.connect("{0}/config.db".format(dir_path))
    return db


def getLastFmApiKey(db):
    with db:
        cursor = db.cursor()
        cursor.execute("SELECT api_key FROM api_key WHERE service='LastFM'")
        api_key_column = cursor.fetchone()
        return api_key_column[0]


def main():
    if len(sys.argv) == 2:
        url = sys.argv[1]
        # Use default regex option. Pattern most seen on kh_insider.
        regex = r"(.*)"
        print("Using default title pattern to parse song titles")

    elif len(sys.argv) == 3:
        regex = sys.argv[1]
        url = sys.argv[2]

    else:
        raise Exception("Usage: ./khinsider_downloader.py [regex] <Game album url>")

    # Get crawleable page object
    soup = getSoup(url)

    # Get the name of the album. Sometimes, blurbs about
    # the soundtrack are included in parentheses after
    # the actual album title. In order for a cleaner album
    # name that will more likely get results from last.fm,
    # we get rid of any parentheses sections at the end.
    album_name = str(soup.h2.text)
    album_name = getCleanAlbumName(album_name)
    print("Album Name: '{0}'".format(album_name))

    # Get the list of songs from the page, whether
    # from a cache made in a previous run or by
    # crawling the page object.
    song_cache_location = os.path.join(os.getcwd(), album_name, "{0}.songlist".format(album_name))
    songs = checkForSongCache(album_name, song_cache_location)
    if songs:
        print("Song URL cache found!")
    else:
        print("No song cache found, crawling for songs URLS")
        songs = getSongList(soup)
        createSongCache(songs, album_name, song_cache_location)

    # Search LastFM for information on the game album being downloaded.
    print("Searching for album on last.fm")
    lastfm_album_name, lastfm_album_artist, lastfm_image_url = searchLastFm(album_name)

    print("-" * 40)
    print("{:-^40s}".format("LAST.FM RESULTS"))
    print("-" * 40)
    print(u"Album cover image found: '{0}'".format(lastfm_image_url))
    print(u"Artist name found: '{0}'".format(lastfm_album_artist))
    print(u"Album name found: '{0}'".format(lastfm_album_name))

    # Since most relevant result might still be wrong, allow the
    # user to specify if they want to not use last.fm's result.
    use_last_fm_data = False
    while True:
        user_input = input("Apply the found results to this album?(y/n):  ").lower()
        if user_input in ('y', 'n'):
            use_last_fm_data = True if user_input == 'y' else False
            break

    # Go through the song list and download each song, then edit its MP3 details accordingly.
    for track_number, song in enumerate(songs, 1):
        title = getCleanSongTitle(song, regex)
        filename = downloadSong(album_name, title, song)
        if filename:
            editMp3Details(filename, title,  album_name, track_number, use_last_fm_data,
                           lastfm_image_url, lastfm_album_artist, lastfm_album_name)
        else:
            print("Unable to download {0}, skipping...".format(filename))


if __name__ == "__main__":
    main()
