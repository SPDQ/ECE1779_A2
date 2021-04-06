from flask import render_template, url_for, session, redirect, request
from flaskr import app
from flaskr.aws import aws
# from flaskr.models import RequestPerMinute
from datetime import datetime, timedelta
from flaskr.models import AutoScalingConfig, users, images
from flaskr import db
from pytz import timezone
import collections
import traceback
import json
import time

awscli = aws.AwsClient()

@app.route('/')
@app.route('/home')
def home():
    try:
        return render_template('home.html')
    except Exception as e:
        traceback.print_tb(e.__traceback__)
        return render_template('error.html', msg='something goes wrong~')

@app.route('/fetch_workers')
def fetch_workers():
    target_instances = awscli.get_target_instances()
    ret = {'data': target_instances}
    return json.dumps(ret)


@app.route('/fetch_cpu_utils', methods=['GET', 'POST'])
def fetch_cpu_utils():
    start_time, end_time = get_time_span(1800)
    instances = json.loads(request.data.decode('utf-8'))
    series = []
    for instance in instances:
        series.append({
            "name": instance,
            "data": awscli.get_cpu_utils(instance, start_time, end_time)
        })
    return json.dumps(series)


@app.route('/fetch_requests_rate', methods=['GET', 'POST'])
def fetch_reqeusts_rate():
    start_time, end_time = get_time_span(1800)
    instances = json.loads(request.data.decode('utf-8'))
    series = []
    for instance in instances:
        series.append({
            "name": instance,
            "data": awscli.fetch_request_rate_worker(instance, start_time, end_time)
        })
    return json.dumps(series)


@app.route('/fetch_healthy_workers', methods=['GET', 'POST'])
def fetch_healthy_workers():
    start_time, end_time = get_time_span(1800)
    series = {"data": awscli.get_healthy_count(start_time, end_time)}

    return json.dumps(series)


@app.route('/grow_one_worker', methods=['GET', 'POST'])
def grow_one_worker():
    response = awscli.grow_worker_by_one()

    if int(response) == 200:
        msg = "A new worker was registered"
        flag = True
    else:
        msg = "Unable to register a new worker"
        flag = False

    return json.dumps({
        'flag': flag,
        'msg': msg
    })


@app.route('/shrink_one_worker', methods=['GET', 'POST'])
def shrink_one_worker():
    flag, msg = awscli.shrink_worker_by_one()

    if flag:
        msg = "A worker was unregistered"

    return json.dumps({
        'flag': flag,
        'msg': msg
    })


@app.route('/stop_manager_app',methods=['GET', 'POST'])
def stop_manager_app():
    awscli.stop_all_instances()


@app.route('/clear_data', methods=['GET', 'POST'])
def clear_data():
    # return json.dumps({
    #     'flag': True,
    #     'msg': "Success"
    # })

    try:
        awscli = aws.AwsClient()
        awscli.clear_s3()
        # print('s3 cleared')
        AutoScalingConfig.query.delete()
        db.session.commit()
        # print('auto scale cleared')
        # RequestPerMinute.query.delete()
        # db.session.commit()
        users.query.filter(users.id != 1).delete()
        db.session.commit()
        # print('users cleared')
        images.query.delete()
        db.session.commit()
        print('all cleared')
        return json.dumps({
            'flag': True,
            'msg': "Success"
        })
    except Exception as e:
        print(e)
        traceback.print_tb(e.__traceback__)
        return json.dumps({
            'flag': False,
            'msg': 'Fail to clear the data'
        })

# def get_requests_per_minute(instance, start_time, end_time):
#     datetimes = RequestPerMinute.query.filter(RequestPerMinute.instance_id == instance) \
#         .filter(RequestPerMinute.timestamp <= end_time) \
#         .filter(RequestPerMinute.timestamp >= start_time) \
#         .with_entities(RequestPerMinute.timestamp).all()
#
#     timestamps = list(map(lambda x: int(round(datetime.timestamp(x[0]))), datetimes))
#
#     ret = []
#     dict = collections.Counter(timestamps)
#
#     start_timestamp = int(round(datetime.timestamp(start_time)))
#     end_timestamp = int(round(datetime.timestamp(end_time)))
#
#     for i in range(start_timestamp, end_timestamp, 60):
#         count = 0
#         for j in range(i, i + 60):
#             count += dict[j]
#
#         ret.append([i*1000, count])
#     # print(ret)
#     return json.dumps(ret)

# get start_time and end_time of latest [latest] seconds
def get_time_span(latest):
    end_time = datetime.now(timezone(app.config['ZONE']))
    start_time = end_time - timedelta(seconds=latest)
    return start_time, end_time

