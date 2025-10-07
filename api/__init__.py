# api/__init__.py
from .schools import bp as schools_bp
from .subjects import bp as subjects_bp
from .terms import bp as terms_bp
from .offerings import bp as offerings_bp
from .class_meetings import bp as meetings_bp
from .auth import bp as auth_bp
from .timetable import bp as timetable_bp  # <-- add this
from .assignments import bp as assignments_bp
from .submissions import bp as submissions_bp
from .grades import bp as grades_bp
from .my_day import bp as myday_bp   # <-- add this
from .rooms import bp as rooms_bp
from .gradebook import bp as gradebook_bp
from .attendance import bp as attendance_bp
from .calendar import bp as calendar_bp
from .submissions import bp as submissions_bp
from .timetable import bp as timetable_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(schools_bp)
    app.register_blueprint(subjects_bp)
    app.register_blueprint(terms_bp)
    app.register_blueprint(offerings_bp)
    app.register_blueprint(meetings_bp)
    app.register_blueprint(timetable_bp, url_prefix="/api/timetable")
    app.register_blueprint(assignments_bp)
    app.register_blueprint(submissions_bp)
    app.register_blueprint(grades_bp)
    app.register_blueprint(assignments_bp)
    app.register_blueprint(submissions_bp)
    app.register_blueprint(grades_bp)
    app.register_blueprint(myday_bp) 
    app.register_blueprint(rooms_bp)
    app.register_blueprint(gradebook_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(submissions_bp)  # <-- add this

