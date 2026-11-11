"""CSV and command file loaders plus basic parsing helpers."""

import calendar
import csv
from datetime import date, datetime
from pathlib import Path

from engine.models import (
    Applicant,
    BankAccount,
    Institution,
    RenewalRequest,
    Scheme,
)


def parse_bool(value: str) -> bool:
    """Convert 'true'/'false' string from CSV into a Python bool."""
    return value.strip().lower() == "true"


def parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD date string."""
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def parse_timestamp(value: str) -> datetime:
    """Parse a YYYY-MM-DD HH:MM:SS timestamp string."""
    return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")


def add_months(start_date: date, months: int) -> date:
    """Return a date exactly ``months`` calendar months after ``start_date``."""
    total_months = (start_date.year * 12) + (start_date.month - 1) + months
    new_year = total_months // 12
    new_month = (total_months % 12) + 1
    max_day = calendar.monthrange(new_year, new_month)[1]
    new_day = min(start_date.day, max_day)
    return date(new_year, new_month, new_day)


def round_money(value: float) -> float:
    """Round a monetary amount cleanly to 2 decimal places."""
    return round(float(value) + 1e-9, 2)


def round_half_up(value: float) -> int:
    """Round a positive number to the nearest integer (0.5 rounds up)."""
    return int(value + 0.5)


def load_schemes(path: Path) -> dict[str, Scheme]:
    """Load schemes.csv into a dict keyed by scheme_code."""
    schemes: dict[str, Scheme] = {}
    with open(path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            seats_text = row["seats_per_district"].strip()
            seats = int(seats_text) if seats_text else None
            budget_text = row.get("budget_cap", "").strip()
            budget_cap = float(budget_text) if budget_text else None
            courses = [c.strip() for c in row["eligible_courses"].split(";") if c.strip()]
            scheme = Scheme(
                scheme_code=row["scheme_code"].strip(),
                scheme_name=row["scheme_name"].strip(),
                scheme_type=row["scheme_type"].strip(),
                income_ceiling=float(row["income_ceiling"]),
                merit_cutoff_pct=float(row["merit_cutoff_pct"]),
                eligible_courses=courses,
                tuition_cap=float(row["tuition_cap"]),
                maintenance_per_month=float(row["maintenance_per_month"]),
                book_grant=float(row["book_grant"]),
                seats_per_district=seats,
                renewal_min_marks_pct=float(row["renewal_min_marks_pct"]),
                renewal_min_marks_sc_st_pct=float(row["renewal_min_marks_sc_st_pct"]),
                budget_cap=budget_cap,
            )
            schemes[scheme.scheme_code] = scheme
    return schemes


def load_institutions(path: Path) -> dict[str, Institution]:
    """Load institutions.csv into a dict keyed by institution_code."""
    institutions: dict[str, Institution] = {}
    with open(path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inst = Institution(
                institution_code=row["institution_code"].strip(),
                institution_name=row["institution_name"].strip(),
                district=row["district"].strip(),
                recognised=parse_bool(row["recognised"]),
            )
            institutions[inst.institution_code] = inst
    return institutions


def load_fee_structure(path: Path) -> dict[tuple[str, str], float]:
    """Load fee_structure.csv into a dict keyed by (institution_code, course)."""
    fees: dict[tuple[str, str], float] = {}
    with open(path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["institution_code"].strip(), row["course"].strip())
            fees[key] = float(row["annual_tuition"])
    return fees


def load_applications(path: Path) -> list[Applicant]:
    """Load applications.csv into a list of Applicant objects."""
    applicants: list[Applicant] = []
    with open(path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            app = Applicant(
                application_id=row["application_id"].strip(),
                applicant_name=row["applicant_name"].strip(),
                date_of_birth=parse_date(row["date_of_birth"]),
                gender=row["gender"].strip(),
                parent_name=row["parent_name"].strip(),
                category=row["category"].strip(),
                minority=parse_bool(row["minority"]),
                disability=parse_bool(row["disability"]),
                home_district=row["home_district"].strip(),
                course=row["course"].strip(),
                year_of_study=int(row["year_of_study"]),
                institution_code=row["institution_code"].strip(),
                previous_exam_pct=float(row["previous_exam_pct"]),
                family_income=float(row["family_income"]),
                income_cert_date=parse_date(row["income_cert_date"]),
                scheme_applied=row["scheme_applied"].strip(),
                application_ts=parse_timestamp(row["application_ts"]),
                central_scholarship=parse_bool(row["central_scholarship"]),
                central_tuition_component=float(row["central_tuition_component"]),
            )
            applicants.append(app)
    return applicants


def load_bank_accounts(path: Path) -> dict[str, BankAccount]:
    """Load bank_accounts.csv into a dict keyed by application_id."""
    accounts: dict[str, BankAccount] = {}
    with open(path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            acct = BankAccount(
                application_id=row["application_id"].strip(),
                account_holder_name=row["account_holder_name"].strip(),
                holder_relation=row["holder_relation"].strip(),
                ifsc=row["ifsc"].strip(),
                account_no_last4=row["account_no_last4"].strip(),
                aadhaar_seeded=parse_bool(row["aadhaar_seeded"]),
            )
            accounts[acct.application_id] = acct
    return accounts


def load_attendance(path: Path) -> dict[tuple[str, str], float]:
    """Load attendance_confirmations.csv keyed by (run_id, application_id)."""
    attendance: dict[tuple[str, str], float] = {}
    with open(path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["run_id"].strip(), row["application_id"].strip())
            attendance[key] = float(row["attendance_pct"])
    return attendance


def load_renewals(path: Path) -> list[RenewalRequest]:
    """Load renewals.csv into a list of RenewalRequest objects."""
    renewals: list[RenewalRequest] = []
    with open(path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            req = RenewalRequest(
                application_id=row["application_id"].strip(),
                academic_year=row["academic_year"].strip(),
                promoted=parse_bool(row["promoted"]),
                prev_year_marks_pct=float(row["prev_year_marks_pct"]),
                income_cert_date=parse_date(row["income_cert_date"]),
                submitted_date=parse_date(row["submitted_date"]),
            )
            renewals.append(req)
    return renewals


def load_commands(path: Path) -> list[list[str]]:
    """Parse commands.txt into a list of command token lists."""
    commands: list[list[str]] = []
    with open(path, mode="r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split("|")]
            commands.append(parts)
    return commands
