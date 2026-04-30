from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
from datetime import datetime, timedelta


from .utils.captcha_rec import captcha_rec
from .SJTUVenueTabLists import venueTabLists
from .config import JACCOUNT_USERNAME, JACCOUNT_PASSWORD

class SportBooker:
    def __init__(
        self,
        task,
        username=None,
        password=None,
        headless=True,
        logger=None,
        stop_event=None,
        poll_interval_ms=500,
        status_callback=None,
    ):
        self.task = task
        self.tryTimes = 0
        self.ordered_flag = False
        self.venue = task['venue']
        self.venueItem = task['venueItem']
        self.date = task['date']
        self.time = task['time']

        self.user_name = username or JACCOUNT_USERNAME
        self.password = password or JACCOUNT_PASSWORD
        self.logger = logger or print
        self.stop_event = stop_event
        self.poll_interval = max(poll_interval_ms / 1000.0, 0.2)
        self.status_callback = status_callback

        self.options = Options()
        if headless:
            self.options.add_argument("-headless") # 无头模式(不显示浏览器界面)
        self.driver = webdriver.Firefox(
            options=self.options)
        self.empty_block_retries = 0
        self.max_empty_block_retries_before_refresh = 3
        self.gen_date()

    def log(self, message):
        self.logger(message)

    def fail(self, step, error):
        message = f"{step} failed: {error}"
        self.log(message)
        raise RuntimeError(message) from error

    def click_element(self, element, label):
        try:
            element.click()
        except Exception as error:
            error_text = str(error)
            if (
                "ElementClickInterceptedError" not in error_text
                and "ElementNotInteractableError" not in error_text
                and "could not be scrolled into view" not in error_text
            ):
                raise
            self.log(f"Falling back to JavaScript click for {label}")
            self.driver.execute_script("arguments[0].click();", element)

    def should_stop(self):
        return self.stop_event is not None and self.stop_event.is_set()

    # 生成真实日期
    def gen_date(self):
        deltaDays = self.date
        today = datetime.now()
        date = [today + timedelta(days=i) for i in deltaDays]
        self.date = [i.strftime('%Y-%m-%d') for i in date]


    # 打开体育预约网站
    def open_website(self):
        url = 'https://sports.sjtu.edu.cn'
        self.driver.get(url)
        if not self.driver.title == '上海交通大学体育场馆预约平台':
            raise Exception('Target site error.')
    
    # 登录
    def login(self):
        self.open_website()
        sleep(3)
        # 进入登录界面
        try:
            btn = self.driver.find_element('css selector', '#app #logoin button')
            btn.click()
        except:
            raise Exception('Failed to enter login page.')
        # Try 10 times in case that the captcha recognition process goes wrong
        times = 0
        while self.driver.title != '上海交通大学体育场馆预约平台' and times < 10:
            self.driver.refresh()
            sleep(1) # Wait for the captcha image to load
            times += 1

            userInput = self.driver.find_element('name', 'user')
            userInput.send_keys(self.user_name)
            passwdInput = self.driver.find_element('name', 'pass')
            passwdInput.send_keys(self.password)
            captcha = self.driver.find_element('id', 'captcha-img')
            captchaVal = captcha_rec(captcha) # captcha recognition
            userInput = self.driver.find_element('id', 'input-login-captcha')
            userInput.send_keys(captchaVal)
            btn = self.driver.find_element('id', 'submit-password-button')
            btn.click()

        assert times < 10, '[ERROR]: Tryed 10 times, but failed to login, please check the captcha recognition process.'
        self.log('Login Successfully!')
    
    # 选择场馆
    def searchVenue(self):
        self.log(f"Searching venue: {self.venue}")
        sleep(1)
        wait = WebDriverWait(self.driver, 10)
        try:
            venueInput = wait.until(EC.presence_of_element_located(('class name', 'el-input__inner')))
            venueInput.send_keys(self.venue)
            btn = wait.until(EC.presence_of_element_located(('class name', 'el-button--default')))
            btn.click()

            self.driver.refresh()
            sleep(1)
            venueInput = wait.until(EC.presence_of_element_located(('class name', 'el-input__inner')))
            venueInput.send_keys(self.venue)
            btn = wait.until(EC.presence_of_element_located(('class name', 'el-button--default')))
            btn.click()

            sleep(1)
            btn = wait.until(EC.presence_of_element_located(('class name', 'el-card__body')))
            btn.click()
            sleep(1)
            self.log(f"Venue selected: {self.venue}")
        except Exception as e:
            self.fail(f"searchVenue[{self.venue}]", e)

    # 选择项目
    def searchVenueItem(self):
        self.log(f"Selecting venue item: {self.venueItem}")
        wait = WebDriverWait(self.driver, 10)
        try:
            tab_id = venueTabLists[self.venue][self.venueItem]
            btn = wait.until(EC.presence_of_element_located(('id', tab_id)))
            btn.click()
            self.log(f"Venue item selected: {self.venueItem} ({tab_id})")
        except Exception as e:
            self.fail(f"searchVenueItem[{self.venue}/{self.venueItem}]", e)

    # 选择日期
    def searchTime(self):
        wait = WebDriverWait(self.driver, 10)
        for date in self.date:
            if self.should_stop():
                raise InterruptedError('任务已取消')
            dateID = 'tab-' + date
            self.log(f"Selecting date tab: {date}")
            try:
                btn = wait.until(EC.presence_of_element_located(('id', dateID)))
                btn.click()
            except Exception as e:
                self.fail(f"searchDate[{dateID}]", e)
            for time in self.time:
                if self.should_stop():
                    raise InterruptedError('任务已取消')
                if self.ordered_flag == False:
                    self.log(f"Checking time slot: {date} {time}:00")
                    try:
                        timeSlotId = time - 7
                        wrapper = wait.until(EC.presence_of_element_located(('class name', 'inner-seat-wrapper')))
                        time_slots = wrapper.find_elements('class name', 'clearfix')
                        if not time_slots:
                            self.log(f"No time blocks rendered for {date}, will retry after refresh")
                            return "empty_blocks"
                        if timeSlotId < 0 or timeSlotId >= len(time_slots):
                            raise RuntimeError(
                                f"time slot index {timeSlotId} out of range, available blocks: {len(time_slots)}"
                            )
                        timeSlot = time_slots[timeSlotId]
                        seats = timeSlot.find_elements('class name', 'unselected-seat')
                        self.log(f"Available seats for {date} {time}:00 -> {len(seats)}")
                        if len(seats) > 0:
                            self.click_element(seats[0], f"seat selection for {date} {time}:00")
                            self.log(f"Seat selected for {date} {time}:00, confirming order")
                            self.confirmOrder()
                            self.ordered_flag = True
                            sleep(1)
                            return "ordered"
                    except Exception as e:
                        self.fail(f"searchTime[{date} {time}:00]", e)
        return "checked"

    # 确认预约
    def confirmOrder(self):
        self.log("Confirming order")
        try:
            btn = self.driver.find_element('css selector', '.drawerStyle>.butMoney>.is-round')
            self.click_element(btn, "confirm order button")

            btn = self.driver.find_element('css selector', '.dialog-footer>.tk>.el-checkbox>.el-checkbox__input>.el-checkbox__inner')
            self.click_element(btn, "agreement checkbox")
            btn = self.driver.find_element('css selector', '.dialog-footer>div>.el-button--primary')
            self.click_element(btn, "final confirm button")
            sleep(1)
            self.log("Order confirmation submitted")
        except Exception as e:
            self.fail("confirmOrder", e)

    def book(self):
        if not hasattr(self, "empty_block_retries"):
            self.empty_block_retries = 0
        if not hasattr(self, "max_empty_block_retries_before_refresh"):
            self.max_empty_block_retries_before_refresh = 3
        self.log("Start Booking")
        self.log(f"venue: {self.venue} | venueItem: {self.venueItem} | date: {self.date} | time: {self.time}")
        try:
            self.searchVenue()
            self.searchVenueItem()
            while self.ordered_flag == False:
                if self.should_stop():
                    raise InterruptedError('任务已取消')
                try:
                    search_result = self.searchTime()
                except InterruptedError:
                    raise
                except Exception as e:
                    self.log(f"[Book ERROR]: {e}")
                    search_result = "error"
                self.log(f"try {self.tryTimes} times")
                if self.status_callback is not None:
                    self.status_callback(self.tryTimes)
                self.tryTimes += 1
                if search_result == "empty_blocks":
                    self.empty_block_retries += 1
                    if self.empty_block_retries >= self.max_empty_block_retries_before_refresh:
                        self.log("Empty time blocks persisted, performing full page refresh")
                        self.driver.refresh()
                        self.empty_block_retries = 0
                else:
                    self.empty_block_retries = 0
                    if not self.ordered_flag:
                        self.driver.refresh()
                sleep(self.poll_interval)
        except Exception as e:
            sleep(1)
            if isinstance(e, InterruptedError):
                raise
            raise
        return self.ordered_flag

    def close(self):
        self.driver.quit()
