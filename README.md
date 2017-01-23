# khinsider_downloader
Allows for batch downloads of music from KH Insider. Also updates the ID3 tags and cover image of each song when downloading album. 

##Usage: 
`./khinsider_download.py ["<regex>"] <KH Insider album URL>`

KH Insider's file names for their songs are incredibly inconsistent, so I've been unable to create a way to parse them universally. However, there is a pattern that is more common than others so if the song titles look like this, then the regex argument is not needed as the script's default regex will be capable of handling them.

```
01.twilight princess theme.mp3

03 twilight princess theme.mp3
```

However, there have been other irregular patterns spotted that will not result in pretty titles with the default regex, like these

```
EON-01-James-Bond-Theme.mp3

01 - going down on it - hot action cop.mp3
```

In these cases, it is useful to hop on over to rubular.com or regex101.com and try out creating a pattern that will parse these titles and pass that to the script. For example, the past two samples could have a pattern that looks like the following:

EON-\d+-(.*)\.mp3 ------------> This will turn "EON-01-James-Bond-Theme.mp3" into "James-Bond-Theme". The script will replace the "-" into spaces

\d+\s-\s(.*)\s-\s.*\.mp3 -----> This will turn "01 - going down on it - hot action cop.mp3" into "going down on it"

A short lesson on regular expressions:

```
\d : Any digit

.  : Absolutely anything

*  : Zero or more of the character to the left of this will show up

+  : 1 or more of the character to the left of this will show up

() : Anything within parentheses is treated as a group. The script expects the first group to be the song title, hence why (.*) shows up so frequently
```
