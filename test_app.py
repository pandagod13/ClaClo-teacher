import os
import pytest
from app import app, db, User, Course, Assignment, AssignmentSubmission, Enrollment
import shutil

@pytest.fixture
def client():
    """
    Create a test client for the application.

    The test client is configured for testing purposes by setting the `TESTING` flag to `True` and
    specifying the upload folder for file uploads. The upload folder is created if it does not exist.

    The test client is created as a context manager to handle the setup and teardown operations
    before and after each test. The application context is also created within the test client.

    :return: The test client for the application.
    """
    app.config['TESTING'] = True
    app.config['UPLOAD_FOLDER'] = './uploads'
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()
        shutil.rmtree(app.config['UPLOAD_FOLDER'])


def test_register_and_login(client):
    """
    :param client: the client object used to make API requests
    :return: the access token of the logged-in user

    This method tests the functionality of registering a teacher and then logging in with the registered teacher's credentials. It verifies that the HTTP response status codes are as expected and returns the access token of the logged-in user.
    """
    # Register a teacher
    response = client.post('/register', json={
        'name': 'Teacher 1',
        'email': 'teacher1@test.com',
        'password': 'securepassword',
        'type': 'teacher'
    })
    assert response.status_code == 201

    # Login with the registered teacher credentials
    response = client.post('/login', json={
        'email': 'teacher1@test.com',
        'password': 'securepassword'
    })
    assert response.status_code == 200
    return response.get_json()['access_token']


# FR-TE-1: Set up exercises and assessment
def test_create_and_get_course(client):
    """
    :param client: the client used to make HTTP requests
    :return: None

    This method tests the functionality of creating and retrieving a course using the provided client.

    1. First, it calls the function test_register_and_login to obtain the access token required for authentication.
    2. It sets the headers for the HTTP request with the access token.
    3. It sends a POST request to create a course with the title 'Math 101' and the description 'Basic Math'. The response is expected to have a status code of 201 (Created).
    4. It retrieves the course ID from the response JSON.
    5. It sends a GET request to retrieve the created course using the course ID. The response is expected to have a status code of 200 (OK).
    """
    access_token = test_register_and_login(client)
    headers = {'Authorization': f'Bearer {access_token}'}

    # Test creating a course
    response = client.post('/courses', json={
        'title': 'Math 101',
        'description': 'Basic Math'
    }, headers=headers)
    assert response.status_code == 201

    # Test retrieving the course
    course_id = response.get_json()['id']
    response = client.get(f'/courses/{course_id}')
    assert response.status_code == 200


def test_assignment_workflow(client):
    """
    :param client: The Flask test client object used to make HTTP requests to the application.
    :return: None

    This method tests the assignment workflow by performing the following steps:

    1. Registering and logging in a user using the provided client object.
    2. Creating a course with a title and description using a POST request to '/courses' endpoint.
    3. Adding an assignment to the created course using a POST request to '/courses/{course_id}/assignments' endpoint.
    4. Asserting that the response status code is equal to 201.
    5. Retrieving the created assignment using a GET request to '/courses/{course_id}/assignments/{assignment_id}' endpoint.
    6. Asserting that the response status code is equal to 200.
    """
    access_token = test_register_and_login(client)
    headers = {'Authorization': f'Bearer {access_token}'}

    # Create a course
    response = client.post('/courses', json={
        'title': 'Science 101',
        'description': 'Basic Science'
    }, headers=headers)
    course_id = response.get_json()['id']

    # Test adding an assignment
    response = client.post(f'/courses/{course_id}/assignments', json={
        'name': 'Assignment 1',
        'due_date': '2024-05-31T23:59:59Z',
        'description': 'Solve these problems'
    }, headers=headers)
    assert response.status_code == 201

    assignment_id = response.get_json()['id']

    # Test retrieving the assignment
    response = client.get(f'/courses/{course_id}/assignments/{assignment_id}', headers=headers)
    assert response.status_code == 200


