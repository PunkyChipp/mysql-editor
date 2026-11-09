"""Run with: python main.py. No passwords stored in coursework."""
import os
import mysql.connector

with mysql.connector.connect(
    host=os.environ["MYSQL_HOST"],
    user=os.environ["MYSQL_USER"],
    password=os.environ["MYSQL_PASSWORD"],
    database=os.environ["MYSQL_DATABASE"],
) as connection:
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE IF NOT EXISTS students (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100) NOT NULL)")
        cursor.execute("SELECT COUNT(*) FROM students")
        count_row = cursor.fetchone()
        if count_row is not None and count_row[0] == 0:
            cursor.executemany("INSERT INTO students (name) VALUES (%s)", [("Alex",), ("Sam",)])
        connection.commit()
        cursor.execute("SELECT id, name FROM students ORDER BY id")
        for row in cursor:
            print(row)
