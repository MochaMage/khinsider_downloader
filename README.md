# khinsider_downloader
Allows for batch downloads of music from KH Insider using Selenium Webdriver. Also updates the ID3 tags and cover image of each song when downloading album. 

##Usage: 
`python khinsider_downloader.py ["<regex>"] <KH Insider album URL>`

KH Insider's file names for their songs are incredibly inconsistent, so I've been unable to create a way to parse them universally.
They've started being better about their file names so I changed the default regex to just use whatever title you see on the web page. However, you will occassionally see irregular titles like this, which will necesitate the use of a regex to make the titles and file names look pretty.

```
EON-01-James-Bond-Theme.mp3

01 - going down on it - hot action cop.mp3
```

In these cases, it is useful to hop on over to rubular.com or regex101.com and try out creating a pattern that will parse these titles and pass that to the script. For example, the past two samples could have a pattern that looks like the following:

```
EON-\d+-(.*)\.mp3 ------------> This will turn "EON-01-James-Bond-Theme.mp3" into "James-Bond-Theme". The script will replace the "-" into spaces

\d+\s-\s(.*)\s-\s.*\.mp3 -----> This will turn "01 - going down on it - hot action cop.mp3" into "going down on it"
```

So the command will look like this: 

```python khinsider_downloader.py "\d+\s-\s(.*)\s-\s.*\.mp3" <url>```

Don't forget the quotations around your regex or your shell might interpret your command in an unintended manner.

##A short lesson on regular expressions that will most apply to you:

```
\d : Any digit

.  : Absolutely anything

*  : Zero or more of the character to the left of this will show up

+  : 1 or more of the character to the left of this will show up

() : Anything within parentheses is treated as a group. The script expects the first group to be the song title, hence why (.*) shows up so frequently
```

## Required to run

* [Python 2.7](https://www.python.org/downloads/release/python-2713)
* Requests (Install using "pip install requests" after installing python)
* Eyed3 (Also install using "pip install eyed3" after installing python)
* BeautifulSoup (Also install using "pip install beautifulsoup" after installing python)

## Possible future features
* Ability to specify which directory to download album to
* "Fast" mode"  using lxml, which depends on external C libs


