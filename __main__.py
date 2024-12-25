import copy
import json
import os
import random
from datetime import datetime, timedelta
import http.client
from apscheduler.schedulers.blocking import BlockingScheduler
import yaml
from wxauto import WeChat
import ssl
import ddddocr


def getCaptcha(conn, ocr):
    conn.request("GET", "/ImgVcode_port")
    # Step 3: 获取响应
    response = conn.getresponse()

    # 检查状态码
    if response.status == 200:
        # Step 4: 读取图片数据（二进制）
        image_data = response.read()

        # Step 5: 将图片保存到本地
        with open("downloaded_image.jpg", "wb") as image_file:
            image_file.write(image_data)
        # print("图片保存成功！")
    else:
        print(f"请求失败，状态码：{response.status}")
    image = open(f'./downloaded_image.jpg', "rb").read()
    result = ocr.classification(image)
    # # 删除文件
    if os.path.exists(f'./downloaded_image.jpg'):  # 确保文件存在
        os.remove(f'./downloaded_image.jpg')  # 删除文件
        # print("downloaded_image.jpg 已删除")
    else:
        print("downloaded_image.jpg 不存在")
    return result


def loginInBatchUser(conn, ocr, user_datas):
    for user_data in user_datas:
        while True:
            result = getCaptcha(conn, ocr)
            # Step 2: 准备请求头和 body
            headers = {
                "Content-Type": "application/json",  # 指定内容类型为 JSON
            }

            body = {
                "name": user_data.get("username"),
                "password": user_data.get("psw"),
                "code": f'{result}'
            }

            json_body = json.dumps(body)

            conn.request("POST", "/login_port", body=json_body, headers=headers)

            response = conn.getresponse()
            if response.status == 200:
                try:
                    response_data = response.read().decode("utf-8")
                    # print(f"状态码: {response.status}")
                    # print(f"响应内容: {response_data}")
                    json_data = json.loads(response_data)  # 将 JSON 字符串解析为字典
                    if json_data.get("code") == 0:
                        data = json_data.get("data", {})
                        # print(data)
                        user_data["token"] = data.get("token")
                        user_data["user_id"] = data.get("user_id")
                        break
                except json.decoder.JSONDecodeError as e:
                    print(f"请求失败，状态码：{response.status}")


def getSiteData(conn, choose_site):
    siteData = {}
    conn.request("GET", "/place/detail_port")
    response = conn.getresponse()
    if response.status == 200:
        response_data = response.read().decode("utf-8")
        json_data = json.loads(response_data)
        data = json_data.get("data", {}).get(choose_site + "场", {})
        book_frequency = int(data.get("book_frequency", 0))
        siteData["book_frequency"] = book_frequency
        today_duration_time, time_duration_tuple = next(iter(data.get("draw_data").items()))
        print(f"当前可选时段数：{book_frequency}" + "当天时段" + today_duration_time)
        siteData["today_duration_time"] = today_duration_time
        temp = {}
        for time_duration, submit_data_raw in time_duration_tuple.items():
            print(f"\n{time_duration}:\n\n{submit_data_raw}")
            temp[time_duration] = submit_data_raw
        siteData["submit_data_raw_tuple"] = temp
    return siteData


def getOrderData(conn, user_datas, drawed_orders: [], choose_site):
    for user_data in user_datas:
        user_id = str(user_data.get("user_id"))
        user_token = str(user_data.get("token"))
        conn.request("GET", f"/order/draworder_port?user_id={user_id}", headers={"token": f"{user_token}"})
        response = conn.getresponse()
        if response.status == 200:
            response_data = response.read().decode("utf-8")
            json_data = json.loads(response_data)
            data = json_data.get("data", {})
            for order in data:
                # 自定义格式化
                date_str = str(order.get("timetable").get("start_time"))
                judge_date = datetime.today()
                if choose_site == "谭兆羽毛球":
                    judge_date = datetime.today() + timedelta(days=1)
                if judge_date.date() == datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").date() and (
                        order.get("status") == 1) and choose_site in str(
                        order.get("place").get("name")):
                    drawed_orders.append({
                        "order_id": order.get("order_id"),
                        "token": user_token,
                        "user_id": user_id,
                        "place": order.get("place").get("name"),
                        "start_time": order.get("timetable").get("start_time"),
                        "end_time": order.get("timetable").get("end_time"),
                        "username": user_data.get("username"),
                        "psw": user_data.get("psw")
                    })
                    user_data["is_invited"] = True


