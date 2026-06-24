"""Odoo 数据库自然语言查询助手 — 基于 CodeBuddy API"""

import asyncio
import sys
import io
import os
import json
import re
from pathlib import Path
from typing import Optional

# 加载 .env 文件
def _load_dotenv():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ[key] = value

_load_dotenv()

# --- 配置 ---

# 注意：以下默认值仅用于本机 dev 环境（CLAUDE.md 记载本机 db 密码即 odoo）。
# 生产环境必须通过环境变量 / .env 覆盖，切勿依赖默认密码。
DB_CONFIG = {
    "host": os.getenv("ODOO_DB_HOST", "localhost"),
    "port": int(os.getenv("ODOO_DB_PORT", "5433")),
    "dbname": os.getenv("ODOO_DB_NAME", "forjoy"),
    "user": os.getenv("ODOO_DB_USER", "odoo"),
    "password": os.getenv("ODOO_DB_PASSWORD", "odoo"),
}

# --- SQL 安全处理 ---

_SQL_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _strip_sql_fence(text: str) -> str:
    """从 AI 输出中提取 SQL：优先取 ``` 代码块内容，否则剥离首尾空白。

    取代旧的 strip("```sql")——后者按字符集删除，会误删 SQL 首尾的
    ` / s / q / l 字符（例如以 l 结尾的列名会被砍掉）。
    """
    if not text:
        return ""
    m = _SQL_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


# 只读语句首关键字白名单
_READONLY_PREFIXES = ("select", "with", "explain", "show", "table", "values")


def _is_readonly_sql(sql: str) -> bool:
    """首关键字白名单：仅放行只读查询。与只读事务一起构成双保险。"""
    if not sql:
        return False
    s = sql.lstrip()
    # 跳过前导行注释
    while s.startswith("--"):
        nl = s.find("\n")
        if nl == -1:
            return False
        s = s[nl + 1:].lstrip()
    parts = s.split(None, 1)
    if not parts:
        return False
    return parts[0].lower() in _READONLY_PREFIXES


# --- 数据库连接 ---

def get_db_connection(readonly: bool = True):
    import psycopg2
    conn = psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )
    if readonly:
        # PG 事务层硬拒绝任何写操作，作为 AI 生成 SQL 的主防线
        conn.set_session(readonly=True)
    return conn


def get_schema_info() -> str:
    """获取数据库表结构信息，供 AI 生成 SQL"""
    conn = get_db_connection()
    schema_lines = []
    try:
        cur = conn.cursor()

        # 获取所有用户表
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]

        # 关键业务表优先
        priority_tables = [
            'res_users', 'res_partner', 'res_company',
            'product_template', 'product_product',
            'account_move', 'account_move_line',
            'sale_order', 'sale_order_line',
            'purchase_order', 'purchase_order_line',
            'stock_picking', 'stock_move',
        ]

        important_tables = priority_tables + [
            t for t in tables
            if t.startswith(('res_', 'product_', 'account_', 'sale_', 'purchase_', 'stock_', 'hr_', 'crm_', 'pos_'))
            and t not in priority_tables
            and not t.startswith(('ir_', '__'))
        ][:20]

        schema_lines = [f"Tables ({len(tables)} total): {', '.join(tables[:30])}..."]

        for table in important_tables[:15]:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position
                LIMIT 10
            """, (table,))
            columns = cur.fetchall()
            if columns:
                col_strs = [f"{c[0]}:{c[1]}" for c in columns]
                schema_lines.append(f"{table}: {', '.join(col_strs)}")

        cur.close()
    finally:
        conn.close()

    # 清理非法 Unicode 字符（surrogate 等）
    result = "\n".join(schema_lines)
    result = "".join(c if ord(c) < 0xD800 or ord(c) > 0xDFFF else "�" for c in result)
    return result


def execute_sql(sql: str) -> tuple[bool, str]:
    """执行只读 SQL 并返回结果。

    双重护栏：(1) 首关键字白名单 _is_readonly_sql；(2) 只读事务连接，
    PG 在事务层硬拒绝任何写操作（含多语句中的写）。
    """
    if not _is_readonly_sql(sql):
        return False, "仅允许只读查询（SELECT/WITH/EXPLAIN/SHOW），已拒绝执行"

    conn = None
    try:
        conn = get_db_connection(readonly=True)
        cur = conn.cursor()
        cur.execute(sql)

        if cur.description:
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchmany(100)  # 最多返回 100 行

            result = [columns]
            for row in rows:
                result.append([str(v) if v is not None else "NULL" for v in row])

            return True, json.dumps(result, ensure_ascii=False, indent=2)
        else:
            return True, "查询无返回结果"

    except Exception as e:
        return False, f"SQL 错误: {str(e)}"
    finally:
        if conn is not None:
            conn.close()


# --- CodeBuddy API 调用 ---

async def ask_codebuddy(prompt: str, system_prompt: str) -> str:
    from codebuddy_adapter import load_config, CodeBuddyClient
    config = load_config()
    client = CodeBuddyClient(config)
    return await client.query_text(prompt, system_prompt=system_prompt)


async def generate_sql(question: str, schema: str) -> str:
    """用 AI 将自然语言转换为 SQL"""
    system_prompt = f"""你是一个 Odoo PostgreSQL 数据库专家。根据用户的自然语言问题，生成 SQL 查询语句。

