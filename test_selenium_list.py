import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def run():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)
    
    driver.get("http://localhost:8080/index.html")
    time.sleep(2)
    
    rows = driver.find_elements(By.CSS_SELECTOR, "tbody#table-body tr")
    print(f"Initial rows: {len(rows)}")
    
    button = driver.find_element(By.ID, "todays-list-btn")
    button.click()
    time.sleep(2)
    
    rows_after = driver.find_elements(By.CSS_SELECTOR, "tbody#table-body tr")
    print(f"After Today's List click: {len(rows_after)} rows")
    
    for log in driver.get_log('browser'):
        print(log)
        
    driver.quit()

if __name__ == "__main__":
    run()
