from flask import Flask, render_template, request, send_from_directory
import os
from pathlib import Path
import sys

# 配置项目路径
project_root = os.path.join(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# 导入数据库操作模块
from database import get_conn, read_data

app = Flask(__name__, static_folder='static')


def get_car_data(page=1, per_page=24):
    """获取分页的汽车数据（数据库和图片解析）"""
    cars = []
    total_count = 0  # 总记录数
    try:
        conn = get_conn()
        # 从数据库读取分页数据和总记录数
        cars, total_count = read_data(conn, page=page, per_page=per_page)
    except Exception as e:
        print(f"数据库读取失败: {e}")

    # 处理数据库数据（补充图片路径）
    if cars:
        car_img_dir = Path("car_img")
        if car_img_dir.exists():
            image_files = list(car_img_dir.glob("*.jpg"))
            # 创建一个图片使用记录
            used_images = set()
            for i, car in enumerate(cars):
                # 根据车辆名称匹配图片
                car_name = car['name']
                matched_image = None
                
                # 首先尝试精确匹配
                for img_file in image_files:
                    if img_file.name not in used_images and car_name in img_file.name:
                        matched_image = img_file
                        break
                
                # 如果没有精确匹配，尝试模糊匹配
                if not matched_image:
                    for img_file in image_files:
                        if img_file.name not in used_images and car_name.split()[0] in img_file.name:
                            matched_image = img_file
                            break
                
                # 记录已使用的图片
                if matched_image:
                    used_images.add(matched_image.name)
                    car['image_path'] = f"/car_img/{matched_image.name}"
                else:
                    car['image_path'] = "/static/img/1.webp"
                
                car['year'] = car.get('year', "未知")
                car['mileage'] = car.get('mileage', "里程待询")
        return cars, total_count

    # 数据库无数据时，从图片解析
    car_img_dir = Path("car_img")
    all_cars = []
    if car_img_dir.exists():
        image_files = list(car_img_dir.glob("*.jpg"))[:2000]  # 限制最大数量
        processed_names = set()
        for img_file in image_files:
            filename = img_file.stem
            parts = filename.split('_')[0].split()
            if len(parts) >= 2:
                brand = parts[0]
                model = ' '.join(parts[1:-1]) if len(parts) > 2 else parts[1]
                year = parts[-1] if (parts[-1].isdigit() and len(parts[-1]) == 4) else "未知"
                car_key = f"{brand}_{model}"
                if car_key not in processed_names:
                    all_cars.append({
                        'brand': brand,
                        'model': model,
                        'year': year,
                        'image_path': f"/car_img/{img_file.name}",
                        'price': "价格待询",
                        'mileage': "里程待询"
                    })
                    processed_names.add(car_key)

    # 手动分页处理
    total_count = len(all_cars)
    offset = (page - 1) * per_page
    current_cars = all_cars[offset:offset + per_page]
    return current_cars, total_count


@app.route('/')
def index():
    # 获取当前页码（默认第1页）
    page = request.args.get('page', 1, type=int)
    per_page = 24  # 每页固定24辆

    # 获取分页数据和总记录数
    current_cars, total_count = get_car_data(page=page, per_page=per_page)

    # 计算总页数（向上取整）
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

    return render_template(
        'index.html',
        cars=current_cars,
        current_page=page,
        total_pages=total_pages,
        total_count=total_count
    )


# 添加专门的二手车列表页面路由
@app.route('/cars')
def car_list():
    # 获取当前页码（默认第1页）
    page = request.args.get('page', 1, type=int)
    per_page = 24  # 每页固定24辆

    # 获取分页数据和总记录数
    current_cars, total_count = get_car_data(page=page, per_page=per_page)

    # 计算总页数（向上取整）
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

    return render_template(
        'index.html',
        cars=current_cars,
        current_page=page,
        total_pages=total_pages,
        total_count=total_count
    )


# 添加自定义静态文件路由，提供car_img目录中的图片
@app.route('/car_img/<path:filename>')
def custom_static(filename):
    return send_from_directory('car_img', filename)


if __name__ == '__main__':
    app.run(debug=True)