# PTT Crawler
PTT crawler is a scrapy project for crawling PTT articles and is ready for the deployment on Scrapinghub. The key feature makes it differ from other similiar projects is that some possible complex PTT article patterns are considered (e.g. signature files (簽名檔), edited articles) and some algorithms are applied to deal with important values that are missing in sources (e.g. exact time and date of comments), so that a better data quality can be guaranteed. Note that due to efficiency issue it currently retrieves only articles from yesterday, although with some minor adjustments in the *ptt_spider.py* it is capable to retrieve articles from any date.  

# Example Usuage
Command pattern:  

    scrapy crawl ptt <-a argument=value> <-o outputfile.json>  

Example 1: Crawl 5 articles from PTT Goossiping and dump the data into output.json

    scrapy crawl ptt -a max_articles=5 -a board='Gossiping' -o output.json

Example 2: Crawl 5 articles that title contain 丹丹 from PTT Goossiping and dump the data into output.json  

    scrapy crawl ptt -a max_articles=5 -a board='Gossiping' -a keyword=丹丹 -o output.json

Example 3: Crawl an article from url (https://www.ptt.cc/bbs/WomenTalk/M.1494689998.A.2AA.html) and dump the data into output.json  

    scrapy crawl ptt -a test_url=https://www.ptt.cc/bbs/WomenTalk/M.1494689998.A.2AA.html -o output.json

# Available Arguments
**`max_articles`**: Maximium articles to crawl. *default=5*  
**`max_retry`**: Maximium retries during the process. *default=5*  
**`board`**: PTT board to crawl. *default='HatePolitics'*  
**`keyword`**: If specified, the spider will only retrieve articles that has the given keyword in its title. *optional argument*    
**`test_url`**: If set, only the article in the given url will be crawled and all arguments above will be ignored. This argument is especially helpful when debugging. *optional argument*  
**`get_content`**: If set *False*, content of articles will not be retrieved. This helps to reduce the size of dataset if you are not interested in them. *default=True*  
**`get_comments`**: If set *False*, comments of articles will not be retrieved and article scores will not be calculated. This helps to reduce the size of dataset if you are not interested in them. *default=True*  
  
# TODOs
- implement two arguments *from* and *until* which allow user to specify a querying time range.  
- implement an argument *fields* which allows user to determine desired the data schema

# References
- [Scrapy Cloud + Scrapy 網路爬蟲](https://city.shaform.com/zh/2017/05/13/scrapy-cloud/)
- [Scrapy 1.5 documentation](https://docs.scrapy.org/en/latest/)