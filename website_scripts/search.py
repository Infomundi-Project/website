import re
from collections import defaultdict
from unidecode import unidecode


def search_text(query, text):
    """
    Search for a multi-word query within a given text and return the relevant snippets.
    """
    def preprocess(text):
        """
        Preprocess the text by lowercasing and removing non-alphanumeric characters.
        """
        text = ' '.join([x for x in text.split(' ') if len(x) >= 3])
        
        text = unidecode(text)
        return re.sub(r'\W+', ' ', text.lower())

    def index_text(text):
        """
        Create an index mapping each word to its positions in the text.
        """
        word_positions = defaultdict(list)
        for pos, word in enumerate(text.split()):
            word_positions[word].append(pos)
        return word_positions

    # Preprocess text and query
    preprocessed_text = preprocess(text)
    preprocessed_query = preprocess(query)

    # Create index from preprocessed text
    word_positions = index_text(preprocessed_text)

    # Search for the preprocessed query in the text
    query_words = preprocessed_query.split()
    query_positions = [word_positions[word] for word in query_words if word in word_positions]

    if not query_positions:
        return []

    results = []
    for start_pos in query_positions[0]:
        if all(start_pos + i in positions for i, positions in enumerate(query_positions[1:], 1)):
            snippet = ' '.join(preprocessed_text.split()[max(0, start_pos-5):start_pos+len(query_words)+5])
            results.append(snippet)

    return results

"""Example usage
text = "This is a sample text to demonstrate the search functionality. "\
       "The search algorithm is designed to handle multiple words in a query efficiently. "\
       "This example uses a simple approach for indexing and searching text."
query = "search algorithm"
search_results = search_text(query, text)

print(search_results)
"""