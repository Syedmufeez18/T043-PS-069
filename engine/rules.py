"""Business rules BR-01 through BR-12 for scholarship screening, ranking,
disbursement gates, and renewals.

Each function corresponds directly to a documented business rule so the
engine logic stays transparent, testable, and easy to follow.
"""

from datetime import date, datetime
from typing import Optional

from engine.loader import add_months, round_half_up, round_money
from engine.models import (
    Applicant,
    BankAccount,
    EligibilityResult,
    Institution,
    RenewalDecision,
    RenewalRequest,
    Scheme,
)

# BR-04: Tie-breaking order when two schemes yield identical total awards.
SCHEME_TYPE_PRIORITY = {
    "MERIT_CUM_MEANS": 1,
    "MEANS": 2,
    "MERIT": 3,
    "MINORITY": 4,
}


def deduplicate_applications(
    applications: list[Applicant],
) -> tuple[set[str], dict[str, str]]:
    """BR-12: Detect and mark duplicate applications for the same person.

    Rule:
    - Two applications to the same scheme by the same person -> keep earliest, discard later.
    - Same person applying to multiple schemes -> keep earliest application to screen once
      across all schemes; discard extra applications as DUPLICATE.

    Returns:
        kept_ids: Set of application_ids that stay active for screening.
        duplicate_reasons: Map of discarded application_id -> reason code.
    """
    sorted_apps = sorted(
        applications,
        key=lambda a: (a.application_ts, a.application_id),
    )

    seen_identity_scheme: set[tuple[tuple[str, date, str], str]] = set()
    seen_identity: dict[tuple[str, date, str], str] = {}
    kept_ids: set[str] = set()
    duplicate_reasons: dict[str, str] = {}

    for app in sorted_apps:
        identity = app.identity_key
        scheme_key = (identity, app.scheme_applied)

        if scheme_key in seen_identity_scheme:
            duplicate_reasons[app.application_id] = "SAME_SCHEME_DUPLICATE"
            continue

        seen_identity_scheme.add(scheme_key)

        if identity in seen_identity:
            duplicate_reasons[app.application_id] = "MULTI_SCHEME_SAME_PERSON"
            continue

        seen_identity[identity] = app.application_id
        kept_ids.add(app.application_id)

    return kept_ids, duplicate_reasons


def get_income_factor_pct(family_income: float) -> float:
    """BR-01: Return the means award percentage (100, 75, or 50) for a family income."""
    if family_income <= 100000.0:
        return 100.0
    if family_income <= 250000.0:
        return 75.0
    return 50.0


def is_income_cert_valid_at_application(
    income_cert_date: date,
    application_ts: datetime,
) -> bool:
    """BR-01: Income certificate must be less than 12 months old at application date."""
    expiry_date = add_months(income_cert_date, 12)
    return application_ts.date() < expiry_date


def get_effective_merit_cutoff(applicant: Applicant, scheme: Scheme) -> float:
    """BR-02: Compute relaxed merit cut-off (SC/ST -5, OBC -3, disability -3; max 5)."""
    if scheme.merit_cutoff_pct <= 0.0:
        return 0.0

    category_relax = 0.0
    if applicant.category in ("SC", "ST"):
        category_relax = 5.0
    elif applicant.category == "OBC":
        category_relax = 3.0

    disability_relax = 3.0 if applicant.disability else 0.0
    # Relaxations do not stack beyond 5 percentage points.
    total_relax = min(5.0, category_relax + disability_relax)
    return max(0.0, scheme.merit_cutoff_pct - total_relax)


