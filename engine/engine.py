"""Core ScholarshipEngine orchestrating command execution and CSV reporting."""

import csv
from collections import defaultdict
from pathlib import Path
from typing import Optional

from engine.loader import (
    load_applications,
    load_attendance,
    load_bank_accounts,
    load_commands,
    load_fee_structure,
    load_institutions,
    load_renewals,
    load_schemes,
    parse_date,
    parse_timestamp,
    round_half_up,
    round_money,
)
from engine.models import (
    Applicant,
    BankAccount,
    EligibilityResult,
    Institution,
    LedgerEntry,
    RenewalDecision,
    RenewalRequest,
    SanctionRecord,
    Scheme,
)
from engine.rules import (
    allocate_district_seats,
    deduplicate_applications,
    evaluate_renewal,
    is_dropout_recoverable,
    months_remaining_in_academic_year,
    screen_application_against_scheme,
    select_best_scheme,
    validate_bank_account,
)


class ScholarshipEngine:
    """Command-driven back-end engine for scholarship screening, sanctioning,
    instalment disbursement, waitlist movement, and annual renewals."""

    def __init__(self, data_dir: Path, quiet: bool = False) -> None:
        self.data_dir = Path(data_dir)
        self.quiet = quiet

        # Load master & transaction input datasets
        self.schemes: dict[str, Scheme] = load_schemes(self.data_dir / "schemes.csv")
        self.institutions: dict[str, Institution] = load_institutions(
            self.data_dir / "institutions.csv"
        )
        self.fee_structure: dict[tuple[str, str], float] = load_fee_structure(
            self.data_dir / "fee_structure.csv"
        )
        self.applications: list[Applicant] = load_applications(
            self.data_dir / "applications.csv"
        )
        self.applications_by_id: dict[str, Applicant] = {
            app.application_id: app for app in self.applications
        }
        self.bank_accounts: dict[str, BankAccount] = load_bank_accounts(
            self.data_dir / "bank_accounts.csv"
        )
        self.attendance: dict[tuple[str, str], float] = load_attendance(
            self.data_dir / "attendance_confirmations.csv"
        )
        self.renewals: list[RenewalRequest] = load_renewals(
            self.data_dir / "renewals.csv"
        )

        # Runtime state populated by commands
        self.kept_application_ids: set[str] = set()
        self.duplicate_reasons: dict[str, str] = {}
        self.eligibility_matrix: list[EligibilityResult] = []
        self.eligibility_by_app: dict[str, list[EligibilityResult]] = defaultdict(list)
        self.sanctions: dict[str, SanctionRecord] = {}
        self.ledger: list[LedgerEntry] = []
        self.renewal_decisions: list[RenewalDecision] = []
        self.renewal_fail_counts: dict[str, int] = defaultdict(int)
        self.completed_runs: set[str] = set()

    def _log(self, text: str) -> None:
        """Print console output unless suppressed (e.g., during unit tests)."""
        if not self.quiet:
            print(text)

    def run_commands_file(self, commands_path: Optional[Path] = None) -> None:
        """Execute every command in commands.txt strictly in file order."""
        path = commands_path or (self.data_dir / "commands.txt")
        commands = load_commands(path)
        for tokens in commands:
            self.execute_command(tokens)

    def execute_command(self, tokens: list[str]) -> None:
        """Dispatch a single parsed command line."""
        cmd = tokens[0].upper()

        if cmd == "RUN_SCREENING":
            self.run_screening(tokens[1])
        elif cmd == "RUN_SELECTION":
            self.run_selection(tokens[1])
        elif cmd == "PRINT_SANCTION":
            self.print_sanction(tokens[1] if len(tokens) > 1 else "ALL")
        elif cmd == "DISBURSE":
            self.disburse(tokens[1], tokens[2])
        elif cmd == "DROPOUT":
            self.handle_dropout(tokens[1], tokens[2], tokens[3])
        elif cmd == "BANK_UPDATE":
            self.handle_bank_update(tokens[1], tokens[2], tokens[3], tokens[4], tokens[5])
        elif cmd == "CANCEL_AWARD":
            reason = tokens[3] if len(tokens) > 3 else ""
            self.cancel_award(tokens[1], tokens[2], reason)
        elif cmd == "RUN_RENEWALS":
            self.run_renewals(tokens[1], tokens[2])
        elif cmd == "PRINT_UTILISATION":
            self.print_utilisation()
        elif cmd == "PRINT_LEDGER":
            self.print_ledger(tokens[1])
        elif cmd == "DBT_RETURN":
            # Optional stretch goal: re-queue a failed DBT credit to deferred balance
            self.handle_dbt_return(tokens[1], tokens[2])
        else:
            raise ValueError(f"Unknown command: {cmd}")

    def run_screening(self, ts_str: str) -> None:
        """Screen every application against every scheme (BR-01..BR-04, BR-10, BR-12)."""
        _ = parse_timestamp(ts_str)
        self.kept_application_ids, self.duplicate_reasons = deduplicate_applications(
            self.applications
        )
        self.eligibility_matrix.clear()
        self.eligibility_by_app.clear()

        sorted_apps = sorted(self.applications, key=lambda a: a.application_id)
        sorted_schemes = sorted(self.schemes.values(), key=lambda s: s.scheme_code)

        for app in sorted_apps:
            is_dup = app.application_id in self.duplicate_reasons
            inst = self.institutions.get(app.institution_code)
            for scheme in sorted_schemes:
                res = screen_application_against_scheme(
                    applicant=app,
                    scheme=scheme,
                    institution=inst,
                    fee_structure=self.fee_structure,
                    is_duplicate=is_dup,
                )
                self.eligibility_matrix.append(res)
                self.eligibility_by_app[app.application_id].append(res)

    def run_selection(self, ts_str: str) -> None:
        """Select final scheme per applicant and rank within district (BR-04, BR-05)."""
        _ = parse_timestamp(ts_str)
        self.sanctions.clear()

        # Group eligible applicants by (winning_scheme_code, home_district)
        grouped: dict[tuple[str, str], list[tuple[Applicant, EligibilityResult]]] = defaultdict(list)

        for app in sorted(self.applications, key=lambda a: a.application_id):
            app_id = app.application_id
            if app_id in self.duplicate_reasons:
                self.sanctions[app_id] = SanctionRecord(
                    application_id=app_id,
                    scheme_code="",
                    status="DUPLICATE",
                    district=app.home_district,
                    rank=None,
                    reserved_category="",
                    tuition=0.0,
                    maintenance=0.0,
                    book_grant=0.0,
                    central_reduction=0.0,
                    income_factor_pct=0.0,
                    award_total=0.0,
                )
                continue

            eligible_results = [
                r for r in self.eligibility_by_app[app_id] if r.eligible
            ]
            best = select_best_scheme(eligible_results, self.schemes)

            if best is None:
                self.sanctions[app_id] = SanctionRecord(
                    application_id=app_id,
                    scheme_code="",
                    status="INELIGIBLE",
                    district=app.home_district,
                    rank=None,
                    reserved_category="",
                    tuition=0.0,
                    maintenance=0.0,
                    book_grant=0.0,
                    central_reduction=0.0,
                    income_factor_pct=0.0,
                    award_total=0.0,
                )
                continue

            grouped[(best.scheme_code, app.home_district)].append((app, best))

        # Rank and allocate seats per (scheme, district)
        for (scheme_code, district), items in sorted(grouped.items()):
            scheme = self.schemes[scheme_code]
            result_by_id = {app.application_id: res for app, res in items}
            apps_only = [app for app, _ in items]

            allocations = allocate_district_seats(
                apps_only, scheme.seats_per_district
            )

            for app, rank, status, reserved_cat in allocations:
                best = result_by_id[app.application_id]
                rec = SanctionRecord(
                    application_id=app.application_id,
                    scheme_code=scheme_code,
                    status=status,
                    district=district,
                    rank=rank,
                    reserved_category=reserved_cat,
                    tuition=best.tuition,
                    maintenance=best.maintenance,
                    book_grant=best.book_grant,
                    central_reduction=best.central_reduction,
                    income_factor_pct=best.income_factor_pct,
                    award_total=best.award_total,
                )
                if status == "SELECTED":
                    self._initialize_instalments(rec)
                self.sanctions[app.application_id] = rec

        # Optional stretch goal: enforce budget_cap if configured on any scheme
        self._apply_optional_budget_caps()

    def _initialize_instalments(self, rec: SanctionRecord) -> None:
        """Compute 50% (+ book grant), 30%, and 20% instalment schedule for a SELECTED award."""
        book_grant_part = min(rec.book_grant, rec.award_total)
        net_means = round_money(max(0.0, rec.award_total - book_grant_part))
        run1_base = round_money(net_means * 0.50)
        rec.run1_due = round_money(run1_base + book_grant_part)
        rec.run2_due = round_money(net_means * 0.30)
        rec.run3_due = round_money(net_means - run1_base - rec.run2_due)

    def _apply_optional_budget_caps(self) -> None:
        """Stretch goal: move lowest-ranked selections to waitlist if budget_cap is exceeded."""
        for scheme_code, scheme in self.schemes.items():
            if scheme.budget_cap is None:
                continue
            selected = [
                rec
                for rec in self.sanctions.values()
                if rec.scheme_code == scheme_code and rec.status == "SELECTED"
            ]
            # Sort by merit descending so highest merit keeps budget first
            selected.sort(
                key=lambda r: (
                    -self.applications_by_id[r.application_id].previous_exam_pct,
                    self.applications_by_id[r.application_id].family_income,
                    self.applications_by_id[r.application_id].application_ts,
                    r.application_id,
                )
            )
            spent = 0.0
            for rec in selected:
                if spent + rec.award_total <= scheme.budget_cap + 1e-9:
                    spent = round_money(spent + rec.award_total)
                else:
                    rec.status = "WAITLISTED"
                    rec.reserved_category = ""
                    rec.run1_due = 0.0
                    rec.run2_due = 0.0
                    rec.run3_due = 0.0

    def disburse(self, run_id: str, run_date_str: str) -> None:
        """Process one disbursement run evaluating bank and attendance gates at run_date."""
        run_date = parse_date(run_date_str)
        base_pct_map = {"RUN-1": 50.0, "RUN-2": 30.0, "RUN-3": 20.0}
        base_pct = base_pct_map[run_id]

        for app_id in sorted(self.sanctions.keys()):
            rec = self.sanctions[app_id]

            # Process records that were selected initially, promoted, or cancelled after selection
            was_ever_selected = (
                rec.status == "SELECTED"
                or rec.is_promoted_waitlist
                or (
                    rec.status == "CANCELLED"
                    and (rec.run1_due + rec.run2_due + rec.run3_due > 0.0)
                )
            )
            if not was_ever_selected:
                continue

            if run_id == "RUN-1":
                scheduled_due = rec.run1_due
            elif run_id == "RUN-2":
                scheduled_due = rec.run2_due
            else:
                scheduled_due = rec.run3_due

            # Promoted waitlisted applicants start at RUN-2
            if run_id == "RUN-1" and rec.is_promoted_waitlist:
                continue

            if rec.is_cancelled:
                self.ledger.append(
                    LedgerEntry(
                        application_id=app_id,
                        run_id=run_id,
                        run_date=run_date,
                        instalment_pct=base_pct,
                        amount_due=scheduled_due,
                        gate_result="CANCELLED",
                        amount_paid=0.0,
                        status="CANCELLED",
                    )
                )
                rec.deferred_amount = 0.0
                rec.deferred_pct = 0.0
                continue

            total_due = round_money(scheduled_due + rec.deferred_amount)
            total_pct = base_pct + rec.deferred_pct

            applicant = self.applications_by_id[app_id]
            account = self.bank_accounts.get(app_id)

            # Attendance gate applies from RUN-2 onwards; bank gate applies at every run.
            if run_id == "RUN-1":
                att_ok = True
            else:
                att_pct = self.attendance.get((run_id, app_id))
                att_ok = att_pct is not None and att_pct >= 75.0

            bank_ok = validate_bank_account(applicant, account, run_date)

            if att_ok and bank_ok:
                self.ledger.append(
                    LedgerEntry(
                        application_id=app_id,
                        run_id=run_id,
                        run_date=run_date,
                        instalment_pct=total_pct,
                        amount_due=total_due,
                        gate_result="PASS",
                        amount_paid=total_due,
                        status="PAID",
                    )
                )
                rec.deferred_amount = 0.0
                rec.deferred_pct = 0.0
                rec.consecutive_deferrals = 0
                rec.last_paid_date = run_date
            else:
                gate_result = "DEFER_ATTENDANCE" if not att_ok else "DEFER_BANK"
                rec.consecutive_deferrals += 1

                if rec.consecutive_deferrals >= 2:
                    rec.is_cancelled = True
                    rec.status = "CANCELLED"
                    rec.deferred_amount = 0.0
                    rec.deferred_pct = 0.0
                    self.ledger.append(
                        LedgerEntry(
                            application_id=app_id,
                            run_id=run_id,
                            run_date=run_date,
                            instalment_pct=total_pct,
                            amount_due=total_due,
                            gate_result=gate_result,
                            amount_paid=0.0,
                            status="CANCELLED",
                        )
                    )
                else:
                    rec.deferred_amount = total_due
                    rec.deferred_pct = total_pct
                    self.ledger.append(
                        LedgerEntry(
                            application_id=app_id,
                            run_id=run_id,
                            run_date=run_date,
                            instalment_pct=total_pct,
                            amount_due=total_due,
                            gate_result=gate_result,
                            amount_paid=0.0,
                            status="DEFERRED",
                        )
                    )

        self.completed_runs.add(run_id)

    def handle_dropout(
        self,
        application_id: str,
        dropout_date_str: str,
        reported_ts_str: str,
    ) -> None:
        """BR-08: Cancel future instalments and mark last payment RECOVERABLE if <= 30 days."""
        dropout_date = parse_date(dropout_date_str)
        _ = parse_timestamp(reported_ts_str)

        rec = self.sanctions.get(application_id)
        if rec is None:
            return

        rec.dropout_date = dropout_date
        rec.is_cancelled = True
        rec.status = "CANCELLED"
        rec.deferred_amount = 0.0
        rec.deferred_pct = 0.0

        # Check the most recent PAID ledger entry for this applicant
        for entry in reversed(self.ledger):
            if entry.application_id == application_id and entry.status == "PAID":
                if is_dropout_recoverable(dropout_date, entry.run_date):
                    entry.status = "RECOVERABLE"
                break

    def handle_bank_update(
        self,
        application_id: str,
        account_holder_name: str,
        holder_relation: str,
        aadhaar_seeded_str: str,
        ts_str: str,
    ) -> None:
        """BR-07: Update bank record so the next run re-validates it."""
        _ = parse_timestamp(ts_str)
        aadhaar_seeded = aadhaar_seeded_str.strip().lower() == "true"
        existing = self.bank_accounts.get(application_id)
        if existing is None:
            self.bank_accounts[application_id] = BankAccount(
                application_id=application_id,
                account_holder_name=account_holder_name.strip(),
                holder_relation=holder_relation.strip(),
                ifsc="",
                account_no_last4="",
                aadhaar_seeded=aadhaar_seeded,
            )
        else:
            existing.account_holder_name = account_holder_name.strip()
            existing.holder_relation = holder_relation.strip()
            existing.aadhaar_seeded = aadhaar_seeded

    def cancel_award(self, application_id: str, ts_str: str, reason: str) -> None:
        """BR-11: Cancel an award and promote next waitlisted applicant if before RUN-2."""
        cancel_dt = parse_timestamp(ts_str)
        _ = reason

        rec = self.sanctions.get(application_id)
        if rec is None:
            return

        was_selected = rec.status == "SELECTED"
        freed_category = rec.reserved_category or "OPEN"
        scheme_code = rec.scheme_code
        district = rec.district

        rec.is_cancelled = True
        rec.status = "CANCELLED"
        rec.deferred_amount = 0.0
        rec.deferred_pct = 0.0

        # Waitlist movement applies only when cancelled before the second instalment (RUN-2).
        if not was_selected or "RUN-2" in self.completed_runs:
            return

        waitlisted = [
            s
            for s in self.sanctions.values()
            if s.scheme_code == scheme_code
            and s.district == district
            and s.status == "WAITLISTED"
        ]
        if not waitlisted:
            return

        waitlisted.sort(key=lambda s: (s.rank or 999999, s.application_id))
        chosen = self._pick_waitlist_replacement(
            scheme_code, district, freed_category, waitlisted
        )

        months_left = months_remaining_in_academic_year(cancel_dt.date())
        pro_rated_maint = round_money(chosen.maintenance * (months_left / 10.0))

        chosen.status = "SELECTED"
        chosen.is_promoted_waitlist = True
        chosen.reserved_category = freed_category
        chosen.maintenance = pro_rated_maint
        # BR-10: Book grant is paid only with the first instalment, not on mid-year promotion.
        chosen.book_grant = 0.0
        chosen.award_total = round_money(
            max(0.0, chosen.tuition + pro_rated_maint - chosen.central_reduction)
        )
        # Split remaining entitlement across RUN-2 (30:20 -> 60%) and RUN-3 (40%).
        chosen.run1_due = 0.0
        chosen.run2_due = round_money(chosen.award_total * 0.60)
        chosen.run3_due = round_money(chosen.award_total - chosen.run2_due)

    def _pick_waitlist_replacement(
        self,
        scheme_code: str,
        district: str,
        freed_category: str,
        waitlisted: list[SanctionRecord],
    ) -> SanctionRecord:
        """Select replacement from waitlist while preserving reserved quotas if underfilled."""
        scheme = self.schemes[scheme_code]
        total_seats = scheme.seats_per_district
        if total_seats is None:
            return waitlisted[0]

        current_selected = [
            s
            for s in self.sanctions.values()
            if s.scheme_code == scheme_code
            and s.district == district
            and s.status == "SELECTED"
        ]

        if freed_category == "DISABILITY":
            dis_quota = round_half_up(0.05 * total_seats)
            current_dis = sum(
                1
                for s in current_selected
                if self.applications_by_id[s.application_id].disability
            )
            if current_dis < dis_quota:
                for cand in waitlisted:
                    if self.applications_by_id[cand.application_id].disability:
                        return cand

        if freed_category == "WOMEN":
            women_quota = round_half_up(0.30 * total_seats)
            current_women = sum(
                1
                for s in current_selected
                if self.applications_by_id[s.application_id].gender == "F"
            )
            if current_women < women_quota:
                for cand in waitlisted:
                    if self.applications_by_id[cand.application_id].gender == "F":
                        return cand

        return waitlisted[0]

    def handle_dbt_return(self, run_id: str, application_id: str) -> None:
        """Stretch goal: re-queue a failed DBT credit so it carries to the next run."""
        rec = self.sanctions.get(application_id)
        if rec is None or rec.is_cancelled:
            return
        for entry in reversed(self.ledger):
            if (
                entry.application_id == application_id
                and entry.run_id == run_id
                and entry.status == "PAID"
            ):
                failed_amount = entry.amount_paid
                entry.amount_paid = 0.0
                entry.status = "DEFERRED"
                entry.gate_result = "DEFER_BANK"
                rec.deferred_amount = round_money(rec.deferred_amount + failed_amount)
                rec.deferred_pct += entry.instalment_pct
                break

    def run_renewals(self, academic_year: str, run_date_str: str) -> None:
        """BR-09: Evaluate renewal requests for the supplied academic_year."""
        _ = parse_date(run_date_str)
        matching = [r for r in self.renewals if r.academic_year == academic_year]
        matching.sort(key=lambda r: r.application_id)

        for req in matching:
            app = self.applications_by_id[req.application_id]
            sanction = self.sanctions.get(req.application_id)
            scheme_code = (
                sanction.scheme_code
                if sanction and sanction.scheme_code
                else app.scheme_applied
            )
            scheme = self.schemes[scheme_code]
            prior_fails = self.renewal_fail_counts[req.application_id]
            decision, updated_fails = evaluate_renewal(req, app, scheme, prior_fails)
            self.renewal_fail_counts[req.application_id] = updated_fails
            self.renewal_decisions.append(decision)

    def print_sanction(self, scheme_code: str = "ALL") -> None:
        """Print formatted sanction list for one scheme or ALL schemes."""
        self._log(f"\n=== SANCTION LIST ({scheme_code}) ===")
        rows = [
            rec
            for rec in sorted(
                self.sanctions.values(),
                key=lambda r: (
                    r.scheme_code or "ZZZ",
                    r.district,
                    r.rank or 999999,
                    r.application_id,
                ),
            )
            if scheme_code == "ALL" or rec.scheme_code == scheme_code
        ]
        counts: dict[str, int] = defaultdict(int)
        for r in rows:
            counts[r.status] += 1
        summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        self._log(f"Summary: {summary}")
        for r in rows:
            if r.status in ("SELECTED", "WAITLISTED", "CANCELLED"):
                rank_str = str(r.rank) if r.rank is not None else "-"
                self._log(
                    f"{r.application_id} | {r.scheme_code or '-':6s} | {r.status:10s} | "
                    f"{r.district:16s} | rank={rank_str:>3s} | {r.reserved_category or '-':10s} | "
                    f"award=Rs {r.award_total:.2f}"
                )

    def compute_utilisation_rows(self) -> list[dict[str, str]]:
        """Compute per-scheme utilisation metrics matching utilisation.csv."""
        rows: list[dict[str, str]] = []
        for scheme_code in sorted(self.schemes.keys()):
            selected_cnt = 0
            waitlisted_cnt = 0
            sanctioned_amt = 0.0

            for rec in self.sanctions.values():
                if rec.scheme_code != scheme_code:
                    continue
                if rec.status == "SELECTED":
                    selected_cnt += 1
                    sanctioned_amt += rec.award_total
                elif rec.status == "CANCELLED" and (
                    rec.run1_due + rec.run2_due + rec.run3_due > 0.0
                ):
                    sanctioned_amt += rec.award_total
                elif rec.status == "WAITLISTED":
                    waitlisted_cnt += 1

            disbursed_amt = 0.0
            recoverable_amt = 0.0
            for entry in self.ledger:
                rec = self.sanctions.get(entry.application_id)
                if rec is None or rec.scheme_code != scheme_code:
                    continue
                if entry.status in ("PAID", "RECOVERABLE"):
                    disbursed_amt += entry.amount_paid
                if entry.status == "RECOVERABLE":
                    recoverable_amt += entry.amount_paid

            rows.append(
                {
                    "scheme_code": scheme_code,
                    "selected": str(selected_cnt),
                    "waitlisted": str(waitlisted_cnt),
                    "sanctioned_amount": f"{round_money(sanctioned_amt):.2f}",
                    "disbursed_amount": f"{round_money(disbursed_amt):.2f}",
                    "recoverable_amount": f"{round_money(recoverable_amt):.2f}",
                }
            )
        return rows

    def print_utilisation(self) -> None:
        """Print formatted scheme utilisation report."""
        self._log("\n=== SCHEME UTILISATION REPORT ===")
        for row in self.compute_utilisation_rows():
            self._log(
                f"{row['scheme_code']} | selected={row['selected']:>3s} | "
                f"waitlisted={row['waitlisted']:>2s} | "
                f"sanctioned=Rs {row['sanctioned_amount']:>10s} | "
                f"disbursed=Rs {row['disbursed_amount']:>10s} | "
                f"recoverable=Rs {row['recoverable_amount']:>8s}"
            )

    def print_ledger(self, application_id: str) -> None:
        """Print disbursement ledger and sanction details for one applicant."""
        rec = self.sanctions.get(application_id)
        if rec is None:
            self._log(f"\n=== LEDGER: {application_id} (NOT FOUND) ===")
            return
        self._log(
            f"\n=== LEDGER: {application_id} | scheme={rec.scheme_code or '-'} | "
            f"status={rec.status} | award=Rs {rec.award_total:.2f} ==="
        )
        entries = [e for e in self.ledger if e.application_id == application_id]
        if not entries:
            self._log("  (no disbursement attempts)")
            return
        for e in entries:
            self._log(
                f"  {e.run_id} | {e.run_date.isoformat()} | {e.instalment_pct:5.2f}% | "
                f"due={e.amount_due:9.2f} | gate={e.gate_result:16s} | "
                f"paid={e.amount_paid:9.2f} | status={e.status}"
            )

    def write_outputs(self, output_dir: Path) -> None:
        """Write all 5 binding CSV output files to output_dir."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # 1. eligibility_matrix.csv
        with open(out / "eligibility_matrix.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["application_id", "scheme_code", "eligible", "rule_ids_failed", "award_total"]
            )
            for res in sorted(
                self.eligibility_matrix,
                key=lambda r: (r.application_id, r.scheme_code),
            ):
                writer.writerow(
                    [
                        res.application_id,
                        res.scheme_code,
                        "true" if res.eligible else "false",
                        ";".join(res.rule_ids_failed),
                        f"{res.award_total:.2f}",
                    ]
                )

        # 2. sanction.csv
        with open(out / "sanction.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "application_id",
                    "scheme_code",
                    "status",
                    "district",
                    "rank",
                    "reserved_category",
                    "tuition",
                    "maintenance",
                    "book_grant",
                    "central_reduction",
                    "income_factor_pct",
                    "award_total",
                ]
            )
            for app_id in sorted(self.sanctions.keys()):
                r = self.sanctions[app_id]
                writer.writerow(
                    [
                        r.application_id,
                        r.scheme_code,
                        r.status,
                        r.district,
                        str(r.rank) if r.rank is not None else "",
                        r.reserved_category,
                        f"{r.tuition:.2f}",
                        f"{r.maintenance:.2f}",
                        f"{r.book_grant:.2f}",
                        f"{r.central_reduction:.2f}",
                        f"{r.income_factor_pct:.2f}",
                        f"{r.award_total:.2f}",
                    ]
                )

        # 3. disbursement_ledger.csv
        with open(out / "disbursement_ledger.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "application_id",
                    "run_id",
                    "run_date",
                    "instalment_pct",
                    "amount_due",
                    "gate_result",
                    "amount_paid",
                    "status",
                ]
            )
            for e in sorted(
                self.ledger,
                key=lambda x: (x.run_date, x.run_id, x.application_id),
            ):
                writer.writerow(
                    [
                        e.application_id,
                        e.run_id,
                        e.run_date.isoformat(),
                        f"{e.instalment_pct:.2f}",
                        f"{e.amount_due:.2f}",
                        e.gate_result,
                        f"{e.amount_paid:.2f}",
                        e.status,
                    ]
                )

        # 4. renewal_decisions.csv
        with open(out / "renewal_decisions.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "application_id",
                    "academic_year",
                    "decision",
                    "reason_code",
                    "maintenance_pct",
                ]
            )
            for d in sorted(
                self.renewal_decisions,
                key=lambda x: (x.academic_year, x.application_id),
            ):
                writer.writerow(
                    [
                        d.application_id,
                        d.academic_year,
                        d.decision,
                        d.reason_code,
                        f"{d.maintenance_pct:.2f}",
                    ]
                )

        # 5. utilisation.csv
        with open(out / "utilisation.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "scheme_code",
                    "selected",
                    "waitlisted",
                    "sanctioned_amount",
                    "disbursed_amount",
                    "recoverable_amount",
                ]
            )
            for row in self.compute_utilisation_rows():
                writer.writerow(
                    [
                        row["scheme_code"],
                        row["selected"],
                        row["waitlisted"],
                        row["sanctioned_amount"],
                        row["disbursed_amount"],
                        row["recoverable_amount"],
                    ]
                )
