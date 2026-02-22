from flask import Flask, request, render_template, url_for,flash, redirect, jsonify, session
import pandas as pd
from openai import OpenAI
from datetime import datetime
from werkzeug.utils import secure_filename
import json
import time
import uuid
import re
from typing import Dict, Any, Optional
import traceback
import os

app = Flask(__name__)

app.secret_key = os.urandom(24)

SAVE_DIR = "excel_files"
os.makedirs(SAVE_DIR, exist_ok=True)
PROFILE_DIR = os.path.join("static", "profile_pics")
os.makedirs(PROFILE_DIR, exist_ok=True)
PROFILE_FILE = os.path.join(SAVE_DIR, "profiles.xlsx")
USERS_FILE = os.path.join(SAVE_DIR, "users.xlsx")

INTERACT_FILE = os.path.join(SAVE_DIR, "interactions.xlsx")

EVALUATION_FILE = os.path.join(SAVE_DIR, "evaluations.xlsx")

@app.route('/evaluations')
def show_evaluations():
    try:
        if "username" not in session:
            return redirect('/login')

        username = session["username"]
        item_id = request.args.get("item_id")

        if not item_id:
            return render_template(
                'evaluations.html',
                username=username,
                evaluations=[],
                message="محتوای مشخصی انتخاب نشده است."
            )

        if not os.path.exists(EVALUATION_FILE):
            return render_template(
                'evaluations.html',
                username=username,
                evaluations=[],
                message="هنوز هیچ ارزیابی ثبت نشده است."
            )

        df = pd.read_excel(EVALUATION_FILE)

        content_evaluations = df[df['item_id'] == int(item_id)]

        if content_evaluations.empty:
            return render_template(
                'evaluations.html',
                username=username,
                evaluations=[],
                message="برای این محتوا هنوز ارزیابی‌ای ثبت نشده است."
            )

        evaluations = []
        for _, row in content_evaluations.iterrows():
            evaluations.append({
                'username': row['username'],
                'category': row['category'],
                'item_id': row['item_id'],
                'fluency': row['fluency'],
                'creativity': row['creativity'],
                'emotional_impact': row['emotional_impact'],
                'imagery': row['imagery'],
                'coherence': row['coherence'],
                'format_suitability': row['format_suitability'],
                'clarity': row['clarity'],
                'overall_value': row['overall_value'],
                'additional_comment': row.get('additional_comment', ''),
                'timestamp': row.get('timestamp', ''),
                'average_score': round((
                    row['fluency'] + row['creativity'] + row['emotional_impact'] +
                    row['imagery'] + row['coherence'] + row['format_suitability'] +
                    row['clarity'] + row['overall_value']
                ) / 8, 1)
            })

        return render_template(
            'evaluations.html',
            username=username,
            evaluations=evaluations,
            total=len(evaluations)
        )

    except Exception as e:
        print("Error loading evaluations:", e)
        return render_template(
            'evaluations.html',
            username=session.get("username", ""),
            evaluations=[],
            error="خطا در بارگذاری ارزیابی‌ها"
        )


