import re, os, random
from collections import Counter
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from langdetect import detect

from website_scripts import json_util, config

tags = {}
STORIES_MAXIMUM = 500


def preprocess_text(text, lang='en'):
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


def process_articles(news_data: list, cache_category: str):
    """Process and tag articles"""
    tags[cache_category] = []
    for title, description in news_data:
        # Detect the language of the article
        try:
            lang = detect(title + " " + description)
        except Exception:
            lang = 'en'  # Default to English if language detection fails

        # Tokenize and preprocess the title and description
        words = preprocess_text(title, lang) + preprocess_text(description, lang)

        # Count word frequency
        word_counts = Counter(words)

        # Select top N words as tags (adjust N as needed)
        N = 3
        tags[cache_category].extend([word for word, count in word_counts.most_common(N)])

    print(f'[+] Got total of {len(tags[cache_category])} tags for {cache_category} (language: {lang})')


cache_files = os.listdir(config.CACHE_PATH)
random.shuffle(cache_files)

# cache_files = ['br_technology.json'] # DEBUG

for cache_file in cache_files:
    cache = json_util.read_json(f"{config.CACHE_PATH}/{cache_file.replace('.json', '')}")

    news_data = []
    for story in cache['stories'][:STORIES_MAXIMUM]:
        news_data.append( (story['title'], story['description']) )

    cache_category = cache_file.replace('.json', '')
    process_articles(news_data, cache_category)


for cache_file in cache_files:
    cache = json_util.read_json(f"{config.CACHE_PATH}/{cache_file.replace('.json', '')}")
    
    cache_category = cache_file.replace('.json', '')
    country_tags = tags[cache_category]
    
    # We count again the most common tags and assign the most common of the most common
    word_counts = Counter(country_tags)

    N = 5
    tags[cache_category] = [word for word, count in word_counts.most_common(N)]
    cache['best_tags'] = tags[cache_category]

    print(f'[+] Best tags for {cache_category}: {tags[cache_category]}')
    
    for story in cache['stories'][:STORIES_MAXIMUM]:
        story['tags'] = []
        for tag in tags[cache_category]:
            if ( tag in story['title'].lower() or tag in story['description'].lower() ) and tag not in story['tags']:
                story['tags'].append(tag)

    json_util.write_json(cache, f"{config.CACHE_PATH}/{cache_file.replace('.json', '')}")

print("\n\n[+] Finished associating tags to the news!")
