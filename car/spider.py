import os
import time
import requests
import threading
from bs4 import BeautifulSoup
from pathlib import Path
import sys

# 添加项目根目录到Python路径
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

# 从项目根目录导入数据库模块
from database import get_conn, save_data, init_table


def car(page=1):
    url = f"https://car.autohome.com.cn/2sc/china/a0_0msdgscncgpi1ltocsp{page}ex/"
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0'
    }
    save_dir = Path("car_img")
    save_dir.mkdir(exist_ok=True)
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = res.apparent_encoding
    except Exception as e:
        print(f"页面请求失败（页码：{page}）: {e}")
        return

    soup = BeautifulSoup(res.text, 'lxml')

    # 提取所有车名
    carname = [span.get_text(strip=True) for span in soup.select('.title')]
    # 提取所有汽车价格
    carmoney = [span.get_text(strip=True) for span in soup.select('.detail-r')]
    # 提取所有汽车年份和公里数
    caryear = [span.get_text(strip=True) for span in soup.select('.detail-l')]

    # 确保三个列表长度一致，避免数据错位
    min_length = min(len(carname), len(carmoney), len(caryear))
    carname = carname[:min_length]
    carmoney = carmoney[:min_length]
    caryear = caryear[:min_length]

    # 保存数据到MySQL
    try:
        conn = get_conn()
        # 每个线程不再重复初始化表（已在主线程初始化）
        save_data(conn, carname, carmoney, caryear)
        conn.close()
    except Exception as e:
        print(f"数据库操作失败（页码：{page}）: {e}")

    # 处理图片下载
    img_tags = soup.find_all('img', attrs={'name': 'LazyloadImg'})
    images = [(img['src2'], img['title']) for img in img_tags if 'src2' in img.attrs]

    session = requests.Session()
    session.headers.update(headers)

    for idx, (link, title) in enumerate(images, 1):
        # 补全协议
        if link.startswith("//"):
            link = "https:" + link

        ext = os.path.splitext(link)[1] or ".jpg"  # 取后缀，默认.jpg
        # 处理文件名特殊字符
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in title)
        file_path = save_dir / f"{safe_name}_{idx}{ext}"

        # 若文件已存在，自动加序号
        counter = 1
        while file_path.exists():
            counter += 1
            file_path = save_dir / f"{safe_name}_{idx}_{counter}{ext}"

        try:
            resp = session.get(link, timeout=15)
            resp.raise_for_status()
            file_path.write_bytes(resp.content)
            print(f"[OK]  {idx:02d}/{len(images)}  {file_path.name}")
        except Exception as e:
            print(f"[ERR] {idx:02d}/{len(images)}  {link}  ->  {e}")

        time.sleep(0.3)  # 控制爬取频率，避免被反爬


if __name__ == "__main__":
    # 主线程初始化数据表（只执行一次）
    try:
        conn = get_conn()
        init_table(conn)
        conn.close()
        print("数据表初始化完成")
    except Exception as e:
        print(f"初始化表失败: {e}")
        sys.exit(1)

    # 启动多线程爬取（1-100页）
    threads = []
    for i in range(1, 101):
        t = threading.Thread(target=car, args=(i,))
        threads.append(t)
        t.start()
        time.sleep(0.1)  # 错开线程启动时间，减少并发压力

    # 等待所有线程完成
    for t in threads:
        t.join()
    print('全部爬取完成')