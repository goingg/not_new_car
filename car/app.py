from flask import Flask, render_template, request, send_from_directory, jsonify
import os
from pathlib import Path
import sys
import urllib.parse
import qiniu

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

# 七牛云图片域名（确保末尾无斜杠）
QINIU_DOMAIN = 'http://t460o974c.hb-bkt.clouddn.com'

LOCAL_IMG_DIR = 'car_img'

access_key = 'j_afhONjyWahQI0k4bGme1tGMr-W-AXKvTAGvk1J'
secret_key = '7LcJJ2DV7VP6iY991evMgRIvlzn2prdmuwjr69lz'
q = qiniu.Auth(access_key, secret_key)


def safe_name(name):
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in name)


def get_image_path(carname, index, ext='.jpg'):
    sname = safe_name(carname)
    encoded_name = urllib.parse.quote(f"{sname}_{index}{ext}")
    url = f"{QINIU_DOMAIN}/car_images/{encoded_name}"
    # 生成带token的私有下载链接（有效期1小时）
    private_url = q.private_download_url(url, expires=3600)
    return private_url


def get_car_data(page=1, per_page=24):
    """获取分页的汽车数据（修复图片路径）"""
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
        for i, car in enumerate(cars):
            car['image_path'] = get_image_path(car['name'], i + 1)
            car['year'] = car.get('year', "未知")
            car['mileage'] = car.get('mileage', "里程待询")
        return cars, total_count

    # 数据库无数据时，从本地图片解析
    car_img_dir = Path(LOCAL_IMG_DIR)
    all_cars = []
    if car_img_dir.exists():
        image_files = list(car_img_dir.glob("*.jpg"))[:2000]  # 限制最大数量
        processed_names = set()
        for img_file in image_files:
            filename = img_file.stem
            # 解析文件名（兼容爬虫生成的格式）
            name_parts = filename.split('_')
            if len(name_parts) >= 2 and name_parts[-1].isdigit():
                # 提取车辆名称（去除索引部分）
                car_name = '_'.join(name_parts[:-1])
                parts = car_name.split()
                if len(parts) >= 2:
                    brand = parts[0]
                    model = ' '.join(parts[1:-1]) if len(parts) > 2 else parts[1]
                    year = parts[-1] if (parts[-1].isdigit() and len(parts[-1]) == 4) else "未知"
                    car_key = f"{brand}_{model}"
                    if car_key not in processed_names:
                        # 生成图片路径
                        img_index = name_parts[-1]
                        all_cars.append({
                            'brand': brand,
                            'model': model,
                            'year': year,
                            'image_path': get_image_path(safe_name(car_name), img_index),
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


# 二手车列表页面路由
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


# 提供本地图片访问
@app.route(f'/{LOCAL_IMG_DIR}/<path:filename>')
def custom_static(filename):
    return send_from_directory(LOCAL_IMG_DIR, filename)


@app.route('/car/<int:car_id>')
def car_detail(car_id):
    """车辆详情页面（修复图片路径）"""
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
            image_path = get_image_path(car['carname'], 1)
            # 解析年份和里程
            year = "未知"
            mileage = "里程待询"
            caryear_str = car.get('caryear', "")
            if caryear_str:
                # 提取年份（如 2014年、2022年）
                year_match = re.search(r'(\d{4})年', caryear_str)
                if year_match:
                    year = year_match.group(1)
                # 提取里程（如 3.1万公里、41700公里）
                mileage_match = re.search(r'([\d.]+万?)公里', caryear_str)
                if mileage_match:
                    mileage = mileage_match.group(1) + "公里"
                else:
                    mileage_match = re.search(r'([\d,]+)公里', caryear_str)
                    if mileage_match:
                        mileage = mileage_match.group(1).replace(",", "") + "公里"
            car_data = {
                'id': car['id'],
                'brand': car['carname'].split()[0] if car['carname'] else "未知品牌",
                'model': " ".join(car['carname'].split()[1:]) if car['carname'] else "未知型号",
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
    # 确保本地图片目录存在
    Path(LOCAL_IMG_DIR).mkdir(exist_ok=True)
    app.run(debug=True)