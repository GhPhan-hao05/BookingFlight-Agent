from binascii import b2a_base64
from crewai.tools import BaseTool
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, Field
import time
from datetime import datetime, timedelta
import os
import re
os.environ["OPENAI_API_KEY"]= '[your_openai_api_key]'  # Replace YOUR_API_KEY with your actual API key



    
# Singleton browser session manager
class TravelokaSession:
    """Class to maintain a single browser session for all Traveloka interactions"""
    _instance = None

    @classmethod
    def get_instance(cls):
        """Singleton pattern to ensure we have only one browser session"""
        if cls._instance is None:
            cls._instance = TravelokaSession()
        return cls._instance

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self.is_initialized = False
    
    def initialize(self):
        """Initialize the browser if not already done"""
        if not self.is_initialized:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=False,
                                                           args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--no-first-run',
                '--disable-extensions',
                '--disable-plugins'
            ])
            self.page = self.browser.new_page()
            self.page.goto("https://www.traveloka.com/vi-vn/flight")
            self.is_initialized = True
            time.sleep(2)
    
    def get_page(self):
        """Get the current page, initializing if needed"""
        if not self.is_initialized:
            self.initialize()
        return self.page
    
    def close(self):
        """Clean up resources"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        self.is_initialized = False
        TravelokaSession._instance = None



class InitInput(BaseModel):
    depart: str = Field(..., description="String what city depart")
    destination: str = Field(..., description="String what city is destination")
    day_depart: int = Field(..., description="the number is day depart")
    month_depart: int = Field(..., description="the number is month depar")
    year_depart: int = Field(..., description="the number is year depar")

# Phase 1: Search Flights Tool
class InsertInf(BaseTool):
    name: str = "insert_flight_inf"
    description: str = "this tools is do playwright code to access traveloka web, fill information icluding: depart-destination in traveloka and choose the day depart and return status of the page"
    args_schema: type[BaseModel] = InitInput
    def _run(self, depart, destination, day_depart, month_depart, year_depart) -> int:
        """
        run playwright code to fill information
        choose filed, insert depart and destination points
        choose date depart and click search
        this tool will return new playwright page
        """
        session = TravelokaSession.get_instance()
        page = session.get_page()
        try:
            time.sleep(1)
            page.click('[data-testid="button-tab-ONE_WAY"]')
            page.wait_for_selector('[data-testid="airport-input-departure"]')
            from_box = page.locator('[data-testid="airport-input-departure"]')
            from_box.click()
            time.sleep(1)
            from_box.fill("")  # clear placeholder
            from_box.type(depart)
            time.sleep(1)
            from_box.press("Enter")
            page.wait_for_selector('[data-testid="airport-input-destination"]')
            from_box = page.locator('[data-testid="airport-input-destination"]')
            from_box.click()
            time.sleep(1)
            from_box.fill("")  
            from_box.type(destination)
            time.sleep(1)
            from_box.press("Enter")

            page.click('[data-testid="departure-date-input"]')
            time.sleep(1)
            # month year hiện tại
            month_year_text = page.locator('[data-testid="calendar-month"]').nth(0).text_content()
            parts = month_year_text.strip().split()    
            current_month = 5
            current_year = 2025
            while True:
                display_month = current_month
                display_year = current_year
                if display_year == year_depart and display_month == month_depart:
                    break
                current_month+=1
                if current_month%13 ==0:
                    current_year+=1
                    current_month =1
                page.click('[data-id="IcSystemChevronRight16"]')
                time.sleep(1)

            selector = f'[data-testid="date-cell-{day_depart}-{month_depart}-{year_depart}"]'
            page.click(selector)
            time.sleep(1)
            # if is_2_way:
            # page.click('[data-testid="desktop-default-search-button"]')
            serch = page.locator('text="Tìm chuyến bay"')
            serch.click()

        # sang trabng chọn chuyến bay
            page.wait_for_url("**/flight/fullsearch**")
            
            return page, 'insert base information success, move to filter'

        except Exception as e:
            return f"Error searching for flights: {str(e)}"


class FilterToolInput(BaseModel):
    time_constrain: str = Field(..., description="String what time user want depart (06:30, 11:00, 21:20,...) or 'null'")
    brand_constrain: str = Field(..., description="String what flight company user want to use (Qatar Airwway, VietJet Air, Fly Emirates, ...) or 'null'")
    id_class: int = Field(..., description="id of class seat user prefer (0: phổ thông - economy, 1 phổ thông đặc biệt - premium economy, và 2: thương gia - business)")


class FilterTool(BaseTool):
    name: str = "filter_flight"
    description: str = """filter flight by (1) time depart and (2) company flight name (3) id class seat; give 2 args is time_constrain, brand_constrain, id_class;
    this tool first get all flight in require seat class, then flights match with time constrain if dont have any flight match, return notice that dont have flight,
    if exist flight match with time, filter by brand constrain, if dont find any flight match with brand constrain, return notice about another brand
    """
    args_schema: type[BaseModel] = FilterToolInput

    def _run(self, time_constrain, brand_constrain, id_class) -> int:
        session = TravelokaSession.get_instance()
        page = session.get_page()
        try:
            time.sleep(4)
            if id_class!=0:
                page.locator('[data-testid="flight-search-header"]')
                page.locator('[data-id="IcSystemSearch"]').click()
                time.sleep(1)
                page.locator('text="Đổi tìm kiếm"').click()
                form = page.locator('[data-testid="desktop-default-form"]')
                form.locator('[data-id="IcTransportSeatClass"]').click()
                listbox = form.locator("div[role='listbox']")
                options = listbox.locator("div[role='option']")
                options.nth(id_class).click()
                sercht = page.locator('text="Tìm chuyến bay"').nth(1)
                sercht.click()
                time.sleep(4)

            for _ in range(4):
                page.evaluate("window.scrollBy(0, window.innerHeight)")  # Scroll down one screen height
                time.sleep(1) 
            card_list = page.locator('[data-testid^="flight-inventory-card-container-"]')
            min_price = float('inf')
            cheapest_index = -1
            time_constrain_fl = []
            brand_constrain_fl = []
            if time_constrain != 'null':
                time_str = re.search(r'\b\d{2}:\d{2}\b', time_constrain).group(0)
                target_time = datetime.strptime(time_str, "%H:%M")
                time_range = timedelta(minutes=50)
                earliest_time = (target_time - time_range).time()
                latest_time = (target_time + time_range).time()

        #loc chuyen bay theo hang và lay gia re nhat
            for i in range(card_list.count()):
                card = card_list.nth(i)
                #=======================
                if time_constrain != 'null':
                    times = card.locator('div[dir="auto"]', has_text=re.compile(r'\d{2}:\d{2}'))
                    if times.count() > 0:
                        depart_time = times.nth(0).text_content()
                        dep_time = datetime.strptime(depart_time, "%H:%M").time()
                        if (earliest_time > dep_time) or (dep_time > latest_time): # ko cùng thời gian: move sang thẻ khác
                            continue
                leaf_divs = card.locator('div:not(:has(div))')
                first_text = None
                for j in range(leaf_divs.count()):
                    text = leaf_divs.nth(j).text_content()
                    if text and text.strip():
                        first_text = text.strip()
                        break

                time_constrain_fl.append([first_text])


                #=======================
                if brand_constrain != 'null':
                    if card.locator(f'text={brand_constrain}').count() == 0:
                        continue
                    brand_constrain_fl.append([first_text])

                price_text = card.locator('[data-testid="label_fl_inventory_price"]').text_content()
                price = int(price_text.split()[0].replace('.', ''))

                if price < min_price:
                    min_price = price
                    cheapest_index = i
            if (len(time_constrain) == 0) and (time_constrain != 'null'):
                return('i dont find any fight in time you want. Stop booking and please choose another one')
            if len(brand_constrain_fl) == 0:
                return(f'i dont find flight in brand you want. Stop booking and please choose another brand'), time_constrain_fl
            if cheapest_index != -1:
                cheapest_card = card_list.nth(cheapest_index)
                cheapest_card.locator('[data-testid="flight-inventory-card-button"]').click()
            time.sleep(3)

            seat_list = page.locator('[data-testid^="view_ticket_option_card_"]')
            seat_inf = f'there are {seat_list.count()} options '
            for i in range(seat_list.count()):
                seat = page.locator(f'[data-testid="view_ticket_option_card_{i}"]')
                seat_inf += ' /[start option]/ '
                seat_inf +=seat.text_content() 
                seat_inf += ' /[end option]/ '
                page.locator('[data-testid="bundle-summary-tray"]')
            return page, 'filter flight success', seat_inf

        except Exception as e:
            return f"Error filtering flights: {str(e)}"

# data-testid="view_ticket_option_card_1"

class IdSeatInput(BaseModel):
    id_seat_option: int = Field(..., description="seat option's id (1, 2, 3, ...)")

class ChooseSeatOptionTool(BaseTool):
    name: str = "choose_seat_option"
    description: str = "this tool give the arg is id_seat_option (1, 2, 3, ...) from user input and choose"
    args_schema: type[BaseModel] = IdSeatInput

    def _run(self, id_seat_option) -> int:
        session = TravelokaSession.get_instance()
        page = session.get_page()
        try:
            page.click(f'[data-testid="button_ticket_option_select_{id_seat_option-1}"]')
            return page, 'choose seat option success, move to insert personal information'
        except Exception as e:
            return f"Error choose_seat_option: {str(e)}"



class PersonalInformationInput(BaseModel):
    first_name: str = Field(..., description="user's first name ('Phan', 'Nguyen', 'Marcus', ...)")
    last_name: str = Field(..., description="user's last name ('Van Hiep', 'Thi Bao Linh', 'Thuram', ...)")
    phone: str = Field(..., description="user's phone number")
    email: str = Field(..., description="user's email (aa@gmail.com, ...)")
    title: str = Field(..., description="user's title (MR, MRS, MISS)")
    id_number: str = Field(..., description="user's id number")
    day: int = Field(..., description="user's born day (1, 3, 5, 11, 29, 30, ...)")
    month: int = Field(..., description="user's born month ( 1, 2, ...12)")
    year: int = Field(..., description="user's born year")

class InsertPersonalInformationTool(BaseTool):
    name: str = "insert_personal_information"
    description: str = """
