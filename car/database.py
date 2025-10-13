import pymysql


def get_conn(db_name='car'):
    """获取数据库连接，不存在则创建数据库"""
    def user():
        return pymysql.connect(
            host='localhost',
            port=3306,
            user='root',
            passwd='1234',
            db=db_name,
            charset='utf8mb4')

    try:
        return user()
    except pymysql.err.OperationalError as e:
        if "Unknown database" in str(e):
            # 创建数据库
            conn = user()
            create_database(conn, db_name)
            conn.close()
            return user()
        else:
            raise e


def create_database(conn, db_name):
    """创建数据库"""
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            conn.commit()
            print(f"数据库 {db_name} 创建成功")
    except Exception as e:
        print(f"创建数据库失败: {e}")


def init_table(conn):
    """初始化数据表"""
    try:
        with conn.cursor() as cursor:
            create_sql = """
            CREATE TABLE IF NOT EXISTS carprice (
                id INT AUTO_INCREMENT PRIMARY KEY,
                carname VARCHAR(255) NOT NULL,
                carmoney VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            cursor.execute(create_sql)
            conn.commit()
            print("数据表初始化成功")
    except Exception as e:
        print(f"初始化表失败: {e}")
        conn.rollback()


def save_data(conn, carname_list, carmoney_list):
    """保存数据到数据库"""
    if not carname_list or not carmoney_list:
        return
    sql = "INSERT INTO carprice(carname, carmoney) VALUES (%s, %s)"
    with conn.cursor() as cur:
        try:
            cur.executemany(sql, zip(carname_list, carmoney_list))
            conn.commit()
            print(f"插入 {cur.rowcount} 条数据")
        except Exception as e:
            conn.rollback()
            print(f"插入失败: {e}")


def read_data(conn, page=1, per_page=24):
    """分页读取数据，返回当前页数据和总记录数"""
    cars = []
    total_count = 0
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 查询总记录数
            cursor.execute("SELECT COUNT(*) AS total FROM carprice")
            total_count = cursor.fetchone()['total']

            # 分页查询
            offset = (page - 1) * per_page
            cursor.execute(
                "SELECT id, carname, carmoney FROM carprice LIMIT %s OFFSET %s",
                (per_page, offset)
            )
            results = cursor.fetchall()


            # 处理数据格式
            for row in results:
                parts = row['carname'].split()
                brand = parts[0] if parts else "未知品牌"
                model = " ".join(parts[1:]) if len(parts) > 1 else "未知型号"
                cars.append({
                    'id': row['id'],
                    'brand': brand,
                    'model': model,
                    'price': row['carmoney'],
                    'name': row['carname']
                })
    except Exception as e:
        print(f"读取数据失败: {e}")
    finally:
        conn.close()
    return cars, total_count