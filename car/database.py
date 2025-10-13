import pymysql
import re


def get_conn(db_name='car'):
    """获取数据库连接，不存在则创建数据库"""
    def user():
        return pymysql.connect(
            host='localhost',
            port=3306,
            user='root',
            passwd='1234',
            db=db_name,
            charset='utf8mb4',
            connect_timeout=10
        )

    def connect():
        return user()

    try:
        return connect()
    except pymysql.err.OperationalError as e:
        if "Unknown database" in str(e):
            # 先连接默认数据库创建新库
            temp_conn = user()
            create_database(temp_conn, db_name)
            temp_conn.close()
            return connect()
        else:
            raise e


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


def init_table(conn):
    """初始化数据表（包含caryear字段）"""
    try:
        with conn.cursor() as cursor:
            create_sql = """
            CREATE TABLE IF NOT EXISTS carprice (
                id INT AUTO_INCREMENT PRIMARY KEY,
                carname VARCHAR(255) NOT NULL,
                carmoney VARCHAR(100) NOT NULL,
                caryear VARCHAR(100) NOT NULL,  # 新增年份+里程字段
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            cursor.execute(create_sql)
            conn.commit()
            print("数据表初始化成功")
    except Exception as e:
        print(f"初始化表失败: {e}")
        conn.rollback()


def save_data(conn, carname_list, carmoney_list, caryear_list=None):
    """保存数据到数据库，支持caryear字段"""
    if not carname_list or not carmoney_list:
        return

    caryear_list = caryear_list or []
    min_length = min(len(carname_list), len(carmoney_list), len(caryear_list))
    carname_list = carname_list[:min_length]
    carmoney_list = carmoney_list[:min_length]
    caryear_list = caryear_list[:min_length]

    # 插入包含caryear的记录
    sql = "INSERT INTO carprice(carname, carmoney, caryear) VALUES (%s, %s, %s)"

    with conn.cursor() as cur:
        try:
            data = zip(carname_list, carmoney_list, caryear_list)
            cur.executemany(sql, data)
            conn.commit()
            print(f"插入 {cur.rowcount} 条数据")
        except Exception as e:
            conn.rollback()
            print(f"插入失败: {e}")


def read_data(conn, page=1, per_page=24):
    """分页读取数据（包含caryear字段）"""
    cars = []
    total_count = 0
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 查询总记录数
            cursor.execute("SELECT COUNT(*) AS total FROM carprice")
            total_count = cursor.fetchone()['total']

            # 分页查询（包含caryear）
            offset = (page - 1) * per_page
            cursor.execute("""
                SELECT id, carname, carmoney, caryear 
                FROM carprice 
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            results = cursor.fetchall()

            # 处理数据格式（解析年份和里程）
            for row in results:
                parts = row['carname'].split()
                brand = parts[0] if parts else "未知品牌"
                model = " ".join(parts[1:]) if len(parts) > 1 else "未知型号"

                # 解析caryear（格式如：2023年/3.2万公里）
                year = "未知"
                mileage = "里程待询"
                if row['caryear']:
                    # 清理数据中的特殊字符
                    clean_caryear = row['caryear'].replace('', '')  # 移除特殊字符
                    
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
                cars.append({
                    'id': row['id'],
                    'brand': brand,
                    'model': model,
                    'price': row['carmoney'],
                    'name': row['carname'],
                    'year': year,
                    'mileage': mileage
                })
    except Exception as e:
        print(f"读取数据失败: {e}")
    finally:
        conn.close()
    return cars, total_count


def get_statistics_data(conn):
    """获取统计分析数据"""
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 品牌分布
            cursor.execute("""
                SELECT 
                    SUBSTRING_INDEX(carname, ' ', 1) as brand,
                    COUNT(*) as count
                FROM carprice 
                GROUP BY SUBSTRING_INDEX(carname, ' ', 1)
                ORDER BY count DESC
                LIMIT 6
            """)
            brand_data = cursor.fetchall()

            # 价格区间分布
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN CAST(REPLACE(REPLACE(REPLACE(carmoney, '￥', ''), '万', ''), '', '') AS DECIMAL(10,2)) < 10 THEN '10万以下'
                        WHEN CAST(REPLACE(REPLACE(REPLACE(carmoney, '￥', ''), '万', ''), '', '') AS DECIMAL(10,2)) BETWEEN 10 AND 20 THEN '10-20万'
                        WHEN CAST(REPLACE(REPLACE(REPLACE(carmoney, '￥', ''), '万', ''), '', '') AS DECIMAL(10,2)) BETWEEN 20 AND 30 THEN '20-30万'
                        WHEN CAST(REPLACE(REPLACE(REPLACE(carmoney, '￥', ''), '万', ''), '', '') AS DECIMAL(10,2)) BETWEEN 30 AND 50 THEN '30-50万'
                        WHEN CAST(REPLACE(REPLACE(REPLACE(carmoney, '￥', ''), '万', ''), '', '') AS DECIMAL(10,2)) > 50 THEN '50万以上'
                        ELSE '其他'
                    END as price_range,
                    COUNT(*) as count
                FROM carprice
                WHERE carmoney LIKE '￥%'
                GROUP BY price_range
                ORDER BY 
                    CASE price_range
                        WHEN '10万以下' THEN 1
                        WHEN '10-20万' THEN 2
                        WHEN '20-30万' THEN 3
                        WHEN '30-50万' THEN 4
                        WHEN '50万以上' THEN 5
                        ELSE 6
                    END
            """)
            price_range_data = cursor.fetchall()

            # 平均价格
            cursor.execute("""
                SELECT AVG(CAST(REPLACE(REPLACE(REPLACE(carmoney, '￥', ''), '万', ''), '', '') AS DECIMAL(10,2))) as avg_price
                FROM carprice
                WHERE carmoney LIKE '￥%'
            """)
            avg_price = cursor.fetchone()['avg_price']

            # 车辆总数
            cursor.execute("SELECT COUNT(*) as total_count FROM carprice")
            total_count = cursor.fetchone()['total_count']

            return {
                'brand_data': brand_data,
                'price_range_data': price_range_data,
                'avg_price': round(avg_price * 10000, 2) if avg_price else 0,  # 转换为元
                'total_count': total_count
            }
    except Exception as e:
        print(f"读取统计数据失败: {e}")
        return None