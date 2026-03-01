[app]
title = NexusVision
package.name = nexusvision
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv
version = 0.1
requirements = python3,kivy,requests
orientation = portrait
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE

[buildozer]
log_level = 2
warn_on_root = 0

[app:android]
# (optional) Add any p4a recipes here
