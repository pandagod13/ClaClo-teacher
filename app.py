from flask import Flask, request, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token
from flask_jwt_extended import get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

# Import dotenv library to load the environment variables
from dotenv import load_dotenv
load_dotenv()  # This function call loads the .env file that sits in the same directory as this script.

app = Flask(__name__)

# Update the configurations to use environment variables
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')


db = SQLAlchemy(app)
jwt = JWTManager(app)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    type = db.Column(db.String(10))  # Could be 'teacher', 'student', etc.

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assignments = db.relationship('Assignment', backref='course', lazy=True)

class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    due_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    description = db.Column(db.Text, nullable=True)

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    enroll_date = db.Column(db.DateTime, default=datetime.utcnow)

class AssignmentSubmission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'))
    marks = db.Column(db.Integer, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    submission_date = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('User', backref='submissions')
    assignment = db.relationship('Assignment', backref='submissions')


# User Registration
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    if not data or not all(k in data for k in ('name', 'email', 'password', 'type')):
        abort(400, description="Missing data for registration")
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already used'}), 409
    user = User(name=data['name'], email=data['email'], type=data['type'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'id': user.id, 'name': user.name, 'email': user.email, 'type': user.type}), 201

# User Login
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and user.check_password(data['password']):
        access_token = create_access_token(identity=user.id)
        return jsonify(access_token=access_token), 200
    return jsonify({"message": "Invalid credentials"}), 401

# Retrieve All Users
@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{"id": user.id, "name": user.name, "email": user.email, "type": user.type} for user in users])

# Error Handling for Not Found
@app.errorhandler(404)
def not_found(error):
    return jsonify({'message': 'Resource not found'}), 404

# Error Handling for Server Error
@app.errorhandler(500)
def server_error(error):
    return jsonify({'message': 'Server error'}), 500

# Course Management Routes
@app.route('/courses', methods=['POST'])
@jwt_required()
def create_course():
    data = request.json
    course = Course(title=data['title'], description=data.get('description'), teacher_id=get_jwt_identity())
    db.session.add(course)
    db.session.commit()
    return jsonify({'id': course.id, 'title': course.title}), 201

@app.route('/courses/<int:course_id>', methods=['GET'])
def get_course(course_id):
    course = Course.query.get_or_404(course_id)
    return jsonify({'id': course.id, 'title': course.title, 'description': course.description})

@app.route('/courses', methods=['GET'])
@jwt_required()
def list_courses():
    # Assuming that only the authenticated teacher should see their courses
    teacher_id = get_jwt_identity()
    courses = Course.query.filter_by(teacher_id=teacher_id).all()

    return jsonify([
        {'id': course.id, 'title': course.title, 'description': course.description}
        for course in courses
    ]), 200


@app.route('/courses/<int:course_id>', methods=['PUT'])
@jwt_required()
def update_course(course_id):
    data = request.json
    course = Course.query.filter_by(id=course_id, teacher_id=get_jwt_identity()).first()
    if not course:
        return jsonify({'message': 'Course not found or unauthorized access'}), 404

    # Update the course title and description
    course.title = data.get('title', course.title)
    course.description = data.get('description', course.description)
    db.session.commit()
    return jsonify({'id': course.id, 'title': course.title, 'description': course.description}), 200

@app.route('/courses/<int:course_id>', methods=['DELETE'])
@jwt_required()
def delete_course(course_id):
    course = Course.query.filter_by(id=course_id, teacher_id=get_jwt_identity()).first()
    if not course:
        return jsonify({'message': 'Course not found or unauthorized access'}), 404

    db.session.delete(course)
    db.session.commit()
    return jsonify({'message': 'Course deleted successfully'}), 200

