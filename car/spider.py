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
    res = requests.get(url, headers=headers)
    res.encoding = res.apparent_encoding

    soup = BeautifulSoup(res.text, 'lxml')

    # 提取所有车名
    carname = [span.get_text(strip=True) for span in soup.select('.title')]
    # 提取所有汽车价格
    carmoney = [span.get_text(strip=True) for span in soup.select('.detail-r')]

    # 保存数据到MySQL
    try:
        conn = get_conn()
        init_table(conn)
        save_data(conn, carname, carmoney)
        conn.close()
    except Exception as e:
        print(f"数据库操作失败: {e}")

    img_tags = soup.find_all('img', attrs={'name': 'LazyloadImg'})
    images = [(img['src2'], img['title']) for img in img_tags if 'src2' in img.attrs]
    # -------------------- 下载并保存 --------------------
    session = requests.Session()
    session.headers.update(headers)

    for idx, (link, title) in enumerate(images, 1):
        # 补全协议
        if link.startswith("//"):
            link = "https:" + link

        ext = os.path.splitext(link)[1] or ".jpg"  # 取后缀，默认.jpg
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

        time.sleep(0.3)


if __name__ == "__main__":
    threads = []
    for i in range(1, 101):
        t = threading.Thread(target=car, args=(i,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    print('全部完成')