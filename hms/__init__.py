
"""Application factory for the Hostel Management System."""

import os
from datetime import date, datetime
from pathlib import Path

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from .config import Config
from .extensions import csrf, db, login_manager
from .utils import money, short_date, time_ago

BASE_DIR = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Temporary initial administrator bootstrap for Render deployment
# --------------------------------------------------------------------------- #
def _bootstrap_admin_from_env(app):
    """
    Create or update the initial administrator using temporary environment
    variables configured in Render.

    Remove all BOOTSTRAP_ADMIN_* variables from Render after successful
    creation. Otherwise, the password will be reset on every app startup.
    """

    name = os.environ.get("BOOTSTRAP_ADMIN_NAME", "").strip()
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")

    # Do nothing when bootstrap variables are not configured.
    if not any((name, email, password)):
        return

    # Prevent incomplete configuration.
    if not all((name, email, password)):
        raise RuntimeError(
            "Admin bootstrap failed: configure all three variables: "
            "BOOTSTRAP_ADMIN_NAME, BOOTSTRAP_ADMIN_EMAIL, "
            "BOOTSTRAP_ADMIN_PASSWORD."
        )

    from .models import Setting, User
    from .utils import password_problem

    problem = password_problem(password)

    if problem:
        raise RuntimeError(
            f"Admin bootstrap failed: {problem}"
        )

    # Find an existing account by email.
    user = User.query.filter(
        db.func.lower(User.email) == email
    ).first()

    if user:
        # Promote the existing account to administrator.
        user.name = name
        user.role = "admin"
        user.set_password(password)

        app.logger.info(
            "Existing account updated to administrator."
        )

    else:
        # Create a new administrator.
        user = User(
            name=name,
            email=email,
            role="admin",
        )

        user.set_password(password)
        db.session.add(user)

        app.logger.info(
            "Initial administrator account created."
        )

    # Insert default hostel settings if they do not exist.
    for key, value in Setting.DEFAULT.items():
        if db.session.get(Setting, key) is None:
            db.session.add(
                Setting(
                    key=key,
                    value=value,
                )
            )

    db.session.commit()

    app.logger.info(
        "Administrator bootstrap completed successfully."
    )


