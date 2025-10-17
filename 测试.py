import requests
from bs4 import BeautifulSoup
import html
import sys
import pymysql
from car.database import get_conn

conn = get_conn()
with conn.cursor(pymysql.cursors.DictCursor) as cursor:
    cursor.execute('SELECT caryear FROM carprice LIMIT 10')
    results = cursor.fetchall()
    print('caryear示例数据:')
    for row in results:
        print(row)
        
    # 检查年份提取
    cursor.execute("""
        SELECT 
            caryear,
            SUBSTRING_INDEX(SUBSTRING_INDEX(caryear, '年份： ', -1), '年', 1) as extracted_year
        FROM carprice
        WHERE caryear LIKE '%年份： %年%'
        LIMIT 5
    """)
    year_results = cursor.fetchall()
    print("\n年份提取结果:")
    for row in year_results:
        print(row)
    
    # 检查里程提取
    cursor.execute("""
        SELECT 
            caryear,
            CASE 
                WHEN caryear LIKE '%万公里%' THEN 
                    CAST(REPLACE(SUBSTRING_INDEX(SUBSTRING_INDEX(caryear, '公里：', -1), '万公里', 1), '万', '') AS DECIMAL(10,2)) * 10000
                WHEN caryear LIKE '%公里%' THEN 
                    CAST(REPLACE(SUBSTRING_INDEX(SUBSTRING_INDEX(caryear, '公里：', -1), '公里', 1), ',', '') AS UNSIGNED)
            END as extracted_mileage
        FROM carprice
        WHERE caryear LIKE '%公里：%%公里%'
        LIMIT 5
    """)
    mileage_results = cursor.fetchall()
    print("\n里程提取结果:")
    for row in mileage_results:
        print(row)
    
    # 检查平均年份查询
    cursor.execute("""
        SELECT AVG(CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(caryear, '年份： ', -1), '年', 1) AS UNSIGNED)) as avg_year
        FROM carprice
        WHERE caryear LIKE '%年份： %年%'
    """)
    avg_year_result = cursor.fetchone()
    print("\n平均年份查询结果:")
    print(avg_year_result)
    
    # 检查平均里程查询
    cursor.execute("""
        SELECT AVG(
            CASE 
                WHEN caryear LIKE '%万公里%' THEN 
                    CAST(REPLACE(SUBSTRING_INDEX(SUBSTRING_INDEX(caryear, '公里：', -1), '万公里', 1), '万', '') AS DECIMAL(10,2)) * 10000
                WHEN caryear LIKE '%公里%' THEN 
                    CAST(REPLACE(SUBSTRING_INDEX(SUBSTRING_INDEX(caryear, '公里：', -1), '公里', 1), ',', '') AS UNSIGNED)
            END
        ) as avg_mileage
        FROM carprice
        WHERE caryear LIKE '%公里：%%公里%'
    """)
    avg_mileage_result = cursor.fetchone()
    print("\n平均里程查询结果:")
    print(avg_mileage_result)
    
conn.close()

page_url = "https://car.autohome.com.cn/2sc/china/a0_0msdgscncgpi1ltocsp1ex/"
headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0'
    }

try:
    res = requests.get(page_url, headers=headers, timeout=10)
    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, 'lxml')

    # 提取所有li标签中"page"属性的值 页面标识
    page_values = [li.get('page') for li in soup.select('li[page]')]
    # 过滤空值并转换为整数
    page_values = [int(page) for page in page_values if page]

    # 提取infoid的值 车辆ID
    infoid_values = [li.get('infoid') for li in soup.select('li[infoid]')]
    infoid_values = [int(infoid) for infoid in infoid_values if infoid]
    # 提取dealerid 经销商ID
    dealerid_values = [li.get('dealerid') for li in soup.select('li[dealerid]')]
    dealerid_values = [int(dealerid) for dealerid in dealerid_values if dealerid]

    try:
        # 获取详细页链接
        detail_url = f"https://www.che168.com/dealer/{dealerid_values}/{infoid_values}.html"
        # # 提取所有车名（车辆名称列表）
        # vehicle_names = [span.get_text(strip=True) for span in soup.select('.title')]
        # # 提取所有汽车价格（车辆价格列表）
        # vehicle_prices = [span.get_text(strip=True) for span in soup.select('.detail-r')]
        # # 提取所有汽车年份和公里数（车辆年份与里程列表）
        # vehicle_year_mileage = [span.get_text(strip=True) for span in soup.select('.detail-l')]
        # # 提取上牌时间
        # register_time = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("上牌时间"))')]
        # # 提取表显里程
        # mileage = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("表显里程"))')]
        # # 提取变速箱
        # gearbox = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("变速箱"))')]
        # # 提取排放标准
        # emission_standard = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("排放标准"))')]
        # # 提取排量
        # displacement = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("排量"))')]
        # # 提取发布时间
        # release_time = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("发布时间"))')]
        # # 提取出险查询文本（含链接描述）
        # insurance_query_text = [html.unescape(li.find('a', class_='link-check').get_text(strip=True)) for li in
        #                         soup.select('.basic-item-ul li:has (span.item-name:contains ("出险查询"))') if
        #                         li.find('a', class_='link-check')]
        # # 提取年检到期时间
        # inspection_due = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("年检到期"))')]
        # # 提取保险到期时间
        # insurance_due = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("保险到期"))')]
        # # 提取质保到期时间
        # warranty_due = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("质保到期"))')]
        # # 提取维修保养查询文本（含链接描述）
        # maintenance_query_text = [html.unescape(li.find('a', id='btnQueryMaintain').get_text(strip=True)) for li in
        #                           soup.select('.basic-item-ul li:has (span.item-name:contains ("维修保养"))') if
        #                           li.find('a', id='btnQueryMaintain')]
        # # 提取过户次数
        # transfer_count = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("过户次数"))')]
        # # 提取车辆所在地
        # location = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li#citygroupid:has (span.item-name:contains ("所在地"))')]
        # # 提取发动机信息
        # engine = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("发动机"))')]
        # # 提取车辆级别
        # car_level = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("车辆级别"))')]
        # # 提取车身颜色
        # body_color = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("车身颜色"))')]
        # # 提取燃油标号
        # fuel_grade = [
        #     html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
        #     for li in soup.select('.basic-item-ul li:has (span.item-name:contains ("燃油标号"))')]
        # 提取驱动方式
        drive_mode = [
            html.unescape(li.get_text(strip=True).replace(li.find('span', class_='item-name').get_text(strip=True), ''))
            for li in soup.select('.basic-item-ul li:has(span.item-name:contains ("驱动方式"))')]
        print(drive_mode)

    except Exception as e:
        print(f"详细页请求失败: {e}")



except Exception as e:
    print(f"页面请求失败: {e}")