# FR-TE-2: Mark student works
def test_mark_assignment(client):
    """
    :param client: the client object used for making HTTP requests
    :return: None

    This method tests the marking of an assignment submission for a specific student. It performs the following steps:

    1. Calls the method `test_register_and_login` to obtain an access token for authentication.
    2. Sets the headers for the HTTP request with the access token.
    3. Creates a new course by making a POST request to the '/courses' endpoint with the required parameters.
    4. Extracts the course ID from the response JSON.
    5. Adds an assignment to the course by making a POST request to the '/courses/{course_id}/assignments' endpoint with the required parameters.
    6. Extracts the assignment ID from the response JSON.
    7. Registers a student by making a POST request to the '/register' endpoint with the required parameters.
    8. Extracts the student ID from the response JSON.
    9. Enrolls the student in the course by making a POST request to the '/courses/{course_id}/enroll' endpoint.
    10. Adds a submission for the student and the assignment (if using a submissions model).
    11. Marks the student's submission by making a PUT request to the '/courses/{course_id}/assignments/{assignment_id}/submissions/{student_id}/mark' endpoint with the required parameters.
    12. Asserts that the response status code is 200 and the response message is 'Marks and feedback updated successfully'.
    """
    access_token = test_register_and_login(client)
    headers = {'Authorization': f'Bearer {access_token}'}

    # Create a course
    response = client.post('/courses', json={
        'title': 'Math 101',
        'description': 'Basic Math'
    }, headers=headers)
    course_id = response.get_json()['id']

    # Add an assignment
    response = client.post(f'/courses/{course_id}/assignments', json={
        'name': 'Assignment 1',
        'due_date': '2024-05-31T23:59:59Z',
        'description': 'Solve problems'
    }, headers=headers)
    assignment_id = response.get_json()['id']

    # Register and enroll a student
    response = client.post('/register', json={
        'name': 'Student 1',
        'email': 'student1@test.com',
        'password': 'securepassword',
        'type': 'student'
    })
    student_id = response.get_json()['id']
    client.post(f'/courses/{course_id}/enroll', headers=headers)

    # Add a submission directly (if using a submissions model)
    with app.app_context():
        submission = AssignmentSubmission(student_id=student_id, assignment_id=assignment_id)
        db.session.add(submission)
        db.session.commit()

    # Mark the student's submission
    response = client.put(f'/courses/{course_id}/assignments/{assignment_id}/submissions/{student_id}/mark', json={
        'marks': 90,
        'feedback': 'Great job!'
    }, headers=headers)
    assert response.status_code == 200
    assert response.get_json()['message'] == 'Marks and feedback updated successfully'


# FR-TE-3: Upload teaching material
def test_upload_material(client):
    """
    :param client: The client object used to make HTTP requests.
    :return: None

    This method tests the functionality of uploading a teaching material file for a course. It takes a client object as a parameter, which is used to make HTTP requests.

    The method first calls the method test_register_and_login(client) to obtain an access token. Then, it creates a course by making a POST request to '/courses' endpoint with the required course details, including the title and description. The response from this request is stored in the `response` variable. The course ID is extracted from the response JSON and stored in the `course_id` variable.

    Next, the method prepares the data for uploading the teaching material file. It sets the value for the `file` parameter as a tuple containing the file object and the filename. In this example, the file object is obtained by opening the current file (__file__) in read-binary ('rb') mode, and the filename is set as 'test_material.txt'.

    Finally, the method makes a POST request to the '/courses/{course_id}/materials' endpoint with the appropriate headers and data. The response from this request is stored in the `response` variable. The method then asserts that the response status code is equal to 201 (indicating success) and the response JSON contains a 'message' key with the value 'File uploaded successfully'.

    Note: This method assumes that there is already an implementation of test_register_and_login(client) method, and the necessary imports for the client object and other dependencies are already done.
    """
    access_token = test_register_and_login(client)
    headers = {'Authorization': f'Bearer {access_token}'}

    # Create a course
    response = client.post('/courses', json={
        'title': 'Physics 101',
        'description': 'Basic Physics'
    }, headers=headers)
    course_id = response.get_json()['id']

    # Upload a teaching material file
    data = {
        'file': (open(__file__, 'rb'), 'test_material.txt')
    }
    response = client.post(f'/courses/{course_id}/materials', content_type='multipart/form-data', headers=headers, data=data)
    assert response.status_code == 201
    assert response.get_json()['message'] == 'File uploaded successfully'


