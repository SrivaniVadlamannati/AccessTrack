"""Excel exports built with openpyxl: the per-program checklist and the reminder list."""
import io

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import services

HEAD = PatternFill("solid", fgColor="2A2521")
HEAD_FONT = Font(bold=True, color="F2EBDC")
OK = PatternFill("solid", fgColor="DDE5D3")
BAD = PatternFill("solid", fgColor="F1D3CE")


def _header(ws, cols):
    ws.append(cols)
    for c in ws[1]:
        c.fill, c.font = HEAD, HEAD_FONT
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 32


def _widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def checklist_workbook(cycle_id):
    c = services.cycle(cycle_id)
    reqs = services.requirements()
    subs = services.list_submissions(cycle_id, sort="college")
    wb = Workbook()

    # Summary
    ws = wb.active
    ws.title = "Summary"
    s = services.summary(cycle_id)
    ws.append([f"Assessment report review · {c['label']} cycle (due {c['due_date']})"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([])
    for label, key in [("Programs", "total"), ("Reports received", "received"), ("Complete and on time", "complete"),
                       ("Late but complete", "late"), ("Missing items", "missing"), ("Not submitted", "not_submitted"),
                       ("Open items to chase", "open_items")]:
        ws.append([label, s[key]])
    ws.append(["On time and complete", s["on_time_complete_pct"] / 100])
    ws.cell(ws.max_row, 2).number_format = "0%"
    _widths(ws, [28, 14])

    ws.append([])
    ws.append(["Requirement", "Missing in received reports"])
    start = ws.max_row
    for g in services.gaps(cycle_id)["by_requirement"]:
        ws.append([g["name"], g["missing"]])
    chart = BarChart()
    chart.type = "bar"
    chart.title = "Most often missing"
    chart.y_axis.title = "reports"
    chart.add_data(Reference(ws, min_col=2, min_row=start, max_row=ws.max_row), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=start + 1, max_row=ws.max_row))
    chart.height, chart.width, chart.legend = 8, 16, None
    ws.add_chart(chart, "D3")

    # Checklist grid
    ws = wb.create_sheet("Checklist")
    cols = ["Program code", "Program", "College", "Coordinator", "Email", "Submitted", "Status", "Open items"] + [r["name"] for r in reqs]
    _header(ws, cols)
    for sub in subs:
        missing = set(sub["missing"])
        row = [sub["code"], sub["program"], sub["college"], sub["coordinator"], sub["email"],
               (sub["submitted_at"] or "")[:10], sub["status_label"], sub["open_items"] or 0]
        row += ["—" if not sub["submitted_at"] else ("MISSING" if r["name"] in missing else "✓") for r in reqs]
        ws.append(row)
    last = get_column_letter(len(cols))
    rng = f"I2:{last}{ws.max_row}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"MISSING"'], fill=BAD))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"✓"'], fill=OK))
    ws.auto_filter.ref = f"A1:{last}{ws.max_row}"
    _widths(ws, [13, 34, 26, 20, 24, 12, 14, 10] + [13] * len(reqs))

    # One row per missing item: easiest to work through and tick off
    ws = wb.create_sheet("Open items")
    _header(ws, ["Program", "Coordinator", "Email", "Missing item", "Kind", "Received (Y/N)"])
    kinds = {r["name"]: r["kind"] for r in reqs}
    for sub in subs:
        for m in sub["missing"]:
            ws.append([sub["program"], sub["coordinator"], sub["email"], m, kinds[m], ""])
    _widths(ws, [34, 20, 24, 20, 10, 14])
    return _save(wb)


def reminders_workbook(cycle_id):
    wb = Workbook()
    ws = wb.active
    ws.title = "Reminders"
    _header(ws, ["Coordinator", "Email", "Programs", "Open items", "Subject", "Message"])
    for g in services.reminders(cycle_id):
        ws.append([g["coordinator"], g["email"], ", ".join(p["program"] for p in g["programs"]),
                   sum(len(p["missing"]) for p in g["programs"]), g["subject"], g["body"]])
        ws.cell(ws.max_row, 6).alignment = Alignment(wrap_text=True, vertical="top")
    _widths(ws, [20, 24, 40, 10, 40, 90])
    return _save(wb)


def xlsx_to_csv(stream):
    """Let staff upload the import file as .xlsx; we turn the first sheet into CSV text."""
    import csv
    wb = load_workbook(stream, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    out = io.StringIO()
    w = csv.writer(out)
    for row in ws.iter_rows(values_only=True):
        w.writerow(["" if v is None else (v.date().isoformat() if hasattr(v, "date") and not isinstance(v, str) else v) for v in row])
    return out.getvalue()


def _save(wb):
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
