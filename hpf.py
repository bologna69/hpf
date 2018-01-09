#!/usr/bin/env python3
from app import app
#app.config['APPLICATION_ROOT'] = '/hpf'
app.config['APPLICATION_ROOT'] = ''

if __name__ == "__main__":
    app.run()
