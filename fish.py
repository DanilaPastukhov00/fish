from flask import Flask, Response, request, send_file, render_template, redirect, url_for, flash, session
import os
import io
import sqlite3
import base64
from datetime import datetime

UPLOAD_FOLDER = r"fish_receiver"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DB_FILE = os.path.join(UPLOAD_FOLDER, "fish_receiver.db")

app = Flask(__name__)
app.secret_key = "secret"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_next_version(conn, section_id, file_name, file_extension):
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(MAX(version), 0) + 1
        FROM registration_files
        WHERE section_id=? AND file_name=? AND file_extension=?
    """, (section_id, file_name, file_extension))
    return cur.fetchone()[0]

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sections (
            section_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_creation_section TIMESTAMP NOT NULL,
            section_name TEXT NOT NULL UNIQUE,
            section_password TEXT NOT NULL
        );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registration_files (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_add_file TIMESTAMP NOT NULL,
            section_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_extension TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            FOREIGN KEY (section_id) REFERENCES Sections(section_id),
            UNIQUE (section_id, file_name, file_extension, version)
        );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id INTEGER NOT NULL,
            file TEXT NOT NULL,
            FOREIGN KEY (registration_id) REFERENCES registration_files(registration_id)
        );
        """)
        conn.commit()

@app.route("/", methods=["GET"])
def sections():
    search = request.args.get("search", "").strip()
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        if search:
            cur.execute("""
                SELECT s.section_name, COUNT(rf.registration_id) as files_count
                FROM sections s
                LEFT JOIN registration_files rf ON s.section_id = rf.section_id
                WHERE s.section_name LIKE ?
                GROUP BY s.section_id
                ORDER BY files_count DESC
                LIMIT 5
            """, (f"%{search}%",))
        else:
            cur.execute("""
                SELECT s.section_name, COUNT(rf.registration_id) as files_count
                FROM sections s
                LEFT JOIN registration_files rf ON s.section_id = rf.section_id
                GROUP BY s.section_id
                ORDER BY files_count DESC
                LIMIT 5
            """)
        top_sections = cur.fetchall()
    return render_template("sections.html", top_sections=top_sections, search=search)

@app.route("/registration", methods=["GET", "POST"])
def registration():
    if request.method == "POST":
        name = request.form.get("username")
        pwd = request.form.get("password")
        if not name or not pwd:
            flash("Заполните все поля!")
            return render_template('registration.html')
        try:
            with sqlite3.connect(DB_FILE, timeout=10) as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO sections (date_creation_section, section_name, section_password) VALUES (?, ?, ?)",
                    (datetime.now(), name, pwd)
                )
                conn.commit()
            flash(f"Вкладка {name} успешно создана!")
            return redirect(url_for("sections"))
        except sqlite3.IntegrityError:
            flash("Вкладка с таким именем уже существует!")
            return render_template('registration.html')
    return render_template('registration.html')

@app.route("/section/<name>", methods=["GET", "POST"])
def password_to_section(name):
    error = None
    if request.method == "POST":
        pwd = request.form.get("password")
        with sqlite3.connect(DB_FILE, timeout=10) as conn:
            cur = conn.cursor()
            cur.execute("SELECT section_password FROM sections WHERE section_name=?", (name,))
            row = cur.fetchone()
        if row and row[0] == pwd:
            session[f"auth_{name}"] = True
            return redirect(url_for("add_file", name=name))
        else:
            error = "Неверный пароль!"
    return render_template('password_to_section.html', name=name, error=error)

@app.route("/section/<name>/add-file", methods=["GET", "POST"])
def add_file(name):
    if not session.get(f"auth_{name}"):
        return redirect(url_for("password_to_section", name=name))
    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename:
            ext = os.path.splitext(file.filename)[1]
            with sqlite3.connect(DB_FILE, timeout=10) as conn:
                cur = conn.cursor()
                cur.execute("SELECT section_id FROM sections WHERE section_name=?", (name,))
                row = cur.fetchone()
                if not row:
                    flash("Вкладка не найдена!")
                    return redirect(url_for("sections"))
                section_id = row[0]
                version = get_next_version(conn, section_id, file.filename, ext)
                cur.execute(
                    "INSERT INTO registration_files (date_add_file, section_id, file_name, file_extension, version) VALUES (?, ?, ?, ?, ?)",
                    (datetime.now(), section_id, file.filename, ext, version)
                )
                registration_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO files (registration_id, file) VALUES (?, ?)",
                    (registration_id, file.read())
                )
                conn.commit()
            flash("Файл загружен!")
        else:
            flash("Файл не выбран!")
    return render_template('add_file.html', name=name)

