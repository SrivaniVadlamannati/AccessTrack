import os
from datetime import datetime
from pathlib import Path

import click
from flask import Flask

ROOT = Path(__file__).resolve().parent.parent


def create_app(test_config=None):
    app = Flask(__name__, instance_path=str(ROOT / "instance"))
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
        DATABASE=str(ROOT / "instance" / "assesstrack.db"),
        DATA_DIR=str(ROOT / "data"),
        EXPORT_DIR=str(ROOT / "exports"),
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    from . import api, auth, db, views
    app.teardown_appcontext(db.close_db)
    app.register_blueprint(auth.bp)
    app.register_blueprint(views.bp)
    app.register_blueprint(api.bp)

    @app.template_filter("day")
    def day(v):
        return datetime.fromisoformat(v).strftime("%b %d, %Y") if v else "—"

    @app.template_filter("stamp")
    def stamp(v):
        return datetime.fromisoformat(v).strftime("%b %d %I:%M %p") if v else "—"

    # first run: build and seed the database automatically
    if not os.path.exists(app.config["DATABASE"]):
        with app.app_context():
            db.init_db()

    register_cli(app)
    return app


def register_cli(app):
    from . import db, excel, services
    from .review import run_review

    @app.cli.command("init-db")
    @click.option("--empty", is_flag=True, help="create tables without sample data")
    def init_db_cmd(empty):
        """Drop and rebuild the database from data/*.csv."""
        db.close_db()
        if os.path.exists(app.config["DATABASE"]):
            os.remove(app.config["DATABASE"])
        db.init_db(seed=not empty)
        click.echo("database rebuilt")

    @app.cli.command("review")
    @click.option("--cycle", "label", help="cycle label, e.g. 2025-26 (default: current)")
    @click.option("--export/--no-export", default=True, help="write checklist and reminder workbooks to exports/")
    def review_cmd(label, export):
        """Run the review for a cycle, the same as the Run review button."""
        c = services.current_cycle() if not label else next((c for c in services.cycles() if c["label"] == label), None)
        if not c:
            raise click.BadParameter(f"no cycle {label!r}")
        r = run_review(c["id"], "cli")
        click.echo(f"{c['label']}: {r['total']} reviewed in {r['duration_ms']} ms | complete {r['complete']} | late {r['late']} | "
                   f"missing {r['missing']} | not submitted {r['not_submitted']} | open items {r['open_items']}")
        if export:
            os.makedirs(app.config["EXPORT_DIR"], exist_ok=True)
            for name, fn in (("checklist", excel.checklist_workbook), ("reminders", excel.reminders_workbook)):
                path = Path(app.config["EXPORT_DIR"]) / f"{name}-{c['label']}.xlsx"
                path.write_bytes(fn(c["id"]).getvalue())
                click.echo(f"wrote {path.relative_to(ROOT)}")
