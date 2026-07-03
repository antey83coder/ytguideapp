[app]
title = YT Guide
package.name = ytguide
package.domain = org.personal
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
icon.filename = app_icon.png
version = 1.0
requirements = python3,kivy,kivymd==1.2.0,sqlite3,openssl,requests,urllib3,certifi,charset-normalizer,idna,pyairtable==1.5.0,yt-dlp
android.permissions = INTERNET
orientation = all
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
