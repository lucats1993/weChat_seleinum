# coding:utf-8
from weChat import WeChat
from logger import Log

if __name__ == "__main__":
    logging =Log()

    try:
        weChat = WeChat(logging)
        account_id="5742"
        weChat.prepare_chrome(account_id)
        weChat.spider_articles()
    except Exception as e:
        logging.error(e)
    finally:
        weChat.update_to_server()
        weChat.close()
