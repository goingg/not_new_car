import pymysql

def get_statistics_data(conn):
    """获取统计分析数据"""
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 年份分布统计（柱状图数据）
            cursor.execute("""
                SELECT 
                    SUBSTRING_INDEX(SUBSTRING_INDEX(caryear, '年份：', -1), '年', 1) AS year,
                    COUNT(*) AS count
                FROM carprice
                WHERE caryear LIKE '%年份：%年%'
                GROUP BY year
                ORDER BY year ASC
            """)
            year_data = cursor.fetchall()

            # 品牌分布百分比+其他
            cursor.execute("SELECT carname FROM carprice")
            all_cars = cursor.fetchall()
            brand_counter = {}
            total = len(all_cars)
            for row in all_cars:
                carname = row['carname']
                brand = carname.split()[0] if carname else '未知品牌'
                brand_counter[brand] = brand_counter.get(brand, 0) + 1
            # 按数量排序
            sorted_brands = sorted(brand_counter.items(), key=lambda x: x[1], reverse=True)
            top_brands = sorted_brands[:10]
            other_count = sum([x[1] for x in sorted_brands[10:]])
            pie_data = []
            for brand, count in top_brands:
                percent = round(count / total * 100, 2)
                pie_data.append({'brand': brand, 'count': count, 'percent': percent})
            if other_count > 0:
                percent = round(other_count / total * 100, 2)
                pie_data.append({'brand': '其他', 'count': other_count, 'percent': percent})

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

            # 统计总数
            cursor.execute("SELECT COUNT(*) as total_count FROM carprice")
            total_count = cursor.fetchone()['total_count']

            # 平均车龄
            cursor.execute("""
                SELECT AVG(CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(caryear, '年份： ', -1), '年', 1) AS UNSIGNED)) as avg_year
                FROM carprice
                WHERE caryear LIKE '%年份： %年%'
            """)
            avg_year_result = cursor.fetchone()
            avg_year = avg_year_result['avg_year'] if avg_year_result['avg_year'] else 0

            # 平均里程
            cursor.execute("""
                SELECT AVG(
                    CASE 
                        WHEN caryear LIKE '%万公里%' THEN 
                            CAST(REPLACE(SUBSTRING_INDEX(SUBSTRING_INDEX(caryear, '公里：', -1), '万公里', 1), '万', '') AS DECIMAL(10,2)) * 10000
                        WHEN caryear LIKE '%公里%' THEN 
                            CAST(REPLACE(SUBSTRING_INDEX(SUBSTRING_INDEX(caryear, '公里：', -1), '公里', 1), ',', '') AS UNSIGNED)
                    END
                ) as avg_mileage
                FROM carprice
                WHERE caryear LIKE '%公里：%%公里%'
            """)
            avg_mileage_result = cursor.fetchone()
            avg_mileage = avg_mileage_result['avg_mileage'] if avg_mileage_result['avg_mileage'] else 0

            # 品牌总数
            brand_count = len(brand_counter)

            # 返回统计数据
            return {
                'brand_data': pie_data,  # 替换为百分比+其他
                'brand_count': brand_count,
                'price_range_data': price_range_data,
                'total_count': total_count,
                'avg_price': round(avg_price * 10000, 2) if avg_price else 0,
                'avg_year': round(2025 - avg_year, 1) if avg_year > 0 else 0,
                'avg_mileage': round(avg_mileage, 0) if avg_mileage > 0 else 0,
                'year_data': year_data  # 新增年份分布
            }
    except Exception as e:
        print(f"读取统计数据失败: {e}")
        return None
