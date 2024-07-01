import re
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from collections import Counter
from langdetect import detect
from sys import exit

from website_scripts import json_util, config, models, extensions
from app import app

with app.app_context():
    session = extensions.db.session
    categories = session.query(models.Category).all()


def preprocess_text(text:str, lang:str='en') -> list:
    """Preprocess text: remove punctuation, lowercase, tokenize, remove stopwords"""
    text = re.sub(r'\W', ' ', text)  # Remove punctuation
    text = text.lower()  # Convert to lowercase
    tokens = word_tokenize(text)  # Tokenize

    # Load stopwords for the detected language
    try:
        lang_stopwords = stopwords.words(lang)
    except OSError:
        lang_stopwords = stopwords.words('english')  # Default to English if the language is not supported

    filtered_words = [word for word in tokens if word not in lang_stopwords and len(word) >= 5]  # Remove stopwords
    return filtered_words


def process_articles(category_id: str):
    with app.app_context():
        # Remove previous tag associations for the category
        existing_associations = session.query(models.CategoryTag).filter_by(category_id=category_id).all()
        for association in existing_associations:
            session.delete(association)
        session.commit()

        stories = session.query(models.Story).filter_by(category_id=category_id).order_by(models.Story.created_at.desc()).limit(1000).all()
        all_tags = []
        
        for story in stories:
            try:
                lang = detect(story.title + " " + story.description)
            except Exception:
                lang = 'en'

            words = preprocess_text(story.title, lang) + preprocess_text(story.description, lang)
            word_counts = Counter(words)
            N = 5
            top_tags = [word for word, count in word_counts.most_common(N)]
            all_tags.extend(top_tags)

        # Deduplicate and count tags for the category
        category_tags_count = Counter(all_tags)
        best_tags = category_tags_count.most_common(10)  # Adjust the number as necessary
        best_tags_names = [tag for tag, _ in best_tags]

        print(f"Best tags for category {category_id}: {best_tags_names}")

        for tag_name in best_tags_names:
            tag = session.query(models.Tag).filter_by(tag=tag_name).first()
            if not tag:
                tag = models.Tag(tag=tag_name)
                session.add(tag)
                session.flush()

            association_exists = session.query(models.CategoryTag).filter_by(category_id=category_id, tag_id=tag.tag_id).first()
            if not association_exists:
                new_association = models.CategoryTag(category_id=category_id, tag_id=tag.tag_id)
                session.add(new_association)

        session.commit()


if __name__ == '__main__':
    with app.app_context():
        categories = session.query(models.Category).all()
        categories = ['br_general'] # DEBUG
        for category in categories:
            #process_articles(category.category_id)
            process_articles(category) # DEBUG