@app.route('/evaluate/<cat>/<item_id>', methods=['POST'])
def evaluate(cat, item_id):
    try:

        if "username" not in session:
            return jsonify({
                "success": False,
                "error": "ابتدا وارد شوید"
            }), 401

        username = session["username"]

        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "No data received"
            }), 400

        required_fields = [
            'fluency',
            'creativity',
            'emotional_impact',
            'imagery',
            'coherence',
            'format_suitability',
            'clarity',
            'overall_value'
        ]

        for field in required_fields:
            if field not in data or data[field] == '':
                return jsonify({
                    "success": False,
                    "error": f"Missing field: {field}"
                }), 400

        if os.path.exists(EVALUATION_FILE):
            df_old = pd.read_excel(EVALUATION_FILE)
        else:
            df_old = pd.DataFrame()

        for col in ['username', 'category', 'item_id']:
            if col not in df_old.columns:
                df_old[col] = None

        duplicate = df_old[
            (df_old['username'] == username) &
            (df_old['category'] == cat) &
            (df_old['item_id'].astype(str) == str(item_id))
        ]

        if not duplicate.empty:
            return jsonify({
                "success": False,
                "error": "شما قبلاً این اثر را ارزیابی کرده‌اید"
            }), 403

        row = {
            'username': username,
            'category': cat,
            'item_id': item_id,
            'fluency': int(data['fluency']),
            'creativity': int(data['creativity']),
            'emotional_impact': int(data['emotional_impact']),
            'imagery': int(data['imagery']),
            'coherence': int(data['coherence']),
            'format_suitability': int(data['format_suitability']),
            'clarity': int(data['clarity']),
            'overall_value': int(data['overall_value']),
            'additional_comment': data.get('additional_comment', ''),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        df_new = pd.DataFrame([row])
        df = pd.concat([df_old, df_new], ignore_index=True)

        df.to_excel(EVALUATION_FILE, index=False)

        return jsonify({"success": True})

    except Exception as e:
        print("SERVER ERROR:", e)
        return jsonify({
            "success": False,
            "error": "خطای داخلی سرور"
        }), 500





@app.route("/", methods=["GET", "POST"])
def index():
    username = session.get('username', 'guest')

    if username == 'guest':
        if request.method == "POST":
            return redirect(url_for('login'))

        profiles = {}
        if os.path.exists(PROFILE_FILE):
            df_profiles = pd.read_excel(PROFILE_FILE)
            for _, row in df_profiles.iterrows():
                profiles[row['username']] = {
                    "first_name": row['first_name'],
                    "last_name": row['last_name'],
                    "phone": row['phone'],
                    "email": row['email'],
                    "photo": row['photo'],
                    "bio": row['bio'] if 'bio' in row else ""
                }

        def attach_author(records):
            for rec in records:
                user = rec.get("username")
                if user in profiles:
                    rec['first_name'] = profiles[user]['first_name']
                    rec['last_name'] = profiles[user]['last_name']
                else:
                    rec['first_name'] = ""
                    rec['last_name'] = ""
                rec['status'] = rec.get('status', 'public')
                rec['tags'] = rec.get('tags', '')
                rec['readability'] = rec.get('readability', 'easy')
                rec['publish_date'] = rec.get('publish_date', '')
                rec['created_at'] = rec.get('created_at', '')
            return records

        poems = attach_author(get_latest_records(route_map['poems']['file'], n=4))
        stories = attach_author(get_latest_records(route_map['stories']['file'], n=4))
        literature = attach_author(get_latest_records(route_map['literature']['file'], n=4))

        def get_total_count(file_name):
            file_path = os.path.join(SAVE_DIR, file_name)
            if os.path.exists(file_path):
                df = pd.read_excel(file_path)
                return len(df)
            return 0

        poems_count = get_total_count(route_map['poems']['file'])
        stories_count = get_total_count(route_map['stories']['file'])
        literature_count = get_total_count(route_map['literature']['file'])

        authors_count = 0
        if os.path.exists(PROFILE_FILE):
            df_profiles = pd.read_excel(PROFILE_FILE)
            active_usernames = set()
            for cat in ['poems', 'stories', 'literature']:
                file_path = os.path.join(SAVE_DIR, route_map[cat]['file'])
                if os.path.exists(file_path):
                    df = pd.read_excel(file_path)
                    if 'username' in df.columns:
                        active_usernames.update(df['username'].dropna().unique())

            authors_count = len(active_usernames)

        max_rows = 4
        rows = []
        for i in range(max_rows):
            rows.append({
                'poem': poems[i] if i < len(poems) else None,
                'story': stories[i] if i < len(stories) else None,
                'literature': literature[i] if i < len(literature) else None
            })

        return render_template(
            "wellcom.html",
            rows=rows,
            username=username,
            poems_count=poems_count,
            stories_count=stories_count,
            literature_count=literature_count,
            authors_count=authors_count,
            total_count=poems_count + stories_count + literature_count
        )

    else:
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            category = request.form.get("category", "").strip()

            publish_status = request.form.get("publish_status", "on")
            tags = request.form.get("tags", "").strip()
            readability = request.form.get("readability", "easy")
            publish_date_str = request.form.get("publish_date", "").strip()

            if not title or not content or not category:
                flash("عنوان، محتوا و دسته‌بندی الزامی هستند.", "error")
                return redirect(url_for('index'))

            if category not in file_map_for_post:
                flash("دسته‌بندی نامعتبر", "error")
                return redirect(url_for('index'))

            is_public = True if publish_status == "on" else False
            status = "public" if is_public else "private"

            tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
            tags_str = ",".join(tags_list[:5])

            publish_date = None
            if publish_date_str:
                try:
                    publish_date = datetime.strptime(publish_date_str, "%Y-%m-%d").date()
                except ValueError:
                    publish_date = None

            file_path = os.path.join(SAVE_DIR, file_map_for_post[category])

            if os.path.exists(file_path):
                df = pd.read_excel(file_path)
            else:
                df = pd.DataFrame(columns=[
                    "شماره", "دسته‌بندی", "عنوان", "محتوا", "username",
                    "status", "tags", "readability", "publish_date", "created_at"
                ])

            new_id = df["شماره"].max() + 1 if not df.empty else 1

            new_row = {
                "شماره": new_id,
                "دسته‌بندی": category,
                "عنوان": title,
                "محتوا": content,
                "username": username,
                "status": status,
                "tags": tags_str,
                "readability": readability,
                "publish_date": publish_date.strftime("%Y-%m-%d") if publish_date else "",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_excel(file_path, index=False)

            flash("محتوا با موفقیت ذخیره شد!", "success")
            return redirect(url_for('index'))

        profiles = {}
        if os.path.exists(PROFILE_FILE):
            df_profiles = pd.read_excel(PROFILE_FILE)
            for _, row in df_profiles.iterrows():
                profiles[row['username']] = {
                    "first_name": row['first_name'],
                    "last_name": row['last_name'],
                    "phone": row['phone'],
                    "email": row['email'],
                    "photo": row['photo'],
                    "bio": row['bio'] if 'bio' in row else ""
                }

        def attach_author(records):
            for rec in records:
                user = rec.get("username")
                if user in profiles:
                    rec['first_name'] = profiles[user]['first_name']
                    rec['last_name'] = profiles[user]['last_name']
                else:
                    rec['first_name'] = ""
                    rec['last_name'] = ""
                rec['status'] = rec.get('status', 'public')
                rec['tags'] = rec.get('tags', '')
                rec['readability'] = rec.get('readability', 'easy')
                rec['publish_date'] = rec.get('publish_date', '')
                rec['created_at'] = rec.get('created_at', '')
            return records

        poems = attach_author(get_latest_records(route_map['poems']['file'], n=4))
        stories = attach_author(get_latest_records(route_map['stories']['file'], n=4))
        literature = attach_author(get_latest_records(route_map['literature']['file'], n=4))

        def get_total_count(file_name):
            file_path = os.path.join(SAVE_DIR, file_name)
            if os.path.exists(file_path):
                df = pd.read_excel(file_path)
                return len(df)
            return 0

        poems_count = get_total_count(route_map['poems']['file'])
        stories_count = get_total_count(route_map['stories']['file'])
        literature_count = get_total_count(route_map['literature']['file'])

        authors_count = 0
        if os.path.exists(PROFILE_FILE):
            df_profiles = pd.read_excel(PROFILE_FILE)
            active_usernames = set()
            for cat in ['poems', 'stories', 'literature']:
                file_path = os.path.join(SAVE_DIR, route_map[cat]['file'])
                if os.path.exists(file_path):
                    df = pd.read_excel(file_path)
                    if 'username' in df.columns:
                        active_usernames.update(df['username'].dropna().unique())

            authors_count = len(active_usernames)

        max_rows = 4
        rows = []
        for i in range(max_rows):
            rows.append({
                'poem': poems[i] if i < len(poems) else None,
                'story': stories[i] if i < len(stories) else None,
                'literature': literature[i] if i < len(literature) else None
            })

        user_profile = None
        if username in profiles:
            photo_file = profiles[username]['photo'] if profiles[username]['photo'] else "default-avatar.png"
            user_profile = {
                "username": username,
                "first_name": profiles[username]['first_name'],
                "last_name": profiles[username]['last_name'],
                "phone": profiles[username]['phone'],
                "email": profiles[username]['email'],
                "photo": photo_file,
                "bio": profiles[username]['bio']
            }

        return render_template(
            "index.html",
            rows=rows,
            user_profile=user_profile,
            username=username,
            poems_count=poems_count,
            stories_count=stories_count,
            literature_count=literature_count,
            authors_count=authors_count,
            total_count=poems_count + stories_count + literature_count
        )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()

        if os.path.exists(USERS_FILE):
            df = pd.read_excel(USERS_FILE)
        else:
            df = pd.DataFrame(columns=["username", "email", "password"])

        user_row = df[(df["username"] == username) & (df["password"] == password)]
        if not user_row.empty:
            session['username'] = username
            return redirect(url_for("index"))
        else:
            return render_template("login_form.html", error="نام کاربری یا رمز عبور اشتباه است.")
    return render_template("login_form.html")



def load_interactions():
    if os.path.exists(INTERACT_FILE):
        df = pd.read_excel(INTERACT_FILE)
        if "comments" not in df.columns:
            df["comments"] = "[]"
        else:
            df["comments"] = df["comments"].fillna("[]")
        if "user_likes" not in df.columns:
            df["user_likes"] = "[]"
        else:
            df["user_likes"] = df["user_likes"].fillna("[]")
        return df
    else:
        return pd.DataFrame(columns=["cat", "item_id", "likes", "comments", "user_likes"])

def save_interactions(df):
    df.to_excel(INTERACT_FILE, index=False)


@app.route("/like/<cat>/<int:item_id>", methods=["POST"])
def like_item(cat, item_id):
    if "username" not in session:
        return jsonify({"error": "ابتدا وارد شوید"}), 401

    username = session["username"]
    df = load_interactions()
    df["item_id"] = df["item_id"].astype(int)
    df["user_likes"] = df.get("user_likes", pd.Series(["[]"]*len(df)))
    df["user_likes"] = df["user_likes"].fillna("[]")

    mask = (df["cat"] == cat) & (df["item_id"] == item_id)

    if mask.any():
        user_likes = json.loads(df.loc[mask, "user_likes"].values[0])
        if username in user_likes:
            user_likes.remove(username)
        else:
            user_likes.append(username)
        df.loc[mask, "user_likes"] = json.dumps(user_likes, ensure_ascii=False)
        df.loc[mask, "likes"] = len(user_likes)
    else:
        df = pd.concat([df, pd.DataFrame([{
            "cat": cat,
            "item_id": item_id,
            "likes": 1,
            "comments": "[]",
            "user_likes": json.dumps([username], ensure_ascii=False)
        }])], ignore_index=True)

    save_interactions(df)

    likes = int(df.loc[(df["cat"] == cat) & (df["item_id"] == item_id), "likes"].values[0])
    user_likes = json.loads(df.loc[(df["cat"] == cat) & (df["item_id"] == item_id), "user_likes"].values[0])
    has_liked = username in user_likes

    return jsonify({"likes": likes, "has_liked": has_liked})


@app.route("/comment/<cat>/<int:item_id>", methods=["POST"])
def comment_item(cat, item_id):
    if "username" not in session:
        return jsonify({"error": "ابتدا وارد شوید"}), 401

    data = request.json
    text = data.get("comment", "").strip()
    if not text:
        return jsonify({"error": "کامنت خالی است"}), 400

    username = session["username"]
    first_name = last_name = ""

    if os.path.exists(PROFILE_FILE):
        df_profiles = pd.read_excel(PROFILE_FILE)
        user_data = df_profiles[df_profiles['username'] == username]
        if not user_data.empty:
            first_name = str(user_data.iloc[0]['first_name']).strip()
            last_name = str(user_data.iloc[0]['last_name']).strip()

    new_comment = {
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "text": text
    }

    df = load_interactions()
    df["item_id"] = df["item_id"].astype(int)
    df["comments"] = df["comments"].fillna("[]")
    mask = (df["cat"] == cat) & (df["item_id"] == item_id)

    if mask.any():
        comments = json.loads(df.loc[mask, "comments"].values[0])
        comments.append(new_comment)
        df.loc[mask, "comments"] = json.dumps(comments, ensure_ascii=False)
    else:
        df = pd.concat([df, pd.DataFrame([{
            "cat": cat,
            "item_id": item_id,
            "likes": 0,
            "comments": json.dumps([new_comment], ensure_ascii=False),
            "user_likes": "[]"
        }])], ignore_index=True)

    save_interactions(df)

    comments = json.loads(df.loc[(df["cat"] == cat) & (df["item_id"] == item_id), "comments"].values[0])
    for c in comments:
        if c.get("first_name") and c.get("last_name"):
            c["name"] = f"{c['first_name']} {c['last_name']}"
        else:
            c["name"] = "کاربر ناشناس"

    return jsonify({"comments": comments, "comment_count": len(comments)})


@app.route("/interactions/<cat>/<int:item_id>")
def get_interactions(cat, item_id):
    df = load_interactions()
    mask = (df["cat"] == cat) & (df["item_id"] == item_id)
    if mask.any():
        likes = int(df.loc[mask, "likes"].values[0])
        comments = json.loads(df.loc[mask, "comments"].values[0])
        user_likes = json.loads(df.loc[mask, "user_likes"].values[0])
        has_liked = session.get("username") in user_likes
    else:
        likes, comments, has_liked = 0, [], False

    for c in comments:
        if c.get("first_name") and c.get("last_name"):
            c["name"] = f"{c['first_name']} {c['last_name']}"
        else:
            c["name"] = "کاربر ناشناس"

    return jsonify({
        "likes": likes,
        "comments": comments,
        "comment_count": len(comments),
        "has_liked": has_liked
    })

@app.route("/likes/<cat>/<int:item_id>")
def get_likes(cat, item_id):
    if not os.path.exists(PROFILE_FILE):
        return jsonify([])

    df = load_interactions()
    mask = (df["cat"] == cat) & (df["item_id"] == item_id)

    if not mask.any():
        return jsonify([])

    user_likes = json.loads(df.loc[mask, "user_likes"].values[0])

    df_profiles = pd.read_excel(PROFILE_FILE)

    result = []
    for uname in user_likes:
        user_data = df_profiles[df_profiles['username'] == uname]
        if not user_data.empty:
            first_name = str(user_data.iloc[0]['first_name']).strip()
            last_name = str(user_data.iloc[0]['last_name']).strip()
        else:
            first_name, last_name = "کاربر", "ناشناس"

        result.append({
            "username": uname,
            "first_name": first_name,
            "last_name": last_name
        })

    return jsonify(result)



@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        if password != confirm_password:
            return render_template("signup.html", error="رمز عبور و تکرار آن یکسان نیست.")
        if os.path.exists(USERS_FILE):
            df_users = pd.read_excel(USERS_FILE)
        else:
            df_users = pd.DataFrame(columns=["username", "email", "password"])
        if username in df_users["username"].values:
            return render_template("signup.html", error="این نام کاربری قبلا ثبت شده است.")
        new_user = {"username": username, "email": email, "password": password}
        df_users = pd.concat([df_users, pd.DataFrame([new_user])], ignore_index=True)
        df_users.to_excel(USERS_FILE, index=False)

        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        phone = request.form.get("phone", "").strip()
        file = request.files.get("photo")

        if not first_name or not last_name or not phone:
            return render_template("signup.html", error="تمام فیلدهای پروفایل الزامی هستند.")

        DEFAULT_PHOTO = "https://i.pinimg.com/1200x/97/21/05/972105c5a775f38cf33d3924aea053f1.jpg"
        photo_filename = DEFAULT_PHOTO
        if file and file.filename != "":
            filename = secure_filename(file.filename)
            photo_filename = f"{username}_{filename}"
            file.save(os.path.join(PROFILE_DIR, photo_filename))

        if os.path.exists(PROFILE_FILE):
            df_profile = pd.read_excel(PROFILE_FILE)
        else:
            df_profile = pd.DataFrame(columns=["username", "first_name", "last_name", "phone", "photo", "email"])

        df_profile = df_profile[df_profile["username"] != username]
        new_profile = {
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "photo": photo_filename,
            "email": email
        }
        df_profile = pd.concat([df_profile, pd.DataFrame([new_profile])], ignore_index=True)
        df_profile.to_excel(PROFILE_FILE, index=False)

        return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.pop('username', None)
    return redirect(url_for("login"))


file_map_for_post = {
    "poems": "poems.xlsx",
    "stories": "stories.xlsx",
    "literature": "literature.xlsx"
}

route_map = {
    "poems": {"file": "poems.xlsx", "name": "شعر"},
    "stories": {"file": "stories.xlsx", "name": "داستان کوتاه"},
    "literature": {"file": "literature.xlsx", "name": "متن ادبی"}
}

client = OpenAI(
    api_key="api_key",
    base_url='https://api.gapgpt.app/v1'
)
def get_latest_records(filename, n=4):
    file_path = os.path.join(SAVE_DIR, filename)
    if os.path.exists(file_path):
        df = pd.read_excel(file_path)
        if not df.empty:
            last = df.tail(n).copy()
            last = last.iloc[::-1]
            return last.to_dict('records')
    return []


@app.route("/update_bio", methods=["POST"])
def update_bio():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})

    data = request.get_json()
    new_bio = data.get('bio', '').strip()
    username = session['username']

    if os.path.exists(PROFILE_FILE):
        df_profiles = pd.read_excel(PROFILE_FILE)
    else:
        df_profiles = pd.DataFrame(columns=['username','first_name','last_name','phone','email','photo','bio'])

    if 'bio' not in df_profiles.columns:
        df_profiles['bio'] = ""

    if username in df_profiles['username'].values:
        df_profiles.loc[df_profiles['username'] == username, 'bio'] = new_bio
    else:
        df_profiles = pd.concat([df_profiles, pd.DataFrame([{
            'username': username,
            'first_name': '',
            'last_name': '',
            'phone': '',
            'email': '',
            'photo': '',
            'bio': new_bio
        }])], ignore_index=True)

    try:
        df_profiles.to_excel(PROFILE_FILE, index=False)
    except PermissionError:
        return jsonify({'success': False, 'error': 'Permission denied to write file'})

    return jsonify({'success': True, 'bio': new_bio})


