# sjtu-sport-booker

[快速上手指南](./quick-start.md) — 5 分钟内让抢票控制台跑起来。

基于 python selenium 实现的 SJTU 体育场馆自动预约脚本，现已支持本地网页控制台配置。

## 实现思路

python 的 selenium 库可以方便地利用id、class、css来定位元素定位，模拟预约的点击操作。交大基本体育场馆的预约流程为：
1. 打开上海交通大学体育场馆预约平台 https://sports.sjtu.edu.cn/
2. 输入jaccount账号与密码，识别图形验证码，点击登录
3. 选择场馆(Venue)、细分项目(VenueItem)、日期、时间(Time)
4. 如果有空余场地，则点击预约按钮，确认预约; 如果没有就刷新网页继续检测
5. 若成功预约则发消息给手机，提醒用户付款

利用 selenium 库实现以上操作即可。

## 环境配置

### macOS 一键安装

```bash
chmod +x install-macos.sh start.sh
./install-macos.sh
```

### Windows 一键安装

```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
```

或直接双击：

```bat
install-windows.bat
```

### 手动方式

创建虚拟环境
```
python3 -m venv .venv
source .venv/bin/activate
```

安装依赖
```
pip install -r requirements.txt
```

安装与浏览器对应版本的 webDriver (以Firefox为例)
- 下载地址 https://github.com/mozilla/geckodriver/releases

安装 tesseract-ocr，用于识别图形验证码
- 下载地址 https://digi.bib.uni-mannheim.de/tesseract/

## 使用方式

### 1. 启动本地网页控制台

推荐使用网页控制台配置账号、场馆和通知参数：

```bash
./start.sh
```

Windows:

```bat
start-windows.bat
```

默认会在 `http://127.0.0.1:3210` 启动本地服务，配置会保存到项目根目录下的 `runtime-config.json`。

首次使用前请先执行：

```bash
chmod +x start.sh
```

完整环境说明见 [quick-start.md](./quick-start.md)。

控制台支持：

- 登录测试
- 场馆/项目/日期/时间段配置
- 立即启动或定时启动
- 邮件通知测试
- 启动/停止任务
- 实时自动更新运行日志
- 抢票成功高亮提示

### 2. 保留命令行兼容模式

如果你仍然想直接运行脚本，也保留了原来的命令行模式。

**使用命令行参数进行预约**
```
python main.py --venue '气膜体育中心' --venueItem '羽毛球' --date '[2,3]' --time '[19,21]' --head
```

**使用 json 配置文件进行预约**
```
python main.py --json template.json --head
```

> 若要开启浏览器界面则加上参数 `--head`

## 通知方式

### 1. 本地网页控制台 SMTP 邮件通知

在网页控制台里填写以下信息即可：

- SMTP Host
- SMTP Port
- 是否启用 SSL
- 发件邮箱
- 授权码/密码
- 收件邮箱

> 邮件发送失败只会记录到日志，不会阻塞抢票主流程。
