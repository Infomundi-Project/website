#!/bin/bash

grep -R '$2' . --exclude-dir=backups --exclude-dir=.git --exclude-dir=.venv --exclude-dir=__pycache__
