[app]
title = Rolex AI
package.name = rolexai
package.domain = org.rolexai

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,json,txt,mp3,wav,ogg
source.exclude_dirs = .git,.github,__pycache__,.buildozer,tests,tools
source.exclude_exts = pyc,pyo

version = 3.0.2

requirements = python3,kivy==2.3.1,charset-normalizer==2.1.1

orientation = portrait
fullscreen = 0

android.api = 34
android.minapi = 24
android.archs = arm64-v8a

android.ndk = 25b

android.permissions = INTERNET,RECORD_AUDIO
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
