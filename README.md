A scrapy project for crawling PTT articles  

# Example Usuage
    scrapy crawl ptt -a max_articles=5 -a board='Gossiping' -a max_retry=5  -o output.json

# Available Arguments
**max_articles**: Maximium articles to crawl. *default=5*  
**max_retry**: Maximium retries during the process. *default=5*  
**board**: Which ptt board to crawl. *default='HatePolitics'*