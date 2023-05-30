import pandas as pd
import numpy as np
import time
import re
import os
import sys
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import requests
import bs4
from datetime import datetime, timezone, timedelta

os.environ['PATH'] = "/kaggle/working:" + os.environ['PATH']
host_url = "https://www.bbc.co.uk"

if not os.path.isdir('output'):
    os.mkdir('output')

class BBC_Crawler:
    def __init__(self):
        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        self.driver = webdriver.Firefox(options=options)
        self.go(f'{host_url}/news/coronavirus')

    def __del__(self):
        self.driver.quit()

    def kill(self):
        self.driver.quit()

    def go(self, url):
        self.driver.get(url)
        time.sleep(0.5)
        try:
            self.find_element(By.CLASS_NAME, "fc-cta-consent").click()
        except:
            pass
        try:
            self.find_element(By.CLASS_NAME, "signin-dismiss").click()
        except:
            pass
        try:
            self.find_element(By.XPATH, "//button[.='Maybe Later']").click()
        except:
            pass
        time.sleep(0.5)

    def find_element(self, tag, value, order=0):
        elements = self.driver.find_elements(tag, value)
        return (elements[order] if order >= 0 else elements)

    def next_page(self):
        right_div = self.find_element(By.CLASS_NAME, "lx-pagination__controls--right")
        if right_div is None:
            return
        next_icon = right_div.find_element(By.CLASS_NAME, "qa-pagination-next-page")
        if next_icon.tag_name == 'div':
            return
        next_icon.click()
        time.sleep(1)

    def last_page(self):
        right_div = self.find_element(By.CLASS_NAME, "lx-pagination__controls--right")
        if right_div is None:
            return
        next_icon = right_div.find_element(By.CLASS_NAME, "qa-pagination-last-page")
        if next_icon.tag_name == 'div':
            return
        next_icon.click()
        time.sleep(1)

    def previous_page(self):
        left_div = self.find_element(By.CLASS_NAME, "lx-pagination__controls--left")
        if left_div is None:
            return
        previous_icon = left_div.find_element(By.CLASS_NAME, "qa-pagination-previous-page")
        if previous_icon.tag_name == 'div':
            return
        previous_icon.click()
        time.sleep(1)

    def first_page(self):
        left_div = self.find_element(By.CLASS_NAME, "lx-pagination__controls--left")
        if left_div is None:
            return
        previous_icon = left_div.find_element(By.CLASS_NAME, "qa-pagination-first-page")
        if previous_icon.tag_name == 'div':
            return
        previous_icon.click()
        time.sleep(1)

    def parse_timestamp(self, ts_string):
        curr_ts = datetime.now()
        items = ts_string.split(' ')
        if len(items) == 1:
            ts = datetime.strptime(ts_string, "%H:%M")
            return datetime(curr_ts.year, curr_ts.month, curr_ts.day, ts.hour, ts.minute)
        elif len(items) == 3:
            ts = datetime.strptime(ts_string, "%H:%M %d %b")
            return datetime(curr_ts.year, ts.month, ts.day, ts.hour, ts.minute)
        elif len(items) == 4:
            return datetime.strptime(ts_string, "%H:%M %d %b %Y")
        else:
            return None

    def save_data(self, data):
        if len(data) == 0:
            return
        fname = data[0]['timestamp'].strftime("%Y%m%d_%H%M%S")
        pd.DataFrame(data).to_csv(f"output/{fname}.csv", index=False)
        data.clear()

    def pick_highlighted_item(self, elem):
        cls_names = pd.Series([item.find('a')['class'][0] for item in elem.find_all('li')])
        cls_names.drop_duplicates(keep=False, inplace=True)
        if len(cls_names) == 0:
            return None
        elif len(cls_names) == 1:
            val = cls_names.iloc[0]
            return elem.find('a', class_=val).text
        else:
            raise Exception("Unexpected submenu")

    def fetch_recent_timestamp(self):
        fnames = os.listdir("output")
        if (len(fnames) > 0):
            raise Exception("Run historical download first followed by live refresh")
        latest_fname = sorted(fnames)[-1]
        latest_ts = datetime.strptime(latest_fname.split('.')[0], "%Y%m%d_%H%M%S")
        return latest_ts

    def fetch_further_info(self, url):
        res = requests.get(url)
        doc = bs4.BeautifulSoup(res.text, 'html.parser')
        if doc.find('nav', class_="orbit-header-links"):
            return None
        
        nav_menus = doc.find_all('nav')[1].find_all('div', recursive=False)
        menu = self.pick_highlighted_item(nav_menus[0].find('div', {'id':'product-navigation-menu'}))
        try:
            submenu = self.pick_highlighted_item(nav_menus[1]) if (len(nav_menus) > 1) else None
        except Exception as e:
            print(f"{str(e)} : {url}")
            submenu = None

        elem = doc.find('article').find('div', {'data-component': 'topic-list'})
        topics = [item.text for item in elem.find_all('li')] if elem else []

        images = []
        images.extend([item.img['src'] for item in doc.find('article').find_all('div', {'data-component': 'image-block'}) if item.img])
        images.extend([item.find('img',recursive=False)['src'] for item in doc.find('article').find_all('div', {'data-component': 'include-block'}) if item.find('img',recursive=False)])

        text = ""
        for x in doc.find('article').find_all('div', {'data-component': 'text-block'}):
            text += x.text + "\n"
        return {'menu':menu, 'submenu':submenu, 'images':images, 'topics':topics, 'text': text}

    def crawl_article(self, article):
        extracted_info = {}
        extracted_info.setdefault('timestamp', self.parse_timestamp(article.time.find_all('span')[1].text))
        header = article.find('h3', {'class': 'lx-stream-post__header-title'})
        extracted_info.setdefault('title', header.text)
        authors = article.find('p', {'class': 'lx-stream-post__contributor-name'})
        extracted_info.setdefault('authors', re.sub(r" (&|and)", ",", authors.text.replace("By ","")) if authors else None)
        role = article.find('p', {'class': 'lx-stream-post__contributor-description'})
        extracted_info.setdefault('role', role.text if role else None)
        link_tag = header.find('a')

        if link_tag:
            if article.find('figure', {'class': ['lx-stream-post-body__media-asset', 'lx-media-asset']}):
                news_link =  host_url + header.find('a')['href'].replace("news","news/av")
            else:
                news_link = host_url + header.find('a')['href']

            if article.find('p', class_ = 'lx-stream-related-story--summary'):
                extracted_info.setdefault('subtitle', article.find('p', class_ = 'lx-stream-related-story--summary').text)
                extracted_info.setdefault('video', None)
            elif article.find('p', class_ = 'lx-media-asset-summary'):
                extracted_info.setdefault('subtitle', article.find('p', class_ = 'lx-media-asset-summary').text)
                extracted_info.setdefault('video', re.sub(r"news/.*-", "news/av-embeds/", news_link))
            else:
                extracted_info.setdefault('subtitle', None)
                extracted_info.setdefault('video', None)

            details = self.fetch_further_info(news_link)
            if not details:
                return None
            extracted_info.setdefault('menu', details['menu'])
            extracted_info.setdefault('submenu', details['submenu'])
            extracted_info.setdefault('images', details['images'])
            extracted_info.setdefault('topics', details['topics'])
            extracted_info.setdefault('text', details['text'])

        else:
            extracted_info.setdefault('subtitle', None)
            extracted_info.setdefault('video', None)
            extracted_info.setdefault('menu', None)
            extracted_info.setdefault('submenu', None)
            extracted_info.setdefault('images', None)
            extracted_info.setdefault('topics', None)

            text = ""
            for x in article.find('div', {'class': 'lx-stream-post-body'}).find_all('p'):
                text += x.text + "\n"
            extracted_info.setdefault('text', text)

        return extracted_info

    def parse_news_data(self, ndays=0):
        # If ndays = 0, the function works in live mode
        # If ndays > 0, the function works in historical mode
        list_of_scraped_articles = []
        end = datetime.now()
        crawl = True
        if ndays:
            history_start = end - timedelta(days=ndays)
        else:
            try:
                history_start = self.fetch_recent_timestamp()
            except Exception as e:
                print(str(e))
                return

        while(crawl):
            parsed_doc = bs4.BeautifulSoup(self.driver.page_source, 'html.parser')
            target_div = parsed_doc.find('div', {'id': 'lx-stream'})
            articles = target_div.find_all('article', {'class': 'lx-stream-post'}) if target_div else []
            for article in articles:
                info = self.crawl_article(article)
                if not info:
                    continue
                ts = info['timestamp']
                if ts <= history_start:
                    self.save_data(list_of_scraped_articles)
                    crawl = False
                    break

                if (datetime(ts.year, ts.month, ts.day) - datetime(end.year, end.month, end.day)).days < 0:
                    end = ts
                    self.save_data(list_of_scraped_articles)

                if ts <= end:
                    list_of_scraped_articles.append(info)

            if crawl:
                self.next_page()
        
	self.first_page()

bug = BBC_Crawler()
bug.parse_news_data(120)