This tool give args is peronal information, just basic insert them and get information about luggage option.
if have luggage option (if flight company offer baggage options) return notice insert personal information success with luggage option information. if not just return notice
    """
    args_schema: type[BaseModel] = PersonalInformationInput

    def _run(self, last_name, first_name, phone, email, title, id_number, day, month, year) -> int:
        session = TravelokaSession.get_instance()
        page = session.get_page()
        try:
            first_name_box = page.locator('[aria-labelledby="name.last"]').nth(0)
            first_name_box.click()
            first_name_box.type(first_name)  
            last_name_box = page.locator('[aria-labelledby="name.first"]').nth(0)
            last_name_box.click()
            last_name_box.type(last_name)
            phone_box = page.locator('[aria-label="Phone Number"]')
            phone_box.click()
            phone_box.type(phone)  
            mail_box = page.locator('[aria-labelledby="emailAddress"]')
            mail_box.click()
            mail_box.type(email) 

            page.select_option('[aria-labelledby="title"] select', title.upper())
            time.sleep(1)

            first_name_box_1 = page.locator('[aria-labelledby="name.last"]').nth(1)
            first_name_box_1.click()
            first_name_box_1.type(first_name)  
            last_name_box_1 = page.locator('[aria-labelledby="name.first"]').nth(1)
            last_name_box_1.click()
            last_name_box_1.type(last_name)
            time.sleep(1)
            page.select_option('[data-testid="day-datepicker"]', str(day))
            page.select_option('[data-testid="month-datepicker"]', str(month))
            page.select_option('[data-testid="year-datepicker"]', str(year))

            page.select_option('[aria-labelledby="nationality"] select', 'VN')
            cccd_box = page.locator('[aria-labelledby="travelerID.number"]')
            cccd_box.click()
            cccd_box.type(id_number)
            time.sleep(2)
            if page.locator('data-testid="view_flight_addons_widget_baggage"', has_text="Chọn"):
                page.locator('[data-testid="view_flight_addons_widget_baggage"]')
                time.sleep(2)
                bt = page.locator('div[dir="auto"][class="css-901oao r-1yadl64 r-1vonz36 r-109y4c4 r-1cis278 r-1udh08x r-t60dpp r-u8s1d r-3s2u2q r-92ng3h"]:has-text("Chọn")').nth(0)
                time.sleep(1)
                bt.click()
                time.sleep(3)
                page.locator('[data-testid="selectionModal.content"]').nth(0)
                print(page)
                time.sleep(2)
                element = page.locator('div[dir="auto"][class="css-901oao r-13awgt0 r-uh8wd5 r-ubezar r-b88u0q r-135wba7 r-fdjqy7"][style="color: rgb(1, 148, 243);"]:has-text("Xem thêm")')
                time.sleep(1)
                element.click()
                text = 'there are all option of luggage: '
                slct = page.locator('[aria-labelledby="baggageSelectionOptions"]')
                text += slct.text_content()
                return page, 'insert personal information sucsess, choose luggage option', text
            else:
                return page, 'insert personal informatin success, dont have luggage option, confirm booking'
        

        except Exception as e:
            return f"Error choose_seat_option: {str(e)}"




class LuggageOptionInput(BaseModel):
    id_luggage: int = Field(..., description="id luggage option which user choose (1, 2, 3, ...)")

class ChooseLuggageOptionTool(BaseTool):
    name: str = "choose_luggage_option"
    description: str = "given arg is id_luggage option, choose which one use prefer"
    args_schema: type[BaseModel] = LuggageOptionInput

    def _run(self, id_luggage) -> int:
        session = TravelokaSession.get_instance()
        page = session.get_page()
        try:
            sub_divs =  page.locator('[data-testid=".capacity"]')
            for i in range(sub_divs.count()):
                time.sleep(1)
                if i == id_luggage-1:
                    sub_divs.nth(i).click()
                    break
            time.sleep(1)
            page.locator('[data-testid="selectionModal.content"]')
            btht = page.locator('[data-testid="selectionModal.submitBtn"]').nth(0)
            btht.click()
            return page, 'choose luggage done, move to payment'
        except Exception as e:
            return f"Error choose_seat_option: {str(e)}"


class GoToPayTool(BaseTool):
    name: str = "go_to_pay"
    description: str = "this tool go to payment page"

    def _run(self) -> int:
        session = TravelokaSession.get_instance()
        page = session.get_page()
        try:
            page.click('[data-testid="bff-submit-page"]')
            time.sleep(2)
            page.click('[data-testid="validation-modal-dialog-confirm-button"]')
            time.sleep(3)
            return page, 'done booking process'
        except Exception as e:
            return f"Error choose_seat_option: {str(e)}"
        
