"""
Builds the sample dataset in data/ that the app seeds from.

Everything here is synthetic: program names follow a typical large public
university catalog, people are made up, and the presence/absence of each
document is drawn from fixed probabilities so the review engine has
something realistic to find. The seed is fixed, so re-running this gives
the same files every time.

    python scripts/generate_data.py
"""
import csv
import random
from datetime import date, datetime, timedelta, time
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)
rng = random.Random(2026)

REQUIREMENTS = [
    ("document", "Assessment Plan", "Current plan listing outcomes, measures and targets"),
    ("document", "Curriculum Map", "Courses mapped to each learning outcome (I/R/M)"),
    ("document", "Data Summary", "Aggregated results for every outcome assessed this cycle"),
    ("document", "Action Plan", "Changes the program will make based on results"),
    ("section", "Mission", "Program mission statement"),
    ("section", "Learning Outcomes", "Measurable student learning outcomes"),
    ("section", "Measures", "At least one direct measure per outcome"),
    ("section", "Targets", "Numeric performance target per measure"),
    ("section", "Findings", "Results compared against targets"),
    ("section", "Use of Results", "How findings were discussed and used"),
]

COLLEGES = {
    "Arts & Sciences": ["Biology BS", "Chemistry BS", "English BA", "History BA", "Mathematics BS",
                        "Physics BS", "Psychology BA", "Sociology BA", "Philosophy BA",
                        "Political Science BA", "Geosciences BS", "Anthropology BA", "Biology MS",
                        "English MA", "History MA", "Psychology PhD", "Chemistry MS",
                        "Mathematics MS", "Sociology MA", "Geography MS", "Religious Studies BA",
                        "World Languages BA", "Neuroscience BS", "Environmental Science BS",
                        "Linguistics BA", "Statistics BS", "Statistics MS", "Philosophy MA"],
    "Business": ["Accounting BBA", "Finance BBA", "Marketing BBA", "Management BBA",
                 "Computer Information Systems BBA", "Risk Management BBA", "Real Estate BBA",
                 "Hospitality BBA", "MBA", "Accountancy MPA", "Analytics MS", "Finance MS",
                 "Marketing MS", "Information Systems PhD", "Business Administration PhD",
                 "Actuarial Science BBA", "Economics BBA", "Global Business MIB",
                 "Supply Chain BBA", "Human Resources MS"],
    "Education & Human Development": ["Early Childhood BSE", "Middle Level BSE", "Special Education MEd",
                                      "Educational Leadership EdS", "Counseling MS", "Kinesiology BS",
                                      "Teaching ESOL MAT", "Instructional Technology MS",
                                      "School Psychology EdS", "Exercise Science MS", "Literacy MEd",
                                      "Educational Policy PhD", "Sport Administration MS",
                                      "Mathematics Education MAT", "Science Education MAT",
                                      "Counseling Psychology PhD"],
    "Nursing & Health Professions": ["Nursing BSN", "Nursing MSN", "Nursing DNP", "Nutrition BS",
                                     "Nutrition MS", "Respiratory Therapy BS", "Physical Therapy DPT",
                                     "Occupational Therapy MOT", "Health Informatics MS",
                                     "Health Administration MSHA", "Public Health MPH",
                                     "Public Health BS", "Biostatistics PhD", "Epidemiology MS",
                                     "Dental Hygiene BS", "Speech Language Pathology MS"],
    "Arts": ["Art & Design BFA", "Music BM", "Film & Media BA", "Theatre BA", "Journalism BA",
             "Communication BA", "Music MM", "Art History MA", "Studio Art MFA", "Interior Design BFA",
             "Music Management BS", "Creative Writing MFA", "Dance BA", "Graphic Design BFA"],
    "Policy Studies": ["Criminal Justice BS", "Public Policy BS", "Public Administration MPA",
                       "Urban Policy MS", "Economics BA", "Economics MA", "Economics PhD",
                       "Nonprofit Leadership MS", "Social Work BSW", "Social Work MSW",
                       "Criminal Justice MS", "Public Policy PhD"],
    "Computing & Engineering": ["Computer Science BS", "Computer Science MS", "Data Science BS",
                                "Cybersecurity MS", "Information Technology BS", "Computer Science PhD",
                                "Applied Data Analytics MS", "Software Engineering BS",
                                "Electrical Engineering BS", "Mechanical Engineering BS",
                                "Engineering Technology BS", "Bioinformatics MS",
                                "Game Design BS", "Computational Biology PhD"],
}

