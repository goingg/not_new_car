from bs4 import BeautifulSoup
from pathlib import Path
import threading
import requests
import time
import sys
import os
import qiniu
import re
import html
import pymysql

# 添加项目根目录到Python路径
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

# 从项目根目录导入数据库模块
from database import get_conn, save_data, init_table
from utils import safe_name, q, BUCKET_NAME

# 配置请求会话，增加重试机制和超时设置
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=3)
session.mount('http://', adapter)
session.mount('https://', adapter)


def upload_to_bucket(local_path, key):
    # 检查文件是否存在
    if not os.path.exists(local_path):
        print(f"[UPL_ERR] 文件不存在: {local_path}")
        return False
        
    try:
        token = q.upload_token(BUCKET_NAME, key)
        ret, info = qiniu.put_file(token, key, local_path)
        return info.status_code == 200
    except Exception as e:
        print(f"[UPL_ERR] {os.path.basename(local_path)} -> 七牛云失败: {e}")
        return False


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
        res = session.get(url, headers=headers, timeout=(5, 10))
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
            resp = session.get(link, timeout=(5, 15))
            resp.raise_for_status()
            file_path.write_bytes(resp.content)
            print(f"[OK]  {idx:02d}/{len(images)}  {file_path.name}")
        except Exception as e:
            print(f"[ERR] {idx:02d}/{len(images)}  {link}  ->  {e}")
            continue

        time.sleep(0.3)  # 控制爬取频率，避免被反爬

        # 保存图片到七牛云
        try:
            img_key = f"car_images/{sname}_{img_index}{ext}"
            if upload_to_bucket(str(file_path), img_key):
                print(f"[UPL] {file_path.name} -> 七牛云成功")
        except Exception as e:
            print(f"[UPL_ERR] {file_path.name} -> 七牛云失败: {e}")


def reset_database():
    """重置数据库：删除现有数据库并重新创建"""
    try:
        # 连接到默认数据库（不指定db_name）
        temp_conn = pymysql.connect(
            host='localhost',
            port=3306,
            user='root',
            passwd='1234',
            charset='utf8mb4',
            connect_timeout=10
        )
        
        # 删除现有数据库
        drop_database(temp_conn, 'car')
        
        # 创建新数据库
        create_database(temp_conn, 'car')
        temp_conn.close()
        
        # 初始化表结构
        conn = get_conn()
        init_table(conn)
        conn.close()
        
        print("数据库重置完成")
        return True
    except Exception as e:
        print(f"数据库重置失败: {e}")
        return False


def drop_database(conn, db_name):
    """删除数据库"""
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS {db_name}")
            conn.commit()
            print(f"数据库 {db_name} 删除成功")
    except Exception as e:
        print(f"删除数据库失败: {e}")
        conn.rollback()


def create_database(conn, db_name):
    """创建数据库"""
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4")
            conn.commit()
            print(f"数据库 {db_name} 创建成功")
    except Exception as e:
        print(f"创建数据库失败: {e}")
        conn.rollback()


if __name__ == "__main__":
    # 重置数据库
    print("正在重置数据库...")
    if not reset_database():
        print("数据库重置失败，程序退出")
        sys.exit(1)
    
    # 清空图片目录
    save_dir = Path("car_img")
    if save_dir.exists():
        import shutil
        shutil.rmtree(save_dir)
    save_dir.mkdir(exist_ok=True)
    
    print("开始爬取前100页数据...")
    
    # 启动多线程爬取（1-100页）
    threads = []
    active_threads = []
    
    for i in range(1, 101):  # 爬取前100页
        t = threading.Thread(target=car, args=(i,))
        threads.append(t)
        active_threads.append(t)
        t.start()
        
        # 控制并发数量，避免过多连接
        if len(active_threads) >= 3:  # 最多同时运行3个线程
            # 等待最早开始的线程完成
            active_threads[0].join(timeout=60)  # 设置超时时间
            active_threads.pop(0)
        
        time.sleep(1)  # 错开线程启动时间，减少并发压力

    # 等待所有线程完成
    for t in active_threads:
        t.join(timeout=60)  # 设置超时时间
    print('全部爬取完成')