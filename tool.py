from playwright.sync_api import sync_playwright
import time
import re
from crewai import Crew, Task
from datetime import datetime, timedelta
from agent import booking_agent



def do_booking(finalrequest):
    input_task = Task(
        description=f"""{finalrequest}
        parse this input, use tools and do these step:
        (step 1) get input, understand (important: how much luggage the user has) and parse to get input for following step
        (step 2) insert depart city, destination city and day depart the information is fixed in tool;
        (step 3) filter flight by time and flight company (can filter with or without results), return note, result and seat options;
        (step 4) choose seat option best fit with user in cheapest price. let ignore the name of option, that not good for you, focus and think in price and luggage it offer
            Each seat option includes free carry-on luggage (usually 7kg or 10kg), and some include extra checked luggage.
            please thinking, reasoning, Calculate the total luggage capacity each seat option gives: total_capacity = carry-on + checked luggage included
            Compare the user’s luggage amount (from step 1) to the total_capacity: Are we sufficient? Do we have a deficiency (need to add more)?
            This reasoning is important because in the next step, you may need to choose an extra luggage option.
        (step 5) insert user information and choose luggage option if flight company offer (options id begin from 1, not 0. Consider no luggage is 1 option and have id is 1) .
        You already chose a seat class and know how much total luggage it provides (carry-on and checked).
        Now decide: Does the user need more luggage capacity?
            If yes, select an extra luggage option.
            If no, choose option 1 (means no extra luggage).
        ** just basically think think think in seat class how much capabilities (don't forget carry-on luggage capabilities) did you have and then how much you want in extra. 
        (step 6) if offer luggage option, do choose option 
        (step 7) go to payment page and done
        the tools need id of options, the id begin from 1, not 0
        some step will return notice and some raw information like seat option, luggage option, you need to parse them, reasoning before feed to tools.
        Call tool step by step, reasoning each step to book the flight, and stop when booking success """,
        agent=booking_agent,
        expected_output="return string all information about flight booking request"
)
    booking_crew = Crew(
        agents=[booking_agent],
        tasks=[input_task ],#, insert_inf_task, filter_flight_task, choose_seat_options
        verbose=True,
        planning=True,
    )

    # Run the crew
    result = booking_crew.kickoff()
    return result

def search_flight_inf(depart, destination, target_day, target_month, target_year, id_class, time_str, brand_str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,
                                    args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--no-first-run',
                    '--disable-extensions',
                    '--disable-plugins'
                ])  # Mở trình duyệt
        page = browser.new_page()
        page.goto("https://www.traveloka.com/vi-vn/flight")
        time.sleep(2)
        page.click('[data-testid="button-tab-ONE_WAY"]')
        page.wait_for_selector('[data-testid="airport-input-departure"]')
        from_box = page.locator('[data-testid="airport-input-departure"]')
        from_box.click()
        from_box.fill("")  # clear placeholder
        from_box.type(depart)    
        time.sleep(1)
        from_box.press("Enter")
        time.sleep(1)


    # nhập data cho điểm đến
        page.wait_for_selector('[data-testid="airport-input-destination"]')
        from_box = page.locator('[data-testid="airport-input-destination"]')
        from_box.click()
        from_box.fill("")  
        from_box.type(destination)
        time.sleep(1)
        from_box.press("Enter")

    #======chọn ngày=========
        page.click('[data-testid="departure-date-input"]')
        time.sleep(1)
        # month year hiện tại
        month_year_text = page.locator('[data-testid="calendar-month"]').nth(0).text_content()
        parts = month_year_text.strip().split()    
        current_month = int(parts[1])
        current_year = int(parts[3])

        while True:
            display_month = current_month
            display_year = current_year
            if display_year == target_year and display_month == target_month:
                break
            current_month+=1
            if current_month%13 ==0:
                current_year+=1
                current_month =1
            page.click('[data-id="IcSystemChevronRight16"]')

        selector = f'[data-testid="date-cell-{target_day}-{target_month}-{target_year}"]'
        page.click(selector)
        serch = page.locator('text="Tìm chuyến bay"')
        serch.click()
        page.wait_for_url("**/flight/fullsearch**")
        time.sleep(4)
    ##################

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

    ###################
        for _ in range(4):
            page.evaluate("window.scrollBy(0, window.innerHeight)")  # Scroll down one screen height
            time.sleep(1) 
        card_list = page.locator('[data-testid^="flight-inventory-card-container-"]')
        time_constrain = []
        brand_constrain = []
        target_time = datetime.strptime(time_str, "%H:%M")
        time_range = timedelta(minutes=40)
        earliest_time = (target_time - time_range).time()
        latest_time = (target_time + time_range).time()

    #loc chuyen bay theo hang và lay gia re nhat
        for i in range(card_list.count()):
            card = card_list.nth(i)
            lines = card.inner_text().strip().split('\n')
            result = {
                'hang_bay': lines[0].strip(),
                'gio_khoi_hanh': lines[1].strip(),
                'san_bay_di': lines[2].strip(),
                'thoi_gian_bay': lines[3].strip(),
                'gio_den': lines[5].strip(),
                'san_bay_den': lines[6].strip(),
                'gia': lines[7].strip()
            }
            #=======================
            if time_str != 'null':
                times = card.locator('div[dir="auto"]', has_text=re.compile(r'\d{2}:\d{2}'))
                if times.count() > 0:
                    depart_time = times.nth(0).text_content()
                    dep_time = datetime.strptime(depart_time, "%H:%M").time()
                    if (earliest_time > dep_time) or (dep_time > latest_time):
                        continue
            time_constrain.append(result)
            #=======================
            if brand_str != 'null':
                if card.locator(f'text={brand_str}').count() == 0:
                    continue
                brand_constrain.append(result) 


        
        if (len(time_constrain) == 0) and (time_str != 'null'):
            return('i dont find any fight in time you want')
        if len(brand_constrain) == 0:
            return('i dont find flight in brand you want but i find in list ZZZ have another brand')
    #chon chuyen bay re nhat
        return brand_constrain