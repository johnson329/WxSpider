from  pywinauto import application
import win32api,time,redis

from pykeyboard import PyKeyboard
from pymouse import PyMouse



def wx_click_loop(wx_code):
    app=application.Application()
    #打开应用
    app.start(r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe")
    #连接进程
    app.connect(path=r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe")
    #获取窗口句柄
    wxwindow=app.window(title="微信",class_name="WeChatMainWndForPC")
    wxwindow.maximize()
    #获取鼠标位置
    print(win32api.GetCursorPos())
    m = PyMouse()
    k = PyKeyboard()
    #点击输入框
    m.click(127, 34)
    k.type_string(wx_code)
    time.sleep(1)
    #点击公众号
    m.click(162, 124)
    #点击历史页面
    m.click(1341, 38)
    time.sleep(0.5)
    m.click(1256, 223)
    m.click(1256, 250)



#多公众号，先从redis中读取公众号wx_code然后点击，未完成任务的公众号再进入redis，再读取，再操作