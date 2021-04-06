import os, cv2
import urllib
import pymysql
import boto3
from flask import render_template, session, redirect, url_for, flash, request, jsonify, make_response
from .FaceMaskDetection.pytorch_infer import inference
from app import app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

con = pymysql.connect(
    host=app.config['Database_host'],
    port=app.config['Database_port'],
    user=app.config['Database_user'],
    password=app.config['Database_password'],
    db=app.config['Database_db'],
    autocommit=True
)
s3 = boto3.client(
    's3',
    region_name='us-east-1',
    aws_access_key_id=app.config['AWS_AccessKeyId'],
    aws_secret_access_key=app.config['AWS_SecretAccessKey'],
    aws_session_token=app.config['AWS_Token'])
s3_r = boto3.resource(
    's3',
    region_name='us-east-1',
    aws_access_key_id=app.config['AWS_AccessKeyId'],
    aws_secret_access_key=app.config['AWS_SecretAccessKey'],
    aws_session_token=app.config['AWS_Token']
)
cloudwatch = boto3.client(
    'cloudwatch',
    region_name='us-east-1',
    aws_access_key_id=app.config['AWS_AccessKeyId'],
    aws_secret_access_key=app.config['AWS_SecretAccessKey'],
    aws_session_token=app.config['AWS_Token'])


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['AllowedImageType']


def get_savepath(userPath, name, t):
    savePath = os.path.join(userPath, name + "." + t)
    file_name = name + "." + t
    if os.path.exists(savePath):
        i = 1
        while os.path.exists(savePath):
            name1 = name + '(' + str(i) + ')'
            i = i + 1
            savePath = os.path.join(userPath, name1 + "." + t)
            file_name = name1 + "." + t
    return savePath, file_name


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    request_count()
    if "username" not in session:
        flash('Please login.')
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            f = request.files.get('myfile')
        except Exception as e:
            print(e)
            flash(str(e))
            return redirect(url_for('upload'))

        if request.form['myurl'] == '' and f.filename == '':
            flash('Please choose one way to upload an image')
            return redirect(url_for('upload'))
        if request.form['myurl'] != '' and f.filename != '':
            flash('You can only choose one way to upload image!')
            return redirect(url_for('upload'))

        userPath = os.path.join(app.config['ImgUploadPath'], session['username'])
        if not os.path.exists(userPath):
            os.mkdir(userPath)

        if f.filename != '':
            if allowed_file(f.filename):
                name = f.filename.rsplit('.', 1)[0].replace(".", "_")
                t = f.filename.rsplit('.', 1)[1]
                savePath, filename = get_savepath(userPath, name, t)

                f.save(savePath)
                # return redirect(url_for('detection', filename=filename))
            else:
                flash('The uploaded file type is not accepted!')
                return redirect(url_for('upload'))

        elif request.form['myurl'] != '':
            if allowed_file(request.form['myurl']):
                name = session['username'] + "_d"
                t = request.form['myurl'].rsplit('.', 1)[-1]
                savePath, filename = get_savepath(userPath, name, t)

                try:
                    urllib.request.urlretrieve(request.form['myurl'], savePath)

                    # return redirect(url_for('detection', filename=filename))
                except Exception as e:
                    print(e)
                    flash('There is something wrong when dowloading image.')
                    return redirect(url_for('upload'))
            else:
                flash('The uploaded file type is not accepted!')
                return redirect(url_for('upload'))

        username = session['username']
        userPath = os.path.join(app.config['ImgResultPath'], username)
        if not os.path.exists(userPath):
            os.mkdir(userPath)
        resultpath, result_name = get_savepath(userPath, filename.rsplit('.')[0], filename.rsplit('.')[1])
        output_info = mask_detection(filename, username, result_name)

        # upload to s3#
        filepath = get_s3_path(username + "/" + filename.rsplit('.', 1)[0], filename.rsplit('.', 1)[1])
        # resultpath = os.path.join(app.config['ImgResultPath'], username, result_name)
        s3.upload_file(resultpath, app.config['Bucket_name'], filepath, ExtraArgs={'ACL': 'public-read'})

        # delete image on local system
        # imgPath = os.path.join(app.config['ImgUploadPath'], username, )
        resPath = os.path.join(app.config['ImgResultPath'], username, result_name)
        if os.path.exists(savePath):
            # print(img_path)
            # import shutil
            # shutil.rmtree(imgPath)
            os.remove(savePath)
        if os.path.exists(resPath):
            # print(img_path)
            # import shutil
            # shutil.rmtree(resPath)
            os.remove(resPath)

        ##################
        # add image_path and label to SQL
        try:
            cursor = con.cursor(pymysql.cursors.DictCursor)
            query = ("SELECT id FROM users WHERE username = %s")
            cursor.execute(query, (username,))
            user_id = cursor.fetchone()["id"]
            add1 = ("INSERT INTO images "
                    "(id, user_id, image_path, image_type) "
                    "VALUES(NULL, %s, %s, %s)")
            # imagePath = '/static/upload/' + username + '/' + filename
            data1 = (user_id, filepath, output_info['picture_label'])
            cursor.execute(add1, data1)
            con.commit()
        except Exception as e:
            flash('database error2')
            return redirect(url_for('upload'))

        return redirect(url_for('detection', filename=filepath, face=output_info["face_num"], unmask=output_info["unmask_num"], mask=output_info["mask_num"]))
    return render_template('upload.html')


