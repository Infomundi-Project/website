source /root/.venv/bin/activate
pip install --upgrade $(pip list --outdated | awk '{print $1}' | tail -n +3 | grep -v cachelib)