数据库表结构：
{schema}

规则：
1. 只输出 SQL 语句，不要解释
2. 使用 PostgreSQL 语法
3. 默认添加 LIMIT 100 限制结果数量
4. 对于大文本字段使用 LEFT 截断
5. 如果问题不明确，生成最合理的查询
6. 只能生成只读 SELECT 查询，不要使用 DROP、DELETE、UPDATE、INSERT 等修改操作
7. 表名和列名区分大小写（PostgreSQL 默认小写）"""

    return await ask_codebuddy(question, system_prompt)


async def explain_result(question: str, sql: str, result: str) -> str:
    """用 AI 解释查询结果"""
    system_prompt = """你是一个数据分析助手。根据用户的 SQL 查询和结果，用简洁的中文解释数据含义。
如果结果为空，说明可能的原因。"""

    prompt = f"""用户问题: {question}

执行的 SQL:
{sql}

查询结果:
{result}

请用简洁的中文解释结果："""

    return await ask_codebuddy(prompt, system_prompt=system_prompt)


# --- 主程序 ---

async def query_loop():
    """交互式查询循环"""
    print("=" * 60)
    print("  Odoo 数据库自然语言查询助手")
    print("  输入问题查询数据库，输入 'quit' 退出")
    print("=" * 60)

    print("\n正在加载数据库结构...")
    schema = get_schema_info()
    print(f"已加载 {len(schema.splitlines())} 个表的信息\n")

    while True:
        try:
            question = input("问题> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            break

        if not question or question.lower() in ("quit", "exit", "q"):
            print("再见!")
            break

        # 1. 生成 SQL
        print("\n正在生成 SQL...")
        sql = _strip_sql_fence(await generate_sql(question, schema))
        print(f"SQL: {sql}\n")

        # 2. 确认执行
        try:
            confirm = input("执行? (y/n/edit) > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            break

        if confirm == "n":
            continue
        elif confirm == "edit":
            sql = input("编辑 SQL> ").strip()

        # 3. 执行 SQL（execute_sql 内部仍有只读护栏，手输写语句同样会被拒）
        print("\n正在执行...")
        success, result = execute_sql(sql)

        if not success:
            print(f"\n❌ {result}\n")
            continue

        print(f"\n结果:\n{result}\n")

        # 4. 解释结果
        if success and result.startswith("["):
            print("正在分析结果...")
            explanation = await explain_result(question, sql, result)
            print(f"\n{explanation}\n")

        print("-" * 40)


async def single_query(question: str, assume_yes: bool = False) -> None:
    """单次查询"""
    print("正在加载数据库结构...")
    schema = get_schema_info()

    print("正在生成 SQL...")
    sql = _strip_sql_fence(await generate_sql(question, schema))
    print(f"SQL: {sql}\n")

    # 非交互模式默认要求确认，避免 AI 生成的语句未经审阅就执行
    if not assume_yes:
        try:
            confirm = input("执行? (y/n) > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return
        if confirm != "y":
            print("已取消")
            return

    print("正在执行...")
    success, result = execute_sql(sql)

    if not success:
        print(f"❌ {result}")
        return

    print(f"结果:\n{result}")

    if success and result.startswith("["):
        print("\n正在分析...")
        explanation = await explain_result(question, sql, result)
        print(f"\n{explanation}")


def main():
    # 仅作为脚本运行时才把 stdout/stderr 包成 UTF-8，避免被 import 时产生全局副作用
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    args = list(sys.argv[1:])
    assume_yes = False
    for flag in ("-y", "--yes"):
        while flag in args:
            args.remove(flag)
            assume_yes = True

    if args:
        question = " ".join(args)
        asyncio.run(single_query(question, assume_yes=assume_yes))
    else:
        asyncio.run(query_loop())


if __name__ == "__main__":
    main()