def mask_detection(filename, username, result_name):
    output_info = {"face_num": 0, "unmask_num": 0, "mask_num": 0}
    imgPath = os.path.join(app.config['ImgUploadPath'], username, filename)
    img = cv2.imread(imgPath)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    result_path = os.path.join(app.config['ImgResultPath'], username, result_name)

    info = inference(img, show_result=False, result_path=result_path, target_shape=(360, 360))
    for list in info:
        if list[0] == 0:
            output_info["face_num"] += 1
            output_info["mask_num"] += 1
        elif list[0] == 1:
            output_info["face_num"] += 1
            output_info["unmask_num"] += 1

    # Label 1: No Faces,  Label 2: All face mask,  Label 3: All face unmask,  Label 4: Some face mask
    if output_info["face_num"] == 0:
        output_info['picture_label'] = "noface"
    elif output_info["unmask_num"] == 0:
        output_info['picture_label'] = "allmasks"
    elif output_info["mask_num"] == 0:
        output_info['picture_label'] = "nomask"
    else:
        output_info['picture_label'] = "somemask"
    return output_info


def get_s3_path(name, t):
    bucket = s3_r.Bucket(app.config['Bucket_name'])
    filename = name + "." + t
    flag = 1
    i = 1
    while flag != 0:
        for key in bucket.objects.all():
            if filename == key.key:
                flag = 1
                name1 = name + "_" + str(i)
                i = i + 1
                filename = name1 + "." + t
                break
            else:
                flag = 0
    return filename


@app.route('/detection')
def detection():
    request_count()
    if "username" not in session:
        flash('Please login.')
        return redirect(url_for('login'))
    filepath = request.args.get('filename')
    face = request.args.get('face')
    mask = request.args.get('mask')
    unmask = request.args.get('unmask')
    if filepath == None:
        flash('Please upload an image first.')
        return redirect(url_for('upload'))
    print(filepath)
    print(app.config['S3_URL'] + filepath)
    output_info = {"face_num": face, "unmask_num": mask, "mask_num": unmask}
    return render_template('detection.html', result_path=app.config['S3_URL'] + filepath, output_info=output_info)


@app.route('/history')
def history():
    request_count()
    if "username" not in session:
        flash('Please login.')
        return redirect(url_for('login'))
    nomasks = []
    allmasks = []
    somemasks = []
    noface = []
    try:
        cursor = con.cursor(pymysql.cursors.DictCursor)
        query = ("SELECT * FROM users WHERE username = %s")
        cursor.execute(query, (session['username'],))
        account = cursor.fetchone()
        print(account)
        user_id = account['id']
        query = ("SELECT * FROM images WHERE user_id = %s")
        cursor.execute(query, (user_id,))
        history = cursor.fetchall()
        for image in history:
            print(image)
            if image["image_type"] == 'somemask':
                somemasks.append(app.config['S3_URL'] + image["image_path"])
            elif image["image_type"] == "allmasks":
                allmasks.append(app.config['S3_URL'] + image["image_path"])
            elif image["image_type"] == "noface":
                noface.append(app.config['S3_URL'] + image["image_path"])
            elif image["image_type"] == "nomask":
                nomasks.append(app.config['S3_URL'] + image["image_path"])
    except Exception as e:
        payload = {"username": session['username'], "is_admin": session['is_admin'], }
        flash(str(e))
        flash('Database error')
        return redirect(url_for("user_home"))
    return render_template('history.html', nomasks=nomasks, noface=noface, somemasks=somemasks, allmasks=allmasks)


