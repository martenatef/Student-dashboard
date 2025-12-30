from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ================= Models =================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    courses = db.relationship('Course', backref='owner', lazy=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    section = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    assignments = db.relationship('Assignment', backref='course', lazy=True)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    type = db.Column(db.String(50))  # Assignment, Quiz, Mid, Final
    due_date = db.Column(db.String(50))
    max_grade = db.Column(db.Float)
    grade = db.Column(db.Float, nullable=True)  # درجة الطالب
    completed = db.Column(db.Boolean, default=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))

# ================= Login Loader =================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ================= Routes =================
@app.route('/')
def home():
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        if User.query.filter_by(username=username).first():
            flash('Username already exists!')
            return redirect(url_for('register'))
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            flash('Invalid credentials!')
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    courses = Course.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', courses=courses)

@app.route('/add_course', methods=['GET','POST'])
@login_required
def add_course():
    if request.method == 'POST':
        name = request.form['name']
        section = request.form['section']
        new_course = Course(name=name, section=section, owner=current_user)
        db.session.add(new_course)
        db.session.commit()
        flash('Course added!')
        return redirect(url_for('dashboard'))
    return render_template('add_course.html')

@app.route('/add_assignment/<int:course_id>', methods=['GET','POST'])
@login_required
def add_assignment(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        title = request.form['title']
        type = request.form['type']
        due_date = request.form['due_date']
        max_grade = float(request.form['max_grade'])
        grade = request.form.get('grade')
        grade = float(grade) if grade else None
        assignment = Assignment(title=title, type=type, due_date=due_date, max_grade=max_grade, grade=grade, course=course)
        if grade is not None:
            assignment.completed = True
        db.session.add(assignment)
        db.session.commit()
        flash('Assignment added!')
        return redirect(url_for('dashboard'))
    return render_template('add_assignment.html', course=course)

@app.route('/edit_grade/<int:assignment_id>', methods=['GET','POST'])
@login_required
def edit_grade(assignment_id):
    task = Assignment.query.get_or_404(assignment_id)
    if request.method == 'POST':
        grade = float(request.form['grade'])
        task.grade = grade
        task.completed = True
        db.session.commit()
        flash('Grade updated!')
        return redirect(url_for('dashboard'))
    return render_template('edit_grade.html', task=task)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/delete_assignment/<int:assignment_id>', methods=['GET'])
@login_required
def delete_assignment(assignment_id):
    task = Assignment.query.get_or_404(assignment_id)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted!')
    return redirect(url_for('dashboard'))

@app.route('/delete_course/<int:course_id>', methods=['GET'])
@login_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    # حذف كل الـ Assignments المرتبطة بالكورس أولاً
    for task in course.assignments:
        db.session.delete(task)
    db.session.delete(course)
    db.session.commit()
    flash('Course and all its tasks deleted!')
    return redirect(url_for('dashboard'))

@app.route('/gpa_calculator', methods=['GET', 'POST'])
@login_required
def gpa_calculator():
    gpa = None
    if request.method == 'POST':
        courses = request.form.getlist('course')
        grades = request.form.getlist('grade')
        credits = request.form.getlist('credit')
        total_points = 0
        total_credits = 0
        for g, c in zip(grades, credits):
            try:
                grade = float(g)
                credit = float(c)
                total_points += grade * credit
                total_credits += credit
            except:
                continue
        if total_credits > 0:
            gpa = round(total_points / total_credits, 2)
    return render_template('gpa_calculator.html', gpa=gpa)

@app.route('/analytics')
@login_required
def analytics():
    courses = Course.query.filter_by(user_id=current_user.id).all()
    chart_data = []
    for course in courses:
        course_data = {
            'name': course.name,
            'assignments': [{'title': a.title, 'grade': a.grade if a.grade is not None else 0} for a in course.assignments]
        }
        chart_data.append(course_data)
    return render_template('analytics.html', chart_data=chart_data)

@app.route('/grade_predictor', methods=['GET', 'POST'])
@login_required
def grade_predictor():
    predicted_grade = None
    course_name = ""
    if request.method == 'POST':
        course_name = request.form['course_name']
        try:
            assignments = [float(x) for x in request.form.getlist('assignment')]
            mid = float(request.form['mid'])
            final = float(request.form['final'])
            # حساب متوسط الـ assignments
            avg_assignments = sum(assignments) / len(assignments) if assignments else 0
            predicted_grade = round(avg_assignments*0.3 + mid*0.3 + final*0.4, 2)
        except:
            predicted_grade = "Invalid input"
    return render_template('grade_predictor.html', predicted_grade=predicted_grade, course_name=course_name)

# ================= Main =================
if __name__ == "__main__":
    # إنشاء قاعدة البيانات والجداول الجديدة
    with app.app_context():
        db.create_all()
    app.run(debug=True)
