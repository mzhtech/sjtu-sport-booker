from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
from datetime import datetime, timedelta
from contextlib import nullcontext


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
        booking_lock=None,
        success_event=None,
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
        self.booking_lock = booking_lock
        self.success_event = success_event

        self.options = Options()
        if headless:
            self.options.add_argument("-headless") # 无头模式(不显示浏览器界面)
        self.driver = webdriver.Firefox(
            options=self.options)
        client_config = getattr(self.driver.command_executor, "_client_config", None)
        if client_config is not None:
            client_config.timeout = 30
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

    def export_session(self):
        def dump_storage(storage_name):
            return self.driver.execute_script(
                """
                const storage = window[arguments[0]];
                const values = {};
                for (let index = 0; index < storage.length; index += 1) {
                    const key = storage.key(index);
                    values[key] = storage.getItem(key);
                }
                return values;
                """,
                storage_name,
            ) or {}

        return {
            "cookies": self.driver.get_cookies(),
            "local_storage": dump_storage("localStorage"),
            "session_storage": dump_storage("sessionStorage"),
        }

    def restore_session(self, session_state):
        self.open_website()
        self.driver.delete_all_cookies()
        self.driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
        allowed_cookie_fields = {
            "name",
            "value",
            "path",
            "domain",
            "secure",
            "httpOnly",
            "sameSite",
            "expiry",
        }
        for source_cookie in session_state.get("cookies", []):
            cookie = {
                key: value
                for key, value in source_cookie.items()
                if key in allowed_cookie_fields and value is not None
            }
            try:
                self.driver.add_cookie(cookie)
            except Exception:
                # Some SSO cookies target a parent domain and cannot be restored
                # from the sports subdomain. The site-specific cookies still apply.
                continue

        for storage_name, values in (
            ("localStorage", session_state.get("local_storage", {})),
            ("sessionStorage", session_state.get("session_storage", {})),
        ):
            for key, value in values.items():
                self.driver.execute_script(
                    "window[arguments[0]].setItem(arguments[1], arguments[2]);",
                    storage_name,
                    key,
                    value,
                )

        self.driver.refresh()
        WebDriverWait(self.driver, 10).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
        WebDriverWait(self.driver, 10).until(
            lambda driver: bool(
                driver.execute_script("return window.sessionStorage.getItem('token');")
            )
        )
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located(('class name', 'el-input__inner'))
        )
        self.log('Authenticated session restored')
    
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
    def _available_dates(self):
        tabs = self.driver.find_elements('css selector', "[id^='tab-20']")
        return {
            tab.get_attribute('id').removeprefix('tab-')
            for tab in tabs
            if tab.get_attribute('id')
        }

    def _select_date(self, date):
        wait = WebDriverWait(self.driver, 5)
        date_id = 'tab-' + date
        current_slots = []
        for wrapper in self.driver.find_elements('class name', 'inner-seat-wrapper'):
            if wrapper.is_displayed():
                current_slots = wrapper.find_elements('class name', 'clearfix')
                if current_slots:
                    break

        btn = wait.until(EC.element_to_be_clickable(('id', date_id)))
        was_active = 'is-active' in btn.get_attribute('class').split()
        self.click_element(btn, f"date tab {date}")

        def date_is_active(driver):
            return 'is-active' in driver.find_element('id', date_id).get_attribute('class').split()

        try:
            WebDriverWait(self.driver, 2).until(date_is_active)
        except TimeoutException:
            self.log(f"Date tab {date} did not activate after normal click; retrying with JavaScript")
            btn = self.driver.find_element('id', date_id)
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();",
                btn,
            )
            wait.until(date_is_active)

        if current_slots and not was_active:
            try:
                WebDriverWait(self.driver, 1).until(EC.staleness_of(current_slots[0]))
            except TimeoutException:
                pass

    def _load_time_slots(self, date):
        def visible_time_slots(driver):
            for wrapper in driver.find_elements('class name', 'inner-seat-wrapper'):
                if wrapper.is_displayed():
                    time_slots = wrapper.find_elements('class name', 'clearfix')
                    if time_slots:
                        return time_slots
            return False

        try:
            return WebDriverWait(self.driver, 3).until(visible_time_slots)
        except TimeoutException:
            return []

    def searchTime(self):
        checked_dates = []
        retry_dates = []
        available_dates = self._available_dates()
        for date in self.date:
            if self.should_stop():
                raise InterruptedError('任务已取消')
            if available_dates and date not in available_dates:
                self.log(
                    f"Date {date} is not currently offered by the platform; "
                    "continuing with remaining dates"
                )
                retry_dates.append(date)
                continue
            self.log(f"Selecting date tab: {date}")
            try:
                self._select_date(date)
            except Exception as e:
                self.log(f"Date {date} could not be selected: {e}; continuing with remaining dates")
                retry_dates.append(date)
                continue

            try:
                time_slots = self._load_time_slots(date)
            except Exception as e:
                self.log(f"Date {date} time blocks failed to load: {e}; continuing with remaining dates")
                retry_dates.append(date)
                continue

            if not time_slots:
                self.log(f"No time blocks rendered for {date}; continuing with remaining dates")
                retry_dates.append(date)
                continue

            date_complete = True
            for time in self.time:
                if self.should_stop():
                    raise InterruptedError('任务已取消')
                self.log(f"Checking time slot: {date} {time}:00")
                time_slot_id = time - 7
                if time_slot_id < 0 or time_slot_id >= len(time_slots):
                    self.log(
                        f"Time slot {date} {time}:00 is not rendered "
                        f"(available blocks: {len(time_slots)}); continuing"
                    )
                    date_complete = False
                    continue
                try:
                    time_slot = time_slots[time_slot_id]
                    seats = time_slot.find_elements('class name', 'unselected-seat')
                except Exception as e:
                    self.log(f"Time slot {date} {time}:00 could not be read: {e}; continuing")
                    date_complete = False
                    continue

                self.log(f"Available seats for {date} {time}:00 -> {len(seats)}")
                if seats:
                    booking_guard = self.booking_lock or nullcontext()
                    with booking_guard:
                        if self.success_event is not None and self.success_event.is_set():
                            raise InterruptedError('其他并发任务已完成预约')
                        if self.should_stop():
                            raise InterruptedError('任务已取消')
                        self.click_element(seats[0], f"seat selection for {date} {time}:00")
                        self.log(f"Seat selected for {date} {time}:00, confirming order")
                        self.confirmOrder()
                        self.ordered_flag = True
                        if self.success_event is not None:
                            self.success_event.set()
                        if self.stop_event is not None:
                            self.stop_event.set()
                    sleep(1)
                    return "ordered"

            if date_complete:
                checked_dates.append(date)
                self.log(f"Completed date check: {date}")
            else:
                retry_dates.append(date)

        checked_text = ', '.join(checked_dates) or 'none'
        retry_text = ', '.join(retry_dates) or 'none'
        self.log(f"Date scan summary | checked: {checked_text} | retry: {retry_text}")
        return "partial" if retry_dates else "checked"

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
                if search_result in {"empty_blocks", "partial"}:
                    self.empty_block_retries += 1
                    if self.empty_block_retries >= self.max_empty_block_retries_before_refresh:
                        self.log("Incomplete date scans persisted, performing full page refresh")
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
        try:
            self.driver.quit()
        except Exception as exc:
            self.log(f"Browser quit failed: {exc}")
            service = getattr(self.driver, "service", None)
            if service is not None:
                try:
                    service.stop()
                except Exception as service_exc:
                    self.log(f"Browser service stop failed: {service_exc}")
