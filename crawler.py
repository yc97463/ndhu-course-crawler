from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import os
import argparse

# 設定 WebDriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def setup_driver():
    options = webdriver.ChromeOptions()

    # 🟢 無頭模式（GitHub Actions 需要）
    options.add_argument("--headless")  # 運行在 GitHub Actions 需隱藏 UI
    options.add_argument("--no-sandbox")  # 避免 root 權限問題
    options.add_argument("--disable-dev-shm-usage")  # 避免 /dev/shm 空間不足
    options.add_argument("--disable-gpu")  # 無頭模式下不需要 GPU 渲染，避免錯誤

    # 🟢 避免 Selenium 被偵測為自動化工具
    options.add_argument("--disable-blink-features=AutomationControlled")  
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 🟢 視窗設定（避免特定網站 UI 錯誤）
    options.add_argument("--window-size=1280,720")  # 設定瀏覽器解析度
    options.add_argument("start-maximized")  # 最大化視窗，避免某些網站 UI 問題

    # 🟢 設定 User-Agent（模仿真實使用者）
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    )

    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def get_semesters(driver):
    # 目標網站
    url = "https://sys.ndhu.edu.tw/aa/class/course/Default.aspx"
    driver.get(url)

    # 等待頁面載入
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "ddlCOLLEGE")))

    # 取得所有學期
    semester_select = Select(driver.find_element(By.NAME, "ddlYEAR"))
    semesters = {option.text.strip(): option.get_attribute("value").strip() for option in semester_select.options}
    return semesters

