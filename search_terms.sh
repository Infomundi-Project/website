#!/bin/bash

grep -R '$2' . --exclude-dir=.venv --exclude-dir=__pycache__
