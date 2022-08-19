from selenium.webdriver import Chrome
from selenium.webdriver import ChromeOptions
from selenium.common.exceptions import (
    WebDriverException, 
    TimeoutException, 
    NoSuchElementException, 
    ElementNotVisibleException
)
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait as wait
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select # drop down select
from selenium.common.exceptions import (
    StaleElementReferenceException
    )

import json 

import time, sys
from bs4 import BeautifulSoup
import re 

from seleniumbase import BaseCase
bs = BaseCase() 
#bs.type()
#driver = Chrome()       
#bs.switch_to_default_content


        
# Ideas mainly based on SeleniumBase 
# since I could not make it usable for my use case
# https://github.com/seleniumbase/SeleniumBase/blob/master/seleniumbase/fixtures/base_case.py


def switch_to_frame(driver, selector, by=By.CSS_SELECTOR, timeout=10):
    """Wait for an iframe to appear, and switch to it. 
    
    * selector - the selector of the iframe
    * frame - the frame element, name, id, index, or selector
    * timeout - the time to wait for the alert in seconds
    """
    frame = wait_for_element_visible(driver, selector, by)
    driver.switch_to.frame(frame)    
        

def send_keys(driver, selector, text, by=By.CSS_SELECTOR, timeout=10, 
              retry_count=3):
    """This method 'send_keys' to an element's text field.
    
    Has multiple parts:
    - Find the element
    - Waits for the element to be visible.
    - Waits for the element to be interactive.
    - Clears the text field. (not doing!)
    - Types in the new text.    
    - Hits Enter/Submit (if the text ends in '\\n').
    
    Params
    * selector - the selector of the text field
    * text - the new text to type into the text field
    * by - the type of selector to search by (Default: CSS Selector)
    * timeout - how long to wait for the selector to be visible
    
    """
    element = driver.find_element(by, selector)    
    wait_until(driver, selector, expected_conditions.visibility_of_element_located, by, timeout)   
    #wait(driver, 10).until(expected_conditions.visibility_of_element_located())             
    try:        
        if text.endswith("\n"): # send Enter also
            text = text + Keys.ENTER
        element.send_keys(text)
    except StaleElementReferenceException:
        wait_for_ready_state_complete(driver)    
        send_keys(driver, selector, text, by, timeout, retry_count-1)


def click(driver, selector, by=By.CSS_SELECTOR, timeout=10, retry=3, jsclick=False):
    """This method 'click' to an element 
    
    Params
    * selector - the selector of the text field
    * text - the new text to type into the text field
    * by - the type of selector to search by (Default: CSS Selector)
    * timeout - how long to wait for the selector to be visible
    """
    element = wait_until(driver, selector, 
                         expected_conditions.presence_of_element_located, by, timeout)   

    if retry > 0 and not jsclick:
        try:
            scrool_to_element(driver, element)
            element = wait_for_element_visible(driver, selector, by)            
            # dont use wait for element to be clickable - seleniumbase method
            element.click()
        except StaleElementReferenceException:
            wait_for_ready_state_complete(driver)
            time.sleep(0.05)
            click(driver, selector, by, timeout, retry-1)
        except ElementNotVisibleException: # element present but not visible
            click(driver, selector, by, timeout, jsclick=True)            
            # link hidden on a div, can just be open if it is valid 
            # look at click_link_text seleniumbase
            # self.open(self.__get_href_from_link_text(link_text)) 
            # href = element.get_attribute('href')
            # driver.open(href)
    else:
        # did not work wit selenium try with javascript
        # possible is in a permanent overlay by other elements of the page
        # so it'll never be 'clickable'
        # https://stackoverflow.com/a/46601444/1207193
        # no other option then click in it using javascript   
        if by == By.CSS_SELECTOR:
            # json dumpstring already fixes all ' or " quotes problems for javascript
            driver.execute_script(f"document.querySelector({json.dumps(selector)}).click()")
        if by == By.XPATH:
            getbyxpath_jscript = """
            function getElementByXpath(path) {
                return document.evaluate(path, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            };
            """
            jscript = getbyxpath_jscript + f"getElementByXpath({json.dumps(selector)}).click();"
            driver.execute_script(jscript)
        # assume it suceed
     
     
def find_element(driver, selector, by=By.CSS_SELECTOR):
   return driver.find_element(by, selector)

def find_elements(driver, selector, by=By.CSS_SELECTOR):
   return driver.find_elements(by, selector)

def wait_until(driver, selector, expected_condition, 
               by=By.CSS_SELECTOR,
               timeout=10):
    return wait(driver, timeout).until(expected_condition((by, selector)))


def try_accept_alert(driver):
    """try dismiss aler if it shows up, if it doesn't dont botter"""
    try :                
        alert = wait(driver, 5).until(expected_conditions.alert_is_present()) 
        alert.accept()
    except:
        pass 
    

# from seleniumbase/fixtures/js_utils.py
def wait_for_ready_state_complete(driver, timeout=3):
    """
    The DOM (Document Object Model) has a property called "readyState".
    When the value of this becomes "complete", page resources are considered
      fully loaded (although AJAX and other loads might still be happening).
    This method will wait until document.readyState == "complete".
    This may be redundant, as methods already wait for page elements to load.
    """
    start_ms = time.time() * 1000.0
    stop_ms = start_ms + (timeout * 1000.0)
    for x in range(int(timeout * 10)):
        try:
            ready_state = driver.execute_script("return document.readyState;")
        except WebDriverException:
            # Bug fix for: [Permission denied to access property "document"]
            time.sleep(0.03)
            return True
        if ready_state == "complete":
            time.sleep(0.01)  # Better be sure everything is done loading
            return True
        else:
            now_ms = time.time() * 1000.0
            if now_ms >= stop_ms:
                break
            time.sleep(0.1)
    return False  # readyState stayed "interactive" (Not "complete")


def scrool_to_element(driver, element):
    element_y = element.location["y"]
    scroll_script = f"window.scrollTo(0, {element_y});" 
    driver.execute_script(scroll_script)
    

# to never use wait for element to be clickable
def wait_for_element_visible(driver, selector, by=By.CSS_SELECTOR,  timeout=5):
    """
    Searches for the specified element by the given selector. Returns the
    element object if the element is present and visible on the page.
    Raises NoSuchElementException if the element does not exist in the HTML
    within the specified timeout.
    Raises ElementNotVisibleException if the element exists in the HTML,
    but is not visible (eg. opacity is "0") within the specified timeout.
    
    - driver - the webdriver object (required)
    - selector - the locator for identifying the page element (required)
    - by - the type of selector being used (Default: By.CSS_SELECTOR)
    - timeout - the time to wait for elements in seconds
    
    - Returns
    A web element object
    """
    element = None
    is_present = False
    start_ms = time.time() * 1000.0
    stop_ms = start_ms + (timeout * 1000.0)
    for x in range(int(timeout * 10)):  # each step is 0.1 s      
        try:
            element = driver.find_element(by=by, value=selector)
            is_present = True
            if element.is_displayed():
                return element
            else:
                element = None
                raise Exception()
        except Exception:
            now_ms = time.time() * 1000.0
            if now_ms >= stop_ms:
                break
            time.sleep(0.1)
    if not is_present: # The element does not exist in the HTML        
        message = f"Element {selector} was not present after {timeout} second%s!"
        raise NoSuchElementException(message)
    if is_present: # The element exists in the HTML, but is not visible
        message = f"Element {selector} was not visible after {timeout} second%s!" 
        raise ElementNotVisibleException(message)
    