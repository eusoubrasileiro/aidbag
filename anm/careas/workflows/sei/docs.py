from .....web.selenium import *
from enum import Enum

class HTMLDOC(Enum):
    NOTA_TECNICA = 1 # editable content iframe is "#cke_6_contents iframe"
    FORMULARIO_PRIORIDADE = 2 # editable content iframe is "#cke_4_contents iframe"


def insertHTMLDoc(driver, htmltext, mainwindow, doctype=HTMLDOC.NOTA_TECNICA):
    """
    Insert HTML code in an SEI editable HTML document
    Sei Doc that supports editing/insering raw HTML in it 
    like Nota Técnica, Formulário Prioridade etc.
    """
    iframe_selector = None
    savebutton_id = None 
    match doctype:
        case HTMLDOC.NOTA_TECNICA:
            # iframe_selector = "#cke_6_contents iframe"
            iframe_selector = "#cke_6_contents iframe"
            savebutton_id = "cke_262"
        case HTMLDOC.FORMULARIO_PRIORIDADE:            
            iframe_selector = "#cke_4_contents iframe"
            savebutton_id = "cke_142"

    click(driver, '#lblPublico.infraLabelRadio') # Publico
    click(driver, 'button#btnSalvar')        
    driver.switch_to.default_content() # go back to main document    
    # insert htmltext code 
    # select text-editor
    wait(driver, 10).until(expected_conditions.number_of_windows_to_be(2))
    # text window now open, but list of handles is not ordered
    textwindow = [hnd for hnd in driver.window_handles if hnd != mainwindow ][0]
    driver.switch_to.window(textwindow) # go to text pop up window
    htmltext = htmltext.replace('\n', '') # just to make sure dont mess with jscript                                
    def write_html_on_iframe():
        driver.switch_to.default_content() # go to parent main document
        switch_to_frame(driver, iframe_selector)
        editor = find_element(driver, "body") # just to enable save button        
        editor.clear()
        editor.send_keys(Keys.BACK_SPACE*42)        
        driver.switch_to.default_content() # go to parent main document                   
        # insert html code of template doc using javascript iframe.write 
        # using arguments 
        # https://stackoverflow.com/questions/52273298/what-is-arguments0-while-invoking-execute-script-method-through-webdriver-in
        jscript = f"""iframe = document.querySelector('{iframe_selector}');
        iframe.contentWindow.document.open();
        iframe.contentWindow.document.write(arguments[0]); 
        iframe.contentWindow.document.close();"""
        driver.execute_script(jscript, htmltext)        
        wait_for_ready_state_complete(driver) # it stalls the page                                    
        click(driver, "a[title*='Salvar']")            
    def check_write_on_iframe():
        driver.switch_to.default_content() # go to parent main document
        switch_to_frame(driver, iframe_selector)
        wait_for_element_presence(driver, "body#sei_edited") # body id to check it wrote            
    while True: # to guarantee it really gets written
        write_html_on_iframe() 
        # to garantee save, wait for button salvar to be disabled
        wait_for_element_presence(driver, 
            f"a#{savebutton_id}[class='cke_button cke_button__save cke_button_disabled']", 
            timeout=60) # very high timeout for save to no keep waiting                                          
        try:
            check_write_on_iframe()
        except NoSuchElementException:
            continue  
        else:
            break 
    driver.close() # close this window         
    