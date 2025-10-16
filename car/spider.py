import os
import time
import requests
import threading
from bs4 import BeautifulSoup
from pathlib import Path
import sys
import qiniu

# 添加项目根目录到Python路径
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

# 从项目根目录导入数据库模块
from database import get_conn, save_data, init_table


# 七牛云密钥和bucket配置
access_key = 'j_afhONjyWahQI0k4bGme1tGMr-W-AXKvTAGvk1J'
secret_key = '7LcJJ2DV7VP6iY991evMgRIvlzn2prdmuwjr69lz'
bucket_name = 'notnew-car'

# 七牛云初始化
q = qiniu.Auth(access_key, secret_key)
bucket = qiniu.BucketManager(q)


# 统一safe_name处理
def safe_name(name):
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in name)


def upload_to_bucket(local_path, key):
    token = q.upload_token(bucket_name, key)
    ret, info = qiniu.put_file(token, key, local_path)
    return info.status_code == 200


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

    title_count = {}
    for idx, (link, title) in enumerate(images, 1):
        # 补全协议
        if link.startswith("//"):
            link = "https:" + link

        ext = os.path.splitext(link)[1] or ".jpg"
        sname = safe_name(title)
        # 统计同名图片序号
        if sname not in title_count:
            title_count[sname] = 1
        else:
            title_count[sname] += 1
        img_index = title_count[sname]
        file_path = save_dir / f"{sname}_{img_index}{ext}"

        try:
            resp = session.get(link, timeout=15)
            resp.raise_for_status()
            file_path.write_bytes(resp.content)
            print(f"[OK]  {idx:02d}/{len(images)}  {file_path.name}")
        except Exception as e:
            print(f"[ERR] {idx:02d}/{len(images)}  {link}  ->  {e}")

        time.sleep(0.3)  # 控制爬取频率，避免被反爬

        # 保存图片到七牛云
        try:
            img_key = f"car_images/{sname}_{img_index}{ext}"
            upload_to_bucket(str(file_path), img_key)
            print(f"[UPL] {file_path.name} -> 七牛云成功")
        except Exception as e:
            print(f"[UPL_ERR] {file_path.name} -> 七牛云失败: {e}")


# 清空bucket所有文件
def clear_bucket():
    bucket_files = bucket.list(bucket_name)[0].get('items', [])
    for item in bucket_files:
        bucket.delete(bucket_name, item['key'])



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