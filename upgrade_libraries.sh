source .venv/bin/activate
pip install --upgrade $(pip list --outdated | awk '{print $1}' | tail -n +3)
