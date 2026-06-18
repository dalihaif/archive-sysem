# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os

try:
    import pandas as pd
    import openpyxl
    print("=" * 80)
    print("依赖检查")
    print("=" * 80)
    print(f"pandas:    {pd.__version__}")
    print(f"openpyxl:  {openpyxl.__version__}")
except ImportError as e:
    print(f"缺少依赖: {e}")
    print("请运行: pip install pandas openpyxl")
    sys.exit(1)

FILE_PATH = r"E:\工作文档\档案室\02_归档文件目录与总库\档案总库\文书档案.xlsx"

# 检查文件
print("\n" + "=" * 80)
print("文件信息")
print("=" * 80)
print(f"路径: {FILE_PATH}")
print(f"存在: {os.path.exists(FILE_PATH)}")
if os.path.exists(FILE_PATH):
    size_mb = os.path.getsize(FILE_PATH) / 1024 / 1024
    print(f"大小: {size_mb:.2f} MB")

# 读取工作表名
print("\n" + "=" * 80)
print("所有工作表名称")
print("=" * 80)
xl = pd.ExcelFile(FILE_PATH, engine='openpyxl')
sheet_names = xl.sheet_names
print(f"共 {len(sheet_names)} 个工作表:")
for i, name in enumerate(sheet_names, 1):
    print(f"  {i:2d}. {name!r}")

# 汇总所有工作表的信息
print("\n" + "=" * 80)
print("各工作表概览")
print("=" * 80)
summary = []
for name in sheet_names:
    df = pd.read_excel(FILE_PATH, sheet_name=name, engine='openpyxl', header=0)
    summary.append({
        'sheet': name,
        'rows': len(df),
        'cols': len(df.columns),
        'columns': list(df.columns)
    })
    print(f"\n【{name}】")
    print(f"  行数: {len(df)}, 列数: {len(df.columns)}")
    print(f"  列名 ({len(df.columns)} 列):")
    for j, col in enumerate(df.columns, 1):
        print(f"    {j:2d}. {col!r}")

# 对每个工作表详细分析
for s in summary:
    name = s['sheet']
    print("\n" + "=" * 80)
    print(f"工作表详情: 【{name}】")
    print("=" * 80)

    df = pd.read_excel(FILE_PATH, sheet_name=name, engine='openpyxl', header=0)

    print(f"\n数据形状: {df.shape[0]} 行 × {df.shape[1]} 列")
    print(f"内存占用: {df.memory_usage(deep=True).sum() / 1024:.1f} KB")

    # 数据类型
    print("\n各列数据类型:")
    for j, col in enumerate(df.columns, 1):
        dtype = str(df[col].dtype)
        nunq = df[col].nunique(dropna=True)
        print(f"  {j:2d}. {col!r:<40}  dtype={dtype:<10}  唯一值={nunq}")

    # 前5行
    print("\n前 5 行数据:")
    print("-" * 80)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    pd.set_option('display.max_colwidth', 50)
    print(df.head(5).to_string(index=True))

    # 末5行
    print("\n末 5 行数据:")
    print("-" * 80)
    print(df.tail(5).to_string(index=True))

    # 空值检查
    print("\n空值统计 (各列 NaN/空 数量):")
    null_counts = df.isnull().sum()
    total_nulls = null_counts.sum()
    has_null = False
    for col, cnt in null_counts.items():
        if cnt > 0:
            has_null = True
            pct = cnt / len(df) * 100
            print(f"  {col!r:<40}  空值数={cnt:<6}  ({pct:.1f}%)")
    if not has_null:
        print("  (无空值)")

    # 完全空白的行/列
    blank_rows = df.isnull().all(axis=1).sum()
    blank_cols = df.isnull().all(axis=0).sum()
    print(f"\n完全空白行数: {blank_rows}")
    print(f"完全空白列数: {blank_cols}")

    # 重复行检查
    dup_count = df.duplicated().sum()
    print(f"\n重复行数: {dup_count}")

    # 字符串列可能存在的脏数据
    print("\n各列样例值 (前3个非空唯一值):")
    for col in df.columns:
        try:
            samples = df[col].dropna().unique()[:3]
            samples_str = [str(s)[:30] for s in samples]
            print(f"  {col!r:<40}  {samples_str}")
        except Exception as e:
            print(f"  {col!r:<40}  读取样例出错: {e}")

print("\n" + "=" * 80)
print("分析完成")
print("=" * 80)
