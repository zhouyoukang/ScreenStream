"""
SRT论文项目 — 统一路径配置
所有分析脚本共享此配置，修改数据源只需改这一个文件
"""
import os

# 项目根目录（本文件所在目录）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据文件
DATA_DIR = os.path.join(BASE_DIR, '数据')
ARG_FILE = os.path.join(DATA_DIR, '1_gene_catalog_ardb_annotation.xls')
ENV_FILE = os.path.join(DATA_DIR, 'ph_swc_ec.xlsx')

# 图表产出目录
OUT_DIR = os.path.join(BASE_DIR, 'figures')
os.makedirs(OUT_DIR, exist_ok=True)

# Word文档输出
DOCX_OUT = os.path.join(BASE_DIR, '论文', 'SRT_论文完整版.docx')

# 验证数据文件存在
def check_data():
    """检查必需数据文件是否存在"""
    missing = []
    if not os.path.exists(ARG_FILE):
        missing.append(f'ARG数据: {ARG_FILE}')
    if not os.path.exists(ENV_FILE):
        missing.append(f'环境因子: {ENV_FILE}')
    if missing:
        print('⚠️ 缺少数据文件:')
        for m in missing:
            print(f'  - {m}')
        return False
    return True