@app.route("/view/<cat>/<int:item_id>")
def view_item(cat, item_id):
    if cat not in route_map:
        return "مسیر نامعتبر", 404

    file_name = route_map[cat]['file']
    cat_name = route_map[cat]['name']
    file_path = os.path.join(SAVE_DIR, file_name)

    if not os.path.exists(file_path):
        return render_template("content.html", item=None, category_name=cat_name, message="فایل مورد نظر یافت نشد"), 404

    df = pd.read_excel(file_path)

    username = session.get('username', 'guest')

    if username == 'guest':
        rec = df[(df['شماره'] == item_id) & (df['status'] == 'public')]
    else:
        rec = df[((df['شماره'] == item_id) & (df['status'] == 'public')) |
                 ((df['شماره'] == item_id) & (df['status'] == 'private') & (df['username'] == username))]

    if rec.empty:
        rec_check = df[df['شماره'] == item_id]
        if rec_check.empty:
            message = "محتوا یافت نشد"
        else:
            item_status = rec_check.iloc[0].get('status', 'public')
            if item_status == 'private' and username == 'guest':
                message = "این محتوا خصوصی است و برای مشاهده نیاز به ورود دارید"
            elif item_status == 'private' and rec_check.iloc[0]['username'] != username:
                message = "شما اجازه مشاهده این محتوا را ندارید"
            else:
                message = "دسترسی به این محتوا امکان‌پذیر نیست"

        return render_template("content.html",
                             item=None,
                             category_name=cat_name,
                             message=message), 404

    item = rec.iloc[0].to_dict()

    item.setdefault('status', 'public')
    item.setdefault('tags', '')
    item.setdefault('readability', 'easy')
    item.setdefault('publish_date', '')
    item.setdefault('created_at', '')

    if os.path.exists(PROFILE_FILE):
        df_profiles = pd.read_excel(PROFILE_FILE)
        user_data = df_profiles[df_profiles['username'] == item['username']]
        if not user_data.empty:
            row = user_data.iloc[0]
            item['first_name'] = row['first_name']
            item['last_name'] = row['last_name']
            item['author_bio'] = row.get('bio', '')
            item['author_photo'] = row.get('photo', 'default-avatar.png')
        else:
            item['first_name'] = ""
            item['last_name'] = ""
            item['author_bio'] = ""
            item['author_photo'] = "default-avatar.png"
    else:
        item['first_name'] = ""
        item['last_name'] = ""
        item['author_bio'] = ""
        item['author_photo'] = "default-avatar.png"

    item['is_public'] = item['status'] == 'public'
    item['is_private'] = item['status'] == 'private'

    item['is_owner'] = username != 'guest' and item['username'] == username

    return render_template("content.html",
                         item=item,
                         category_name=cat_name,
                         username=username)