def submitOrder(conn, user_datas, choose_duration,choose_site):
    # 获得场地信息。
    siteData = getSiteData(conn, choose_site)
    for user_data in user_datas:
        durations = list(siteData.get("submit_data_raw_tuple").keys())
        # print("siteData:\n" + str(siteData))
        submitData = siteData.get("submit_data_raw_tuple")
        # 抽场的时段逻辑
        max_today_duration_By_site = 1
        week_day = datetime.now().weekday()
        # 周5和周6
        if  (week_day >= 4 and week_day <= 5) and choose_site == '谭兆羽毛球':
            max_today_duration_By_site = 3
        # 周6周日
        elif (week_day >= 5 and week_day <= 6) and choose_site == '综合体育馆羽毛球':
            max_today_duration_By_site = 3
        if choose_duration > max_today_duration_By_site:
            choose_duration = max_today_duration_By_site
        duration = durations[random.randint(0, choose_duration)]
        # 得到提交的信息
        timetable_ids = submitData[duration].get("timetable_ids")
        body = {
            "timetable_ids": timetable_ids,
            "book_num": 2
        }
        headers = {
            "Content-Type": "application/json",
            "token": str(user_data.get("token"))
        }
        user_id = str(user_data.get("user_id"))
        # 发送提交信息
        conn.request("POST", f"/order/joindraw_port?user_id={user_id}", body=json.dumps(body), headers=headers)
        response = conn.getresponse()
        if response.status == 200:
            print(response.read().decode("utf-8"))


def getAuthCode(conn, user_datas):
    for user_data in user_datas:
        user_id = str(user_data.get("user_id"))
        conn.request("GET", f"/user/auth_code?user_id={user_id}", headers={"token": str(user_data.get("token"))})
        response = conn.getresponse()
        if response.status == 200:
            response_data = response.read().decode("utf-8")
            auth_code = json.loads(response_data).get("data", {})
            user_data["auth_code"] = auth_code


def inviteUser(conn, user_datas, drawed_orders,choose_site):
    getOrderData(conn, user_datas, drawed_orders, choose_site)
    for order_data in drawed_orders:
        for user_data in user_datas:
            if  not user_data.get("is_invited"):
                user_id = str(order_data.get("user_id"))
                username = order_data.get("username")
                invited_username = user_data.get("username")
                body = {
                    "order_id": order_data.get("order_id"),
                    "auth_codelist": [
                        user_data.get("auth_code")
                    ]
                }
                headers = {
                   "token": str(order_data.get("token")),
                    "Content-Type": "application/json"
                    }
                conn.request("POST", f"/order/inviteuser_port?user_id={user_id}",
                             headers=headers,body=json.dumps(body))
                response = conn.getresponse()
                if response.status == 200:
                    response_data = json.loads(response.read().decode("utf-8"))
                    if response_data.get('msg',{}) == '成功':
                        print(f"username:{username}邀请,{invited_username}{response_data.get('msg', {})}")
                        user_data["is_invited"] = True
                        break
def deleteInvitedUser(conn, user_datas, drawed_orders, choose_site):
    headers = {
        "token": str(drawed_orders.get("token")),
        "Content-Type": "application/json"
    }
    conn.request("GET", f"/order/del_order_port?user_id={user_id}",
                 headers=headers)
    response = conn.getresponse()