FIRST = ["Dana", "Marcus", "Priya", "Keisha", "Tomas", "Hannah", "Olu", "Grace", "Ravi", "Lauren",
         "Andre", "Mei", "Jordan", "Fatima", "Caleb", "Nadia", "Derek", "Imani", "Sofia", "Wes",
         "Ayesha", "Brian", "Tanya", "Luis", "Rebecca", "Kwame", "Elena", "Jamal", "Yuki", "Patrick"]
LAST = ["Okafor", "Hill", "Ramaswamy", "Barnes", "Delgado", "Kim", "Adeyemi", "Foster", "Nair",
        "Whitfield", "Price", "Zhang", "Coleman", "Haddad", "Moore", "Petrov", "Lang", "Brooks",
        "Reyes", "Grant", "Siddiqui", "Lowe", "Mercer", "Ortiz", "Quinn", "Abara", "Vance", "Ito"]

CYCLES = [
    # label, due date, item present probability, late share, not submitted share
    ("2023-24", date(2024, 10, 15), 0.90, 0.22, 0.10),
    ("2024-25", date(2025, 10, 15), 0.93, 0.15, 0.07),
    ("2025-26", date(2026, 10, 15), 0.965, 0.08, 0.03),
]


def level_of(name):
    tail = name.split()[-1]
    if tail in {"PhD", "DNP", "DPT"}:
        return "Doctoral"
    if tail.startswith("M") or tail in {"EdS", "MIB"}:
        return "Graduate"
    return "Undergraduate"


def write(name, header, rows):
    with open(DATA / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote data/{name} ({len(rows)} rows)")


def main():
    write("requirements.csv", ["id", "kind", "name", "description"],
          [(i + 1, k, n, d) for i, (k, n, d) in enumerate(REQUIREMENTS)])

    # coordinators: one per 3-4 programs, unique names
    names = set()
    while len(names) < 36:
        names.add((rng.choice(FIRST), rng.choice(LAST)))
    coords = []
    for i, (f, l) in enumerate(sorted(names)):
        coords.append((i + 1, f"{f} {l}", f"{f[0].lower()}{l.lower()}@univ.edu"))
    write("coordinators.csv", ["id", "name", "email"], coords)

    programs = []
    pid = 0
    all_programs = [(c, p) for c, ps in COLLEGES.items() for p in ps][:120]
    assert len(all_programs) == 120, len(all_programs)
    for college, name in all_programs:
        pid += 1
        coord = coords[(pid * 7) % len(coords)][0]
        words = name.replace("&", "").split()
        stem = words[0][:4] if len(words) == 2 else "".join(w[0] for w in words[:-1])[:4]
        code = f"{stem.upper()}-{words[-1].upper()}"
        programs.append((pid, code, name, level_of(name), college, coord))
    write("programs.csv", ["id", "code", "name", "level", "college", "coordinator_id"], programs)

    write("cycles.csv", ["id", "label", "due_date", "is_current"],
          [(i + 1, lbl, due.isoformat(), int(i == len(CYCLES) - 1)) for i, (lbl, due, *_ ) in enumerate(CYCLES)])

    subs, items = [], []
    sid = 0
    for cid, (label, due, p_item, p_late, p_none) in enumerate(CYCLES, start=1):
        for prog in programs:
            sid += 1
            roll = rng.random()
            if roll < p_none:
                submitted = ""
            else:
                if rng.random() < p_late:
                    offset = rng.randint(1, 21)
                else:
                    offset = -rng.randint(0, 35)
                d = due + timedelta(days=offset)
                submitted = datetime.combine(d, time(rng.randint(8, 22), rng.randint(0, 59))).isoformat()
            subs.append((sid, prog[0], cid, submitted))
            if submitted:
                for rid, (kind, rname, _) in enumerate(REQUIREMENTS, start=1):
                    p = p_item
                    if rname == "Assessment Plan":
                        p = 0.99
                    if rname in ("Use of Results", "Action Plan"):
                        p -= 0.05  # the part programs most often leave out
                    items.append((sid, rid, int(rng.random() < p)))
    write("submissions.csv", ["id", "program_id", "cycle_id", "submitted_at"], subs)
    write("submission_items.csv", ["submission_id", "requirement_id", "present"], items)


if __name__ == "__main__":
    main()
