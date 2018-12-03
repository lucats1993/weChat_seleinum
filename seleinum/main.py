# coding:utf-8
from weChat import WeChat
from logger import Log
import configparser

if __name__ == "__main__":
    logging =Log()
    conf = configparser.ConfigParser()
    conf.read('config.ini')
    username =conf.get('login','username')
    password =conf.get('login','password')
    try:
        weChat = WeChat(logging)
        weChat.prepare((username,password))
        result = weChat.spider_articles(accs)
        if result.get('is_success'):
            logging.info("已爬取全部%d公众号"%len(accs))
        else:
            logging.error("爬取失败，爬取至%d公众号"%result.get('index'))
    except Exception as e:
        logging.error(e)
    finally:
        weChat.close()
