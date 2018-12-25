# -*- coding: utf-8 -*-
# ./crawler_app/spiders/ptt_spider.py
# Jie-Ting Jiang
import re
from datetime import datetime, timedelta
import pytz
import scrapy
from scrapy.http import FormRequest
from crawler_app.items import ArticleItem

class PTTSpider(scrapy.Spider):
    """
    Spider Class
    """
    # TODO: use binary search to retrieve articles if datetime is specified as a search condition

    name = 'ptt'
    allowed_domains = ['ptt.cc']

    # get yesterday's date
    tz = pytz.timezone('Asia/Taipei')
    taipei_now = datetime.now(tz)
    _yesterday = (taipei_now - timedelta(1)).strftime('%m/%d')
    # mmdd -> (m)mdd
    if _yesterday[0] == '0':
        _yesterday = _yesterday.replace('0', ' ', 1)

    re_url_pattern = r"^https://www\.ptt\.cc/bbs/(?P<board>[a-z0-9A-Z_-]{,12})/(?P<a_id>M\.\d{10}\.A\.\w{3})\.html$"
    re_push_ip_datetime_pattern = r"""
        ^                                                                       # beginning
        (?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})?\s?                          # ip
        (?P<month>\d{2})\/(?P<day>\d{2})\s?                                     # month and day
        (?P<time>\d{2}:\d{2})?                                                  # time
        $                                                                       # ending
        """
    re_ptt_article_page_pattern = r"""
        (?P<head1>^<!DOCTYPE\shtml>\s*<html>\s*)                                # beginning
        <head>.*?</head>\s*
        (?P<head2><body>\s*)
        (?P<main_content>.*?)                                                   # 1st section, main content
        (?P<signature_file>\n-+\n.*)?                                           # sig. file & sep. line
        \n--\n
        <span\sclass=\"f2\">※\s發信站:\s批踢踢實業坊\(ptt\.cc\),\s來自:\s           # meta header
        (?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})                              # 3rd section, ip
        \n</span><span\sclass=\"f2\">※\s文章網址:\s<a\shref=\"                   # more meta
        (?P<url>https://www\.ptt\.cc/bbs/(?P<board>[a-z0-9A-Z_-]{,12})/(?P<a_id>M\.\d{10}\.A\.\w{3})\.html) # 4, 5, 6th section, article url
        \"\s*target=\"_blank\"\s*rel=\"nofollow\">(?P=url)</a>\n</span>         # more meta
        (?P<edited>\n<span\sclass=\"f2\">※\s編輯:\s\w*\s                         # more meta,
        \(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\),                          # 7th section, if the author edited the article before the first comment
        \s\d{2}/\d{2}/\d{4}\s\d{2}:\d{2}:\d{2}\n</span>)?
        (?P<comments>.*)                                                        # 8th section, comments
        (?P<tail></body>\s*</html>\s*$)                                        # ending
        """

    def __init__(self, board='HatePolitics', max_articles=10, max_retry=5, get_content=True, get_comments=True, *args, **kwargs):
        """
        Constructor
        """
        super(PTTSpider, self).__init__(*args, **kwargs)

        self.test_url = None
        if 'test_url' in kwargs:
            self.test_url = kwargs['test_url']
        # Specify start_urls
        start_url = ""
        # if a keyword is given
        if 'keyword' in kwargs:
            start_url = "https://www.ptt.cc/bbs/%s/search?q=%s"%(board, kwargs['keyword'])
        else:
            start_url = 'https://www.ptt.cc/bbs/%s/index.html'%board
        self.start_urls = [start_url]

        self._retries = 0 # private, retires than have made
        self._list_page = 0 # private, pages of article list that have crawled
        self._articles = 0  # private, articles that have crawled

        self.max_articles = int(max_articles)
        self.max_retry = int(max_retry)
        self.get_content = True
        if get_content == 'False' or not get_content:
            self.get_content = False
            self.logger.info('get_content=False is specified, no article content will be retrieved')
        self.get_comments = True
        if get_comments == 'False' or not get_comments:
            self.get_comments = False
            self.logger.info('get_comments=False is specified, no comment will be retrieved and article score will not be calculated')

    def start_requests(self):
        """
        url switcher
        """
        # normal case
        if not self.test_url:
            for url in self.start_urls:
                yield scrapy.Request(url, callback=self.parse_ptt_article_list)
        # if a certain test url is specified, crawl it only (designed for debugging)
        else:
            self.logger.info('test_url specified, retrieving from %s'%self.test_url)
            yield scrapy.Request(self.test_url, callback=self.parse_article)

    def parse_ptt_article_list(self, response):
        """
        parser for the ptt article list
        """
        # if retried too many times
        if self._retries > self.max_retry:
            self.logger.info('MAX RETRY reached, shutting down spider')

        # if asked to log in
        elif response.xpath('//div[@class="over18-notice"]'):
            self._retries += 1
            self.logger.info('retry {} times...'.format(self._retries))
            # answer the question and callback to parse
            yield FormRequest.from_response(response,
                                            formdata={'yes': 'yes'},
                                            callback=self.parse_ptt_article_list,
                                            dont_filter=True)
        # we are in, turn pages and crawl
        else:
            self.logger.info('Got successful response from {}'.format(response.url))

            # the nth page of article list
            self._list_page += 1
            # count of expired articles (from the day before yesterday or earlier)
            expired_articles = 0

            # get next page's url
            next_page = response.xpath(
                '//div[@id="action-bar-container"]//a[contains(text(), "上頁")]/@href'
            )

            # make a list for this page
            for title in response.css('.r-ent'):
                # limit reached
                if self._articles >= self.max_articles:
                    self.logger.info('max_articles reached')
                    break
                #print(title.css('div.meta > div.date::text').extract_first())
                # only extract titles within the scope of the given time peroid; yesterday
                elif title.css('div.meta > div.date::text').extract_first() == self._yesterday:
                    # one article to crawl
                    self._articles += 1
                    # extract the url
                    url = response.urljoin(title.css('div.title > a::attr(href)').extract_first())
                    self.logger.info('Found a targrt article: '+url)
                    # crawl the content of the title
                    yield scrapy.Request(
                        url,
                        callback=self.parse_article
                    )
                # ignore today's article
                elif title.css('div.meta > div.date::text').extract_first() > self._yesterday:
                    continue
                # expired article
                else:
                    expired_articles += 1

            # yesterday's articles all crawled
            if self._list_page > 1 and expired_articles > 1:
                self.logger.info('yesterday\'s articles all crawled')
            # if there's next page, turn to the next page and continue crawling
            elif next_page and self._articles < self.max_articles:
                url = response.urljoin(next_page.extract_first())
                self.logger.info('turning into page %s', format(url))
                expired_articles = 0
                yield scrapy.Request(url, self.parse_ptt_article_list)
            # if no next page
            else:
                self.logger.info('no next page or max_articles reached, finshing process.')


    # parse ptt article
    def parse_article(self, response):
        """
        parser for the ptt articles
        """
        if response.xpath('//div[@class="over18-notice"]'):
            # answer the question and callback to parse
            yield FormRequest.from_response(response,
                                            formdata={'yes': 'yes'},
                                            callback=self.parse_article,
                                            dont_filter=True)
        else:
            # extract all contents including tags in a string
            # decode response.body from ascii to unicode
            body = response.body.decode()
            regexmatch = re.match(
                self.re_ptt_article_page_pattern,
                body,
                re.S|re.X
            ) # make "." also match \n and allow verbose regex
            # if the article is not a standard pattern
            if regexmatch is None:
                self.logger.error('pattern not match at ' + response.url)

            else:
                self.logger.info('crawling ' + response.url)
                # find author's ip
                ip = regexmatch.group('ip')
                # remove the signature file and <head></head> from original data
                n_body = re.sub(
                    self.re_ptt_article_page_pattern,
                    r"\g<head1>\g<head2>\g<main_content>\g<comments>\g<tail>",
                    body,
                    0,
                    re.S|re.X
                ) # make "." also match \n and allow verbose regex
                n_response = response.replace(body=n_body)
                article = ArticleItem()
                # extract user's ip
                article['ip'] = ip
                # extract article title
                article['title'] = n_response.xpath(
                    '//div[@class="article-metaline"]/span[text()="標題"]/following-sibling::span[1]/text()'
                ).extract_first().strip()
                # extract author, discard nickname
                article['author'] = n_response.xpath('//div[@class="article-metaline"]/span[text()="作者"]/following-sibling::span[1]/text()').extract_first().split(' ')[0]
                # extract article date time
                datetime_str = n_response.xpath(
                    '//div[@class="article-metaline"]/span[text()="時間"]/following-sibling::span[1]/text()'
                ).extract_first()
                publish_dt = datetime.strptime(datetime_str+' +0800', '%a %b %d %H:%M:%S %Y %z')
                # save a date pointer for later use
                date_ptr = publish_dt
                # publish date
                article['publish_dt'] = datetime.strftime(publish_dt, '%Y-%m-%d %H:%M:%S')
                if self.get_content:
                    # convert content from a list of strings to a single string
                    content = str.join(
                        '\n',
                        n_response.xpath('//div[@id="main-content"]/text()').extract()
                    )
                    article['content'] = content.strip()
                # extract article url
                article['url'] = response.url
                url_groups = re.search(
                    self.re_url_pattern,
                    response.url
                )
                # board name
                article['board'] = url_groups.group('board')
                # article id
                article['a_id'] = url_groups.group('a_id')

                if self.get_comments:
                    total_score = 0
                    article['comments'] = []
                    # for each comment in comments
                    for floor, cm in enumerate(n_response.xpath('//div[@class="push"]'), start=1):
                        push_ipdatetime_str = cm.css('span.push-ipdatetime::text').extract_first().strip()
                        # matches re_push_ip_datetime_pattern
                        # re.match()?
                        push_ipdatetime_str_groups = re.search(
                            self.re_push_ip_datetime_pattern,
                            push_ipdatetime_str,
                            re.S|re.X
                        )
                        try:
                            #if push_ipdatetime_str_groups.group(1) is not None:
                            push_ip = push_ipdatetime_str_groups.group('ip')
                            push_month_str = push_ipdatetime_str_groups.group('month')
                            push_day_str = push_ipdatetime_str_groups.group('day')
                            push_time_str = push_ipdatetime_str_groups.group('time')
                            push_year = date_ptr.year
                            # if date_of_this_push < date_pointer, year++
                            # TODO: consider if a signature file causes the failure of this logic
                            if int(push_month_str) < date_ptr.month and int(push_day_str) < date_ptr.day:
                                push_year = date_ptr.year + 1
                            push_dt = datetime.strptime(
                                str(push_year)+' '+push_month_str+' '+push_day_str+' '+push_time_str+' +0800',
                                '%Y %m %d %H:%M %z'
                            )
                            # fetch date_pointer
                            date_ptr = push_dt

                            # real comments
                            push_tag = cm.css('span.push-tag::text').extract_first()
                            push_user = cm.css('span.push-userid::text').extract_first()

                            # content starts from the third char (': blabla')
                            push_content = cm.css('span.push-content::text').extract_first()[2:]

                            if '推' in push_tag:
                                push_score = 1
                            elif '噓' in push_tag:
                                push_score = -1
                            else:
                                push_score = 0
                            total_score += push_score

                            comment = {}
                            comment['floor'] = floor
                            comment['commentor'] = push_user
                            comment['score'] = push_score
                            comment['content'] = push_content.strip()
                            comment['dt'] = datetime.strftime(push_dt, '%Y-%m-%d %H:%M:%S')
                            if push_ip:
                                comment['ip'] = push_ip

                            # append item into the item list
                            article['comments'].append(comment)

                        # if an unhandable AttributeError occurs
                        except AttributeError:
                            self.logger.error('sth goes wrong at the '+ str(floor) + ' floor at '+ response.url)
                    # return the items to the pipeline (one article one return)
                    article['score'] = total_score
                #print(article)
                yield article
