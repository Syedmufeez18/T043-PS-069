"""Data models for the Scholarship Eligibility and Disbursement Engine.

All money amounts are stored as plain floats rounded to 2 decimal places,
and dates use standard Python ``datetime.date`` / ``datetime.datetime``.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Scheme:
    """Represents a state scholarship scheme loaded from schemes.csv."""

    scheme_code: str
    scheme_name: str
    scheme_type: str  # MERIT, MEANS, MERIT_CUM_MEANS, MINORITY
    income_ceiling: float
    merit_cutoff_pct: float
    eligible_courses: list[str]
    tuition_cap: float
    maintenance_per_month: float
    book_grant: float
    seats_per_district: Optional[int]  # None means no seat limit
    renewal_min_marks_pct: float
    renewal_min_marks_sc_st_pct: float
    budget_cap: Optional[float] = None  # Optional stretch goal: max scheme budget


@dataclass
class Institution:
    """Represents an institution from institutions.csv."""

    institution_code: str
    institution_name: str
    district: str
    recognised: bool


@dataclass
class Applicant:
    """Represents a single scholarship application from applications.csv."""

    application_id: str
    applicant_name: str
    date_of_birth: date
    gender: str  # M or F
    parent_name: str
    category: str  # GEN, OBC, SC, ST
    minority: bool
    disability: bool
    home_district: str
    course: str
    year_of_study: int
    institution_code: str
    previous_exam_pct: float
    family_income: float
    income_cert_date: date
    scheme_applied: str
    application_ts: datetime
    central_scholarship: bool
    central_tuition_component: float

    @property
    def identity_key(self) -> tuple[str, date, str]:
        """Identity key used for duplicate detection (BR-12)."""
        return (
            self.applicant_name.strip().lower(),
            self.date_of_birth,
            self.parent_name.strip().lower(),
        )


@dataclass
class BankAccount:
    """Represents a bank account record from bank_accounts.csv."""

    application_id: str
    account_holder_name: str
    holder_relation: str  # SELF or PARENT
    ifsc: str
    account_no_last4: str
    aadhaar_seeded: bool


@dataclass
class RenewalRequest:
    """Represents an annual renewal entry from renewals.csv."""

    application_id: str
    academic_year: str
    promoted: bool
    prev_year_marks_pct: float
    income_cert_date: date
    submitted_date: date


@dataclass
class EligibilityResult:
    """Screening result for one application against one scheme."""

    application_id: str
    scheme_code: str
    eligible: bool
    rule_ids_failed: list[str] = field(default_factory=list)
    tuition: float = 0.0
    maintenance: float = 0.0
    book_grant: float = 0.0
    central_reduction: float = 0.0
    income_factor_pct: float = 0.0
    award_total: float = 0.0


@dataclass
class SanctionRecord:
    """Final sanction and disbursement tracking state for an application."""

    application_id: str
    scheme_code: str
    status: str  # SELECTED, WAITLISTED, INELIGIBLE, DUPLICATE, CANCELLED
    district: str
    rank: Optional[int]
    reserved_category: str
    tuition: float
    maintenance: float
    book_grant: float
    central_reduction: float
    income_factor_pct: float
    award_total: float

    # Runtime disbursement state
    run1_due: float = 0.0
    run2_due: float = 0.0
    run3_due: float = 0.0
    deferred_amount: float = 0.0
    deferred_pct: float = 0.0
    consecutive_deferrals: int = 0
    is_promoted_waitlist: bool = False
    is_cancelled: bool = False
    dropout_date: Optional[date] = None
    last_paid_date: Optional[date] = None
    marks_fail_count: int = 0


@dataclass
class LedgerEntry:
    """One instalment attempt recorded in disbursement_ledger.csv."""

    application_id: str
    run_id: str
    run_date: date
    instalment_pct: float
    amount_due: float
    gate_result: str  # PASS, DEFER_BANK, DEFER_ATTENDANCE, CANCELLED
    amount_paid: float
    status: str  # PAID, DEFERRED, CANCELLED, RECOVERABLE


@dataclass
class RenewalDecision:
    """Result of evaluating one renewal request in renewal_decisions.csv."""

    application_id: str
    academic_year: str
    decision: str  # RENEWED, ON_PROBATION, TERMINATED, REJECTED_CERT
    reason_code: str
    maintenance_pct: float
