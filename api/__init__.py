"""Blueprint registry for the uniBot API."""
from .auth import bp as auth_bp
from .schools import bp as schools_bp
from .years import bp as years_bp
from .terms import bp as terms_bp
from .subjects import bp as subjects_bp
from .offerings import bp as offerings_bp
from .class_meetings import bp as meetings_bp
from .enrollments import bp as enrollments_bp
from .timetable import bp as timetable_bp
from .assignments import bp as assignments_bp
from .submissions import bp as submissions_bp
from .grades import bp as grades_bp
from .my_day import bp as myday_bp
from .rooms import bp as rooms_bp
from .gradebook import bp as gradebook_bp
from .attendance import bp as attendance_bp
from .calender import bp as calendar_bp
from .documents import bp as documents_bp
from .departments import bp as departments_bp
from .identity import bp as identity_bp
from .finance import bp as finance_bp
from .resources import bp as resources_bp
from .peers import bp as peers_bp
from .ta import bp as ta_bp
from .leaderboards import bp as leaderboards_bp
from .graduation import bp as graduation_bp
from .study_plans import bp as study_plans_bp
from .research import bp as research_bp
from .discipline import bp as discipline_bp
from .alumni import bp as alumni_bp
from .plugins import bp as plugins_bp
from .analytics import bp as analytics_bp
from .appointments import bp as appointments_bp
from .notifications import bp as notifications_bp
from .cafeteria import bp as cafeteria_bp
from .events import bp as events_bp
from .tickets import bp as tickets_bp
from .consent import bp as consent_bp
from .opportunities import bp as opportunities_bp
from .risks import bp as risks_bp
from .policies import bp as policies_bp
from .library import bp as library_bp
from .ai import bp as ai_bp


def register_blueprints(app):
    """Attach all feature blueprints to the Flask app."""

    # auth first so other modules can rely on /api/auth
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    # academic structure
    app.register_blueprint(schools_bp, url_prefix="/api/schools")
    app.register_blueprint(years_bp, url_prefix="/api/years")
    app.register_blueprint(terms_bp, url_prefix="/api/terms")
    app.register_blueprint(subjects_bp, url_prefix="/api/subjects")
    app.register_blueprint(offerings_bp, url_prefix="/api/offerings")
    app.register_blueprint(meetings_bp)
    app.register_blueprint(enrollments_bp, url_prefix="/api/enrollments")
    app.register_blueprint(timetable_bp, url_prefix="/api/timetable")

    # learning + coursework
    app.register_blueprint(assignments_bp)
    app.register_blueprint(submissions_bp)
    app.register_blueprint(grades_bp)
    app.register_blueprint(myday_bp)
    app.register_blueprint(rooms_bp)
    app.register_blueprint(gradebook_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(calendar_bp)

    # expanded platform modules
    app.register_blueprint(documents_bp)
    app.register_blueprint(departments_bp)
    app.register_blueprint(identity_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(resources_bp)
    app.register_blueprint(peers_bp)
    app.register_blueprint(ta_bp)
    app.register_blueprint(leaderboards_bp)
    app.register_blueprint(graduation_bp)
    app.register_blueprint(study_plans_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(discipline_bp)
    app.register_blueprint(alumni_bp)
    app.register_blueprint(plugins_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(cafeteria_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(consent_bp)
    app.register_blueprint(opportunities_bp)
    app.register_blueprint(risks_bp)
    app.register_blueprint(policies_bp)
    app.register_blueprint(library_bp)
    app.register_blueprint(ai_bp)

