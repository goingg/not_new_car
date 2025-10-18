# 工具函数和统一配置
import qiniu

# 七牛云配置
QINIU_DOMAIN = 'http://t460o974c.hb-bkt.clouddn.com'
ACCESS_KEY = 'j_afhONjyWahQI0k4bGme1tGMr-W-AXKvTAGvk1J'
SECRET_KEY = '7LcJJ2DV7VP6iY991evMgRIvlzn2prdmuwjr69lz'
BUCKET_NAME = 'notnew-car'

q = qiniu.Auth(ACCESS_KEY, SECRET_KEY)


def safe_name(name):
    """统一处理文件名安全字符"""
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in name)

