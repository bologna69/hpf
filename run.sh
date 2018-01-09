#!/usr/bin/env sh
uwsgi --socket 127.0.0.1:6000 --manage-script-name --enable-threads --thunder-lock --callable app --file hpf.py
