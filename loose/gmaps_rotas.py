from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait as wait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
import platform
from bs4 import BeautifulSoup 
import re, time, os


def set_route(driver, origin, destination):
    driver.get("https://www.google.com/maps/")

    element = wait(driver, 10).until(
            expected_conditions.visibility_of_element_located((By.ID, "searchboxinput")))
    element.send_keys(destination) # origen
    element.send_keys(Keys.ENTER)
    rotas = wait(driver, 10).until(
                expected_conditions.visibility_of_element_located((By.CSS_SELECTOR, "button[data-value='Rotas']")))
    rotas.click()
    # driver.find_element_by_css_selector("button[data-value='Rotas']").click() # rotas 
    partida= wait(driver, 10).until(
                expected_conditions.visibility_of_element_located((By.XPATH, 
                "//input[@class='tactile-searchbox-input' and @placeholder and contains(@aria-label, 'partida')]")))
    
    # partida = driver.find_element_by_css_selector("input[role='combobox'][aria-label='Escolher ponto de partida ou clicar no mapa...']")
    partida.send_keys(origin)  # origin
    partida.send_keys(Keys.ENTER)

def get_time(driver):
    wait(driver, 10).until(
                expected_conditions.visibility_of_element_located((By.CSS_SELECTOR, 
                "img[aria-label='  Carro  ']"))) # if this image is present time is loaded
    soup = BeautifulSoup(driver.page_source, features="lxml")
    time = soup.findAll('span', text=re.compile(".*min"), jstcache=True, recursive=True)[0]
    time = float(time.text.strip('min').strip())
    return time    

def get_times_round_trip(driver, origin, destination):
    """return round trip times from google-maps destinations"""
    set_route(driver, origin, destination)
    going = get_time(driver)
    #time.sleep(4)
    set_route(driver, destination, origin)
    back = get_time(driver)
    return going, back 

def get_times(driver):
    """when setting a specific data to get estimated times
    a minimal and maximum time as returned"""
    wait(driver, 10).until(
            expected_conditions.visibility_of_element_located((By.CSS_SELECTOR, 
            "img[aria-label='  Carro  ']"))) # if this image is present time is loaded
    soup = BeautifulSoup(driver.page_source, features="lxml")
    times = soup.findAll('span', text=re.compile(".*min"), jstcache=True, recursive=True)[0]
    time_min, time_max = list(map(float, times.text.strip('min').strip().split('-')))
    return time_min, time_max


if __name__ == "__main__":
    
    destinations = { 'bernardino-peregrinos' : ('-19.653687,-43.981871', 'igreja presbiteriana peregrinos'),
                    'andreia-peregrinos' : ('rosa dos ventos vespasiano', 'igreja presbiteriana peregrinos'),
                    'tiradentes-peregrinos' : ('Condomínio Tiradentes de São José da Lapa', 'igreja presbiteriana peregrinos'),
                    'ipes-sj-lapa-peregrinos' : ('Quintas dos Ipês São josé da Lapa', 'igreja presbiteriana peregrinos')
                    }

    if platform.system() == "Linux":
      options = webdriver.FirefoxOptions()
      options.add_argument("--headless") # to hide window in 'background'
      cwebdriver = webdriver.Firefox
    else: # Chrome Windows      
      options = webdriver.ChromeOptions()
      options.add_argument("--headless") # to hide window in 'background'
      cwebdriver = webdriver.Chrome
            
    # better use chromium on linux faster and easier to install.. like
    with cwebdriver(options=options) as driver: 
        while(True):
            for route_name, origin_destination in destinations.items():
                try: 
                    origin, destination = origin_destination
                    going, back = get_times_round_trip(driver, origin, destination)
                    print(' '.join([time.strftime("%X %x"), route_name, str(going), str(back)]))
                    with open('lote_rotas.txt', 'a') as file:
                        file.write(' '.join([time.strftime("%X %x"), route_name, str(going), str(back), '\n']))
                except Exception as exc:
                    print(route_name, exc)
                    #raise(exc)
            time.sleep(30*60) # wait 30 mins