def screen_application_against_scheme(
    applicant: Applicant,
    scheme: Scheme,
    institution: Optional[Institution],
    fee_structure: dict[tuple[str, str], float],
    is_duplicate: bool,
) -> EligibilityResult:
    """BR-01, BR-02, BR-03, BR-04, BR-10, BR-12: Screen one application against one scheme."""
    if is_duplicate:
        return EligibilityResult(
            application_id=applicant.application_id,
            scheme_code=scheme.scheme_code,
            eligible=False,
            rule_ids_failed=["BR-12_DUPLICATE"],
            award_total=0.0,
        )

    failed_rules: list[str] = []

    # BR-01: Income certificate freshness and income ceiling
    if not is_income_cert_valid_at_application(
        applicant.income_cert_date, applicant.application_ts
    ):
        failed_rules.append("BR-01_INVALID_CERT")

    if applicant.family_income > scheme.income_ceiling:
        failed_rules.append("BR-01_INELIGIBLE_INCOME")

    # BR-02: Minority check (for MINORITY schemes) and merit cut-off
    if scheme.scheme_type == "MINORITY" and not applicant.minority:
        failed_rules.append("BR-02_MINORITY_REQUIRED")

    if scheme.merit_cutoff_pct > 0.0:
        effective_cutoff = get_effective_merit_cutoff(applicant, scheme)
        if applicant.previous_exam_pct < effective_cutoff:
            failed_rules.append("BR-02_MERIT_CUTOFF")

    # BR-03: Course eligibility and institution recognition
    if applicant.course not in scheme.eligible_courses:
        failed_rules.append("BR-03_INELIGIBLE_COURSE")

    if institution is None or not institution.recognised:
        failed_rules.append("BR-03_UNRECOGNISED_INST")

    if failed_rules:
        return EligibilityResult(
            application_id=applicant.application_id,
            scheme_code=scheme.scheme_code,
            eligible=False,
            rule_ids_failed=failed_rules,
            award_total=0.0,
        )

    # Compute award components (BR-01, BR-03, BR-04, BR-10)
    factor_pct = get_income_factor_pct(applicant.family_income)
    factor = factor_pct / 100.0

    actual_tuition = fee_structure.get(
        (applicant.institution_code, applicant.course), 0.0
    )
    capped_tuition = min(actual_tuition, scheme.tuition_cap)
    tuition = round_money(capped_tuition * factor)

    outside_home_district = institution.district != applicant.home_district
    raw_maintenance = scheme.maintenance_per_month * 10.0 if outside_home_district else 0.0
    maintenance = round_money(raw_maintenance * factor)

    # BR-10: Book grant is Rs 5,000 in first year only, not scaled or pro-rated.
    book_grant = round_money(scheme.book_grant if applicant.year_of_study == 1 else 0.0)

    # BR-04: State award reduced by central scholarship tuition component if held.
    central_reduction = round_money(
        applicant.central_tuition_component if applicant.central_scholarship else 0.0
    )

    award_total = round_money(
        max(0.0, tuition + maintenance + book_grant - central_reduction)
    )

    return EligibilityResult(
        application_id=applicant.application_id,
        scheme_code=scheme.scheme_code,
        eligible=True,
        rule_ids_failed=[],
        tuition=tuition,
        maintenance=maintenance,
        book_grant=book_grant,
        central_reduction=central_reduction,
        income_factor_pct=factor_pct,
        award_total=award_total,
    )


def select_best_scheme(
    eligible_results: list[EligibilityResult],
    schemes: dict[str, Scheme],
) -> Optional[EligibilityResult]:
    """BR-04: Pick the single scheme with highest award_total and type tie-breaker."""
    if not eligible_results:
        return None

    return min(
        eligible_results,
        key=lambda r: (
            -r.award_total,
            SCHEME_TYPE_PRIORITY.get(schemes[r.scheme_code].scheme_type, 99),
            r.scheme_code,
        ),
    )


def sort_district_applicants(applicants: list[Applicant]) -> list[Applicant]:
    """BR-05: Sort applicants by merit % desc, family income asc, application_ts asc."""
    return sorted(
        applicants,
        key=lambda a: (
            -a.previous_exam_pct,
            a.family_income,
            a.application_ts,
            a.application_id,
        ),
    )


def allocate_district_seats(
    applicants: list[Applicant],
    seats_per_district: Optional[int],
) -> list[tuple[Applicant, int, str, str]]:
    """BR-05: Rank applicants and allocate seats with women (30%) & disability (5%) quotas.

    Reserved seats are filled first from eligible applicants in those groups (in merit
    rank order). Unfilled reserved seats revert to the open pool. Applicants beyond the
    available seats are marked WAITLISTED.

    Returns list of tuples: (applicant, rank, status, reserved_category).
    """
    ranked = sort_district_applicants(applicants)

    if seats_per_district is None:
        return [(app, idx, "SELECTED", "OPEN") for idx, app in enumerate(ranked, start=1)]

    total_seats = seats_per_district
    disability_quota = min(total_seats, round_half_up(0.05 * total_seats))
    women_quota = min(total_seats - disability_quota, round_half_up(0.30 * total_seats))

    selected_category: dict[str, str] = {}

    # 1. Fill disability reservation first (5%)
    disability_filled = 0
    for app in ranked:
        if disability_filled >= disability_quota:
            break
        if app.disability and app.application_id not in selected_category:
            selected_category[app.application_id] = "DISABILITY"
            disability_filled += 1

    # 2. Fill women reservation next (30%)
    women_filled = 0
    for app in ranked:
        if women_filled >= women_quota:
            break
        if app.gender == "F" and app.application_id not in selected_category:
            selected_category[app.application_id] = "WOMEN"
            women_filled += 1

    # 3. Fill remaining seats (including any unfilled reserved seats reverting to OPEN)
    for app in ranked:
        if len(selected_category) >= total_seats:
            break
        if app.application_id not in selected_category:
            selected_category[app.application_id] = "OPEN"

    decisions: list[tuple[Applicant, int, str, str]] = []
    for idx, app in enumerate(ranked, start=1):
        if app.application_id in selected_category:
            decisions.append((app, idx, "SELECTED", selected_category[app.application_id]))
        else:
            decisions.append((app, idx, "WAITLISTED", ""))

    return decisions


