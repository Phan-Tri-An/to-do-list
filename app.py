import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
import google.generativeai as genai # Import genai

# --- Khởi tạo ứng dụng ---
app = Flask(__name__)
CORS(app) # Kích hoạt CORS cho tất cả các route

# --- Cấu hình ---
# THAY ĐỔI 1: ĐỌC DATABASE_URL TỪ BIẾN MÔI TRƯỜNG CỦA RENDER
# (Không còn dùng DB_USERNAME, DB_PASSWORD, DB_HOST, DB_NAME nữa)
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# THAY ĐỔI 2: ĐỌC JWT_SECRET_KEY TỪ BIẾN MÔI TRƯỜNG
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'default-fallback-key-for-local-dev') # Thay đổi key này sau

# --- Khởi tạo các thư viện ---
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# --- Cấu hình AI ---
# THAY ĐỔI 3: ĐỌC GOOGLE_API_KEY TỪ BIẾN MÔI TRƯỜNG
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash') # Sửa lại tên model
else:
    print("CẢNH BÁO: GOOGLE_API_KEY không được tìm thấy. API AI sẽ không hoạt động.")
    model = None

# --- Models (Thiết kế "Trí nhớ") ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) # Sẽ lưu pass đã mã hóa
    
    # Quan hệ: Một User có nhiều Task
    tasks = db.relationship('Task', backref='owner', lazy=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    
    # Khóa ngoại liên kết tới bảng User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- Routes (Sẽ thêm ở bước sau) ---
@app.route('/')
def hello():
    return "Backend Server đang chạy!"


# --- API Xác thực ---

@app.route('/register', methods=['POST'])
def register():
    # 1. Lấy dữ liệu từ request JSON
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # 2. Kiểm tra xem username đã tồn tại chưa
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'message': 'Tên đăng nhập đã tồn tại'}), 400 # 400 Bad Request

    # 3. Mã hóa mật khẩu
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    # 4. Tạo user mới và lưu vào DB
    new_user = User(username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'Đăng ký thành công'}), 201 # 201 Created


# ... (code của /register) ...

@app.route('/login', methods=['POST'])
def login():
    # 1. Lấy dữ liệu từ request JSON
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # 2. Tìm user trong DB
    user = User.query.filter_by(username=username).first()

    # 3. Kiểm tra user và mật khẩu
    # Dùng bcrypt để so sánh mật khẩu nhập vào với mật khẩu đã mã hóa trong DB
    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({'message': 'Tên đăng nhập hoặc mật khẩu không đúng'}), 401 # 401 Unauthorized

    # 4. Tạo JWT Token
    # Nếu đúng, tạo một token (vé vào cửa) cho user này
    access_token = create_access_token(identity=str(user.id))
    
    return jsonify({'access_token': access_token, 'username': user.username}), 200 # Trả về thêm username


# ... (code của /login) ...

# --- API Quản lý Công việc (Tasks) ---
# API này được bảo vệ, yêu cầu phải có access_token
@app.route('/tasks', methods=['POST'])
@jwt_required() # Đánh dấu route này cần xác thực
def create_task():
    # 1. Lấy user_id từ token
    current_user_id = get_jwt_identity()
    
    # 2. Lấy dữ liệu task từ request
    data = request.get_json()
    title = data.get('title')
    description = data.get('description', '') # Description không bắt buộc

    # 3. Tạo task mới và gán cho user
    new_task = Task(title=title, description=description, owner=User.query.get(current_user_id))
    db.session.add(new_task)
    db.session.commit()
    
    return jsonify({'message': 'Tạo task thành công', 'task_id': new_task.id}), 201

# API này cũng được bảo vệ
@app.route('/tasks', methods=['GET'])
@jwt_required()
def get_tasks():
    # 1. Lấy user_id từ token
    current_user_id = get_jwt_identity()
    
    # 2. Lấy tất cả task của user đó
    user_tasks = Task.query.filter_by(user_id=current_user_id).all()
    
    # 3. Chuyển đổi tasks thành định dạng JSON để trả về
    tasks_list = []
    for task in user_tasks:
        tasks_list.append({
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'is_completed': task.is_completed
        })
        
    return jsonify(tasks_list), 200

# ... (code của GET /tasks) ...

@app.route('/tasks/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    current_user_id = int(get_jwt_identity()) # Đảm bảo user_id là integer để so sánh
    
    # 1. Tìm task theo id
    task = Task.query.get(task_id)

    # 2. Kiểm tra task có tồn tại không
    if not task:
        return jsonify({'message': 'Không tìm thấy task'}), 404
        
    # 3. Kiểm tra task này có thuộc về user đang đăng nhập không
    if task.user_id != current_user_id:
        return jsonify({'message': 'Không có quyền sửa task này'}), 403 # 403 Forbidden
        
    # 4. Lấy dữ liệu mới và cập nhật
    data = request.get_json()
    task.title = data.get('title', task.title) # Nếu không gửi title, giữ lại title cũ
    task.description = data.get('description', task.description)
    task.is_completed = data.get('is_completed', task.is_completed)
    
    db.session.commit()
    
    return jsonify({'message': 'Cập nhật task thành công'}), 200

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    current_user_id = int(get_jwt_identity())
    
    # 1. Tìm task
    task = Task.query.get(task_id)

    # 2. Kiểm tra
    if not task:
        return jsonify({'message': 'Không tìm thấy task'}), 404
        
    if task.user_id != current_user_id:
        return jsonify({'message': 'Không có quyền xóa task này'}), 403
        
    # 3. Xóa task
    db.session.delete(task)
    db.session.commit()
    
    return jsonify({'message': 'Xóa task thành công'}), 200


@app.route('/ai-breakdown', methods=['POST'])
@jwt_required() # Thêm bảo vệ cho API này
def ai_breakdown():
    # 1. Lấy công việc lớn từ React
    data = request.get_json()
    task_title = data.get('title')

    if not task_title:
        return jsonify({'error': 'Không có tiêu đề'}), 400
    
    # Kiểm tra xem model AI đã được khởi tạo chưa
    if not model:
        return jsonify({'error': 'Chức năng AI chưa được cấu hình (Thiếu API Key).'}), 500

    # 2. Tạo câu lệnh (Prompt) cho AI
    prompt = f"Bạn là một trợ lý quản lý dự án. Hãy phân rã công việc lớn sau đây: '{task_title}' thành các bước con cụ thể. Chỉ trả về danh sách các bước con (bắt đầu bằng gạch đầu dòng -), không cần giải thích thêm."

    try:
        # 3. Gọi AI
        response = model.generate_content(prompt)

        # 4. Trả kết quả về cho React
        return jsonify({'subtasks': response.text})

    except Exception as e:
        print("!!!!!!!!!!!! LỖI AI !!!!!!!!!!!!")
        print(e)
        return jsonify({'error': str(e)}), 500

# Tạo bảng CSDL (nếu chưa có) trước khi chạy
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True) # Giữ lại để test local, Render sẽ không chạy dòng này