from flask import Flask, render_template, request, send_from_directory, jsonify
import os
from pathlib import Path
import sys

# 配置项目路径
project_root = os.path.join(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# 导入数据库操作模块
from database import get_conn, read_data, get_statistics_data
import pymysql
import re

# 导入pyecharts相关模块
from pyecharts.charts import Pie, Line
from pyecharts import options as opts


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
        return [], 0

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


def create_charts(stats_data):
    """创建图表"""
    # 图表初始化参数
    init_opts = opts.InitOpts(width="100%", height="100%", 
                             renderer="canvas")
    
    # 品牌分布饼图
    brand_data = stats_data.get('brand_data', [])
    pie = None
    if brand_data:
        pie = (
            Pie(init_opts=init_opts)
            .add(
                "",
                [(item['brand'], item['count']) for item in brand_data],
                radius=["40%", "75%"],
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(title="品牌分布"),
                legend_opts=opts.LegendOpts(orient="vertical", pos_top="15%", pos_left="2%"),
            )
            .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
        )

    # 价格趋势折线图
    # 使用模拟数据，因为数据库中没有年份信息
    line = (
        Line(init_opts=init_opts)
        .add_xaxis(['2018', '2019', '2020', '2021', '2022', '2023'])
        .add_yaxis(
            "平均价格 (元)",
            [350000, 265000, 280000, 295000, 210000, int(stats_data.get('avg_price', 0))],
            is_smooth=True,
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(title="二手车价格趋势"),
            xaxis_opts=opts.AxisOpts(type_="category"),
            yaxis_opts=opts.AxisOpts(
                type_="value",
                axislabel_opts=opts.LabelOpts(formatter="{value} 元"),
            ),
        )
        .set_series_opts(
            label_opts=opts.LabelOpts(is_show=False)
        )
    )

    return pie, line


@app.route('/analytics')
def analytics():
    """数据分析页面"""
    try:
        conn = get_conn()
        stats_data = get_statistics_data(conn)
        if stats_data:
            pie_chart, line_chart = create_charts(stats_data)
            return render_template(
                'analytics.html',
                pie_chart=pie_chart.render_embed() if pie_chart else None,
                line_chart=line_chart.render_embed(),
                stats_data=stats_data
            )
        else:
            return "无法获取统计数据", 500
    except Exception as e:
        print(f"获取统计数据时出错: {e}")
        return "服务器内部错误", 500


@app.route('/api/statistics')
def statistics_api():
    """提供统计数据的API接口"""
    try:
        conn = get_conn()
        stats_data = get_statistics_data(conn)
        if stats_data:
            return jsonify({
                'success': True,
                'data': stats_data
            })
        else:
            return jsonify({
                'success': False,
                'message': '无法获取统计数据'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取统计数据时出错: {str(e)}'
        })


# 添加自定义静态文件路由，提供car_img目录中的图片
@app.route('/car_img/<path:filename>')
def custom_static(filename):
    return send_from_directory('car_img', filename)


@app.route('/car/<int:car_id>')
def car_detail(car_id):
    """车辆详情页面"""
    try:
        conn = get_conn()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT id, carname, carmoney, caryear 
                FROM carprice 
                WHERE id = %s
            """, (car_id,))
            car = cursor.fetchone()
            
        if car:
            # 解析车辆信息
            parts = car['carname'].split()
            brand = parts[0] if parts else "未知品牌"
            model = " ".join(parts[1:]) if len(parts) > 1 else "未知型号"
            
            # 解析年份和里程
            year = "未知"
            mileage = "里程待询"
            if car['caryear']:
                # 清理数据中的特殊字符
                clean_caryear = car['caryear'].replace('', '')  # 移除特殊字符
                
                # 提取年份
                year_match = re.search(r'(\d{4})年', clean_caryear)
                if year_match:
                    year = year_match.group(1)
                
                # 提取里程
                mileage_match = re.search(r'([\d.]+万?)公[里里]', clean_caryear)
                if mileage_match:
                    mileage = mileage_match.group(1) + "公里"
                elif re.search(r'(\d+\.?\d*)万?公[里里]', clean_caryear):
                    mileage_match = re.search(r'(\d+\.?\d*)万?公[里里]', clean_caryear)
                    if mileage_match:
                        mileage = mileage_match.group(1) + "万公里"
                else:
                    # 如果没有匹配到"万"字，尝试匹配普通数字
                    mileage_match = re.search(r'(\d+\.?\d*)公[里里]', clean_caryear)
                    if mileage_match:
                        mileage = mileage_match.group(1) + "公里"
            
            # 查找对应的图片
            car_img_dir = Path("car_img")
            image_path = "/static/img/1.webp"  # 默认图片
            
            if car_img_dir.exists():
                # 根据车辆名称匹配图片
                car_name = car['carname']
                image_files = list(car_img_dir.glob("*.jpg"))
                
                # 首先尝试精确匹配
                for img_file in image_files:
                    if car_name in img_file.name:
                        image_path = f"/car_img/{img_file.name}"
                        break
                
                # 如果没有精确匹配，尝试模糊匹配
                if image_path == "/static/img/1.webp":
                    for img_file in image_files:
                        if car_name.split()[0] in img_file.name:
                            image_path = f"/car_img/{img_file.name}"
                            break
            
            car_data = {
                'id': car['id'],
                'brand': brand,
                'model': model,
                'name': car['carname'],
                'price': car['carmoney'],
                'year': year,
                'mileage': mileage,
                'image_path': image_path
            }
            
            return render_template('car_detail.html', car=car_data)
        else:
            return "车辆未找到", 404
            
    except Exception as e:
        print(f"获取车辆详情失败: {e}")
        return "服务器内部错误", 500


if __name__ == '__main__':
    app.run(debug=True)