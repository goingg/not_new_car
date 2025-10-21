from database import get_conn, read_data, verify_user, create_user, check_username_exists
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from pyecharts.charts import Pie, Line, Bar
from pyecharts import options as opts
from pathlib import Path
import urllib.parse
import pymysql
import sys
import os
import re
from utils import safe_name, q, QINIU_DOMAIN
from statistics import get_statistics_data
from functools import wraps
import requests

# 配置项目路径
project_root = os.path.join(os.path.dirname(__file__))
sys.path.insert(0, project_root)


app = Flask(__name__, static_folder='static')
app.secret_key = 'your_secret_key_here'  # 用于会话加密

LOCAL_IMG_DIR = 'car_img'


def login_required(f):
    """装饰器：检查用户是否已登录"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def get_ai_recommended_cars(conn, top_n=8):
    # 按价格、年份、品牌等简单规则推荐
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT id, carname, carmoney, caryear
            FROM carprice
            ORDER BY RAND()  -- 随机推荐
            LIMIT %s
        """, (top_n,))
        results = cursor.fetchall()
        # 解析数据
        cars = []
        for row in results:
            parts = row['carname'].split()
            brand = parts[0] if parts else "未知品牌"
            model = " ".join(parts[1:]) if len(parts) > 1 else "未知型号"
            year = "未知"
            mileage = "里程待询"
            if row['caryear']:
                clean_caryear = row['caryear'].replace('', '')  # 移除特殊字符
                year_match = re.search(r'(\d{4})年', clean_caryear)
                if year_match:
                    year = year_match.group(1)
                mileage_match = re.search(r'([\d.]+万?)公里', clean_caryear)
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
            cars.append({
                'id': row['id'],
                'brand': brand,
                'model': model,
                'price': row['carmoney'],
                'name': row['carname'],
                'year': year,
                'mileage': mileage,
                'image_path': get_image_path(row['carname'], 1)  # 使用固定索引1，与爬虫逻辑保持一致
            })
        return cars


def get_image_path(carname, index, ext='.jpg'):
    sname = safe_name(carname)
    encoded_name = urllib.parse.quote(f"{sname}_{index}{ext}")
    url = f"{QINIU_DOMAIN}/car_images/{encoded_name}"
    # 生成带token的私有下载链接（有效期1小时）
    private_url = q.private_download_url(url, expires=3600)
    return private_url


def get_car_data(page=1, per_page=24):
    """获取分页的汽车数据"""
    cars = []
    total_count = 0  # 总记录数
    try:
        conn = get_conn()
        # 从数据库读取分页数据和总记录数
        cars, total_count = read_data(conn, page=page, per_page=per_page)
    except Exception as e:
        print(f"数据库读取失败: {e}")
        return [], 0

    # 处理数据库数据
    if cars:
        for i, car in enumerate(cars):
            # 修改图片路径生成方式，使用固定索引1，与首页保持一致
            car['image_path'] = get_image_path(car['name'], 1)
            car['year'] = car.get('year', "未知")
            car['mileage'] = car.get('mileage', "里程待询")
        return cars, total_count


