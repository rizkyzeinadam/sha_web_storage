from app import app, db
from models import User

with app.app_context():
    user = User(email="gustanto@mail.com")
    user.set_password("passwordku123")
    db.session.add(user)
    db.session.commit()
    print("User berhasil dibuat!")
