[app]
title = YT Guide
package.name = ytguide
package.domain = org.personal
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
icon.filename = app_icon.png
version = 1.0
requirements = python3,kivy,kivymd,pyairtable,yt-dlp
android.permissions = INTERNET
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
