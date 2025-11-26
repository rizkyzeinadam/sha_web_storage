from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, Folder, File, bcrypt
from config import Config
from utils.aes_encrypt import encrypt_file, decrypt_file
import io
import os

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
bcrypt.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ------------------ Register User (sekali saja) ------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        pwd = request.form.get("password")

        user = User(email=email)
        user.set_password(pwd)

        db.session.add(user)
        db.session.commit()

        flash("User created!")
        return redirect("/login")

    return render_template("register.html")


# ------------------ Login ------------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        pwd = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(pwd):
            login_user(user)
            return redirect("/dashboard")
        flash("Email atau password salah")

    return render_template("login.html")


# ------------------ Dashboard ------------------
@app.route("/dashboard")
@login_required
def dashboard():
    folder_id = request.args.get('folder_id', type=int)
    page = request.args.get('page', 1, type=int)
    
    current_folder = None
    if folder_id:
        current_folder = Folder.query.get_or_404(folder_id)
        # Ensure folder belongs to user
        if current_folder.user_id != current_user.id:
            flash("Unauthorized access!")
            return redirect(url_for('dashboard'))

    # If we are in a folder, we don't show subfolders (flat structure assumption)
    # If we are at root (folder_id is None), we show folders
    folders = []
    if folder_id is None:
        folders = Folder.query.filter_by(user_id=current_user.id).all()

    # Fetch files for current folder (or root)
    # Pagination: 25 items per page
    files_query = File.query.filter_by(user_id=current_user.id, folder_id=folder_id)
    files_pagination = files_query.paginate(page=page, per_page=25, error_out=False)

    return render_template(
        "dashboard.html", 
        folders=folders, 
        files=files_pagination, 
        current_folder=current_folder
    )


# ------------------ Create Folder ------------------
@app.route("/create-folder", methods=["POST"])
@login_required
def create_folder():
    folder_name = request.form.get("folder_name")
    if folder_name:
        new_folder = Folder(name=folder_name, owner=current_user)
        db.session.add(new_folder)
        db.session.commit()
        flash("Folder created!")
    return redirect("/dashboard")


# ------------------ Upload File ------------------
@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files["file"]

        # Pastikan folder uploads ada
        os.makedirs("uploads", exist_ok=True)

        # Save file asli sementara
        original_path = os.path.join("uploads", file.filename)
        file.save(original_path)

        # AES-256 Encryption 32 bytes
        encrypted_path = encrypt_file(
            original_path,
            key="s3ribuMimpi"
        )

        # Hapus file asli agar tidak menuh-menuhin storage
        if os.path.exists(original_path):
            os.remove(original_path)

        # Simpan metadata ke database
        folder_id = request.form.get('folder_id', type=int)
        # Verify folder ownership if provided
        if folder_id:
            folder = Folder.query.get(folder_id)
            if not folder or folder.user_id != current_user.id:
                folder_id = None # Fallback to root if invalid

        new_file = File(
            filename=file.filename,
            filepath=encrypted_path,
            user_id=current_user.id,
            folder_id=folder_id
        )
        db.session.add(new_file)
        db.session.commit()

        flash(f"File terenkripsi tersimpan sebagai: {encrypted_path}")
        
        if folder_id:
             return redirect(url_for('dashboard', folder_id=folder_id))
        return redirect("/dashboard")

    return render_template("upload.html")


# ------------------ Download File ------------------
@app.route("/download/<int:file_id>")
@login_required
def download_file(file_id):
    file_record = File.query.get_or_404(file_id)

    # Pastikan yang download adalah pemilik file
    if file_record.user_id != current_user.id:
        flash("Unauthorized access!")
        return redirect("/dashboard")

    try:
        decrypted_data = decrypt_file(file_record.filepath, key="s3ribuMimpi")
        
        return send_file(
            io.BytesIO(decrypted_data),
            as_attachment=True,
            download_name=file_record.filename
        )
    except Exception as e:
        flash(f"Error decrypting file: {str(e)}")
        return redirect("/dashboard")


# ------------------ Delete File ------------------
@app.route("/delete-file/<int:file_id>")
@login_required
def delete_file(file_id):
    file_record = File.query.get_or_404(file_id)

    if file_record.user_id != current_user.id:
        flash("Unauthorized access!")
        return redirect("/dashboard")

    # Remove physical file
    if os.path.exists(file_record.filepath):
        os.remove(file_record.filepath)

    # Remove from DB
    db.session.delete(file_record)
    db.session.commit()

    flash("File deleted!")
    
    # Redirect back to the same folder if applicable
    if file_record.folder_id:
        return redirect(url_for('dashboard', folder_id=file_record.folder_id))
    return redirect("/dashboard")


# ------------------ Delete Folder ------------------
@app.route("/delete-folder/<int:folder_id>")
@login_required
def delete_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)

    if folder.user_id != current_user.id:
        flash("Unauthorized access!")
        return redirect("/dashboard")

    # Delete all files in the folder
    files = File.query.filter_by(folder_id=folder.id).all()
    for f in files:
        if os.path.exists(f.filepath):
            os.remove(f.filepath)
        db.session.delete(f)

    # Delete folder from DB
    db.session.delete(folder)
    db.session.commit()

    flash("Folder and all its contents deleted!")
    return redirect("/dashboard")


# ------------------ Logout ------------------
@app.route("/logout")
def logout():
    logout_user()
    return redirect("/login")


# ------------------ Init DB ------------------
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
