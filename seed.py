from datetime import date
from lms_models import create_app, db, School, AcademicYear, Term, Subject, CourseOffering, User, Role, user_roles

app = create_app()
with app.app_context():
    db.create_all()

    # School
    school = School(name="Demo High School", country="KW", timezone="Asia/Kuwait")
    db.session.add(school); db.session.flush()
    print("school_id:", school.id)

    # Admin user
    admin = User(school_id=school.id, email="admin@demo.school", full_name="Admin User", is_active=True)
    admin.set_password("Admin123!")
    db.session.add(admin); db.session.flush()
    db.session.execute(user_roles.insert().values(user_id=admin.id, role=Role.ADMIN))
    print("admin_id:", admin.id)

    # Year + Term
    year = AcademicYear(school_id=school.id, name="2025-2026",
                        start_date=date(2025, 9, 1), end_date=date(2026, 6, 30))
    db.session.add(year); db.session.flush()

    term = Term(academic_year_id=year.id, name="Fall",
                start_date=date(2025, 9, 1), end_date=date(2025, 12, 20))
    db.session.add(term); db.session.flush()
    print("term_id:", term.id)

    # Subject + Offering
    subj = Subject(school_id=school.id, code="MATH101", name="Math 1")
    db.session.add(subj); db.session.flush()

    off = CourseOffering(subject_id=subj.id, term_id=term.id, section="A", capacity=30)
    db.session.add(off); db.session.flush()

    db.session.commit()
    print("Seed complete.")
