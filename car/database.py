import pymysql
import re


def get_conn(db_name='car'):
    """获取数据库连接，不存在则创建数据库"""
    try:
        return pymysql.connect(
            host='localhost',
            port=3306,
            user='root',
            passwd='1234',
            db=db_name,
            charset='utf8mb4',
            connect_timeout=10
        )
    except pymysql.err.OperationalError as e:
        if "Unknown database" in str(e):
            try:
                # 先连接默认数据库创建新库
                temp_conn = pymysql.connect(
                    host='localhost',
                    port=3306,
                    user='root',
                    passwd='1234',
                    charset='utf8mb4',
                    connect_timeout=10
                )
                create_database(temp_conn, db_name)
                temp_conn.close()
                # 再次尝试连接
                return get_conn(db_name)
            except pymysql.err.OperationalError as conn_err:
                print(f"数据库连接失败: {conn_err}")
                raise conn_err
        else:
            print(f"数据库操作错误: {e}")
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
            
            # 创建用户表
            create_user_table_sql = """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            cursor.execute(create_user_table_sql)
            
            # 插入默认管理员用户 (用户名: admin, 密码: password)
            insert_default_user_sql = """
            INSERT IGNORE INTO users (username, password) VALUES ('admin', 'password')
            """
            cursor.execute(insert_default_user_sql)
            
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


def verify_user(conn, username, password):
    """验证用户凭据"""
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT id, username FROM users 
                WHERE username = %s AND password = %s
            """, (username, password))
            user = cursor.fetchone()
            return user
    except Exception as e:
        print(f"验证用户时出错: {e}")
        return None


def create_user(conn, username, password):
    """创建新用户"""
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO users (username, password) 
                VALUES (%s, %s)
            """, (username, password))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        print(f"创建用户时出错: {e}")
        conn.rollback()
        return None


def check_username_exists(conn, username):
    """检查用户名是否已存在"""
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id FROM users WHERE username = %s
            """, (username,))
            result = cursor.fetchone()
            return result is not None
    except Exception as e:
        print(f"检查用户名时出错: {e}")
        return False
