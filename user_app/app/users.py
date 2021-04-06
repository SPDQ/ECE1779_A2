from flask import Blueprint,render_template,session,redirect,request,flash,url_for, g
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
import boto3
import os
from app import app
from datetime import datetime


s3 = boto3.client(
    's3',
    region_name='us-east-1',
    aws_access_key_id=app.config['AWS_AccessKeyId'],
    aws_secret_access_key=app.config['AWS_SecretAccessKey'],
    aws_session_token=app.config['AWS_Token'])
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


@app.route('/user_home')
def user_home():
    request_count()
    if 'username' not in session.keys():
        flash('Please login')
        return redirect("/login")
    is_admin = True if session['is_admin'] == 1 else False
    payload = {"username":session['username'], "is_admin":is_admin, }
    return render_template("user_home.html", is_admin = session['is_admin'], payload = payload)


@app.route('/add', methods = ['GET','POST'])
def add():
    request_count()
    con = db_connect()
    if 'username' not in session.keys():
        flash('Please login')
        return redirect("/login")
    if session["username"] != 'admin':
        flash("You are not admin. You cannot add account")
        return redirect(url_for("user_home"))
    error = None
    if request.method == 'POST' and request.form["username"] != '' and  request.form['password'] != '':
        username = request.form['username']
        password = request.form['password']
        if request.form['email'] == '':
            email = None
            flash("CAUTION: "+ str(username) + " do not have email. Unable to recovery password later.")
        else:
            email = request.form['email']
        cursor = con.cursor(pymysql.cursors.DictCursor)
        exit_user = cursor.execute("SELECT * FROM users WHERE username = %s ",(username,))
        if exit_user > 0:
            flash("The username already exist.")
            return redirect(url_for('add'))
        else:
            try:
                cursor.execute("INSERT INTO users (username, password, email, admin) VALUE (%s, %s, %s, false)",(username,generate_password_hash(password) ,email,))
                con.commit()
                flash("Successfully add user: " + str(username))
                return redirect(url_for('add'))
            except Exception as e:
                flash("Error: " + str(e))
                return redirect(url_for('add'))
    elif request.method == 'POST' :
        error = "Please provide username and password to add new user."
    if error is not None:
        flash(error)
    return render_template("add_user.html")


@app.route('/delete', methods = ['GET', 'POST'])
def delete():
    request_count()
    con = db_connect()
    if 'username' not in session.keys():
        flash('Please login')
        return redirect("/login")
    if session["username"] != 'admin':
        flash("You are not admin. You cannot delete account")
        return redirect(url_for("user_home"))
    error = None
    if request.method == 'POST' and request.form["username"] != '':
        username = request.form["username"]
        cursor = con.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE username = %s ", (username,))
        account = cursor.fetchone()
        if not account:
            flash("The user do not exist.")
            return redirect(url_for('delete'))
        else:
            if account["username"]=='admin':
                flash("You cannot delete admin account")
                return redirect(url_for('delete'))
            try:
                cursor.execute("SELECT * FROM images WHERE user_id = %s ", (account['id'],))
                imgs = cursor.fetchall()
                for image in imgs:
                    s3.delete_object(
                        Bucket=app.config['Bucket_name'],
                        Key=image["image_path"],
                    )
                cursor.execute("DELETE FROM users WHERE username = %s", (username, ))
                cursor.execute("DELETE FROM images WHERE user_id = %s", (account['id'],))
                con.commit()

                # img_path = os.path.join(app.config['ImgUploadPath'], username)
                # img_result = os.path.join(app.config['ImgResultPath'], username)
                # if os.path.exists(img_path):
                #     #print(img_path)
                #     import shutil
                #     shutil.rmtree(img_path)
                # if os.path.exists(img_result):
                #     import shutil
                #     shutil.rmtree(img_result)

                flash("Successfull delete user: " + str(username))
                return redirect(url_for('delete'))
            except Exception as e:
                flash('ERROR: ' + str(e))
                return redirect(url_for('delete'))
    elif request.form == 'POST':
        error = "Please provide user name."

    if error is not None:
        flash(error)
    return render_template('delete_user.html')


@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    request_count()
    con = db_connect()
    error = None
    if 'username' in session.keys():
        redirect(url_for("login"))
    if request.method == 'POST':
        if request.form["username"] != '' and request.form["new_passwd"] != '':
            username = request.form["username"]
            email = request.form["email"]
            if username != session["username"]:
                flash('You cannot change the password of other accounts.')
                return (url_for('change_password'))
            cursor = con.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            account = cursor.fetchone()
            if account and account["email"] == email:
                new_passwd = generate_password_hash(request.form["new_passwd"])
                try:
                    cursor.execute("UPDATE users SET password=%s WHERE username = %s", (new_passwd, username,))
                    con.commit()
                    flash("Successfully change password for user:  " + str(username))
                    if 'username' in session.keys():
                        session.pop('username', None)
                    if 'is_admin' in session.keys():
                        session.pop('is_admin', None)
                    return redirect(url_for("login"))
                except Exception as e:
                    flash(str(e))
                    print(e)
                    return(url_for('change_password'))
            else:
                error = "Your email or username is incorrect."
        else:
            error = "Please fill the form to recovery your password."
    if error is not None:
        flash(error)
    return render_template("change_password.html", error = error)


@app.route('/logout')
def logout():
    request_count()
    if 'username' not in session.keys():
        flash('Please login')
        return redirect("/login")
    error = "You have logout."
    session.pop('username', None)
    session.pop('is_admin', None)
    # Redirect to login page
    return redirect(url_for('login'))


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