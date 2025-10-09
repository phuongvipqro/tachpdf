import os
import io
import zipfile
import datetime
import chardet
from flask import Flask, render_template, request, send_file, jsonify
from PyPDF2 import PdfReader, PdfWriter
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["OUTPUT_FOLDER"] = "outputs"  # chỉ dùng để lưu log

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)

LOG_FILE = os.path.join(app.config["OUTPUT_FOLDER"], "log.txt")

# Bộ nhớ tạm để giữ zip cuối cùng
LAST_ZIP = {}

def write_log(username, action, details):
    """Ghi log vào file outputs/log.txt"""
    time_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"🕒 Thời gian: {time_now}\n")
        f.write(f"👤 Người dùng: {username}\n")
        f.write(f"📌 Hành động: {action}\n")
        f.write(f"📄 Chi tiết: {details}\n")
        f.write(f"{'='*60}\n")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/split", methods=["POST"])
def split_pdf():
    try:
        pdf_file = request.files["pdf_file"]
        names_file = request.files["names_file"]
        pages_per_file = int(request.form["pages_per_file"])
        username = request.form.get("username", "Ẩn danh")

        # Lưu file upload
        pdf_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(pdf_file.filename))
        names_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(names_file.filename))
        pdf_file.save(pdf_path)
        names_file.save(names_path)

        # Phát hiện encoding của file names.txt để tránh lỗi
        with open(names_path, "rb") as raw:
            raw_data = raw.read()
            result = chardet.detect(raw_data)
            encoding = result["encoding"] if result["encoding"] else "utf-8"

        with open(names_path, "r", encoding=encoding, errors="ignore") as f:
            new_names = [line.strip() for line in f if line.strip()]

        # Đọc PDF
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        if total_pages == 0:
            return jsonify({"status": "error", "message": "File PDF không có trang nào!"})

        # Tạo file ZIP trong bộ nhớ
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            name_index = 0
            contract_index = 1
            generated_files = []

            for i in range(0, total_pages, pages_per_file):
                writer = PdfWriter()
                for j in range(i, min(i + pages_per_file, total_pages)):
                    writer.add_page(reader.pages[j])

                if name_index < len(new_names):
                    output_name = f"{new_names[name_index]}.pdf"
                else:
                    output_name = f"hopdong_{contract_index}.pdf"

                pdf_bytes = io.BytesIO()
                writer.write(pdf_bytes)
                pdf_bytes.seek(0)

                zipf.writestr(output_name, pdf_bytes.read())
                generated_files.append(output_name)

                name_index += 1
                contract_index += 1

        zip_buffer.seek(0)
        LAST_ZIP["buffer"] = zip_buffer
        LAST_ZIP["filename"] = "contracts.zip"

        # Ghi log
        details = f"Tách {pdf_file.filename} thành {len(generated_files)} file: {', '.join(generated_files)}"
        write_log(username, "Tách PDF", details)

        return jsonify({"status": "success", "message": "Tách PDF thành công! Nhấn nút để tải ZIP."})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Lỗi xử lý: {str(e)}"})

@app.route("/download_zip")
def download_zip():
    if "buffer" in LAST_ZIP:
        zip_buffer = LAST_ZIP["buffer"]
        filename = LAST_ZIP["filename"]
        zip_buffer.seek(0)
        return send_file(zip_buffer, as_attachment=True, download_name=filename, mimetype="application/zip")
    return "❌ Không có file ZIP nào sẵn để tải.", 404

if __name__ == "__main__":
    app.run(debug=True)
