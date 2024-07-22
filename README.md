# Infomundi
InfoMundi utilizes various global media channels to cover international news, developing a community dedicated to staying well-informed about global affairs.

This is the repository that holds all the necessary code and assets for running InfoMundi.

## Clone
`git clone git@github.com:Infomundi-Project/website.git`

## Configuration


### Crontabs

#### root
```
0 0 */5 * * /root/venv/bin/python /root/backup.py
```

#### web user
```
0 */6 * * * /var/www/infomundi/.venv/bin/python /var/www/infomundi/create_cache.py > /var/www/infomundi/logs/cache.log
0 */2 * * * /var/www/infomundi/.venv/bin/python /var/www/infomundi/collect_world_data.py > /var/www/infomundi/logs/world_data.log
10 */6 * * * /var/www/infomundi/.venv/bin/python /var/www/infomundi/search_images.py > /var/www/infomundi/logs/search_images.log
15 */2 * * * /var/www/infomundi/.venv/bin/python /var/www/infomundi/get_statistics.py
```