@app.route("/my_artworks")
def my_artworks():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    all_artworks = []
    for key, info in route_map.items():
        file_path = os.path.join(SAVE_DIR, info['file'])
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            df = df[df['username'] == username]

            for _, row in df.iterrows():
                artwork = {
                    "id": row['شماره'],
                    "category": key,
                    "دسته‌بندی": row.get('دسته‌بندی', ''),
                    "title": row['عنوان'],
                    "content": row['محتوا']
                }

                if 'created_at' in row:
                    created_at = row['created_at']
                    if isinstance(created_at, pd.Timestamp):
                        artwork['created_at'] = created_at.strftime('%Y-%m-%d')
                    elif isinstance(created_at, (int, float)):
                        try:
                            dt = datetime.fromtimestamp(created_at)
                            artwork['created_at'] = dt.strftime('%Y-%m-%d')
                        except:
                            artwork['created_at'] = str(created_at)
                    else:
                        artwork['created_at'] = str(created_at)
                else:
                    artwork['created_at'] = 'تاریخ نامشخص'

                all_artworks.append(artwork)

    all_artworks.sort(key=lambda x: x["id"], reverse=True)

    return render_template("my_artworks.html", artworks=all_artworks)


@app.route("/delete_artwork/<cat>/<int:item_id>", methods=["POST"])
def delete_artwork(cat, item_id):
    if 'username' not in session:
        return redirect(url_for("login"))

    username = session['username']

    if cat not in file_map_for_post:
        return "دسته‌بندی نامعتبر", 400

    file_path = os.path.join(SAVE_DIR, file_map_for_post[cat])

    if not os.path.exists(file_path):
        return redirect(url_for("my_artworks"))

    df = pd.read_excel(file_path)

    if 'username' not in df.columns:
        df['username'] = ""

    mask = (df['شماره'] == item_id) & (df['username'] == username)
    if mask.any():
        df = df[~mask]
        df.to_excel(file_path, index=False)

    return redirect(url_for("my_artworks"))


@app.route("/edit/<cat>/<int:item_id>", methods=["GET", "POST"])
def edit_artwork(cat, item_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    if cat not in route_map:
        return "مسیر نامعتبر", 404

    file_path = os.path.join(SAVE_DIR, route_map[cat]['file'])
    if not os.path.exists(file_path):
        return "فایل پیدا نشد", 404

    df = pd.read_excel(file_path)
    rec = df[df['شماره'] == item_id]
    if rec.empty:
        return "رکورد پیدا نشد", 404

    artwork = rec.iloc[0].to_dict()

    if artwork.get("username") != username:
        return "شما اجازه ویرایش این اثر را ندارید", 403

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        df.loc[df['شماره'] == item_id, 'عنوان'] = title
        df.loc[df['شماره'] == item_id, 'محتوا'] = content
        df.to_excel(file_path, index=False)

        return redirect(url_for("my_artworks"))
    return render_template("edit_artwork.html", artwork=artwork)


@app.route("/categories")
def categories():
    def get_all_records_with_name(filename):
        file_path = os.path.join(SAVE_DIR, filename)
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            if not df.empty:
                df = df.iloc[::-1]
                records = df.to_dict('records')

                if os.path.exists(PROFILE_FILE):
                    df_profiles = pd.read_excel(PROFILE_FILE)
                    for rec in records:
                        username = rec.get('username', '')
                        user_data = df_profiles[df_profiles['username'] == username]
                        if not user_data.empty:
                            rec['first_name'] = user_data.iloc[0]['first_name']
                            rec['last_name'] = user_data.iloc[0]['last_name']
                        else:
                            rec['first_name'] = ''
                            rec['last_name'] = ''

                        if 'created_at' in rec:
                            rec['created_at'] = str(rec['created_at'])
                        else:
                            rec['created_at'] = 'تاریخ نامشخص'

                return records
        return []

    poems = get_all_records_with_name(route_map['poems']['file'])
    stories = get_all_records_with_name(route_map['stories']['file'])
    literature = get_all_records_with_name(route_map['literature']['file'])

    return render_template("categories.html",
                           poems=poems,
                           stories=stories,
                           literature=literature)

@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()

    if not query:
        return render_template(
            "search.html",
            query=query,
            poems=[],
            stories=[],
            literature=[]
        )

    def search_in_file(filename):
        file_path = os.path.join(SAVE_DIR, filename)
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)

            result = df[
                df['عنوان'].str.contains(query, case=False, na=False) |
                df['محتوا'].str.contains(query, case=False, na=False)
            ]

            records = result.to_dict('records')

            if os.path.exists(PROFILE_FILE):
                df_profiles = pd.read_excel(PROFILE_FILE)
                for rec in records:
                    username = rec.get('username', '')
                    user_data = df_profiles[df_profiles['username'] == username]
                    if not user_data.empty:
                        rec['first_name'] = user_data.iloc[0]['first_name']
                        rec['last_name'] = user_data.iloc[0]['last_name']
                    else:
                        rec['first_name'] = ''
                        rec['last_name'] = ''
            return records
        return []

    poems_results = search_in_file(route_map['poems']['file'])
    stories_results = search_in_file(route_map['stories']['file'])
    literature_results = search_in_file(route_map['literature']['file'])

    return render_template(
        "search.html",
        query=query,
        poems=poems_results,
        stories=stories_results,
        literature=literature_results
    )




