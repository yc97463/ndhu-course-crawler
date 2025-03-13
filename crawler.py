from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import os

# 設定 WebDriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

options = webdriver.ChromeOptions()
options.add_argument("--headless")  # 隱藏瀏覽器
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 目標網站
url = "https://sys.ndhu.edu.tw/aa/class/course/Default.aspx"
driver.get(url)

# 等待頁面載入
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "ddlCOLLEGE")))

# 取得所有學院
college_select = Select(driver.find_element(By.NAME, "ddlCOLLEGE"))
colleges = {option.text.strip(): option.get_attribute("value").strip() for option in college_select.options if option.get_attribute("value") != "NA"}

# 儲存資料的結構
all_courses = {}  # 儲存至 `main.json`
course_details = {}  # 個別儲存至 `course/{sql_id}.json`

# 確保 course 目錄存在
if not os.path.exists("course"):
    os.makedirs("course")

# 先抓取前 N 個學院的資料測試
MAX_COLLEGES = 2
college_count = 0

for college_name, college_value in colleges.items():
    if college_count >= MAX_COLLEGES:
        break  # 達到限制後停止爬取
    college_count += 1
    
    print(f"🔄 正在處理學院：{college_name}")

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
            print(f"  🔄 正在處理系所：{department_name}")

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

                        # 建立 course/{sql_id}.json
                        if sql_id:
                            if sql_id not in course_details:
                                course_details[sql_id] = {
                                    "course_id": course_id,
                                    "sql_id": sql_id,
                                    "course_name": columns[6].text.strip(),
                                    "english_course_name": columns[11].text.strip(),
                                    "credits": columns[12].text.strip(),
                                    "teacher": [t.strip() for t in columns[13].text.strip().split("/") if t.strip()],
                                    "classroom": [t.strip() for t in columns[14].text.strip().split("/") if t.strip()],
                                    "class_time": [{"day": t[0], "period": t[1:]} for t in columns[3].text.strip().split("/") if t],
                                    "syllabus_link": columns[7].find_element(By.TAG_NAME, "a").get_attribute("href") if columns[7].find_elements(By.TAG_NAME, "a") else "",
                                    "teaching_plan_link": columns[8].find_element(By.TAG_NAME, "a").get_attribute("href") if columns[8].find_elements(By.TAG_NAME, "a") else "",
                                    "departments": []  # 紀錄該課程在哪些系所開課
                                }
                            course_details[sql_id]["departments"].append({
                                "college": college_name,
                                "department": department_name,
                                
                            })

                    # 儲存個別課程資料
                    for sql_id, data in course_details.items():
                        with open(f"course/{sql_id}.json", "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=4, ensure_ascii=False)

                if courses:
                    print(f"    ✅ {department_name} 抓取 {len(courses)} 門課程")
                    all_courses.update({course["sql_id"]: course["course_id"] for course in courses if course["sql_id"]})
                else:
                    print(f"    ❌ {department_name} 無開課資料")

            except Exception as e:
                print(f"    ❌ {department_name} 找不到課表，錯誤: {str(e)}")

    except Exception as e:
        print(f"❌ {college_name} 沒有可選擇的系所，錯誤: {str(e)}")

# 存成 main.json
with open("main.json", "w", encoding="utf-8") as f:
    json.dump(all_courses, f, indent=4, ensure_ascii=False)

print("\n🎉 爬取完成！已存入 `main.json` 與 `course/{sql_id}.json`")
driver.quit()
