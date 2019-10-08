#!/usr/bin/env bash
# Run single threaded server with debugger & reloading enabled.
export FLASK_APP=cubedash
export FLASK_DEBUG=1
export PYTHONPATH=${PYTHONPATH}:`pwd`

flask run -p 5000