def crawl_semester(driver, semester_name, semester_value):
    # 學期目錄名稱格式: "113-2"
    semester_dir = semester_value.replace("/", "-")
    print(f"🔄 正在處理學期：{semester_name} ({semester_dir})")
    
    # 跳過超過通常的學期
    if semester_dir.split("-")[-1] > "2":
        print(f"👋 {semester_name} 超過通常的學期，跳過")
        return
    
    # 105 學年度之前的學期不處理
    if semester_dir.split("-")[0] < "105":
        print(f"👋 {semester_name} 105 學年度之前的學期，跳過")
        return
    
    # 選擇學期
    semester_select = Select(driver.find_element(By.NAME, "ddlYEAR"))
    semester_select.select_by_value(semester_value)
    time.sleep(3)  # 等待 JavaScript 更新
    
    # 建立學期目錄
    if not os.path.exists(semester_dir):
        os.makedirs(semester_dir)
    
    # 建立課程目錄
    course_dir = os.path.join(semester_dir, "course")
    if not os.path.exists(course_dir):
        os.makedirs(course_dir)
    
    # 儲存資料的結構
    all_courses = {}  # 儲存至 `{semester_dir}/main.json`
    course_details = {}  # 個別儲存至 `{semester_dir}/course/{course_id}.json`

    # 取得所有學院
    college_select = Select(driver.find_element(By.NAME, "ddlCOLLEGE"))
    colleges = {option.text.strip(): option.get_attribute("value").strip() for option in college_select.options if option.get_attribute("value") != "NA"}

    for college_name, college_value in colleges.items():    
        print(f"  🔄 正在處理學院：{college_name}")

        # 選擇學院
        college_select = Select(driver.find_element(By.NAME, "ddlCOLLEGE"))
        college_select.select_by_value(college_value)
        time.sleep(3)  # 等待 JavaScript 更新

        # 取得對應系所
        try:
            department_select = Select(driver.find_element(By.NAME, "ddlDEP"))
            departments = {
                option.text.strip(): option.get_attribute("value").strip()
                for option in department_select.options if option.get_attribute("value") != "NA"
            }

            for department_name, department_value in departments.items():
                print(f"    🔄 正在處理系所：{department_name}")

                # 選擇系所
                department_select = Select(driver.find_element(By.NAME, "ddlDEP"))
                department_select.select_by_value(department_value)
                time.sleep(3)  # 等待 JavaScript 更新

                # 點擊查詢按鈕
                search_button = driver.find_element(By.NAME, "btnCourse")
                driver.execute_script("arguments[0].click();", search_button)  # 強制點擊
                time.sleep(5)  # 等待表格載入

                # 檢查頁面是否正確載入
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

                # 嘗試抓取課程表
                courses = []
                try:
                    table = driver.find_element(By.ID, "GridView1")
                    rows = table.find_elements(By.TAG_NAME, "tr")[1:]  # 跳過 header

                    for row in rows:
                        columns = row.find_elements(By.TAG_NAME, "td")
                        if len(columns) >= 10:
                            course_id = columns[5].text.strip()
                            sql_id = columns[7].find_element(By.TAG_NAME, "a").get_attribute("href").split("=")[-1] if columns[7].find_elements(By.TAG_NAME, "a") else ""

                            course_data = {
                                "campus": columns[0].text.strip(),
                                "department": columns[1].text.strip(),
                                "course_id": course_id,
                                "sql_id": sql_id,
                                "course_name": columns[6].text.strip(),
                                "syllabus_link": columns[7].find_element(By.TAG_NAME, "a").get_attribute("href") if columns[7].find_elements(By.TAG_NAME, "a") else "",
                                "teaching_plan_link": columns[8].find_element(By.TAG_NAME, "a").get_attribute("href") if columns[8].find_elements(By.TAG_NAME, "a") else "",
                                "class_time": columns[3].text.strip(),
                                "english_course_name": columns[11].text.strip(),
                                "credits": columns[12].text.strip(),
                                "teacher": columns[13].text.strip(),
                                "classroom": columns[14].text.strip(),
                                "offering_department": department_name,
                                "college": college_name
                            }
                            courses.append(course_data)

                            # 使用 course_id 來建立檔案
                            if course_id:
                                if course_id not in course_details:
                                    course_details[course_id] = {
                                        "course_id": course_id,
                                        "sql_id": sql_id,
                                        "course_name": columns[6].text.strip(),
                                        "english_course_name": columns[11].text.strip(),
                                        "credits": columns[12].text.strip(),
                                        "teacher": [t.strip() for t in columns[13].text.strip().split("/") if t.strip()],
                                        "classroom": [t.strip() for t in columns[14].text.strip().split("/") if t],
                                        "class_time": [{"day": t[0], "period": t[1:]} for t in columns[3].text.strip().split("/") if t],
                                        "syllabus_link": columns[7].find_element(By.TAG_NAME, "a").get_attribute("href") if columns[7].find_elements(By.TAG_NAME, "a") else "",
                                        "teaching_plan_link": columns[8].find_element(By.TAG_NAME, "a").get_attribute("href") if columns[8].find_elements(By.TAG_NAME, "a") else "",
                                        "departments": []  # 紀錄該課程在哪些系所開課
                                    }
                                course_details[course_id]["departments"].append({
                                    "college": college_name,
                                    "department": department_name,
                                })

                    # 儲存個別課程資料到對應的學期目錄
                    for course_id, data in course_details.items():
                        with open(f"{course_dir}/{course_id}.json", "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=4, ensure_ascii=False)

                    if courses:
                        print(f"      ✅ {department_name} 抓取 {len(courses)} 門課程")
                        all_courses.update({course["course_id"]: course for course in courses if course["course_id"]})
                    else:
                        print(f"      ❌ {department_name} 無開課資料")

                except Exception as e:
                    print(f"      ❌ {department_name} 找不到課表，錯誤: {str(e)}")

        except Exception as e:
            print(f"    ❌ {college_name} 沒有可選擇的系所，錯誤: {str(e)}")

    # 將學期課程資料存入 {semester_dir}/main.json
    with open(f"{semester_dir}/main.json", "w", encoding="utf-8") as f:
        json.dump(all_courses, f, indent=4, ensure_ascii=False)
    
    print(f"✅ 已完成學期 {semester_name} 的資料爬取")

def main():
    parser = argparse.ArgumentParser(description='Crawl course data from NDHU course system')
    parser.add_argument('--semester', help='Specific semester to crawl (e.g., 113-2)')
    args = parser.parse_args()

    driver = setup_driver()
    try:
        semesters = get_semesters(driver)
        
        if args.semester:
            # 只爬取指定的學期
            semester_value = args.semester.replace("-", "/")
            if semester_value in semesters.values():
                semester_name = [k for k, v in semesters.items() if v == semester_value][0]
                crawl_semester(driver, semester_name, semester_value)
            else:
                print(f"❌ 找不到指定的學期：{args.semester}")
        else:
            # 爬取所有學期時才生成 semester.json
            semester_list = [semester_value.replace("/", "-") for semester_value in semesters.values()]
            with open("semester.json", "w", encoding="utf-8") as f:
                json.dump(semester_list, f, indent=4, ensure_ascii=False)
            
            for semester_name, semester_value in semesters.items():
                crawl_semester(driver, semester_name, semester_value)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
