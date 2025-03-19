SPECIAL_CHARACTERS = ('^', '*', '{', '}', '[', ']', '|', '\\', '<', '>')

EU_COUNTRIES = ('austria', 'belgium', 'bulgaria', 'croatia', 'cyprus', 'czech republic', 'denmark', 'estonia', 'finland', 'france', 'germany', 'greece', 'hungary', 'ireland', 'italy', 'latvia', 'lithuania', 'luxembourg', 'malta', 'netherlands', 'poland', 'portugal', 'romania', 'slovakia', 'slovenia', 'spain', 'sweden')

USER_AGENTS = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3", "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:58.0) Gecko/20100101 Firefox/58.0", "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:58.0) Gecko/20100101 Firefox/58.0", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:58.0) Gecko/20100101 Firefox/58.0", "Opera/9.80 (Windows NT 6.2; Win64; x64) Presto/2.12.388 Version/12.18", "Opera/9.80 (Windows NT 6.1; Win64; x64) Presto/2.12.388 Version/12.18", "Opera/9.80 (Macintosh; Intel Mac OS X 10.12.6) Presto/2.12.388 Version/12.18", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

IMAGE_EXTENSIONS = ('png', 'jpg', 'jpeg', 'webp', 'avif')

RSS_ENDPOINTS = (
    "/rss",
    "/feed",
    "/rss.xml",
    "/feed.xml",
    "/atom.xml",
    "/rss/feed",
    "/blog/rss",
    "/blog/feed",
    "/news/rss",
    "/news/feed",
    
    # WordPress
    "/wp-feed.php",
    "/wp-rss.php",
    "/wp-rss2.php",
    "/wp-atom.php",
    
    # Drupal
    "/rss.xml",
    "/feeds/rss.xml",
    
    # Joomla
    "/index.php?format=feed&type=rss",
    "/index.php?format=feed&type=atom",
    
    # Magento
    "/rss/catalog",
    "/rss/order",
)
