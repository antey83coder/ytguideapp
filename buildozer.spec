[app]
title = YT Guide
package.name = ytguide
package.domain = org.personal
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
icon.filename = app_icon.png
version = 1.0
requirements = python3,kivy,kivymd,openssl,requests,urllib3,certifi,pyairtable,yt-dlp, sqlite3, pillow
android.permissions = INTERNET
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