@app.route("/section/<name>/sent-files")
def sent_files(name):
    if not session.get(f"auth_{name}"):
        return redirect(url_for("password_to_section", name=name))
    with sqlite3.connect(DB_FILE, timeout=10) as conn:
        cur = conn.cursor()
        cur.execute("SELECT section_id FROM sections WHERE section_name=?", (name,))
        row = cur.fetchone()
        if not row:
            flash("Вкладка не найдена!")
            return redirect(url_for("sections"))
        section_id = row[0]
        cur.execute("""
            SELECT rf.file_name, MAX(rf.version)
            FROM registration_files rf
            WHERE rf.section_id = ?
            GROUP BY rf.file_name
            ORDER BY MAX(rf.date_add_file) DESC
            LIMIT 20
        """, (section_id,))
        files = cur.fetchall()
    return render_template("sent_files.html", files=files, section_name=name)

@app.route("/section/<name>/download-history")
def download_history(name):
    if not session.get(f"auth_{name}"):
        return redirect(url_for("password_to_section", name=name))
    file_name = request.args.get("file_name")
    if not file_name:
        return "Файл не указан", 400
    with sqlite3.connect(DB_FILE, timeout=10) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT rf.file_name, rf.date_add_file, rf.version
            FROM registration_files rf
            JOIN sections s ON rf.section_id = s.section_id
            WHERE rf.file_name = ? AND s.section_name = ?
            ORDER BY rf.version DESC
        """, (file_name, name))
        versions = cur.fetchall()
    return render_template("download_history.html", versions=versions, file_name=file_name, section_name=name)

@app.route("/section/<name>/download/<file_name>/<int:version>")
def download_file(name, file_name, version):
    if not session.get(f"auth_{name}"):
        return redirect(url_for("password_to_section", name=name))
    with sqlite3.connect(DB_FILE, timeout=10) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT f.file, rf.file_extension
            FROM registration_files rf
            JOIN files f ON rf.registration_id = f.registration_id
            JOIN sections s ON rf.section_id = s.section_id
            WHERE rf.file_name = ? AND rf.version = ? AND s.section_name = ?
            ORDER BY rf.date_add_file DESC
            LIMIT 1
        """, (file_name, version, name))
        row = cur.fetchone()
    if row:
        file_data, file_extension = row
        return send_file(
            io.BytesIO(file_data),
            as_attachment=True,
            download_name=f"{file_name}",
            mimetype="application/octet-stream"
        )
    else:
        return "Файл не найден", 404
    

# API
API_USER = os.environ.get("FISH_API_USER")
API_PASSWORD = os.environ.get("FISH_API_PASSWORD")

def check_auth(username, password):
    return username == API_USER and password == API_PASSWORD

def authenticate():
    return Response(
        'Требуется авторизация', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

@app.route("/api/all_data", methods=["GET"])
def get_full_data():
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                s.section_id,
                s.section_name,
                s.date_creation_section,
                s.section_password,
                rf.registration_id,
                rf.date_add_file,
                rf.file_name,
                rf.file_extension,
                rf.version,
                f.file_id,
                f.file
            FROM sections s
            LEFT JOIN registration_files rf ON s.section_id = rf.section_id
            LEFT JOIN files f ON rf.registration_id = f.registration_id
            ORDER BY s.section_id, rf.registration_id, f.file_id
        """)
        sections = []
        for row in cur.fetchall():
            file_bytes = row[10]
            if file_bytes is not None:
                file_str = base64.b64encode(file_bytes).decode('utf-8')
            else:
                file_str = None
            sections.append({
                "section_id": row[0],
                "section_name": row[1],
                "date_creation_section": row[2],
                "section_password": row[3],
                "registration_id": row[4],
                "date_add_file": row[5],
                "file_name": row[6],
                "file_extension": row[7],
                "version": row[8],
                "file_id": row[9],
                "file": file_str
            })
    return {"data": sections}

if __name__ == "__main__":
    port = 3001
    init_db()
    app.run(port=port, debug=True)