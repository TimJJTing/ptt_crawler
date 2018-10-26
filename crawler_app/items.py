# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html

import scrapy
class ArticleItem(scrapy.Item):
    # define the fields for your item here like:
    title = scrapy.Field()
    author = scrapy.Field()
    publish_dt = scrapy.Field()
    #content = scrapy.Field()
    board = scrapy.Field()
    ip = scrapy.Field()
    comments = scrapy.Field()
    a_id = scrapy.Field()
    t_id = scrapy.Field()
    url = scrapy.Field()
    score = scrapy.Field()
