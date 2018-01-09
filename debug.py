#!/usr/bin/env python3
from app import app

app.config['APPLICATION_ROOT'] = ''

app.run(debug=True)
