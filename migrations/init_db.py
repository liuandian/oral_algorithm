"""
数据库初始化脚本
执行方式: python migrations/init_db.py
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2 import sql
from app.config import settings


def init_database():
    """初始化数据库表结构"""
    print("=" * 60)
    print("智能口腔健康监测系统 - 数据库初始化")
    print("=" * 60)

    # 连接到 PostgreSQL（首先连接到默认的 postgres 数据库）
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database="postgres"
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # 检查目标数据库是否存在
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (settings.DB_NAME,)
        )
        exists = cursor.fetchone()

        if not exists:
            print(f"\n[创建数据库] {settings.DB_NAME}")
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(settings.DB_NAME)
                )
            )
            print(f"✓ 数据库 '{settings.DB_NAME}' 创建成功")
        else:
            print(f"\n[数据库已存在] {settings.DB_NAME}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"✗ 数据库创建失败: {e}")
        sys.exit(1)

    # 连接到目标数据库并执行 Schema 初始化
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME
        )
        cursor = conn.cursor()

        # 读取 SQL 脚本
        schema_file = Path(__file__).parent / "init_schema.sql"
        print(f"\n[执行 Schema] {schema_file.name}")

        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        # 执行 SQL
        cursor.execute(schema_sql)
        conn.commit()

        print("✓ Schema 初始化成功")

        # 验证表创建
        print("\n[验证表创建]")
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)

        tables = cursor.fetchall()
        for table in tables:
            print(f"  ✓ {table[0]}")

        cursor.close()
        conn.close()

        print("\n" + "=" * 60)
        print("数据库初始化完成！")
        print("=" * 60)

    except Exception as e:
        print(f"✗ Schema 初始化失败: {e}")
        sys.exit(1)


def drop_database():
    """删除数据库（危险操作，仅用于开发环境）"""
    print("⚠️  警告：此操作将删除整个数据库！")
    confirm = input(f"确认删除数据库 '{settings.DB_NAME}'? (yes/no): ")

    if confirm.lower() != 'yes':
        print("操作已取消")
        return

    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database="postgres"
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # 断开所有连接
        cursor.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{settings.DB_NAME}'
            AND pid <> pg_backend_pid();
        """)

        # 删除数据库
        cursor.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(settings.DB_NAME)
            )
        )

        print(f"✓ 数据库 '{settings.DB_NAME}' 已删除")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"✗ 删除失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="数据库管理工具")
    parser.add_argument(
        "action",
        choices=["init", "drop"],
        help="操作类型: init(初始化) 或 drop(删除)"
    )

    args = parser.parse_args()

    if args.action == "init":
        init_database()
    elif args.action == "drop":
        drop_database()