@app.route("/search_my_artworks")
def search_my_artworks():
    if 'username' not in session:
        return redirect(url_for('login'))

    query = request.args.get("q", "").strip()
    username = session['username']

    results = []
    for key, info in route_map.items():
        file_path = os.path.join(SAVE_DIR, info['file'])
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)

            df = df[df['username'] == username]

            df = df[df['عنوان'].str.contains(query, case=False, na=False) |
                    df['محتوا'].str.contains(query, case=False, na=False)]

            for _, row in df.iterrows():
                results.append({
                    "id": row['شماره'],
                    "category": key,
                    "title": row['عنوان'],
                    "content": row['محتوا']
                })
    return render_template("search_my_artworks.html", query=query, results=results)


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/human_admin")
def human_admin():
    return render_template("human_admin.html")


@app.route("/AI_admin")
def AI_admin():
    if 'username' not in session:
        return redirect(url_for("login"))

    username = session['username']
    user_profile = None

    if os.path.exists(PROFILE_FILE):
        df_profiles = pd.read_excel(PROFILE_FILE)
        user_row = df_profiles[df_profiles['username'] == username]
        if not user_row.empty:
            user_row = user_row.iloc[0]
            photo_file = user_row['photo'] if user_row['photo'] else "default-avatar.png"
            user_profile = {
                "username": username,
                "first_name": user_row.get('first_name',''),
                "last_name": user_row.get('last_name',''),
                "phone": user_row.get('phone',''),
                "email": user_row.get('email',''),
                "photo": photo_file,
                "bio": user_row.get('bio','')
            }

    return render_template("AI_admin.html", user_profile=user_profile)



@app.route("/Human_AI_admin")
def Human_AI_admin():
    return render_template("Human_AI_admin.html")


AI_GENERATIONS: Dict[str, Dict[str, Any]] = {}
def _cleanup_generations(ttl_seconds=1800):
    now = time.time()
    dead = [k for k,v in AI_GENERATIONS.items() if now - v.get("created_at", now) > ttl_seconds]
    for k in dead:
        AI_GENERATIONS.pop(k, None)

def _to_bool(v, default=False):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ["true","1","yes","on","checked"]
    return default

def _to_int(v, default, min_v=None, max_v=None):
    try:
        x = int(v)
    except:
        x = default
    if min_v is not None: x = max(min_v, x)
    if max_v is not None: x = min(max_v, x)
    return x

def resolve_eval_model(main_model: str, selected: str) -> str:

    MODEL_PRIORITY = [
        "gpt-4o",
        "gpt-4-turbo-preview",
        "gpt-4",
        "gpt-4o-mini",
    ]

    if selected and selected.startswith("gpt-"):
        if selected in MODEL_PRIORITY:
            return selected
        else:
            return "gpt-4o"

    elif selected == "auto":
        return "gpt-4o"

    elif selected in ["gpt-4", "gpt-4o", "gpt-4-turbo"]:
        mapping = {
            "gpt-4": "gpt-4",
            "gpt-4o": "gpt-4o",
            "gpt-4-turbo": "gpt-4-turbo-preview"
        }
        return mapping.get(selected, "gpt-4o")

    else:
        return "gpt-4o"