UPLOAD_FOLDER = '/path/to/upload/folder'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/courses/<int:course_id>/materials', methods=['POST'])
@jwt_required()
def upload_material(course_id):
    # Ensure the authenticated user is the teacher who owns the course
    course = Course.query.filter_by(id=course_id, teacher_id=get_jwt_identity()).first()
    if not course:
        return jsonify({'message': 'Course not found or unauthorized access'}), 404

    # Verify that a file is present in the request
    if 'file' not in request.files:
        return jsonify({'message': 'No file part found in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No file selected'}), 400

    # Save the uploaded file to the configured directory
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return jsonify({'message': 'File uploaded successfully'}), 201

@app.route('/courses/<int:course_id>/students', methods=['GET'])
@jwt_required()
def list_course_students(course_id):
    course = Course.query.filter_by(id=course_id, teacher_id=get_jwt_identity()).first()
    if not course:
        return jsonify({'message': 'Course not found or unauthorized access'}), 404

    enrollments = Enrollment.query.filter_by(course_id=course_id).all()
    return jsonify([
        {'student_id': enrollment.student_id}
        for enrollment in enrollments
    ]), 200

@app.route('/courses/<int:course_id>/students/<int:student_id>', methods=['DELETE'])
@jwt_required()
def remove_student_from_course(course_id, student_id):
    # Ensure the authenticated user is the teacher who owns the course
    course = Course.query.filter_by(id=course_id, teacher_id=get_jwt_identity()).first()
    if not course:
        return jsonify({'message': 'Course not found or unauthorized access'}), 404

    # Find the enrollment record
    enrollment = Enrollment.query.filter_by(course_id=course_id, student_id=student_id).first()
    if not enrollment:
        return jsonify({'message': 'Student not enrolled in the course'}), 404

    db.session.delete(enrollment)
    db.session.commit()
    return jsonify({'message': 'Student removed successfully'}), 200


# Assignment Routes

@app.route('/courses/<int:course_id>/assignments/<int:assignment_id>/submissions/<int:student_id>/mark', methods=['PUT'])
@jwt_required()
def mark_submission(course_id, assignment_id, student_id):
    data = request.json
    # Ensure the authenticated user is the teacher who owns the course
    course = Course.query.filter_by(id=course_id, teacher_id=get_jwt_identity()).first()
    if not course:
        return jsonify({'message': 'Course not found or unauthorized access'}), 404

    # Find the specific student's submission
    submission = AssignmentSubmission.query.filter_by(
        assignment_id=assignment_id,
        student_id=student_id
    ).first()

    if not submission:
        return jsonify({'message': 'Submission not found'}), 404

    submission.marks = data.get('marks')
    submission.feedback = data.get('feedback')
    db.session.commit()
    return jsonify({'message': 'Marks and feedback updated successfully'}), 200


@app.route('/courses/<int:course_id>/assignments', methods=['POST'])
@jwt_required()
def add_assignment_to_course(course_id):
    data = request.json
    # Convert the due date string to a Python datetime object
    due_date = datetime.strptime(data['due_date'], '%Y-%m-%dT%H:%M:%SZ')
    assignment = Assignment(
        name=data['name'],
        due_date=due_date,
        course_id=course_id,
        description=data.get('description')
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify({'id': assignment.id, 'name': assignment.name}), 201

@app.route('/courses/<int:course_id>/assignments/<int:assignment_id>', methods=['GET'])
@jwt_required()
def get_assignment(course_id, assignment_id):
    assignment = Assignment.query.filter_by(id=assignment_id, course_id=course_id).first()
    if not assignment:
        return jsonify({'message': 'Assignment not found'}), 404
    return jsonify({
        'id': assignment.id,
        'name': assignment.name,
        'due_date': assignment.due_date.isoformat(),
        'description': assignment.description
    }), 200

# Enrollment Routes

@app.route('/courses/<int:course_id>/enroll', methods=['POST'])
@jwt_required()
def enroll_student(course_id):
    student_id = get_jwt_identity()  # Assuming the JWT identity is the student's ID
    enrollment = Enrollment(course_id=course_id, student_id=student_id)
    db.session.add(enrollment)
    db.session.commit()
    return jsonify({'message': 'Student enrolled successfully'}), 200


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)  # Turn off debug for production