@app.route('/')
def index():
    # 获取当前页码（默认第1页）
    page = request.args.get('page', 1, type=int)
    per_page = 24  # 每页固定24辆

    # 获取分页数据和总记录数
    current_cars, total_count = get_car_data(page=page, per_page=per_page)

    # 计算总页数（向上取整）
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

    # 智能推荐热门车辆
    conn = get_conn()
    recommended_cars = get_ai_recommended_cars(conn, top_n=8)

    return render_template(
        'index.html',
        cars=current_cars,
        recommended_cars=recommended_cars,  # 首页推荐车辆
        current_page=page,
        total_pages=total_pages,
        total_count=total_count
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # 数据库验证用户
        try:
            conn = get_conn()
            user = verify_user(conn, username, password)
            conn.close()
            
            if user:
                # 登录成功，设置会话
                session['user'] = user
                return redirect(url_for('index'))
            else:
                # 登录失败，返回错误信息
                return render_template('login.html', error='用户名或密码错误')
        except Exception as e:
            print(f"登录时出错: {e}")
            return render_template('login.html', error='登录过程中发生错误')
    
    # GET 请求显示登录页面
    return render_template('login.html')


@app.route('/logout')
def logout():
    # 清除会话
    session.pop('user', None)
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # 验证输入
        if not username or not password:
            return render_template('register.html', error='用户名和密码不能为空')
        
        if password != confirm_password:
            return render_template('register.html', error='密码和确认密码不匹配')
        
        if len(password) < 6:
            return render_template('register.html', error='密码长度至少为6位')
        
        try:
            conn = get_conn()
            
            # 检查用户名是否已存在
            if check_username_exists(conn, username):
                conn.close()
                return render_template('register.html', error='用户名已存在')
            
            # 创建新用户
            user_id = create_user(conn, username, password)
            conn.close()
            
            if user_id:
                # 注册成功，重定向到登录页面
                return redirect(url_for('login', success='注册成功，请登录'))
            else:
                return render_template('register.html', error='注册失败，请稍后重试')
                
        except Exception as e:
            print(f"注册时出错: {e}")
            return render_template('register.html', error='注册过程中发生错误')
    
    # GET 请求显示注册页面
    return render_template('register.html')


# 二手车列表页面路由
@app.route('/cars')
def car_list():
    # 获取当前页码（默认第1页）
    page = request.args.get('page', 1, type=int)
    per_page = 24  # 每页固定24辆

    # 获取价格分类参数
    price_category = request.args.get('price_category', 'all')

    # 根据价格分类获取车辆
    def get_cars_by_price_category_local(category: str = 'all'):
        """
        根据价格分类获取车辆的本地实现
        """
        # 获取所有车辆数据
        all_cars, _ = get_car_data(page=1, per_page=10000)  # 获取所有车辆

        # 如果是获取所有车辆，直接返回
        if category == 'all':
            # 为所有车辆添加价格标签
            for car in all_cars:
                # 使用本地的价格转换和分类函数
                price_value = _to_float_local(car['price'])
                price_label = _label_local(price_value)
                car['price_label'] = price_label
            return all_cars

        # 筛选特定分类的车辆
        classified_cars = []
        for car in all_cars:
            # 使用本地的价格转换和分类函数
            price_value = _to_float_local(car['price'])
            price_label = _label_local(price_value)

            # 如果分类匹配，则添加到结果中
            if price_label == category:
                car['price_label'] = price_label
                classified_cars.append(car)

        return classified_cars

    # 本地实现的工具函数
    def _to_float_local(carmoney: str):
        """
        把原始价格字符串转成浮点数
        """
        try:
            return float(carmoney.replace("￥", "").replace("万", "").replace("", ""))
        except Exception:
            return -1.0

    def _label_local(price: float):
        """
        根据价格返回对应标签
        这个函数将车辆价格转换为用户友好的价格区间标签，用于在前端界面显示。
        价格区间配置：左闭右开，单位"万元"
        Args:
            price: 车辆价格（以万元为单位）
        Returns:
            str: 对应的价格区间标签，如"经济实惠"、"家用首选"等
        """
        # 价格区间配置：左闭右开，单位"万元"
        PRICE_SEG_LOCAL = [
            (0, 10, "经济实惠"),
            (10, 20, "家用首选"),
            (20, 30, "品质之选"),
            (30, 50, "豪华舒适"),
            (50, float('inf'), "高端定制")
        ]

        if price < 0:
            return "价格异常"
        for low, high, tag in PRICE_SEG_LOCAL:
            if low <= price < high:
                return tag
        # 兜底（理论上不会走到）
        return "价格异常"

    # 调用本地函数
    all_cars = get_cars_by_price_category_local(price_category)

    # 对筛选后的数据进行手动分页
    total_count = len(all_cars)
    offset = (page - 1) * per_page
    current_cars = all_cars[offset:offset + per_page]

    # 计算总页数（向上取整）
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

    return render_template(
        'index.html',
        cars=current_cars,
        current_page=page,
        total_pages=total_pages,
        total_count=total_count,
        current_category=price_category
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

    # 年份分布柱状图
    year_data = stats_data.get('year_data', [])
    bar = None
    if year_data:
        years = [item['year'] for item in year_data]
        counts = [item['count'] for item in year_data]
        bar = (
            Bar(init_opts=init_opts)
            .add_xaxis(years)
            .add_yaxis("二手车数量", counts)
            .set_global_opts(
                title_opts=opts.TitleOpts(title="各年份二手车数量分布"),
                xaxis_opts=opts.AxisOpts(type_="category"),
                yaxis_opts=opts.AxisOpts(type_="value"),
            )
            .set_series_opts(label_opts=opts.LabelOpts(is_show=True))
        )

    return pie, line, bar


@app.route('/analytics')
@login_required
def analytics():
    """数据分析页面"""
    try:
        conn = get_conn()
        stats_data = get_statistics_data(conn)
        if stats_data:
            pie_chart, line_chart, bar_chart = create_charts(stats_data)
            return render_template(
                'analytics.html',
                pie_chart=pie_chart.render_embed() if pie_chart else None,
                line_chart=line_chart.render_embed(),
                bar_chart=bar_chart.render_embed() if bar_chart else None,
                stats_data=stats_data
            )
        else:
            return "无法获取统计数据", 500
    except Exception as e:
        print(f"获取统计数据时出错: {e}")
        return "服务器内部错误", 500


@app.route('/api/statistics')
@login_required
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


@app.route('/api/refresh_recommendations')
def refresh_recommendations():
    """API接口：获取新的推荐车辆"""
    try:
        conn = get_conn()
        recommended_cars = get_ai_recommended_cars(conn, top_n=8)
        conn.close()
        
        # 转换为可JSON序列化的格式
        cars_data = []
        for car in recommended_cars:
            cars_data.append({
                'id': car['id'],
                'brand': car['brand'],
                'model': car['model'],
                'price': car['price'],
                'year': car['year'],
                'mileage': car['mileage'],
                'image_path': car['image_path']
            })
        
        return jsonify({
            'success': True,
            'cars': cars_data
        })
    except Exception as e:
        print(f"获取推荐车辆时出错: {e}")
        return jsonify({
            'success': False,
            'message': f'获取推荐车辆时出错: {str(e)}'
        }), 500


@app.route('/api/check_login')
def check_login():
    return jsonify({'logged_in': 'user' in session})


@app.route('/api/ai-assistant', methods=['POST'])
def ai_assistant():
    """AI助理接口：接收用户问题，调用通义千问API，返回AI答案"""
    data = request.get_json()
    question = data.get('question', '').strip()
    is_greeting = data.get('is_greeting', False)
    if not question:
        return jsonify({'answer': '请输入您的问题'}), 400
    # 通义千问API配置
    api_key = 'sk-3b5dd537e2b2436abe2e766f7761b408'
    url = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    # 限定AI只回答二手车相关内容
    system_prompt = "你是一个专注于二手车领域的智能助理，只能解答二手车买卖、选购、行情、车型、价格等相关问题，对于其他领域请直接拒绝回答。"
    if is_greeting:
        prompt = question  # 问候时直接用前端传来的问候指令
    else:
        prompt = f"{system_prompt}\n用户提问：{question}"
    payload = {
        "model": "qwen-turbo",
        "input": {
            "prompt": prompt
        }
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            answer = result.get('output', {}).get('text') or result.get('result', {}).get('output', {}).get('text')
            if not answer:
                answer = result.get('choices', [{}])[0].get('message', {}).get('content', 'AI未能理解您的问题')
            return jsonify({'answer': answer})
        else:
            return jsonify({'answer': 'AI服务暂时不可用'}), 500
    except Exception as e:
        return jsonify({'answer': 'AI服务异常'}), 500


if __name__ == '__main__':
    # 确保本地图片目录存在
    Path(LOCAL_IMG_DIR).mkdir(exist_ok=True)
    app.run(debug=True)