# FR-TE-4: Manage classes
def test_manage_classes(client):
    """
    Manage Classes Test

    This method tests the functionality of managing classes in the system. It performs the following actions:

    1. Registers and logs in a client.
    2. Creates a course.
    3. Registers and enrolls a student.
    4. Retrieves the list of students in the course.

    :param client: The client object used for making requests to the API.

    :return: None.

    """
    access_token = test_register_and_login(client)
    headers = {'Authorization': f'Bearer {access_token}'}

    # Create a course
    response = client.post('/courses', json={
        'title': 'Biology 101',
        'description': 'Intro to Biology'
    }, headers=headers)
    course_id = response.get_json()['id']

    # Register and enroll a student
    response = client.post('/register', json={
        'name': 'Student 2',
        'email': 'student2@test.com',
        'password': 'securepassword',
        'type': 'student'
    })
    student_id = response.get_json()['id']
    enroll_response = client.post(f'/courses/{course_id}/enroll', headers=headers)
    assert enroll_response.status_code == 200, "Enrollment failed."

    # List students in the course
    response = client.get(f'/courses/{course_id}/students', headers=headers)
    assert response.status_code == 200



# Additional tests
def test_duplicate_registration(client):
    """
    Test Duplicate Registration

    Tests the registration process for duplicate users.

    :param client: the client object used for making HTTP requests to the server
    :return: None

    """
    # Register a user
    client.post('/register', json={
        'name': 'Test Teacher',
        'email': 'teacher@test.com',
        'password': 'securepassword',
        'type': 'teacher'
    })

    # Attempt to register the same user again
    response = client.post('/register', json={
        'name': 'Test Teacher',
        'email': 'teacher@test.com',
        'password': 'securepassword',
        'type': 'teacher'
    })
    assert response.status_code == 409  # Conflict
    assert 'Email already used' in response.get_json()['message']


def test_invalid_login(client):
    """
    Test the behavior of the login endpoint with an invalid password.

    :param client: the Flask testing client
    :return: None
    """
    # Register a user
    client.post('/register', json={
        'name': 'Test Teacher',
        'email': 'teacher@test.com',
        'password': 'securepassword',
        'type': 'teacher'
    })

    # Attempt to log in with an incorrect password
    response = client.post('/login', json={
        'email': 'teacher@test.com',
        'password': 'wrongpassword'
    })
    assert response.status_code == 401  # Unauthorized
    assert 'Invalid credentials' in response.get_json()['message']


def test_update_course(client):
    """
    Test update_course method.

    :param client: Flask test client object.
    :return: None

    This method tests the functionality of the update_course endpoint. It makes use of the test_register_and_login method to authenticate the client and obtain an access_token. The method then creates a new course using the client's post method, and retrieves the newly created course's id from the response. It then updates the course using the client's put method, with the new title and description. Assertions are performed to check if the response status code is 200, and if the updated_course's title and description match the updated values.
    """
    access_token = test_register_and_login(client)
    headers = {'Authorization': f'Bearer {access_token}'}

    # Create a course
    response = client.post('/courses', json={
        'title': 'Math 101',
        'description': 'Basic Math'
    }, headers=headers)
    course_id = response.get_json()['id']

    # Update the course
    response = client.put(f'/courses/{course_id}', json={
        'title': 'Advanced Math',
        'description': 'In-depth Math'
    }, headers=headers)
    assert response.status_code == 200
    updated_course = response.get_json()
    assert updated_course['title'] == 'Advanced Math'
    assert updated_course['description'] == 'In-depth Math'


def test_delete_course(client):
    """
    :param client: the client object used to make API requests
    :return: None

    This method tests the delete_course functionality of the API.

    The method first registers and logs in a user using the test_register_and_login method. It then creates a new course using a POST request to the '/courses' endpoint with the provided client and access token. The course details are passed as a JSON object in the request body.

    The method retrieves the ID of the created course from the POST response and uses it to send a DELETE request to the '/courses/{course_id}' endpoint, with the corresponding course ID and headers.

    The method asserts that the response status code for the DELETE request is 200, indicating a successful deletion.

    Finally, the method sends a GET request to the '/courses/{course_id}' endpoint to verify that the deleted course cannot be accessed anymore. It asserts that the response status code is 404, indicating the course is not found.

    Note: This method assumes that the test_register_and_login method is implemented and returns an access token. The headers used for the request include the access token for authorization.
    """
    access_token = test_register_and_login(client)
    headers = {'Authorization': f'Bearer {access_token}'}

    # Create a course
    response = client.post('/courses', json={
        'title': 'History 101',
        'description': 'World History'
    }, headers=headers)
    course_id = response.get_json()['id']

    # Delete the course
    response = client.delete(f'/courses/{course_id}', headers=headers)
    assert response.status_code == 200

    # Verify the course is gone
    response = client.get(f'/courses/{course_id}')
    assert response.status_code == 404

