# coding: utf-8

import re
import os
import time
import base64
import pymongo
import requests
import subprocess
import configparser
from hashlib import md5
from selenium import webdriver
from bs4 import BeautifulSoup
"""
note: 需要使用selenium，chrome版本需要与chromedriver版本对应。具体见https://chromedriver.storage.googleapis.com/
"""
class MyException(Exception):
    def __init__(self,message):
        Exception.__init__(self)
        self.message=message

class WeChat():
    def __init__(self,logging):
        self.driver = None
        self.logging = logging
        self.sleep_time =3
        self.date = self.get_date()
        self.to_spider_accounts = self.get_accounts(self.date)

    def prepare_chrome(self,account_id):
        """
        :param account_id: 配置文件中登录账户标识id
        :return:
        """
        self.logging.info('准备工作开始！')
        self.logging.info('新建chrome！')
        self.driver = webdriver.Chrome()
        self.logging.info('开始登录')
        self.logining(account_id)
        self.logging.info('登录成功')
        self.jump_to_article()
        self.logging.info('准备工作结束')
        self.prepare_db()

    def prepare_db(self):
        myclient = pymongo.MongoClient("mongodb://localhost:27017/")
        mydb = myclient["weChat"]
        self.db={
            "account_col":mydb["weChat_account"],
            "media_col": mydb["media"],
            "new_media_col": mydb["media"+self.date],
        }

    def spider_articles(self):
        """
        :return:
        {
            'result':0 or 1 ，1：success 0：faied
            '_id': //结束爬取时的公众号id
            'number'://结束爬取时的公众号编号
        }
        """
        for i, nickinfo in enumerate(self.to_spider_accounts):
            self.logging.info("公众号%d：%s,最近更新时间：%s，爬取开始，" % (i+1, nickinfo.get("weChat_name"), nickinfo.get('last_update_time')))
            self.sleep(i + 1)
            retry_times =1
            res = self.get_info(nickinfo)
            if res.get("error_code") != "001":
                while not res.get("result") and retry_times < 4:
                    self.logging.info("故障,重试第%d次" % retry_times)
                    res = self.get_info(nickinfo)
                    retry_times = retry_times + 1
                if not res.get("result"):
                    self.logging.info("重试%d次，爬取失败，结束程序" % retry_times)
                    break
            else:
                break
            self.db.get("account_col").update({"_id": nickinfo.get('_id')},
                                                  {"$set": {"last_spider_time": self.date}})
            self.recover_search()

    def get_info(self,nickinfo):
        data={"result":False,"error_code":""}
        nickname = nickinfo.get("weChat_name")
        try:
            if self.get_account_info(nickname):
                time.sleep(self.sleep_time)
                result = self.get_articles(nickinfo.get("_id"))
                if result.get("data"):
                    self.db.get("new_media_col").insert_many(result.get("data"))
                    self.db.get("media_col").insert_many(result.get("data"))
                    last_time = result.get("data")[0].get('time').replace("-", "")
                    if (nickinfo.get('last_update_time') != last_time):
                        self.logging.info("发布时间更新至：%s" % last_time)
                        self.db.get("account_col").update({"_id": nickinfo.get('_id')},
                                                          {"$set": {"last_update_time": last_time}})
                    if not result.get("is_exist"):
                        page_num = self.driver.find_elements_by_class_name('page_num')[-1].text.split('/')[-1].lstrip()
                        if page_num:
                            # 点击下一页
                            for _ in range(1, int(page_num)):
                                pagination = self.driver.find_elements_by_class_name('pagination')[1]
                                pagination.find_elements_by_tag_name('a')[2].click()
                                time.sleep(4)
                                res1 = self.get_articles(nickinfo.get("_id"))
                                if res1.get("is_exist"):
                                    break
                else:
                    self.logging.info("此公众号无更新，最近更新时间%s" % nickinfo.get('last_update_time'))
        except MyException as e:
            self.logging.error("%s,请更换账号或者24小时后再试" % e.message)
            data['error_code'] = "001"
        except Exception as e:
            data['error_code'] = "002"
            self.logging.error(e)
        data['result'] = True
        return data


    def get_account_info(self,nickname):
        driver =self.driver
        self.logging.info('休眠%d秒后，输入公众号名称：%s' %(self.sleep_time,nickname))
        time.sleep(self.sleep_time)
        driver.find_element_by_xpath('//*[@id="myform"]/div[3]/div[3]/div[1]/div/span[1]/input').clear()
        driver.find_element_by_xpath('//*[@id="myform"]/div[3]/div[3]/div[1]/div/span[1]/input').send_keys(nickname)
        self.logging.info('休眠%d秒后，点击搜索' %(self.sleep_time))
        time.sleep(self.sleep_time)
        # 点击搜索
        driver.find_element_by_xpath('//*[@id="myform"]/div[3]/div[3]/div[1]/div/span[1]/a[2]').click()
        self.logging.info('休眠%d秒后，查找对应公众号文章' %(self.sleep_time*3))
        time.sleep(self.sleep_time*3)
        # 查找对应公众号 frm_msg_content
        account_nodes = driver.find_elements_by_xpath('//*[@id="myform"]//div[@data-nickname="'+nickname+'"]')
        if account_nodes:
            account_node = account_nodes[0]
            # self.get_account_info(nickname,account_node)
            account_node.find_element_by_xpath('./div[3]/p[2]').click()
            # return self.get_account_detail(account_node)
            return True
        else:
            node = driver.find_element_by_class_name('frm_msg_content')
            if node:
                raise MyException(node.text)
            return None

    def get_articles(self,account_id):
        """
        查找文章信息
        :param account_id: 公众号id
        :return: {is_exist:true or false ,"data":to add db datas}
        data ={
            "_id":url's md5 value,
            'title':article title,
            'url': article url,
            'time': article publish_time,
            'yuan': article key id
            'content':article content
            'tag':article tag
        }
        """
        results ={"is_exist":False}
        data =[]
        # yuan =base64.b64decode(data.get('nick_biz')).decode("utf-8")
        for item in self.driver.find_elements_by_class_name('my_link_item'):
            publish_time =item.text.split('\n')[0]
            url = item.find_element_by_tag_name('a').get_attribute('href').replace("&amp;","&")
            url = re.sub(r'&scene=\d{2}', "", url.replace("&amp;","&"))
            m5 = md5()
            m5.update(url.encode("utf-8"))
            id = m5.hexdigest()
            res =self.db.get("media_col").find_one({"_id": id})
            res1 =self.db.get("new_media_col").find_one({"_id": id})
            if res or res1:
                # logging.info("文章:%s,已存在"  %temp_dict.get('msg_title'))
                results['is_exist'] = True
                break
            else:
                temp_dict = {
                    "_id":id,
                    'title':item.text.split('\n')[1],
                    'url': url,
                    'time': publish_time,
                    'yuan': account_id
                }
                temp_dict.update(self.get_tag(url))
                self.logging.info("新增文章:%s,发布时间%s" % (temp_dict.get('title'), temp_dict.get('time')))
                data.append(temp_dict)
                # new_media_col.insert_one(atticle_data)
                time.sleep(1)
        results['data'] =data
        return results

    def logining(self,account_id):
        """
        处理登录相关工作
        :param account: (username,password)
        :return: None
        """
        conf = configparser.ConfigParser()
        conf.read('config.ini')
        username = conf.get(account_id, 'username')
        password = conf.get(account_id, 'password')
        driver = self.driver
        self.logging.info('打开微信公众号登录页面')
        driver.get('https://mp.weixin.qq.com/')
        driver.maximize_window()
        self.logging.info('休眠%d秒，自动填充帐号密码' %(self.sleep_time))
        time.sleep(self.sleep_time)
        driver.find_element_by_xpath("//*[@id=\"header\"]/div[2]/div/div/form/div[1]/div[1]/div/span/input").clear()
        driver.find_element_by_xpath("//*[@id=\"header\"]/div[2]/div/div/form/div[1]/div[1]/div/span/input").send_keys(
            username)
        driver.find_element_by_xpath("//*[@id=\"header\"]/div[2]/div/div/form/div[1]/div[2]/div/span/input").clear()
        driver.find_element_by_xpath("//*[@id=\"header\"]/div[2]/div/div/form/div[1]/div[2]/div/span/input").send_keys(
            password)
        self.logging.info('休眠%d秒，自动点击登录按钮进行登录' %(self.sleep_time))
        time.sleep(self.sleep_time)
        driver.find_element_by_xpath("//*[@id=\"header\"]/div[2]/div/div/form/div[4]/a").click()
        self.logging.info('休眠40秒，拿手机扫二维码')
        time.sleep(40)

    def jump_to_article(self):
        """
        在微信公共号平台里，跳转至查找文章
        :return: None
        """
        driver = self.driver
        self.logging.info('进入素材管理')
        driver.find_element_by_xpath('//*[@id="menuBar"]/li[4]/ul/li[3]/a/span/span').click()
        self.logging.info('休眠%d秒，新建图文素材' % (self.sleep_time))
        time.sleep(self.sleep_time)
        driver.find_element_by_xpath('//*[@id="js_main"]/div[3]/div[1]/div[2]/div[2]/div/button[1]').click()
        self.logging.info('休眠%d秒，切换到新窗口' %(self.sleep_time))
        time.sleep(self.sleep_time)
        for handle in driver.window_handles:
            if handle != driver.current_window_handle:
                driver.switch_to.window(handle)
        self.logging.info('休眠%d秒，点击超链接' %(self.sleep_time*10))
        time.sleep(self.sleep_time*10)
        driver.find_element_by_xpath('//*[@id="edui23_body"]/div').click()
        self.logging.info('休眠%d秒，点击查找文章' %(self.sleep_time))
        time.sleep(self.sleep_time)
        driver.find_element_by_xpath('//*[@id="myform"]/div[3]/div[1]/div/label[2]').click()

    def get_tag(self,url):
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'}
        response = requests.get(url, headers=headers)
        html = response.content
        html = html.decode('utf-8', 'ignore')
        soup = BeautifulSoup(html, 'lxml')
        pmark = []
        for s in soup('script'):
            s.extract()
        for s in soup('style'):
            s.extract()
        for s in soup('p'):
            pmark.append(s.get_text())
            s.extract()
        text = soup.get_text()
        article_data={
            'content':'\n'.join(pmark),
            'tag':text.strip()
        }
        # article_data['content'] = '\n'.join(pmark)
        # article_data['tag'] = text.strip()
        return article_data

    def recover_search(self):
        """
        在存在公众号时，恢复到搜索状态
        :return:
        """
        self.logging.info('休眠%d秒，恢复到搜索状态' %(self.sleep_time))
        time.sleep(self.sleep_time)
        self.driver.find_element_by_xpath('//*[@id="myform"]/div[3]/div[3]/div[1]/div/span[2]/a').click()

    @staticmethod
    def recover_no_search(self,nickname):
        """
        在不存在公众号时，恢复到搜索状态
        :return:
        """
        self.logging.info('休眠%d秒，恢复到搜索状态' %(self.sleep_time))
        time.sleep(self.sleep_time)
        self.driver.find_element_by_xpath('//*[@id="myform"]/div[3]/div[3]/div[1]/div/span[1]/input').clear()
        self.driver.find_element_by_xpath('//*[@id="myform"]/div[3]/div[3]/div[1]/div/span[1]/input').send_keys(nickname)

    @staticmethod
    def get_account_detail(account_node):
        """
        获取公众号的详细信息
        :param nickname: 公众号名称
        :param account_node: 对应公众号节点
        :return: {"_id":fakeid,"weChat_id": ""}
        """
        fakeid = account_node.get_attribute("data-fakeid")
        fakeid =base64.b64decode(fakeid)
        data = {"_id":fakeid}
        biz_id_text = account_node.find_element_by_xpath('./div[3]/p[2]').text
        results = re.findall(r'[a-zA-Z\d_]{5,}', biz_id_text)
        if results:
            data['weChat_id'] =results[0]
        return data

    def sleep(self,i):
        sleep_time =self.sleep_time*10
        self.logging.info('休眠%d秒' %sleep_time)
        time.sleep(sleep_time)
        if (i % 2 == 0):
            self.logging.info('休眠%d秒' %(sleep_time*2))
            time.sleep(sleep_time*2)
        if (i % 5 == 0):
            self.logging.info('休眠%d秒' %(sleep_time*2))
            time.sleep(sleep_time*2)

    def close(self):
        if self.driver:
            self.driver.quit()

    def get_accounts(self,finish_time,start_time="2018-01-01"):
        """

        :param finish_time: 爬取截止时间 ex：20180101
        :param start_time:  账号更新开始时间 ex：20180101
        :return:
        """
        cursor =self.db.get("account_col").find({"last_update_time":{"$gt":start_time},"last_spider_time":{"$lt":finish_time}})
        for item in cursor.sort("last_update_time",pymongo.DESCENDING):
            yield item

    @staticmethod
    def get_date():
        return time.strftime("%Y%m%d",time.localtime())

    def new_to_old(self):
        for item in self.db.get("new_media_col").find():
            self.db.get("media_col").insert_one(item)

    def update_account(self):
        for item in self.db.get("account_col").find():
            last_update_time =""
            if item.get('last_update_time'):
                last_update_time =item.get('last_update_time').replace("-","")
            self.db.get("account_col").update({"_id": item.get('_id')}, {"$set": {"last_spider_time": "20181202","last_update_time": last_update_time}})

    @staticmethod
    def update_to_server():
        bin_path = r"C:\Program Files\MongoDB\Server\4.0\bin"
        mongo = os.path.join(bin_path, "mongo.exe")
        cmd = '"' + mongo + '" ../script/update.js'
        # return_code = subprocess.call(,shell=True)
        subprocess.call(cmd, shell=True)

#
# if __name__ == "__main__":
#     pass






