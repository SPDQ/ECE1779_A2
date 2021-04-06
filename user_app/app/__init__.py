from flask import Flask
import os
import requests
from flask_mail import Mail

app = Flask(__name__)
base_dir = os.path.dirname(os.path.abspath(__file__))
# print(base_dir)

app.config['AllowedImageType'] = ["JPEG", "JPG", "PNG", "jpeg", "jpg", "png"]
app.config['ImgUploadPath'] = os.path.join(base_dir, 'static', 'upload')
app.config['ImgResultPath'] = os.path.join(base_dir, 'static', 'result')
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "secret string")
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['MAIL_SERVER'] = 'smtp.qq.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = '307736651@qq.com'
app.config['MAIL_PASSWORD'] = 'urfcqgbldinsbiej'

# Change the following config to make app able to run on your computer #
app.config['Database_host'] = 'database-1.cxfhc4txk40y.us-east-1.rds.amazonaws.com'
app.config['Database_port'] = 3306
app.config['Database_user'] = 'admin'
app.config['Database_password'] = 'ece1779pass'
app.config['Database_db'] = 'assignment1_ece1779'
app.config['Bucket_name'] = 'david-ece1779-test'
app.config['S3_URL'] = 'https://david-ece1779-test.s3.amazonaws.com/'
app.config['IAM_role'] = "ec2_s3_role"
##################################################################

access_key = requests.get("http://169.254.169.254/latest/meta-data/iam/security-credentials/"+app.config['IAM_role'])
keys = access_key.json()
app.config['AWS_AccessKeyId'] = keys["AccessKeyId"]
app.config['AWS_SecretAccessKey'] = keys["SecretAccessKey"]
app.config['AWS_Token'] = keys["Token"]
app.config['instance_id'] = os.popen('ec2metadata --instance-id').read().strip()


from app import image
from app import home
from app import users

