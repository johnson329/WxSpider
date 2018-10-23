import requests, time, random, redis, re, json,pymysql
from urllib.parse import quote
from wx_oper import wx_click_loop


class wx_crawler(object):
    def __init__(self):
        self.r=redis.Redis()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36 MicroMessenger/6.5.2.501 NetType/WIFI WindowsWechat QBCore/3.43.901.400 QQBrowser/9.0.2524.400',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        self.conn=pymysql.connect(host='47.98.167.151', port=3306,
                                              user='root', password='js', db='Weixin')
    def get_index_info(self, offset,biz,uin,key):
        url = "https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz={}" \
              "&f=json&offset={}&count=10&is_ok=1&scene=124&uin={}&key={}" \
              "&x5=0&f=json".format(
            biz,offset,uin,key)
        resp = requests.get(url, headers=self.headers, verify=False)
        resp_eval = eval(resp.text)
        print(resp_eval,"*"*100)
        return resp_eval
    def parse_index_info(self,biz,uin,key,resp_eval):
        '''
        article_msg_per_time是公众每次推送的文章信息集合，info_list_of_articles是一页的文章信息集合
        is_multi为0表示一次推送了多篇文章

        :param resp_eval:
        :return:
        '''
        info_list_of_articles = eval(resp_eval['general_msg_list'])['list']
        index_info = []

        for article_msg_per_time in info_list_of_articles:
            timestamp = article_msg_per_time['comm_msg_info']['datetime']
            if 'app_msg_ext_info' in article_msg_per_time:
                pre_article_info = article_msg_per_time['app_msg_ext_info']
                title, digest, content_url = pre_article_info['title'], pre_article_info['digest'], \
                                             pre_article_info['content_url'].replace("\\", "")
                print(title)
                if self.r.sismember("weixin:crawled_item",content_url):
                    print("url is in redis",content_url,title)
                    break
                read_num,like_num=self.get_like_read(biz,uin,key,content_url,title)
                time.sleep(10)

                is_multi=pre_article_info['is_multi']
                index_info.append((title, digest,timestamp,content_url,read_num,like_num))
                if is_multi:
                    for pre_article_info in pre_article_info['multi_app_msg_item_list']:
                        title, digest, content_url = pre_article_info['title'], pre_article_info['digest'], \
                                                     pre_article_info['content_url'].replace("\\", "")
                        read_num, like_num = self.get_like_read(biz, uin, key, content_url, title)
                        time.sleep(10)
                        index_info.append((title, digest,timestamp,content_url,read_num,like_num))
                        print(title)
        print(index_info)
        return index_info
    def insert2redis(self,index_info,wx_code,offset):
        pipe = self.r.pipeline()
        pipe.multi()
        url_list=[]
        for i in index_info:
            url_list.append(i[3])
        pipe.sadd("weixin:crawled_item",*url_list)
        pipe.set("wx_code_offset:"+wx_code,offset+10)
        pipe.execute()
    def get_idx(self, content_url):
        idx_pattern = re.compile("idx=(.*?)&")
        idx = re.search(idx_pattern, content_url).group(1)
        return idx
    def get_mid_sn_chksm(self, content_url):
        print(content_url)
        mid_sn_chksm_pattern = re.compile('mid=(.*?)&.*?sn=(.*?)&.*?chksm=(.*?)&')
        mid, sn, chksm = re.search(mid_sn_chksm_pattern, content_url).groups()
        return mid, sn, chksm
    def get_comment_id_key(self, article_text):
        comment_id_pattern = re.compile('comment_id = "(.*?)"', re.S)
        key_pattern = re.compile('window.key =.*?"(.*?)"', re.S)
        comment_id = re.search(comment_id_pattern, article_text).group(1)
        key = re.search(key_pattern, article_text).group(1)
        return comment_id, key

    def get_article(self, idx, mid_sn_chksm):
        mid, sn, chksm = mid_sn_chksm
        url = 'http://mp.weixin.qq.com/s?__biz={}&mid={}&idx={}&sn={}&chksm={}&scene=38&key' \
              '={}&ascene=7&uin={}&devicetype=Windows+10&version=6206042f&' \
              'lang=zh_CN&pass_ticket={}&winzoom=1'.format(self.biz, mid, idx, sn, chksm, self.key, self.uin,
                                                           self.pass_ticket)
        headers = self.headers.copy()
        headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        resp = requests.get(url, headers=headers, verify=False)
        return resp.text

    def get_like_read(self, biz,uin,key,content_url,title):
        mid_sn_chksm=self.get_mid_sn_chksm(content_url)
        idx=self.get_idx(content_url)
        mid, sn = mid_sn_chksm[:-1]
        title_encode = quote(title)
        # comment_id, key = self.get_comment_id_key(article_text)
        print("args of like_num", mid_sn_chksm, title_encode, key)
        post_params = "__biz={}&appmsg_type=9&mid={}&sn={}&idx={}&scene=38&" \
                      "title={}&is_only_read=1".format(biz, mid,sn, idx, title_encode)
        url = "http://mp.weixin.qq.com/mp/getappmsgext?uin={}&key={}&wxtoken=777".format(uin, key)

        resp_str = requests.post(url, headers=self.headers, data=post_params, verify=False)
        print(resp_str.text)
        read_num = json.loads(resp_str.text)['appmsgstat']['read_num']
        like_num = json.loads(resp_str.text)['appmsgstat']['like_num']
        return read_num, like_num


    def save2mysql(self, params):
        sql = 'INSERT INTO `articles`(`title`, `digest`, `timestamp`,' \
              ' `url`, `read_num`, `like_num`) VALUES(%s,%s,%s,%s,%s,%s)'
        with self.conn.cursor() as cur:
            cur.executemany(sql, params)
        self.conn.commit()
    def get_access_args(self,wx_code):
        wx_click_loop(wx_code)
        biz, uin, key = eval(self.r.blpop("wx_key")[1])
        offset = self.r.get("wx_code_offset:"+wx_code)
        if not offset:
            offset = 0
        else:
            offset = eval(offset)
        return biz,uin,key,offset


    def main(self):
        wx_code_set=self.r.smembers("wx_code")
        for wx_code in wx_code_set:
            wx_code=wx_code.decode()
            biz, uin, key,offset = self.get_access_args(wx_code)

            print(biz,offset)
            while True:
                index_info = self.get_index_info(offset,biz,uin,key)
                try:
                    msg_count = index_info["msg_count"]
                except:
                    print("fuck wx_key out of date")
                    biz, uin, key,offset=self.get_access_args(wx_code)
                else:
                    pre_article_info_list = self.parse_index_info(biz,uin,key,index_info)
                    if not pre_article_info_list:
                        print("no new")
                        break

                    self.save2mysql(pre_article_info_list)
                    try:
                        self.insert2redis(pre_article_info_list,wx_code,offset)
                    except KeyboardInterrupt:
                        self.insert2redis(pre_article_info_list, wx_code, offset)

                    # self.insert2redis(pre_article_info_list,wx_code,biz,offset)

                    if msg_count < 10:
                        self.r.set("biz:"+biz,0)
                        break
                    offset += 10
if __name__ == '__main__':
    wc = wx_crawler()
    wc.main()
