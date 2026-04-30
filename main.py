import logging
import argparse
import json
import ast
import os

from sjtusportbooker.config import FANGTANG_KEY
from sjtusportbooker.utils.messages import send_message_fangtang
from sjtusportbooker.web.app import create_app


def play_success_sound():
    try:
        import winsound
    except ImportError:
        print("\a")
        return
    winsound.Beep(440, 10000)

def main(str, args):
    from sjtusportbooker import SportBooker

    ## 解析参数
    # 1. json文件模式
    if str == 'json':
        with open(args.json, 'r', encoding='utf-8') as f:
            task = json.load(f)
    # 2. 命令行模式
    elif str == 'terminal':
        try:
            args.date = ast.literal_eval(args.date)
            args.time = ast.literal_eval(args.time)
        except:
            raise Exception("Date and Time should be list.")
        task = {
            "venue": args.venue,
            "venueItem": args.venueItem,
            "date": [int(item) for item in args.date],
            "time": [int(item) for item in args.time]
        }
    # 3. 默认
    else:
        task = {
            "venue": "气膜体育中心",
            "venueItem": "羽毛球",
            "date": [3,4,5,6,7],
            "time": [19,20,21]
        }

    # 创建任务
    worker = SportBooker(task, headless=not args.head)
    
    try:
        worker.login()
    except Exception as e:
        print(f"[Login ERROR]: {e}")
    # 预约
    try:
        worker.book()
        print("Booking Venue!")
        send_message_fangtang('抢到场地了!', '第一行\n\n第二行', FANGTANG_KEY)
        play_success_sound()
    except Exception as e:
        print(f"[Booking ERROR]: {e}")
        send_message_fangtang('抢场地失败!', '第一行\n\n第二行', FANGTANG_KEY)


if __name__ == "__main__":
    print("Start SJTU Sport Appointment")

    # Baic Logging Config
    currentPath = os.path.dirname(os.path.abspath(__file__))
    logfilePath = os.path.join(currentPath, "sport.log")
    logging.basicConfig(
        filename=logfilePath,
        level='INFO',
        format='%(asctime)s  %(filename)s : %(levelname)s  %(message)s',
        datefmt='%Y-%m-%d %A %H:%M:%S',
    )
    logging.info("=================================")
    logging.info("Log Started")
    
    # 解析参数
    parser = argparse.ArgumentParser()
    parser.add_argument('--head', action='store_true')
    parser.add_argument('--json', help='json file')
    parser.add_argument('--venue', help='场馆名称')
    parser.add_argument('--venueItem', help='细分项目名称')
    parser.add_argument('--date', help='日期，用方括号表示，例如 [2,3]')
    parser.add_argument('--time', help='时间，用方括号表示，例如 [19,21]')
    parser.add_argument('--serve', action='store_true', help='启动本地网页控制台')
    parser.add_argument('--host', default='127.0.0.1', help='Web 服务监听地址')
    parser.add_argument('--port', default=3210, type=int, help='Web 服务端口')

    args = parser.parse_args()
    if args.serve or (not args.json and not args.venue):
        app = create_app(os.path.join(currentPath, "runtime-config.json"))
        app.run(host=args.host, port=args.port, debug=False)
    elif args.json:
        main('json', args)
    else:
        main('terminal', args)
