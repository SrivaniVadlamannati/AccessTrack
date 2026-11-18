"""JSON API. Every route needs a logged in session (cookie)."""
from flask import Blueprint, abort, g, jsonify, request, send_file

from . import excel, services
from .auth import login_required
from .review import run_review

bp = Blueprint("api", __name__, url_prefix="/api")


def _cycle_id():
    cid = request.args.get("cycle", type=int) or (request.get_json(silent=True) or {}).get("cycle_id")
    if cid is None:
        return services.current_cycle()["id"]
    if not services.cycle(cid):
        abort(404, "unknown cycle")
    return int(cid)


@bp.errorhandler(404)
@bp.errorhandler(400)
def _err(e):
    return jsonify(error=getattr(e, "description", str(e))), e.code


@bp.get("/cycles")
@login_required
def get_cycles():
    return jsonify(services.cycles())


@bp.get("/requirements")
@login_required
def get_requirements():
    return jsonify(services.requirements())


@bp.get("/summary")
@login_required
def get_summary():
    return jsonify(services.summary(_cycle_id()))


@bp.get("/submissions")
@login_required
def get_submissions():
    a = request.args
    rows = services.list_submissions(_cycle_id(), a.get("status"), a.get("college"), a.get("q"), a.get("sort", "program"))
    return jsonify(count=len(rows), results=rows)


@bp.get("/submissions/<int:sid>")
@login_required
def get_submission(sid):
    s = services.submission(sid)
    if not s:
        abort(404, "submission not found")
    return jsonify(s)


@bp.patch("/submissions/<int:sid>/items/<int:rid>")
@login_required
def patch_item(sid, rid):
    body = request.get_json(force=True)
    if "present" not in body:
        abort(400, "body needs {'present': true|false}")
    try:
        res = services.set_item(sid, rid, bool(body["present"]), g.user["username"])
    except LookupError as e:
        abort(404, str(e))
    return jsonify(status=res.status, missing=res.missing)


@bp.put("/submissions/<int:sid>/notes")
@login_required
def put_notes(sid):
    services.save_notes(sid, (request.get_json(force=True).get("notes") or "")[:2000], g.user["username"])
    return jsonify(ok=True)


@bp.post("/reviews")
@login_required
def post_review():
    return jsonify(run_review(_cycle_id(), g.user["username"])), 201


@bp.get("/reviews")
@login_required
def get_reviews():
    return jsonify(services.review_runs(_cycle_id()))


@bp.get("/reminders")
@login_required
def get_reminders():
    r = services.reminders(_cycle_id())
    return jsonify(count=len(r), results=r)


@bp.get("/gaps")
@login_required
def get_gaps():
    return jsonify(services.gaps(_cycle_id()))


@bp.get("/activity")
@login_required
def get_activity():
    return jsonify(services.activity(request.args.get("limit", 100, type=int)))


@bp.post("/import")
@login_required
def post_import():
    f = request.files.get("file")
    if not f:
        abort(400, "attach a .csv or .xlsx as 'file'")
    if f.filename.lower().endswith(".xlsx"):
        text = excel.xlsx_to_csv(f.stream)
    else:
        text = f.read().decode("utf-8", errors="replace")
    try:
        result = services.import_csv(_cycle_id(), text, g.user["username"])
    except ValueError as e:
        abort(400, str(e))
    return jsonify(result)


@bp.get("/export/checklist.xlsx")
@login_required
def export_checklist():
    cid = _cycle_id()
    return send_file(excel.checklist_workbook(cid), as_attachment=True,
                     download_name=f"assessment-checklist-{services.cycle(cid)['label']}.xlsx")


@bp.get("/export/reminders.xlsx")
@login_required
def export_reminders():
    cid = _cycle_id()
    return send_file(excel.reminders_workbook(cid), as_attachment=True,
                     download_name=f"reminders-{services.cycle(cid)['label']}.xlsx")
