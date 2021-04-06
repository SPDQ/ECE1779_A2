import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ece1779_a2-secretkey'
    BUCKET_NAME = 'ece1779-images'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'mysql+pymysql://admin:ece1779pass@database-3.cxfhc4txk40y.us-east-1.rds.amazonaws.com:3306/assignment1_ece1779'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ZONE = 'Canada/Eastern'
