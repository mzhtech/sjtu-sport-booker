# Quick Start

这份文档用于把仓库和本机环境一次性配好，然后用一条命令启动本地抢票控制台。

## 1. 准备仓库

```bash
git clone <your-fork-or-repo-url>
cd sjtu-sport-booker
```

如果你已经有仓库，先确认当前目录里能看到这些关键文件：

- `main.py`
- `requirements.txt`
- `start.sh`
- `install-macos.sh`
- `install-windows.ps1`
- `sjtu_sport_booker/`

## 2. 一键安装依赖

### macOS

第一次运行前给脚本执行权限：

```bash
chmod +x install-macos.sh start.sh
```

然后执行：

```bash
./install-macos.sh
```

脚本会自动检查并按需安装：

- `python3`
- `Firefox`
- `geckodriver`
- `tesseract`
- `.venv`
- `requirements.txt` 里的 Python 依赖

如果某项依赖已经存在，脚本会直接跳过，不会重复安装。

### Windows

用 PowerShell 打开项目目录后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
```

如果你更希望双击直接跑，也可以直接执行：

```bat
install-windows.bat
```

脚本会优先使用 `winget` 自动检查并按需安装：

- `Python 3`
- `Firefox`
- `GeckoDriver`
- `Tesseract OCR`
- `.venv`
- `requirements.txt` 里的 Python 依赖

如果依赖已经存在，也会自动跳过。

> Windows 首次安装后，如果脚本提示命令还不在 PATH 里，重新打开一个新的 PowerShell 再执行一次即可。

## 3. 手动安装说明（备用）

这个项目不是只装 Python 包就够了，还依赖 3 个本机程序：

- `Firefox`
- `geckodriver`
- `tesseract`

### macOS

先安装 Homebrew，然后执行：

```bash
brew install --cask firefox
brew install geckodriver
brew install tesseract
```

### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y firefox tesseract-ocr
sudo apt-get install -y firefox-geckodriver || sudo apt-get install -y geckodriver
```

### 检查是否安装成功

```bash
firefox --version
geckodriver --version
tesseract --version
python3 --version
```

## 4. 一键启动

第一次运行前给脚本执行权限：

```bash
chmod +x start.sh
```

然后直接启动：

```bash
./start.sh
```

Windows 启动：

```bat
start-windows.bat
```

脚本会自动完成这些事情：

- 检查 `python3 / firefox / geckodriver / tesseract`
- 首次创建 `.venv`
- 安装 `requirements.txt` 里的 Python 依赖
- 启动本地网页控制台

默认地址：

```text
http://127.0.0.1:3210
```

## 5. 可选环境变量

如果你想换监听地址或端口，可以直接这样启动：

```bash
HOST=127.0.0.1 PORT=4321 ./start.sh
```

## 6. 页面里需要配置什么

启动后在本地页面里填写：

### 登录配置

- JAccount 账号
- JAccount 密码
- 是否无头模式

### 抢票目标

- 场馆
- 项目
- 目标日期
- 时间段

### 邮件通知

- 是否启用
- SMTP Host
- SMTP Port
- 是否 SSL
- 发件邮箱
- 授权码或邮箱密码
- 收件邮箱

### 任务控制

- 启动前轮询间隔
- 启动后轮询间隔

配置会保存在仓库根目录的 `runtime-config.json`。

页面特性：

- 日志会自动更新，不需要手动点"刷新"
- 任务运行中会自动禁用"开始任务 / 保存配置 / 测试登录 / 测试邮件"，避免重复触发
- 抢票成功后会显示明显的成功横幅和状态高亮

## 7. 首次使用建议流程

推荐按这个顺序操作：

1. 启动 `./start.sh` 或 `start-windows.bat`
2. 打开页面
3. 先填账号并点击"测试登录"
4. 再选择场馆、项目、日期和时间
5. 如果需要邮件提醒，再测试邮件
6. 最后点击"开始任务"

## 8. 常见问题

### 页面能打开，但测试登录失败

优先检查：

- JAccount 账号密码是否正确
- 本机 Firefox 是否能正常打开
- `geckodriver` 版本是否和 Firefox 兼容
- 本机是否已安装 `tesseract`

### 日志不更新

当前版本默认使用实时推送更新日志；如果浏览器不支持，会自动退回到轮询刷新。通常不需要手动点"刷新"。

### 脚本提示缺少系统依赖

`start.sh` 只会帮你建虚拟环境和装 Python 包，不会替你安装浏览器和 OCR 工具。请先按上面的系统依赖步骤安装。

如果你不想手动装，优先直接运行：

- macOS: `./install-macos.sh`
- Windows: `powershell -ExecutionPolicy Bypass -File .\install-windows.ps1`

### 端口被占用

改端口启动即可：

```bash
PORT=4321 ./start.sh
```

## 9. 兼容的老用法

如果你仍想保留老的命令行模式，也可以继续用：

```bash
.venv/bin/python main.py --venue '气膜体育中心' --venueItem '羽毛球' --date '[2,3]' --time '[19,21]' --head
```