def validate_bank_account(
    applicant: Applicant,
    account: Optional[BankAccount],
    run_date: date,
) -> bool:
    """BR-07: Validate Aadhaar seeding and account ownership at run_date."""
    if account is None or not account.aadhaar_seeded:
        return False

    holder = account.account_holder_name.strip().lower()
    if account.holder_relation == "SELF":
        return holder == applicant.applicant_name.strip().lower()

    if account.holder_relation == "PARENT":
        eighteenth_birthday = add_months(applicant.date_of_birth, 18 * 12)
        is_under_18 = run_date < eighteenth_birthday
        return is_under_18 and holder == applicant.parent_name.strip().lower()

    return False


def months_remaining_in_academic_year(cancel_date: date) -> int:
    """BR-11: Return full months left in the 10-month Aug-May academic year.

    For example, a cancellation on 2027-01-28 leaves 4 months (Feb, Mar, Apr, May).
    """
    # Map calendar month to 1-based academic month (Aug=1 .. May=10).
    month_to_academic = {
        8: 1,
        9: 2,
        10: 3,
        11: 4,
        12: 5,
        1: 6,
        2: 7,
        3: 8,
        4: 9,
        5: 10,
    }
    if cancel_date.month in (6, 7):
        return 10

    current_acad = month_to_academic[cancel_date.month]
    start_acad = current_acad + 1 if cancel_date.day > 1 else current_acad
    return max(0, min(10, 10 - start_acad + 1))


def is_dropout_recoverable(dropout_date: date, last_paid_date: Optional[date]) -> bool:
    """BR-08: Last instalment is RECOVERABLE if dropout is within 30 days of payment."""
    if last_paid_date is None:
        return False
    days_since_payment = (dropout_date - last_paid_date).days
    return 0 <= days_since_payment <= 30


def evaluate_renewal(
    renewal_req: RenewalRequest,
    applicant: Applicant,
    scheme: Scheme,
    prior_fail_count: int,
) -> tuple[RenewalDecision, int]:
    """BR-09: Evaluate a renewal request and return (RenewalDecision, updated_fail_count)."""
    if not renewal_req.promoted:
        return (
            RenewalDecision(
                application_id=renewal_req.application_id,
                academic_year=renewal_req.academic_year,
                decision="TERMINATED",
                reason_code="NOT_PROMOTED",
                maintenance_pct=0.0,
            ),
            prior_fail_count,
        )

    # New income certificate is required every 2 years (>= 24 months old -> REJECTED_CERT).
    cert_expiry = add_months(renewal_req.income_cert_date, 24)
    if renewal_req.submitted_date >= cert_expiry:
        return (
            RenewalDecision(
                application_id=renewal_req.application_id,
                academic_year=renewal_req.academic_year,
                decision="REJECTED_CERT",
                reason_code="CERT_EXPIRED_2YR",
                maintenance_pct=0.0,
            ),
            prior_fail_count,
        )

    min_marks = (
        scheme.renewal_min_marks_sc_st_pct
        if applicant.category in ("SC", "ST")
        else scheme.renewal_min_marks_pct
    )

    if renewal_req.prev_year_marks_pct >= min_marks:
        return (
            RenewalDecision(
                application_id=renewal_req.application_id,
                academic_year=renewal_req.academic_year,
                decision="RENEWED",
                reason_code="ELIGIBLE",
                maintenance_pct=100.0,
            ),
            0,
        )

    new_fail_count = prior_fail_count + 1
    if new_fail_count == 1:
        return (
            RenewalDecision(
                application_id=renewal_req.application_id,
                academic_year=renewal_req.academic_year,
                decision="ON_PROBATION",
                reason_code="LOW_MARKS_PROBATION",
                maintenance_pct=50.0,
            ),
            new_fail_count,
        )

    return (
        RenewalDecision(
            application_id=renewal_req.application_id,
            academic_year=renewal_req.academic_year,
            decision="TERMINATED",
            reason_code="REPEATED_MARKS_FAILURE",
            maintenance_pct=0.0,
        ),
        new_fail_count,
    )