def parse_json_safely(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    patterns = [
        r'\{[\s\S]*\}',
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            json_str = match.group(1) if len(match.groups()) > 0 else match.group(0)
            try:
                return json.loads(json_str.strip())
            except:
                continue

    try:
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]
            return json.loads(json_str)
    except:
        pass

    return None
def evaluate_text(client, text: str, eval_model: str, prompt: str,
                  evaluation_criteria: Dict[str, bool] = None) -> Dict[str, Any]:

    if evaluation_criteria is None:
        evaluation_criteria = {
            "relevance": True,
            "coherence": True,
            "creativity": True,
            "grammar": True,
            "engagement": True,
            "completeness": True
        }

    active_criteria = {k: v for k, v in evaluation_criteria.items() if v}

    if not active_criteria:
        return {
            "score_overall": 0,
            "score_details": {},
            "issues": [],
            "suggestions": [],
            "rewrite_hint": "",
            "analysis_summary": "ارزیابی غیرفعال است",
            "parse_error": False,
            "evaluation_disabled": True
        }

    system_msg = """شما یک ارزیاب متون فارسی هستید. کیفیت متن را با دقت و تنوع ارزیابی کنید.
لطفاً خروجی را فقط به صورت JSON برگردانید، بدون هیچ متن اضافی.

**دستورالعمل‌های مهم:**
1. فقط برای معیارهای مشخص شده نمره بدهید
2. برای هر معیار نمره‌ای بین ۱ تا ۱۰ بدهید (ممکن است اعداد اعشاری هم باشد مثل ۷.۵)
3. نمره کلی به صورت خودکار از میانگین نمرات جزئی محاسبه خواهد شد
4. ایرادات و پیشنهادات باید متناسب با خود متن باشد، نه کلی
5. rewrite_hint باید کاملاً اختصاصی و کاربردی باشد"""

    criteria_labels = {
        "relevance": "انطباق با درخواست کاربر",
        "coherence": "انسجام و ساختار متن",
        "creativity": "خلاقیت و ابتکار",
        "grammar": "دستور زبان و نگارش",
        "engagement": "جذابیت و تاثیرگذاری",
        "completeness": "طول و جزئیات متن (کامل بودن)"
    }

    active_criteria_list = []
    for criterion, is_active in active_criteria.items():
        if is_active and criterion in criteria_labels:
            active_criteria_list.append(criteria_labels[criterion])

    criteria_text = "\n".join([f"{i+1}. {criterion}" for i, criterion in enumerate(active_criteria_list)])


    score_details_schema = {}
    for criterion in active_criteria.keys():
        if criterion in criteria_labels:
            score_details_schema[criterion] = f"عدد بین 1-10 ({criteria_labels[criterion]})"

    user_msg = f"""## درخواست اصلی کاربر:
{prompt}

## متن تولید شده:
{text}

## معیارهای ارزیابی (فقط برای موارد زیر نمره بدهید):
{criteria_text}

لطفاً با ساختار دقیق زیر پاسخ دهید (فقط JSON):
{{
  "score_details": {{
    {', '.join([f'"{k}": "{v}"' for k, v in score_details_schema.items()])}
  }},
  "issues": ["مشکلات اختصاصی این متن"],
  "suggestions": ["پیشنهادات عملی برای این متن"],
  "rewrite_hint": "راهنمایی دقیق برای بهبود این متن خاص",
  "analysis_summary": "تحلیل مختصر نقاط قوت و ضعف"
}}"""

    print(f" ارزیابی با مدل: {eval_model}")
    print(f" معیارهای فعال: {list(active_criteria.keys())}")
    print(f" درخواست: {prompt[:100]}...")

    try:
        response = client.chat.completions.create(
            model=eval_model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.5,
            max_tokens=300,
            response_format={"type": "json_object"}
        )

        result_text = response.choices[0].message.content
        print(f" پاسخ خام ارزیاب: {result_text[:300]}...")

        parsed = parse_json_safely(result_text)

        if not parsed:
            print(" خطا: JSON استخراج نشد")
            import random
            random_score = random.uniform(5.0, 9.0)
            return {
                "score_overall": round(random_score, 1),
                "score_details": {},
                "issues": ["خطا در پردازش پاسخ ارزیاب"],
                "suggestions": [],
                "rewrite_hint": "لطفاً دوباره ارزیابی کنید",
                "analysis_summary": "",
                "parse_error": True,
                "raw_response": result_text[:500]
            }

        print(f" JSON استخراج شد")

        score = 5.0

        if parsed.get("score_details"):
            details = parsed.get("score_details", {})
            if isinstance(details, dict):
                values = []
                for criterion in active_criteria.keys():
                    if criterion in details:
                        value = details[criterion]
                        num_value = None

                        if isinstance(value, (int, float)):
                            num_value = float(value)
                        elif isinstance(value, str):
                            try:
                            #    import re
                                match = re.search(r'(\d+(?:\.\d+)?)', str(value))
                                if match:
                                    num = float(match.group(1))
                                    if num > 10:
                                        num = num / 10.0
                                    num_value = num
                            except:
                                pass

                        if num_value is not None:
                            values.append(num_value)

                if values:
                    score = sum(values) / len(values)
                    print(f" نمرات جزئی (فعال): {values}")
                    print(f" میانگین محاسبه شده: {score}")

        score = max(1.0, min(float(score), 10.0))
        score = round(score, 1)
        print(f" نمره نهایی: {score}")

        issues = parsed.get("issues", [])
        if isinstance(issues, str):
            if "،" in issues:
                issues = [i.strip() for i in issues.split("،") if i.strip()]
            elif "," in issues:
                issues = [i.strip() for i in issues.split(",") if i.strip()]
            else:
                issues = [issues]
        elif not isinstance(issues, list):
            issues = []

        suggestions = parsed.get("suggestions", [])
        if isinstance(suggestions, str):
            if "،" in suggestions:
                suggestions = [s.strip() for s in suggestions.split("،") if s.strip()]
            elif "," in suggestions:
                suggestions = [s.strip() for s in suggestions.split(",") if s.strip()]
            else:
                suggestions = [suggestions]
        elif not isinstance(suggestions, list):
            suggestions = []

        rewrite_hint = parsed.get("rewrite_hint", "")
        if not isinstance(rewrite_hint, str):
            rewrite_hint = str(rewrite_hint)

        analysis_summary = parsed.get("analysis_summary", "")
        if not isinstance(analysis_summary, str):
            analysis_summary = str(analysis_summary)

        score_details = {}
        for criterion in active_criteria.keys():
            if criterion in parsed.get("score_details", {}):
                value = parsed["score_details"][criterion]
                if isinstance(value, (int, float)):
                    score_details[criterion] = round(float(value), 1)
                elif isinstance(value, str):
                    try:
                    #    import re
                        match = re.search(r'(\d+(?:\.\d+)?)', str(value))
                        if match:
                            num = float(match.group(1))
                            if num > 10:
                                num = num / 10.0
                            score_details[criterion] = round(num, 1)
                        else:
                            score_details[criterion] = value
                    except:
                        score_details[criterion] = value
                else:
                    score_details[criterion] = value

        return {
            "score_overall": score,
            "score_details": score_details,
            "issues": issues[:3],
            "suggestions": suggestions[:3],
            "rewrite_hint": rewrite_hint[:250],
            "analysis_summary": analysis_summary[:200],
            "parse_error": False,
            "evaluation_criteria": active_criteria,
            "raw_response": result_text[:500]
        }

    except Exception as e:
        print(f" خطا در ارزیابی: {str(e)}")
        print(traceback.format_exc())
        import random
        random_score = random.uniform(4.0, 8.0)
        return {
            "score_overall": round(random_score, 1),
            "score_details": {},
            "issues": [f"خطا در ارزیابی: {str(e)[:100]}"],
            "suggestions": [],
            "rewrite_hint": "",
            "analysis_summary": "",
            "parse_error": True,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.route("/generate_simple", methods=["POST"])
def generate_simple():
    data = request.get_json() or {}
    prompt = data.get("prompt", "")

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )

    return jsonify({
        "response": completion.choices[0].message.content
    })

@app.route("/generate_ai", methods=["POST"])
def generate_ai():
    _cleanup_generations()
    data = request.get_json() or {}

    print(f"دریافت درخواست generate_ai: {json.dumps(data, ensure_ascii=False)[:500]}...")

    prompt = (data.get("prompt") or "").strip()
    use_bio = _to_bool(data.get("use_bio", False), False)
    bio_text = data.get("bio_text")
    print(f"BIO BARAN BAHAR: {bio_text}")
    mode = data.get("mode", "write")

    creativity = _to_int(data.get("creativity", 50), 50, 0, 100)
    print(f"CREATIVITY: {creativity}")
    max_tokens = _to_int(data.get("max_tokens", 200), 200, 50, 4000)
    generate_image = _to_bool(data.get("generate_image", False), False)
    size = data.get("img_size", "1024x1024")
    if size not in ["1024x1024", "1024x1536", "1536x1024", "auto"]:
        size = "1024x1024"

    enable_evaluation = _to_bool(data.get("enable_evaluation", False), False)
    evaluation_model_selected = (data.get("evaluation_model") or "auto").strip()
    quality_threshold = _to_int(data.get("quality_threshold", 7), 7, 1, 10)
    max_retry_attempts = _to_int(data.get("max_retry_attempts", 3), 3, 1, 10)

    evaluation_criteria = {
        "relevance": _to_bool(data.get("eval_relevance", True), True),
        "coherence": _to_bool(data.get("eval_coherence", True), True),
        "creativity": _to_bool(data.get("eval_creativity", False), False),
        "grammar": _to_bool(data.get("eval_grammar", True), True),
        "engagement": _to_bool(data.get("eval_engagement", False), False),
        "completeness": _to_bool(data.get("eval_completeness", True), True),
    }

    print(f"تنظیمات ارزیابی: enable={enable_evaluation}, model={evaluation_model_selected}, threshold={quality_threshold}")
    print(f"معیارهای انتخاب شده: {[k for k, v in evaluation_criteria.items() if v]}")
    print(f"BIO واقعی از کاربر: {bio_text}")
    messages = []

    if use_bio and bio_text:
        messages.append({
            "role": "system",
            "content": f"""هویت من '{bio_text}' است و باید حداقل یک بار در پاسخ نام برده شود.
همچنین مطمئن شو که تمام جملات در پاسخ کامل هستند و هیچ جمله نیمه‌کاری وجود ندارد. هر پاراگراف باید با نقطه پایان یابد."""
        })
    else:
        messages.append({
            "role": "system",
            "content": "مطمئن شو که تمام جملات در پاسخ کامل هستند و هیچ جمله نیمه‌کاری وجود ندارد. هر پاراگراف باید با نقطه پایان یابد."
        })

    creativity_style = ""
    if creativity <= 25:
        creativity_style = "از جملات ساده و روان استفاده کن."
    elif creativity <= 50:
        creativity_style = "متن کمی ادبی و لطیف باشد، اما قابل فهم."
    elif creativity <= 75:
        creativity_style = "متن ادبی و خیال‌انگیز باشد."
    else:
        creativity_style = "متن بسیار ادبی و شاعرانه باشد."

    user_prompt = ""

    user_prompt += f"متن تولید شده باید کامل باشد و حدود {max_tokens} کلمه باشد. "
    user_prompt += "هر جمله باید مفهوم کامل داشته باشد و در حالت نیمه‌تمام نباشد. "

    if "شعر" in prompt:
        user_prompt += "تعداد ابیات باید کامل باشد. "

    user_prompt += f"{creativity_style}\n\n"

    if use_bio and bio_text:
        user_prompt += f"با هویت '{bio_text}'، {prompt}"
    else:
        user_prompt += f"{prompt}"

    messages.append({"role": "user", "content": user_prompt})

    generator_model = "gpt-4o"
    print(f"تولید با مدل: {generator_model}")
    print(f"messages: {messages}")

    completion = client.chat.completions.create(
        model=generator_model,
        messages=messages,
        temperature=max(0.1, creativity / 100),
        max_tokens=max_tokens if mode == "write" else 150,
    )
    response_text = completion.choices[0].message.content or ""
    print(f"متن تولید شده ({len(response_text)} کاراکتر): {response_text[:200]}...")

    response_text = response_text.strip()
    if response_text and not response_text.endswith(('.', '!', '؟', '?')):
        response_text += '.'

    if use_bio and bio_text:
        if bio_text not in response_text:
            print(f" هویت '{bio_text}' در پاسخ ذکر نشده. اضافه کردن...")
            response_text = f"به عنوان {bio_text}، {response_text}"
        else:
            print(f" هویت '{bio_text}' در پاسخ ذکر شده است.")

    evaluation = None
    final_score = None
    evaluator_model = None
    parse_error = False

    if enable_evaluation:
        evaluator_model = resolve_eval_model(generator_model, evaluation_model_selected)
        print(f"ارزیابی با مدل: {evaluator_model}")
        evaluation = evaluate_text(client, response_text, evaluator_model, prompt, evaluation_criteria)

        final_score = evaluation.get("score_overall", 1)
        try:
            final_score = float(final_score)
        except:
            final_score = 1.0
        parse_error = bool(evaluation.get("parse_error", False))
        print(f"نمره ارزیابی: {final_score}, parse_error: {parse_error}")

    image_url = ""
    if generate_image:
        try:
            image_resp = client.images.generate(model="dall-e-3", prompt=prompt, size=size)
            if hasattr(image_resp, "data") and len(image_resp.data) > 0:
                image_url = image_resp.data[0].url
        except Exception as e:
            print(f"خطا در تولید تصویر: {e}")

    generation_id = str(uuid.uuid4())
    AI_GENERATIONS[generation_id] = {
        "created_at": time.time(),
        "prompt": prompt,
        "messages": messages,
        "generator_model": generator_model,
        "temperature": creativity / 100,
        "max_tokens": max_tokens if mode == "write" else 150,
        "enable_evaluation": enable_evaluation,
        "evaluator_model": evaluator_model,
        "evaluation_criteria": evaluation_criteria,
        "quality_threshold": quality_threshold,
        "remaining": max_retry_attempts,
        "last_score": final_score,
        "last_evaluation": evaluation,
        "last_parse_error": parse_error,
        "original_response": response_text,
    }
    print(f"generation_id ایجاد شد: {generation_id}")

    response_data = {
        "response": response_text,
        "image_url": image_url,
        "generation_id": generation_id,
        "evaluation_enabled": enable_evaluation,
        "remaining": max_retry_attempts,
    }

    if enable_evaluation:
        response_data.update({
            "evaluation_model": evaluator_model,
            "quality_threshold": quality_threshold,
            "final_score": final_score,
            "parse_error": parse_error,
            "evaluation": evaluation,
            "evaluation_criteria": evaluation_criteria
        })

    print(f"ارسال پاسخ به فرانت")
    return jsonify(response_data)


@app.route("/regenerate_ai", methods=["POST"])
def regenerate_ai():
    _cleanup_generations()
    data = request.get_json() or {}
    generation_id = data.get("generation_id")

    print(f" درخواست regenerate_ai برای: {generation_id}")

    if not generation_id or generation_id not in AI_GENERATIONS:
        print(f" generation_id نامعتبر: {generation_id}")
        return jsonify({"ok": False, "message": "شناسه تولید معتبر نیست."})

    st = AI_GENERATIONS[generation_id]
    print(f" state بازیابی شد: remaining={st.get('remaining')}, last_score={st.get('last_score')}")

    if not st.get("enable_evaluation"):
        return jsonify({"ok": False, "message": "ارزیابی فعال نیست."})

    threshold = float(st.get("quality_threshold", 7))
    remaining = int(st.get("remaining", 0))
    last_score = float(st.get("last_score", 0))
    last_parse_error = bool(st.get("last_parse_error", False))

    evaluation_criteria = st.get("evaluation_criteria", {
        "relevance": True,
        "coherence": True,
        "creativity": False,
        "grammar": True,
        "engagement": False,
        "completeness": True,
    })

    print(f" وضعیت فعلی: threshold={threshold}, remaining={remaining}, last_score={last_score}, parse_error={last_parse_error}")
    print(f" معیارهای ارزیابی: {[k for k, v in evaluation_criteria.items() if v]}")

    if remaining <= 0:
        print(" تلاش‌ها تمام شده")
        return jsonify({"ok": False, "message": "تعداد تلاش برای تولید مجدد تمام شد."})

    if (not last_parse_error) and (last_score is not None) and (float(last_score) >= float(threshold)):
        print(f" نمره کافی است: {last_score} >= {threshold}")
        return jsonify({"ok": False, "message": "به حد کافی خوب است."})

    print(" شروع تولید مجدد...")
    try:
        original_temperature = st["temperature"]
        regeneration_count = st.get("regeneration_count", 0)

        if regeneration_count == 0:
            temperature = original_temperature
        elif regeneration_count == 1:
            temperature = min(original_temperature + 0.1, 0.8)
        elif regeneration_count == 2:
            temperature = max(original_temperature - 0.1, 0.2)
        else:
            import random
            temperature = random.uniform(0.3, 0.7)

        messages = st["messages"].copy()
        prompt_text = st.get("prompt", "")

        last_eval = st.get("last_evaluation")
        if last_eval and last_eval.get("rewrite_hint"):
            rewrite_hint = last_eval["rewrite_hint"]
            if rewrite_hint and len(rewrite_hint) > 10:
                hint_message = f"\n\nنکته برای بهبود: {rewrite_hint}"

                for i, msg in enumerate(messages):
                    if msg["role"] == "user":
                        messages[i] = {
                            "role": "user",
                            "content": msg["content"] + hint_message
                        }
                        break

        elif last_eval and last_eval.get("issues"):
            issues = last_eval["issues"][:2]
            if issues:
                improvement_note = f"\n\nلطفاً این موارد را بهبود بده: {', '.join(issues)}"

                for i, msg in enumerate(messages):
                    if msg["role"] == "user":
                        messages[i] = {
                            "role": "user",
                            "content": msg["content"] + improvement_note
                        }
                        break

        print(f" دمای جدید: {temperature} (اصلی: {original_temperature})")
        print(f" تعداد تولید مجدد: {regeneration_count + 1}")

        completion = client.chat.completions.create(
            model=st["generator_model"],
            messages=messages,
            temperature=temperature,
            max_tokens=st["max_tokens"],
        )
        new_text = completion.choices[0].message.content or ""
        print(f" متن جدید تولید شد ({len(new_text)} کاراکتر): {new_text[:200]}...")

        evaluator_model = st.get("evaluator_model") or st["generator_model"]
        print(f" ارزیابی مجدد با مدل: {evaluator_model}")

        evaluation = evaluate_text(client, new_text, evaluator_model, st.get("prompt", ""), evaluation_criteria)

        score = evaluation.get("score_overall", 0)
        if isinstance(score, (int, float)):
            score = float(score)
        else:
            try:
                score = float(score)
            except:
                score = 0.0
        parse_error = bool(evaluation.get("parse_error", False))
        print(f" نمره جدید: {score}, parse_error: {parse_error}")

        remaining -= 1
        st["remaining"] = remaining
        st["last_score"] = score
        st["last_evaluation"] = evaluation
        st["last_parse_error"] = parse_error
        st["regeneration_count"] = regeneration_count + 1
        st["last_temperature"] = temperature

        response_data = {
            "ok": True,
            "response": new_text,
            "evaluation_enabled": True,
            "evaluation_model": evaluator_model,
            "quality_threshold": threshold,
            "remaining": remaining,
            "final_score": score,
            "parse_error": parse_error,
            "evaluation": evaluation,
            "evaluation_criteria": evaluation_criteria,
            "temperature_used": temperature,  # for debug
            "regeneration_count": regeneration_count + 1
        }

        print(f" ارسال پاسخ regenerate")
        return jsonify(response_data)

    except Exception as e:
        print(f" خطا در تولید مجدد: {e}")
        print(traceback.format_exc())
        return jsonify({
            "ok": False,
            "message": f"خطا در تولید مجدد: {str(e)}"
        })
@app.route("/save_ai", methods=["POST"])
def save_ai():
    try:
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        content = request.form.get("content", "").strip()
        username = session.get("username", "guest")

        publish_status = request.form.get("publish_status", "public").strip().lower()
        tags = request.form.get("tags", "").strip()
        readability = request.form.get("readability", "easy")
        publish_date_str = request.form.get("publish_date", "").strip()
        max_tokens = request.form.get("max_tokens", "300")

        if not title or not content or not category:
            flash("عنوان، محتوا و دسته‌بندی الزامی هستند.", "error")
            return redirect(url_for('ai_panel'))

        if category not in file_map_for_post:
            flash("دسته‌بندی نامعتبر", "error")
            return redirect(url_for('ai_panel'))

        status = "public"
        if publish_status == 'private':
            status = "private"

        tags_list = []
        if tags:
            tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        tags_str = ",".join(tags_list[:5])


        publish_date = None
        if publish_date_str:
            try:
                publish_date = datetime.strptime(publish_date_str, "%Y-%m-%d")
            except ValueError:
                publish_date = None
        file_path = os.path.join(SAVE_DIR, file_map_for_post[category])
        os.makedirs(SAVE_DIR, exist_ok=True)

        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            for col in ["status", "tags", "readability", "publish_date", "created_at", "max_tokens", "image_url"]:
                if col not in df.columns:
                    df[col] = ""
        else:
            df = pd.DataFrame(columns=[
                "شماره", "دسته‌بندی", "عنوان", "محتوا", "username",
                "status", "tags", "readability", "publish_date", "created_at",
                "max_tokens", "image_url"
            ])

        new_id = 1
        if not df.empty and "شماره" in df.columns:
            max_id = df["شماره"].max()
            if pd.notna(max_id):
                new_id = int(max_id) + 1
        image_url = session.pop('ai_generated_image', None) if session.get('ai_generated_image') else ""
        new_row = {
            "شماره": new_id,
            "دسته‌بندی": category,
            "عنوان": title,
            "محتوا": content,
            "username": username,
            "status": status,
            "tags": tags_str,
            "readability": readability,
            "publish_date": publish_date.strftime("%Y-%m-%d") if publish_date else "",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "max_tokens": max_tokens,
            "image_url": image_url if image_url else ""
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_excel(file_path, index=False)

        flash(f"محتوای AI با موفقیت ذخیره شد! (وضعیت: {'عمومی' if status == 'public' else 'خصوصی'})", "success")
        return redirect(url_for('index'))

    except Exception as e:
        flash(f"خطا در ذخیره محتوا: {str(e)}", "error")
        import traceback
        traceback.print_exc()
        return redirect(url_for('ai_panel'))


@app.route("/authors")
def Authors():
    authors = []

    if os.path.exists(PROFILE_FILE):
        df = pd.read_excel(PROFILE_FILE)

        for _, row in df.iterrows():
            image_file = row['photo'] if pd.notna(row['photo']) else "default-avatar.png"

            authors.append({
                "username": row['username'],
                "first_name": row['first_name'],
                "last_name": row['last_name'],
                "phone": row['phone'],
                "email": row['email'],
                "bio": row['bio'] if 'bio' in row and pd.notna(row['bio']) else "",
                "image": image_file
            })

    return render_template("Authors.html", authors=authors)

@app.route("/author/<username>/works")
def author_works(username):
    """
    نمایش آثار یک نویسنده خاص
    """
    print(f"درخواست آثار برای نویسنده: {username}")

    author = None
    if os.path.exists(PROFILE_FILE):
        try:
            df_profiles = pd.read_excel(PROFILE_FILE)
            user_data = df_profiles[df_profiles['username'] == username]

            if not user_data.empty:
                row = user_data.iloc[0]
                author = {
                    "username": username,
                    "first_name": row['first_name'],
                    "last_name": row['last_name'],
                    "phone": row['phone'],
                    "email": row['email'],
                    "bio": row['bio'] if 'bio' in row and pd.notna(row['bio']) else "",
                    "image": row['photo'] if pd.notna(row['photo']) else "default-avatar.png"
                }
                print(f"نویسنده پیدا شد: {author['first_name']} {author['last_name']}")
            else:
                print(f"نویسنده با username '{username}' یافت نشد")
                return render_template("error.html",
                                       message=f"نویسنده با نام کاربری '{username}' یافت نشد"), 404

        except Exception as e:
            print(f"خطا در خواندن پروفایل: {e}")
            return render_template("error.html",
                                   message="خطا در خواندن اطلاعات نویسنده"), 500
    else:
        print(f"فایل پروفایل وجود ندارد: {PROFILE_FILE}")
        return render_template("error.html",
                               message="فایل پروفایل‌ها یافت نشد"), 404

    all_artworks = []

    for cat, cat_info in route_map.items():
        file_name = cat_info['file']
        cat_name = cat_info['name']
        file_path = os.path.join(SAVE_DIR, file_name)

        print(f"جستجو در دسته‌بندی: {cat_name} -> فایل: {file_name}")

        if os.path.exists(file_path):
            try:
                df = pd.read_excel(file_path)

                required_columns = ['شماره', 'عنوان', 'محتوا', 'username']
                if all(col in df.columns for col in required_columns):
                    author_works_df = df[df['username'] == username]

                    if not author_works_df.empty:
                        print(f"  ✓ {len(author_works_df)} اثر یافت شد")

                        for _, row in author_works_df.iterrows():
                            status = str(row['status']).lower() if 'status' in df.columns and pd.notna(row.get('status')) else "public"

                            item_link = url_for('view_item', cat=cat, item_id=row['شماره'])

                            date_str = ""
                            if 'تاریخ' in df.columns and pd.notna(row.get('تاریخ')):
                                date_str = str(row['تاریخ'])
                            elif 'created_at' in df.columns and pd.notna(row.get('created_at')):
                                date_str = str(row['created_at'])

                            if status == "public":
                                artwork = {
                                    "id": int(row['شماره']),
                                    "title": str(row['عنوان']),
                                    "content": str(row['محتوا']),
                                    "category": cat_name,
                                    "category_key": cat,
                                    "date": date_str,
                                    "link": item_link,
                                    "excerpt": str(row['محتوا'])[:150] + "..." if len(str(row['محتوا'])) > 150 else str(row['محتوا']),
                                    "status": status
                                }
                            else:
                                artwork = {
                                    "id": int(row['شماره']),
                                    "title": str(row['عنوان']),
                                    "content": "",
                                    "category": cat_name,
                                    "category_key": cat,
                                    "date": date_str,
                                    "link": item_link,
                                    "excerpt": "",
                                    "status": status
                                }

                            all_artworks.append(artwork)
                    else:
                        print(f"  ✗ اثری یافت نشد")
                else:
                    missing_cols = [col for col in required_columns if col not in df.columns]
                    print(f"  ✗ ستون‌های گمشده: {missing_cols}")
            except Exception as e:
                print(f"  ✗ خطا در خواندن فایل: {e}")
        else:
            print(f"  ✗ فایل وجود ندارد: {file_path}")

    print(f"مجموع آثار یافت شده: {len(all_artworks)}")
    all_artworks.sort(key=lambda x: x.get('id', 0), reverse=True)
    return render_template("author_works.html",
                           author=author,
                           artworks=all_artworks,
                           total_works=len(all_artworks))

@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True)
