#!/bin/bash
python bot.py
gunicorn -w 4 -b 0.0.0.0:10000 bot:app