# --------------------------------------------------------------------------- #
# Application factory
# --------------------------------------------------------------------------- #
def create_app(config_class=Config):

    app = Flask(__name__)

    app.config.from_object(config_class)

    app.config["UPLOAD_FOLDER"] = Path(
        app.config["UPLOAD_FOLDER"]
    )

    config_class.init_app(app)

    # Ensure the SQLite database directory exists when SQLite is used.
    database_uri = app.config["SQLALCHEMY_DATABASE_URI"]

    if database_uri.startswith("sqlite:///"):
        sqlite_path = database_uri.replace(
            "sqlite:///",
            "",
            1,
        )

        Path(sqlite_path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    # Initialize Flask extensions.
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Import blueprints.
    from .blueprints.auth import auth_bp
    from .blueprints.public import public_bp
    from .blueprints.student import student_bp
    from .blueprints.admin import admin_bp

    # Register blueprints.
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Register application functionality.
    _register_filters(app)
    _register_context(app)
    _register_errors(app)
    _register_cli(app)

    # Initialize database and optional administrator bootstrap.
    with app.app_context():

        from . import models  # noqa: F401

        # Create missing database tables.
        db.create_all()

        # Create/update initial administrator when configured.
        _bootstrap_admin_from_env(app)

    return app


# --------------------------------------------------------------------------- #
# Jinja template filters
# --------------------------------------------------------------------------- #
def _register_filters(app):

    app.jinja_env.filters["money"] = money
    app.jinja_env.filters["date"] = short_date
    app.jinja_env.filters["ago"] = time_ago

    app.jinja_env.filters["dt"] = (
        lambda value:
        value.strftime("%d %b %Y, %I:%M %p")
        if value else "—"
    )

    @app.template_filter("nl2br")
    def nl2br(value):

        from markupsafe import Markup, escape

        return Markup(
            "<br>".join(
                escape(value or "").split("\n")
            )
        )


# --------------------------------------------------------------------------- #
# Global template context
# --------------------------------------------------------------------------- #
def _register_context(app):

    @app.context_processor
    def inject_globals():

        from .models import (
            Announcement,
            Complaint,
            ContactMessage,
            Notification,
            Setting,
        )

        from .extensions import db as _db

        hostel_name = Setting.get(
            "hostel_name",
            app.config["HOSTEL_NAME"],
        )

        ctx = {
            "hostel_name": hostel_name,
            "hostel_tagline": Setting.get("hostel_tagline", ""),
            "hostel_email": Setting.get("contact_email", ""),
            "hostel_phone": Setting.get("contact_phone", ""),
            "hostel_address": Setting.get("address", ""),
            "academic_session": Setting.get("academic_session", ""),
            "now": datetime.utcnow(),
            "today": date.today(),
        }

        if current_user.is_authenticated:

            unread = (
                _db.session.query(Notification)
                .filter_by(
                    user_id=current_user.id,
                    is_read=False,
                )
                .order_by(Notification.created_at.desc())
                .limit(12)
                .all()
            )

            ctx["nav_notifications"] = unread

            ctx["nav_notification_count"] = (
                _db.session.query(Notification)
                .filter_by(
                    user_id=current_user.id,
                    is_read=False,
                )
                .count()
            )

            if current_user.role == "admin":

                ctx["nav_pending_complaints"] = (
                    _db.session.query(Complaint)
                    .filter(
                        Complaint.status.in_(
                            ["Pending", "In Progress"]
                        )
                    )
                    .count()
                )

                ctx["nav_unread_messages"] = (
                    _db.session.query(ContactMessage)
                    .filter_by(is_read=False)
                    .count()
                )

                from .models import Student

                ctx["nav_pending_fees"] = (
                    _db.session.query(Student)
                    .filter(Student.status == "Active")
                    .count()
                )

            if (
                current_user.role == "student"
                and current_user.student
            ):

                ctx["nav_my_complaints"] = (
                    current_user.student.complaints.count()
                )

            latest = (
                _db.session.query(Announcement)
                .filter_by(is_published=True)
                .order_by(
                    Announcement.is_pinned.desc(),
                    Announcement.created_at.desc(),
                )
                .first()
            )

            ctx["nav_latest_announcement"] = latest

        return ctx


# --------------------------------------------------------------------------- #
# Error handlers
# --------------------------------------------------------------------------- #
def _register_errors(app):

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(_e):

        flash(
            "That file is larger than the 4 MB upload limit.",
            "danger",
        )

        return redirect(
            request.referrer or url_for("public.home")
        )

    @app.errorhandler(500)
    def server_error(_e):

        db.session.rollback()

        return render_template("errors/500.html"), 500


# --------------------------------------------------------------------------- #
# Flask CLI commands
# --------------------------------------------------------------------------- #
def _register_cli(app):

    import click

    @app.cli.command("init-db")
    def init_db():

        """Create all database tables."""

        db.create_all()

        click.echo(
            "Database tables created."
        )

    @app.cli.command("create-admin")
    @click.option(
        "--name",
        prompt="Admin full name",
    )
    @click.option(
        "--email",
        prompt="Admin email",
    )
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
    )
    def create_admin(name, email, password):

        """Create or update an administrator account."""

        from .models import Setting, User
        from .utils import password_problem

        name = name.strip()
        email = email.strip().lower()

        problem = password_problem(password)

        if problem:
            raise click.ClickException(problem)

        user = User.query.filter(
            db.func.lower(User.email) == email
        ).first()

        if user:

            user.name = name
            user.role = "admin"
            user.set_password(password)

            click.echo(
                f"Updated existing account {email} to an admin."
            )

        else:

            user = User(
                name=name,
                email=email,
                role="admin",
            )

            user.set_password(password)

            db.session.add(user)

            click.echo(
                f"Created administrator {email}."
            )

        for key, value in Setting.DEFAULT.items():

            if db.session.get(Setting, key) is None:

                db.session.add(
                    Setting(
                        key=key,
                        value=value,
                    )
                )

        db.session.commit()

        click.echo(
            "Administrator setup completed successfully."
        )

    @app.cli.command("seed-demo")
    @click.option(
        "--yes",
        is_flag=True,
        help="Skip the confirmation prompt.",
    )
    def seed_demo_cmd(yes):

        """Load clearly labelled demo data."""

        if not yes:

            click.confirm(
                "This adds DEMO data to the database. Continue?",
                abort=True,
            )

        from seed_demo import seed

        with app.app_context():
            seed()
