from website_scripts import json_util, models, extensions
from sqlalchemy import and_

from app import app


def main():
	count_file_path = '/var/www/infomundi/data/json/website/page_count'
	page_count = json_util.read_json(count_file_path)

	with app.app_context():
		session = extensions.db.session
		
		categories = [x.category_id for x in session.query(models.Category).all()]
		for category in categories:
			print(f'[~] Obtaining data for {category}')
			total = models.Story.query.filter(
				and_(
            		models.Story.category_id == category,
            		models.Story.media_content_url.contains('bucket.infomundi.net')
        		)).count()
			page_count[category] = total
			print(f'[+] Total of {total} records for {category}')

	json_util.write_json(page_count, count_file_path)


if __name__ == '__main__':
	main()