def getShowOrder(conn,user_datas,choose_site,drawed_orders):
    getOrderData(conn, user_datas, drawed_orders, choose_site)
    showOrders = copy.deepcopy(drawed_orders)
    last_username = ''
    last_psw = ''
    for order in showOrders:
        del order["user_id"]
        del order["order_id"]
        del order["token"]
        last_username = order.pop("username")
        last_psw = order.pop("psw")
    # 去重
    seen = set()
    new_l = []
    for d in showOrders:
        t = tuple(d.items())
        if t not in seen:
            seen.add(t)
            new_l.append(d)
    new_l.append({
        "上场账号": last_username,
        "上场密码": last_psw,
    })
    return new_l

def log_in_and_draw():
    # 基本设置信息
    config_path = os.path.join('.', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    choose_sites = list(config["choose_site"])
    choose_duration = int(config["choose_duration"])
    if datetime.now().weekday() <=4 and datetime.now().weekday() >= 0:
        choose_sites.remove("综合体育馆羽毛球")
    user_datas = []
    for user_data in config['user_datas']:
        user_datas.append({
            "username": user_data["username"],
            "psw": user_data["psw"],
            "user_id": "",
            "token": "",
            "auth_code": '',
            "is_invited": False
        })
    ocr = ddddocr.DdddOcr()
    conn = http.client.HTTPSConnection("www.wyu-pesystem.com",context = ssl._create_unverified_context())
    # 获取所有登陆用户的信息。
    loginInBatchUser(conn, ocr, user_datas)
    getAuthCode(conn, user_datas)
    print("全部登陆成功")
    # 提交订单。
    for choose_site in choose_sites:
        submitOrder(conn, user_datas, choose_duration, choose_site)
    print("全部提交成功")
    # Step 6: 关闭连接
    conn.close()
def invited_and_show_order():
    # 基本设置信息
    config_path = os.path.join('.', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    choose_sites = list(config["choose_site"])
    if datetime.now().weekday() <=4 and datetime.now().weekday() >= 0:
        choose_sites.remove("综合体育馆羽毛球")
    drawed_orders = []
    user_datas = []
    for user_data in config['user_datas']:
        user_datas.append({
            "username": user_data["username"],
            "psw": user_data["psw"],
            "user_id": "",
            "token": "",
            "auth_code": '',
            "is_invited": False
        })

    ocr = ddddocr.DdddOcr()
    context = ssl._create_unverified_context()
    conn = http.client.HTTPSConnection("www.wyu-pesystem.com",context = context)
    # 获取所有登陆用户的信息。
    loginInBatchUser(conn, ocr, user_datas)
    getAuthCode(conn, user_datas)
    print("全部登陆成功")
    # 对于已经抽到的用户，填写邀请码。
    showOrders = ''
    for choose_site in choose_sites:
        # # 展示抽到的场信息。
        getOrderData(conn, user_datas, drawed_orders, choose_site)
        # inviteUser(conn, user_datas, drawed_orders, choose_site)
        showOrders = getShowOrder(conn,user_datas,choose_site,drawed_orders)
    print(showOrders)

    # # Step 6: 关闭连接
    # conn.close()
    # wx = WeChat()
    # content = showOrders
    # step = int(len(content)/5) + 1
    # for i in range(step):
    #     fragmentContent = content[i*5:(i+1)*5]
    #     who = 'wyu羽球小助手'
    #     wx.SendMsg(msg=fragmentContent, who=who)
invited_and_show_order()
# sched = BlockingScheduler()  #创建调度器
# sched.add_job(log_in_and_draw, 'cron', day_of_week= 'mon,wed,sat,sun', hour=9, minute=1, end_date='2027-05-30',misfire_grace_time=30,max_instances=2)
# sched.add_job(invited_and_show_order, 'cron', day_of_week= 'mon,wed,sat,sun', hour=11, minute=1, end_date='2027-05-30',misfire_grace_time=30,max_instances=2)
# sched.start()
# sched.add_job(invited_and_show_order, 'cron', day_of_week= 'mon,wed,sat,sun', hour=16, minute=1, end_date='2027-05-30',misfire_grace_time=30,max_instances=2)
# # invited_and_show_order()
# try:
#     print("任务调度启动中...")
#     sched.start()
# except (KeyboardInterrupt, SystemExit):
#     print("任务调度已停止。")
