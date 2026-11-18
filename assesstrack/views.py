"""Server rendered pages. Interactive bits (ticking items, running a review) call the JSON API."""
from flask import Blueprint, Response, abort, render_template, request, session

from . import services
from .auth import login_required
from .review import LABELS

bp = Blueprint("views", __name__)


def _cycle():
    cid = request.args.get("cycle", type=int) or session.get("cycle_id")
    c = services.cycle(cid) if cid else None
    c = c or services.current_cycle()
    session["cycle_id"] = c["id"]
    return c


@bp.app_context_processor
def inject():
    return {"all_cycles": services.cycles() if request.endpoint and request.endpoint != "auth.login" else [], "LABELS": LABELS}


@bp.route("/")
@login_required
def dashboard():
    c = _cycle()
    return render_template("dashboard.html", cycle=c, s=services.summary(c["id"]), gaps=services.gaps(c["id"]),
                           runs=services.review_runs(c["id"])[:5], activity=services.activity(8))


@bp.route("/submissions")
@login_required
def submissions():
    c = _cycle()
    a = request.args
    rows = services.list_submissions(c["id"], a.get("status") or None, a.get("college") or None, a.get("q") or None, a.get("sort", "program"))
    return render_template("submissions.html", cycle=c, rows=rows, colleges=services.colleges(), args=a)


@bp.route("/submissions/<int:sid>")
@login_required
def submission(sid):
    s = services.submission(sid)
    if not s:
        abort(404)
    return render_template("submission.html", s=s, cycle=services.cycle(s["cycle_id"]))


@bp.route("/reminders")
@login_required
def reminders():
    c = _cycle()
    return render_template("reminders.html", cycle=c, groups=services.reminders(c["id"]), s=services.summary(c["id"]))


@bp.route("/gaps")
@login_required
def gaps():
    c = _cycle()
    return render_template("gaps.html", cycle=c, gaps=services.gaps(c["id"]))


@bp.route("/import")
@login_required
def import_page():
    return render_template("import.html", cycle=_cycle(), reqs=services.requirements())


@bp.route("/import/template.csv")
@login_required
def import_template():
    return Response(services.import_template(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=assesstrack-import-template.csv"})


@bp.route("/activity")
@login_required
def activity():
    c = _cycle()
    return render_template("activity.html", cycle=c, rows=services.activity(300), runs=services.review_runs(c["id"]))
