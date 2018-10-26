# -*- coding: utf-8 -*-
# ./crawler_app/spiders/ptt_spider.py
# Jie-Ting Jiang
# TODO: use binary search to retrieve articles if datetime is specified as a search condition
import re
from datetime import datetime, timedelta
import pytz
import scrapy
from scrapy.http import FormRequest
from crawler_app.items import ArticleItem

class PTTSpider(scrapy.Spider):
    name = 'ptt'
    allowed_domains = ['ptt.cc']

    # get yesterday's date
    tz = pytz.timezone('Asia/Taipei')
    taipei_now = datetime.now(tz)
    _yesterday = (taipei_now - timedelta(1)).strftime('%m/%d')
    # mmdd -> (m)mdd
    if _yesterday[0] == '0':
        _yesterday = _yesterday.replace('0', ' ', 1)

    re_url_pattern = r"^https://www\.ptt\.cc/bbs/([a-z0-9A-Z_-]{,12})/(M\.\d{10}\.A\.\w{3})\.html$"
    re_push_ip_datetime_pattern = r"""
        ^                                                                       # beginning
        (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})?\s?                                # ip
        (\d{2})\/(\d{2})\s?                                                     # month and day
        (\d{2}:\d{2})?                                                          # time
        $                                                                       # ending
        """
    re_ptt_article_page_pattern = r"""
        ^                                                                       # beginning
        (.*)                                                                    # 1st section, main content
        --\n                                                                    # sepration line
        (.*)?(\n--\n)?                                                          # signature file and the second sepration line
        <span\sclass=\"f2\">※\s發信站:\s批踢踢實業坊\(ptt\.cc\),\s來自:\s          # meta header
        (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})                                    # 4rd section, ip
        \n</span><span\sclass=\"f2\">※\s文章網址:\s<a\shref=\"                   # more meta
        (https://www\.ptt\.cc/bbs/([a-z0-9A-Z_-]{,12})/(M\.\d{10}\.A\.\w{3})\.html)    # 5, 6, 7th section, article url
        \"\s*target=\"_blank\"\s*rel=\"nofollow\">\5</a>\n</span>               # more meta
        (\n<span\sclass=\"f2\">※\s編輯:\s\w*\s                                   # more meta,
        \(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\),                          # 8th section, if the author edited the article before the first comment
        \s\d{2}/\d{2}/\d{4}\s\d{2}:\d{2}:\d{2}\n</span>)?
        (.*)                                                                    # 9th section, comments
        $                                                                       # ending
        """
    # constructor
    def __init__(self, max_articles=10, max_retry=5, *args, **kwargs):
        #def __init__(self, boards=[], *args, **kwargs):
        #self.start_urls = ['https://www.ptt.cc/bbs/%s/index.html' % board for board in boards]

        super(PTTSpider, self).__init__(*args, **kwargs)
        self.start_urls = [
            #'https://www.ptt.cc/bbs/Gossiping/index.html',
            'https://www.ptt.cc/bbs/HatePolitics/index.html',
        ]

        self._retries = 0 # private, retires than have made
        self._list_page = 0 # private, pages of article list that have crawled
        self._articles = 0  # private, articles that have crawled

        self.max_articles = int(max_articles)
        self.max_retry = int(max_retry)

    # url switcher
    def start_requests(self):
        for url in self.start_urls:
            if url is self.start_urls[0]:
                yield scrapy.Request(url, callback=self.parse_ptt_article_list)

    def parse_ptt_article_list(self, response):
        """
        parser for the ptt article list
        """
        # if retried too many times
        if self._retries > self.max_retry:
            self.logger.info('MAX RETRY reached, shutting down spider')

        # if asked to log in
        elif len(response.xpath('//div[@class="over18-notice"]')) > 0:
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
                    print(url)
                    # crawl the content of the title
                    yield scrapy.Request(
                        url,
                        callback=self.parse_article,
                        meta={'article_no': self._articles}
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
                self.logger.info('follow %s', format(url))
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
            self.logger.info('pattern not match at ' + response.url)

        else:
            ip = regexmatch.group(4)
            # delete the signature file
            n_body = re.sub(
                self.re_ptt_article_page_pattern,
                r"\1\9",
                body,
                0,
                re.S|re.X
            ) # make "." also match \n and allow verbose regex
            n_response = response.replace(body=n_body)

            article = ArticleItem()
            article['ip'] = ip
            # extract article title
            article['title'] = n_response.xpath(
                '//meta[@property="og:title"]/@content'
            ).extract_first()
            # extract article date time
            datetime_str = n_response.xpath(
                '//div[@class="article-metaline"]/span[text()="時間"]/following-sibling::span[1]/text()'
            ).extract_first()
            # remember to add timezone
            publish_dt = datetime.strptime(
                datetime_str+' +0800',
                '%a %b %d %H:%M:%S %Y %z'
            )
            date_ptr = publish_dt
            
            article['url'] = response.url
            url_groups = re.search(
                self.re_url_pattern,
                response.url
            )
            article['board'] = url_groups.group(1)
            # article id
            a_id = url_groups.group(2)
            article['a_id'] = a_id
            article['publish_dt'] = datetime.strftime(publish_dt, '%Y-%m-%d %H:%M:%S')
            total_score = 0
            article['comments'] = []
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
                    push_ip = push_ipdatetime_str_groups.group(1)
                    push_month_str = push_ipdatetime_str_groups.group(2)
                    push_day_str = push_ipdatetime_str_groups.group(3)
                    push_time_str = push_ipdatetime_str_groups.group(4)
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
                    comment['content'] = push_content
                    comment['dt'] = datetime.strftime(push_dt, '%Y-%m-%d %H:%M:%S')
                    comment['ip'] = push_ip

                    # append item into the item list
                    article['comments'].append(comment)

                # if an error occurs
                except AttributeError:
                    self.logger.info('sth goes wrong at the '+ str(floor) + ' floor at '+ response.url)
            # return the items to the pipeline (one article one return)
            article['score'] = total_score
            return article
