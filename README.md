# Infomundi
InfoMundi utilizes various global media channels to cover international news, developing a community dedicated to staying well-informed about global affairs.

This is the repository that holds all the necessary code and assets for running InfoMundi.

## Clone
`git clone git@github.com:Infomundi-Project/website.git`

## Configuration and Start
Just run `setup.sh` and fill in the required information.

Crontab to automate the cache generation process: `0 */12 * * * /var/www/infomundi/.venv/bin/python /var/www/infomundi/create_cache.py > /var/www/infomundi/logs/cache.log`