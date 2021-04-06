from flaskr import db

class AutoScalingConfig(db.Model):
    __tablename__ = 'autoscalingconfig'
    ascid = db.Column(db.Integer, primary_key=True)
    cpu_grow = db.Column(db.Float)
    cpu_shrink = db.Column(db.Float)
    ratio_expand = db.Column(db.Float)
    ratio_shrink = db.Column(db.Float)
    timestamp = db.Column(db.DateTime) # A type for datetime.datetime() objects.
    def __repr__(self): # how to print User
        return '<AutoScalingConfig {}>'.format(self.ascid)

# class RequestPerMinute(db.Model):
#     __tablename__ = 'requestperminute'
#     requestid = db.Column(db.Integer, primary_key=True)
#     instance_id = db.Column(db.String(50))
#     timestamp = db.Column(db.DateTime)  # A type for datetime.datetime() objects.
#
#     def __repr__(self):
#         return '<RequestPerMinute {}>'.format(self.instance_id)

class users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), index=True, unique=True, nullable = False)
    password = db.Column(db.String(255), nullable = False)
    email = db.Column(db.String(100))
    admin = db.Column(db.Boolean)

    def __repr__(self): # how to print User
        return '<User {}>'.format(self.username)

    def serialize(self):
        return {
            'userid': self.id,
            'username': self.username,
        }

class images(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    image_path = db.Column(db.String(255))
    image_type = db.Column(db.String(255))


    def __repr__(self):
        return '<Post {}>'.format(self.image_path)

    def serialize(self):
        return {
            'id': self.id,
            'path': self.image_path,
        }