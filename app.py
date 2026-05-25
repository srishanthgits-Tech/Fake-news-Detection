import random
import smtplib
import qrcode
import os
from base64 import b64encode
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_bcrypt import Bcrypt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_session import Session
from flask_migrate import Migrate
import wikipedia
from keras.models import load_model
from PIL import Image, ImageChops, ImageEnhance
import numpy as np
import os

# Load model
fake_model = load_model('model.h5')

UPLOAD_FOLDER = "static/uploads/"

app = Flask(__name__)

# Secret Key for Session
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'srishanthgits@gmail.com'
app.config['MAIL_PASSWORD'] = 'hsbzgirmqdchfoci'
app.config['MAIL_DEFAULT_SENDER'] = 'parreddynavyareddy@gmail.com'

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Flask-Session Config (for Persistent Sessions)
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Initialize Extensions
mail = Mail(app)
bcrypt = Bcrypt(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    district = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<User {self.name}>"

### register otp #####

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(recipient_email, otp):
    subject = "Your OTP Code"
    body = f"Your OTP code is: {otp}"
    
    msg = MIMEMultipart()
    msg['From'] = app.config['MAIL_USERNAME']
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.sendmail(app.config['MAIL_USERNAME'], recipient_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        city = request.form['city']
        district = request.form['district']
        
        session['user_details'] = {'name': name, 'email': email, 'phone': phone, 'password': password, 'city': city, 'district': district}
        
        otp = generate_otp()
        session['otp'] = otp
        
        if send_otp_email(email, otp):
            return redirect(url_for('verify_otp'))
        else:
            flash('Failed to send OTP. Try again.', 'danger')
    return render_template('register.html')


@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        user_otp = request.form['otp']
        if 'otp' in session and session['otp'] == user_otp:
            user_details = session.pop('user_details', None)
            
            if user_details:
                # Check if user already exists
                existing_user = User.query.filter_by(email=user_details['email']).first()
                if existing_user:
                    flash('User already registered. Please login.', 'warning')
                    return redirect(url_for('login'))

                new_user = User(
                    name=user_details['name'],
                    email=user_details['email'],
                    phone=user_details['phone'],
                    password=user_details['password'],
                    city = user_details['city'],
                    district=user_details['district']
                )
                db.session.add(new_user)
                db.session.commit()

                print(f"✅ User saved: {new_user.email}")  # Debug: Ensure user is saved
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
        else:
            flash('Invalid OTP. Please try again.', 'danger')
    return render_template('verify_otp.html')

########### Login Section #####################
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name  # Store name in session for personalization
            print(f"✅ User logged in: {user.email}")  # Debug message
            flash('Login successful!', 'success')
            return  redirect(url_for('home'))
        
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    return render_template('home.html')


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Ensure user is logged in
    content = None
    if request.method == 'POST':
        topic = request.form['topic']
        try:
            content = wikipedia.page(topic).content
        except wikipedia.exceptions.DisambiguationError as e:
            content = f"Multiple results found: {e.options[:5]}"
        except wikipedia.exceptions.PageError:
            content = "Topic not found. Please try another one."
        except Exception as e:
            content = f"An error occurred: {e}"
        return render_template('dashboard.html', topic=topic, content=content)
    return render_template('dashboard.html', topic=None, content=None)

import re
def check_fake_content(content):
    fake_keywords = ["conspiracy", "hoax", "fake news", "misleading"]
    for word in fake_keywords:
        if re.search(word, content, re.IGNORECASE):
            return "Fake"
    return "Real"

@app.route('/summarize', methods=['POST'])
def summarize():
    topic = request.form['topic']
    try:
        summary = wikipedia.summary(topic, sentences=5)
        status = check_fake_content(summary)
    except wikipedia.exceptions.DisambiguationError as e:
        summary = f"Multiple results found: {e.options[:5]}"
        status = "Unknown"
    except wikipedia.exceptions.PageError:
        summary = "Topic not found. Please try another one."
        status = "Unknown"
    except Exception as e:
        summary = f"An error occurred: {e}"
        status = "Unknown"
    return render_template('summary.html', topic=topic, summary=summary, status=status)


@app.route('/download/<topic>')
def download_article(topic):
    try:
        content = wikipedia.page(topic).content
        file_path = f"{topic}.txt"
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return f"An error occurred: {e}"

@app.route('/share/<topic>')
def share_article(topic):
    share_link = request.url_root + f"download/{topic}"
    return render_template('share.html', topic=topic, share_link=share_link)

####################################################################

def convert_to_ela_image(path, quality=90):
    resaved_filename = 'static/tempresaved.jpg'

    im = Image.open(path).convert('RGB')
    im.save(resaved_filename, 'JPEG', quality=quality)
    resaved_im = Image.open(resaved_filename)

    ela_im = ImageChops.difference(im, resaved_im)

    extrema = ela_im.getextrema()
    max_diff = max([ex[1] for ex in extrema])
    if max_diff == 0:
        max_diff = 1

    scale = 255.0 / max_diff
    ela_im = ImageEnhance.Brightness(ela_im).enhance(scale)

    return ela_im


def predict_fake_image(file_path):
    X = []

    ela_img = convert_to_ela_image(file_path, 90).resize((128, 128))
    X.append(np.array(ela_img).flatten() / 255.0)

    X = np.array(X)
    X = X.reshape(-1, 128, 128, 3)

    pred = fake_model.predict(X)
    pred = np.argmax(pred, axis=1)[0]

    if pred == 0:
        return "Real Image ✅"
    else:
        return "Fake Image ⚠️"
    

@app.route("/fake_image", methods=["GET", "POST"])
def fake_image():
    if request.method == "POST":
        file = request.files["image"]

        if file.filename == "":
            return render_template("fake_image.html", result="No file selected ❌")

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        result = predict_fake_image(filepath)

        return render_template("fake_image.html", result=result, image=filepath)

    return render_template("fake_image.html")





# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Run Flask App
import os

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)