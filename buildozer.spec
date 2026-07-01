[app]
title = YT Guide
package.name = ytguide
package.domain = org.personal
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
icon.filename = app_icon.png
version = 1.0
requirements = python3,kivy==2.3.0,kivymd==1.2.0,sqlite3,openssl,requests,urllib3,certifi,charset-normalizer,idna,typing_extensions,pyairtable,yt-dlp
android.permissions = INTERNET
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
