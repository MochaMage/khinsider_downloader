from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait # available since 2.4.0
from selenium.webdriver.support import expected_conditions as EC # available since 2.26.0
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException
from selenium.webdriver.common.keys import Keys
#from selenium.webdriver.common.action_chains import ActionChains

import shutil
import threading
import requests
import re
import os
import eyed3
import cPickle as pickle
import sys
import pudb

LAST_FM_URL = "http://ws.audioscrobbler.com/2.0"
LAST_FM_API_KEY = "f96fd5108b56d1228c5fc3a6bba4c8ee"
COVER_FILE_NAME = "front_cover"
ICON_FILE_NAME = "icon"

if len(sys.argv) == 2:
    url = sys.argv[1]
    # Use default regex option. Pattern most seen on kh_insider.
    regex = r"^\d*\s?\.?\s?(.*)\.mp3$"

elif len(sys.argv) == 3:
    regex = sys.argv[1]
    url = sys.argv[2]
else:
    raise Exception("Wrong number of arguments")

driver = webdriver.Chrome()
driver.get(url)

print "Starting Browser"

center = driver.find_element_by_class_name("contentpaneopen")
tbody = center.find_element_by_tag_name('table')
table = tbody.find_elements_by_tag_name('tr')

# Get the name of the album
album_name = center.find_element_by_tag_name('h2').text
clean_album_name = re.search(r"^(.*)\s\(.*$", album_name)
if clean_album_name:
    album_name = clean_album_name.group(1)

print "Album Name: '{0}'".format(album_name)

songs = []
# Find if this directory and song source URL file exists,
# otherwise, use selenium to get the song sources.
if os.path.exists(os.path.join(os.getcwd(), album_name, album_name)):
    print "Song URL cache found!"
    with open(os.path.join(os.path.join(os.getcwd(), album_name, album_name)), "rb") as f:
        songs = pickle.load(f)
else:
    print "Crawling for songs URLS"
    # Go get the song list
    for el in table:
        try:
            song_link = el.find_element_by_tag_name('a')
            anchor = song_link.get_attribute('href')
            song_title = song_link.text
            print "Adding '{0}'".format(song_title)

            dl_driver = webdriver.Chrome()
            dl_driver.get(anchor)
            page = dl_driver.find_element_by_id('EchoTopic')
            button = page.find_element_by_link_text('Click here to download')

            song_url = button.get_attribute('href')
            songs.append((song_title, song_url))

    # old method involved downloading the songs themselves using the browser but I wanted
    # the least amount of browser time open as possible. No browser would be even better.
    #        ActionChains(dl_driver).key_down(Keys.ALT).click(button).key_up(Keys.ALT).perform()
    #        sleep(10)
            dl_driver.quit()

        except NoSuchElementException:
            pass

    # Create directory to store songs in. 
    # if directory exists, just keep going.
    try:
        os.mkdir(album_name)
    except OSError:
        pass
   
    # Save the songs list to disk so that if we want to download again, selenium won't be required.
    with open(os.path.join(os.path.join(os.getcwd(), album_name, album_name)), "wb") as f:
        pickle.dump(songs, f)

# Close the inital selenium window, no longer needed
driver.quit()

# Use last.fm to get the album artwork, if it can find it.
print "Searching for album on last.fm"
params = {'api_key': LAST_FM_API_KEY, 'format': 'json', 'method': 'album.search', 'album': album_name, 'limit': 1}
res = requests.get(LAST_FM_URL, params=params)
album_artist = ""
real_album_name = ""

cover_data = None
cover_mime = ""

# Use the most relevant result and find its largest album album art file location
if int(res.json()['results']['opensearch:totalResults']) > 0:
    images = res.json()['results']['albummatches']['album'][0]['image']
    album_artist = res.json()['results']['albummatches']['album'][0]['artist']
    real_album_name = res.json()['results']['albummatches']['album'][0]['name']

    image_url = ""

    for image in images:
        if image['size'] == 'extralarge':
            image_url = image['#text']

    if image_url:
        img_res = requests.get(image_url, stream=True)
        cover_mime = img_res.headers['Content-Type']
        img_res.raw.decode_content = True
        cover_data = img_res.raw.read()

    print "Album cover image found: '{0}'".format(image_url)

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
        print "Bad regex, using found title"
        title = re.search(r"(.*)\.mp3", song[0]).group(1)
    
    title = title.replace("-", " ").title()

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

    # Edit the new file with ID3 data
    # to make songs somewhat easier to track.
    song = eyed3.load(filename)
    song.tag.title = title
    song.tag.track_num = idx

    if cover_data:
        song.tag.images.set(0x03, img_data=cover_data, mime_type=cover_mime, description=u"")

    if album_artist:
        song.tag.artist = album_artist

    if real_album_name:
        song.tag.album = real_album_name
    else:
        song.tag.album = album_name

    song.tag.save(encoding='utf-8')