def generate_error_response(error_message, errorcode):
    response = jsonify(
        {
            "success": False,
            "error": {
                "code": errorcode,
                "message": error_message
            }
        }
    )
    # response.headers["Content-Type"] = "application/json"
    return response


def generate_success_responses(val):
    info = {'num_faces': val["face_num"], 'num_masked': val["mask_num"], 'num_unmasked': val["mask_num"]}
    response = jsonify(
        {"success": True, "payload": info}
    )
    # response.headers["Content-Type"] = "application/json"
    return response


@app.route('/api/upload', methods=['POST'])
def api_upload():
    request_count()
    print(request)
    if "username" not in request.form or "password" not in request.form:
        return generate_error_response('Please input username and password', 401)
    username = request.form['username']
    password = request.form['password']
    try:
        cursor = con.cursor(pymysql.cursors.DictCursor)
        query = ("SELECT * FROM users WHERE username = %s")
        cursor.execute(query, (username,))
        account = cursor.fetchone()
    except Exception as e:
        return generate_error_response("Database error1", 500)

    if account and check_password_hash(account['password'], password):
        user_id = account["id"]
    else:
        return generate_error_response('User not exist or wrong password', 403)

    file_obj = request.files
    if 'file' not in file_obj:
        return generate_error_response('Please upload a file', 102)
    flist = request.files.getlist('file')
    if len(flist) > 1:
        return generate_error_response('You can only upload one file', 106)
    f = request.files.getlist('file')[0]
    if f.filename == "":
        return generate_error_response('Please upload a file', 403)
    if not allowed_file(f.filename):
        return generate_error_response('File type is wrong', 406)
    userPath = os.path.join(app.config['ImgUploadPath'], username)
    if not os.path.exists(userPath):
        os.mkdir(userPath)
    name = f.filename.rsplit('.', 1)[0].replace(".", "_")
    t = f.filename.rsplit('.', 1)[1]
    savePath, filename = get_savepath(userPath, name, t)
    f.save(savePath)

    # filename = f.filename
    # result_name = filename.rsplit('.')[0] + '.' + filename.rsplit('.')[1]
    userPath = os.path.join(app.config['ImgResultPath'], username)
    if not os.path.exists(userPath):
        os.mkdir(userPath)
    resultpath, result_name = get_savepath(userPath, filename.rsplit('.')[0], filename.rsplit('.')[1])
    output_info = mask_detection(filename, username, result_name)

    # upload to s3#
    filepath = get_s3_path(username + "/" + filename.rsplit('.', 1)[0], filename.rsplit('.', 1)[1])
    # resultpath = os.path.join(app.config['ImgResultPath'], username, result_name)
    s3.upload_file(resultpath, app.config['Bucket_name'], filepath,
                   ExtraArgs={'ACL': 'public-read'})
    # delete image on local system
    # imgPath = os.path.join(app.config['ImgUploadPath'], username, )
    resPath = os.path.join(app.config['ImgResultPath'], username, result_name)
    if os.path.exists(savePath):
        # print(img_path)
        # import shutil
        # shutil.rmtree(imgPath)
        os.remove(savePath)
    if os.path.exists(resPath):
        # print(img_path)
        # import shutil
        # shutil.rmtree(resPath)
        os.remove(resPath)

    ##################
    # add image_path and label to SQL
    # try:
    #     add1 = ("INSERT INTO images "
    #             "(id, user_id, image_path, image_type) "
    #             "VALUES(NULL, %s, %s, %s)")
    #     # imagePath = '/static/upload/' + username + '/' + filename
    #     data1 = (user_id, filepath, output_info['picture_label'])
    #     cursor.execute(add1, data1)
    #     con.commit()
    # except Exception as e:
    #     return generate_error_response("Database error2", 500)
    ##################

    return generate_success_responses(output_info)


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
