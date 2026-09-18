[app]
title = ROLEX AI
package.name = rolexai
package.domain = org.rolexai
source.dir = .
source.include_exts = py,json,txt,md,png,jpg,jpeg,kv,atlas
source.exclude_exts = pyc,pyo,db,log
version = 38.0.0
requirements = python3,kivy==2.3.1
orientation = portrait
fullscreen = 0
[buildozer]
log_level = 2
warn_on_root = 1

[app:android]
android.api = 34
android.minapi = 23
android.ndk = 25b
android.archs = arm64-v8a
android.permissions = INTERNET,RECORD_AUDIO,POST_NOTIFICATIONS,SEND_SMS,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,FOREGROUND_SERVICE
android.allow_backup = False
android.uses_cleartext_traffic = False
