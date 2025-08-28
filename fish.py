from flask import Flask, request, render_template_string, redirect, url_for, flash
import os

# Папка, куда будут сохраняться файлы
UPLOAD_FOLDER = r"fish_receiver"  # 👉 укажи свой путь
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "secret"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

HTML_PAGE = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Загрузка файла</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cherry+Bomb+One&family=Rampart+One&family=Rubik+Glitch&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
  <style>
    html { height: 100%; }
    body {
      background-color: #2590EB;
      height: 100%;
      margin: 0;
      font-family: Arial, sans-serif; /* 👉 по умолчанию Arial */
    }
    .logo {
      position: absolute;
      top: 20px;
      left: 30px;
      font-family: 'Cherry Bomb One', Arial, sans-serif; /* 👉 для Fish */
      font-size: 36px;
      color: #fff;
      user-select: none;
    }
    .wrapper {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
    }
    .file-upload {
      height: 200px;
      width: 200px;
      border-radius: 100px;
      position: relative;
      display: flex;
      justify-content: center;
      align-items: center;
      border: 4px solid #FFFFFF;
      overflow: hidden;
      background-image: linear-gradient(to bottom, #2590EB 50%, #FFFFFF 50%);
      background-size: 100% 200%;
      transition: all 1s;
      color: #FFFFFF;
      font-size: 100px;
    }
    .file-upload input[type='file'] {
      height: 200px;
      width: 200px;
      position: absolute;
      top: 0;
      left: 0;
      opacity: 0;
      cursor: pointer;
    }
    .file-upload:hover {
      background-position: 0 -100%;
      color: #2590EB;
    }
    .message {
      margin-top: 20px;
      color: #fff;
      font-size: 18px;
    }
  </style>
</head>
<body>
  <div class="logo">Fish</div>
  <div class="wrapper">
    <form class="file-upload" method="post" enctype="multipart/form-data">
      <input type="file" name="file" onchange="this.form.submit()" />
      <i class="fa fa-arrow-up"></i>
    </form>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <div class="message">
          {% for msg in messages %}
            <p>{{ msg }}</p>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
  </div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            flash("Файл не выбран")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            flash("Файл не выбран")
            return redirect(request.url)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        flash(f"Файл ({file.filename}) успешно загружен!")
        return redirect(url_for("upload_file"))

    return render_template_string(HTML_PAGE)


if __name__ == "__main__":
    app.run(debug=True)
