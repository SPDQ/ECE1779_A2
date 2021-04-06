from flask import Blueprint, render_template, session, request, url_for, redirect, flash, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from app import app
from .image import generate_error_response
import jwt
from time import time
from flask_mail import Message, Mail
import os
from datetime import datetime
import boto3


cloudwatch = boto3.client(
    'cloudwatch',
    region_name='us-east-1',
    aws_access_key_id=app.config['AWS_AccessKeyId'],
    aws_secret_access_key=app.config['AWS_SecretAccessKey'],
    aws_session_token=app.config['AWS_Token'])


def db_connect():
    return pymysql.connect(host=app.config['Database_host'],
                           port=app.config['Database_port'],
                           user=app.config['Database_user'],
                           password=app.config['Database_password'],
                           db=app.config['Database_db'],
                           autocommit=True
                           )


@app.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route('/')
def home_page():
    request_count()
    # path = "../upload/home.png"
    return render_template('home_page.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    request_count()
    error = None
    con = db_connect()
    if request.method == 'POST':
        if 'username' in request.form and 'password' in request.form:
            username = request.form['username']
            cursor = con.cursor(pymysql.cursors.DictCursor)
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            account = cursor.fetchone()
            print(account)
            if account and check_password_hash(account["password"], request.form['password']):
                session['username'] = account['username']
                session['is_admin'] = account['admin']
                return redirect(url_for('user_home'))
            else:
                error = "Wrong passwords or username does not exist. Please try again."
        else:
            error = "Wrong passwords or username does not exist. Please try again."
    print(error)
    if error is not None:
        flash(error)
    return render_template('login.html')


def get_reset_password_token(username):
    return jwt.encode(
        {'reset_password': username},
        app.config['SECRET_KEY'], algorithm='HS256')


def verify_reset_password_token(token):
    try:
        username = jwt.decode(token, app.config['SECRET_KEY'],
                              algorithms=['HS256'])['reset_password']
    except:
        return
    return username


@app.route('/recovery_password', methods=['GET', 'POST'])
def recover_passwd():
    request_count()
    con = db_connect()
    error = None
    if request.method == 'POST':
        if request.form["username"] != '' and request.form["email"] != '':
            username = request.form["username"]
            email = request.form["email"]
            cursor = con.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            account = cursor.fetchone()
            if account and account["email"] == email:
                message = Message(subject='Password Recovery',
                                  sender="307736651@qq.com",
                                  recipients=[email])
                token = get_reset_password_token(username)
                # message.body = "test"
                message.html = render_template('reset_email.html', username=username, token=token)
                try:
                    mail = Mail(app)
                    mail.send(message)
                    flash("Your password recovery email is sent successfully.")
                except:
                    error = "Fail to send password recovery email."
            else:
                error = "Your email or username is incorrect."
        else:
            error = "Please fill the form to recovery your password."
            print(error)
    if error is not None:
        flash(error)
    return render_template("password_recovery.html")


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    request_count()
    con = db_connect()
    if "username" in session:
        return redirect(url_for('user_home'))
    username = verify_reset_password_token(token)
    if not username:
        flash("Invalid link. Redirect to Login Page")
        return redirect(url_for('login'))
    if 'username' in request.form and 'password' in request.form:
        if request.form["username"] == username:
            new_passwd = generate_password_hash(request.form["password"])
            try:
                cursor = con.cursor(pymysql.cursors.DictCursor)
                cursor.execute("UPDATE users SET password=%s WHERE username = %s", (new_passwd, username,))
                con.commit()
                flash("Successfully change password for user:  " + str(username))
            except Exception as e:
                flash(str(e))
                print(e)
            return redirect(url_for("login"))
        else:
            flash('Wrong Username')
    else:
        flash('Input username and new password')
    return render_template('reset_password.html')


def register_generate_success_responses():
    response = jsonify(
            {"success": True}
        )
    # response.headers["Content-Type"] = "application/json"
    return response


@app.route('/api/register', methods=['POST'])
def api_register():
    request_count()
    con = db_connect()
    try:
        if "username" not in request.form or "password" not in request.form:
            return generate_error_response('Please input username and password', 401)
        username = request.form['username']
        password = request.form['password']
        cur = con.cursor(pymysql.cursors.DictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        account = cur.fetchone()
        if account:
            return generate_error_response('User already existed', 403)
        else:
            cur.execute("INSERT INTO users (username, password, admin) VALUES (%s, %s, false)",
                        (username, generate_password_hash(password)))
            con.commit()
            return register_generate_success_responses()
    except Exception as e:
        error = "Database error: " + str(e)
        return generate_error_response(error, 500)


def request_count():
    cloudwatch.put_metric_data(
        MetricData=[
            {
                'MetricName': 'Request_Rate',
                'Dimensions': [
                    {
                        'Name': 'InstanceId',
                        'Value': app.config['instance_id']
                    },
                ],
                'Timestamp': datetime.utcnow(),
                'Unit': 'None',
                'Value': 1.0
            },
        ],
        Namespace='My_Service'
    )