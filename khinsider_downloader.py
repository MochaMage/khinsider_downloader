from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait # available since 2.4.0
from selenium.webdriver.support import expected_conditions as EC # available since 2.26.0
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException
from selenium.webdriver.common.keys import Keys

import shutil
import threading
import requests
import re
import os
import eyed3
import cPickle as pickle
import sys
import string
import codecs

LAST_FM_URL = "http://ws.audioscrobbler.com/2.0"
LAST_FM_API_KEY = "f96fd5108b56d1228c5fc3a6bba4c8ee"

UTF8Writer = codecs.getwriter('utf8') 
sys.stdout = UTF8Writer(sys.stdout)


if len(sys.argv) == 2:
    url = sys.argv[1]
    # Use default regex option. Pattern most seen on kh_insider.
    regex = r"^\d*\s?\.?\s?(.*)\.mp3$"
    print "Using default title pattern to parse song titles"

elif len(sys.argv) == 3:
    regex = sys.argv[1]
    url = sys.argv[2]

else:
    raise Exception("Wrong number of arguments")

print "Starting Browser to get album name"
driver = webdriver.Chrome()
driver.get(url)

center = driver.find_element_by_class_name("contentpaneopen")
tbody = center.find_element_by_tag_name('table')
table = tbody.find_elements_by_tag_name('tr')

# Get the name of the album. Sometimes, blurbs about
# the soundtrack are included in parentheses after 
# the actual album title. In order for a cleaner album
# name that will more likely get results from last.fm,
# we get rid of any parentheses sections at the end.
album_name = center.find_element_by_tag_name('h2').text
clean_album_name = re.search(r"^(.*)\s\(.*$", album_name)
if clean_album_name:
    album_name = clean_album_name.group(1)

print "Album Name: '{0}'".format(album_name)

songs = []

# Find if this directory and song source URL file exists,
# otherwise, use selenium to get the song sources.
song_cache_location = os.path.join(os.getcwd(), album_name, "{0}.songlist".format(album_name))
if os.path.exists(song_cache_location):
    print "Song URL cache found!"
    with open(song_cache_location, "rb") as f:
        songs = pickle.load(f)
else:
    print "No song cache found, crawling for songs URLS"
    song_links = []

    # Get the links to the song pages and save to song_links
    for el in table:
        try:
            song_link = el.find_element_by_tag_name('a')
            anchor = song_link.get_attribute('href')
            song_title = song_link.text

            print "Adding '{0}' to song list".format(song_title)
            song_links.append((song_title, anchor))

        except NoSuchElementException:
            pass

    # Go to each song and find the links to the actual song files
    for song_title, anchor in song_links:
            driver.get(anchor)
            page = driver.find_element_by_id('EchoTopic')
            button = page.find_element_by_link_text('Click here to download')
            song_url = button.get_attribute('href')
            songs.append((song_title, song_url))

    # Create directory to store songs in. 
    # if directory exists, just keep going.
    try:
        os.mkdir(album_name)
    except OSError:
        pass
   
    # Save the songs list to disk so that if we want to download again, selenium won't be required.
    with open(song_cache_location, "wb") as f:
        pickle.dump(songs, f)

# Close the inital selenium window, no longer needed
driver.quit()

# Use last.fm to get the album artwork, if it can find it.
print "Searching for album on last.fm"

found_album_artist = ""
found_album_name = ""
found_cover_data = None
found_cover_mime = ""
found_image_url = ""

# Since most relevant result might still be wrong, allow the
# user to specify if they want to not use last.fm's result
use_last_fm_data = True

params = {'api_key': LAST_FM_API_KEY, 
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

    if found_image_url:
        img_res = requests.get(found_image_url, stream=True)
        found_cover_mime = img_res.headers['Content-Type']
        img_res.raw.decode_content = True
        found_cover_data = img_res.raw.read()

    print "-" * 40
    print "LAST.FM RESULTS"
    print "-" * 40
    print u"Album cover image found: '{0}'".format(found_image_url)
    print u"Artist name found: '{0}'".format(found_album_artist)
    print u"Album name found: '{0}'".format(found_album_name)
    
    while True:
        user_input = raw_input("Apply the found results to this album?(y/n):  ").lower()
        if user_input in ('y', 'n'):
            use_last_fm_data = True if user_input=='y' else False
            break

for idx, song in enumerate(songs, 1):
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
        print "Bad regex, using file name for title"
        try:
            title = re.search(r"(.*)\.mp3", song[0]).group(1)
        except:
            print "Unable to parse title of file, is this an MP3 file?"
    
    title = string.capwords(title.replace("-", " "))
    filename = "{0}/{1}.mp3".format(album_name, title)

    if os.path.exists(filename):
        print "File already available locally, aborting download"
    else:
        print "Downloading: '{0}'. Saving as '{1}'".format(song[1], title)
        # Try to fetch the song from the server
        res = requests.get(song[1], stream=True)

        if res.status_code == 200:
            # Write the song to a file on disk
            with open(filename,  "wb") as f:
                res.raw.decode_content = True
                shutil.copyfileobj(res.raw, f)
        else:
            print "Unable to download file, skipping..."
            break

    # Edit the new file with ID3 data
    # to make songs somewhat easier to track.
    song = eyed3.load(filename)
    song.tag.title = title
    song.tag.track_num = idx
    song.tag.album = album_name

    if use_last_fm_data:
        if found_cover_data:
            song.tag.images.set(0x03, img_data=found_cover_data, mime_type=found_cover_mime, description=u"")
        if found_album_artist:
            song.tag.artist = found_album_artist
        if found_album_name:
            song.tag.album = found_album_name

    song.tag.save(encoding='utf-8')
