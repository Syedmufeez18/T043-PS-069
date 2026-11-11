"""Comprehensive test suite covering BR-01..BR-12, EC-01..EC-08, extra traps,
optional stretch goals, and end-to-end execution on T043-PS-069-sample-data.
"""

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from engine.engine import ScholarshipEngine


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DATA_DIR = PROJECT_ROOT / "T043-PS-069-sample-data"


def write_csv(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    """Helper to write a CSV file for isolated test fixtures."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


class FixtureBuilder:
    """Creates minimal self-contained CSV datasets in a temporary folder."""

    def __init__(self, tmp_dir: Path) -> None:
        self.dir = tmp_dir
        self.schemes: list[list[object]] = [
            [
                "SCH-01",
                "Merit-cum-Means",
                "MERIT_CUM_MEANS",
                "250000.00",
                "60.00",
                "BSC;BE;BCOM;BA",
                "50000.00",
                "1500.00",
                "5000.00",
                "7",
                "50.00",
                "45.00",
            ],
            [
                "SCH-02",
                "State Means",
                "MEANS",
                "450000.00",
                "0.00",
                "BSC;BE;BCOM;BA",
                "40000.00",
                "1000.00",
                "5000.00",
                "",
                "50.00",
                "45.00",
            ],
            [
                "SCH-03",
                "Merit Award",
                "MERIT",
                "600000.00",
                "85.00",
                "BSC;BE",
                "75000.00",
                "0.00",
                "5000.00",
                "10",
                "50.00",
                "45.00",
            ],
            [
                "SCH-04",
                "Minority Award",
                "MINORITY",
                "200000.00",
                "50.00",
                "BSC;BE;BCOM;BA",
                "30000.00",
                "1200.00",
                "5000.00",
                "",
                "50.00",
                "45.00",
            ],
        ]
        self.institutions: list[list[object]] = [
            ["INS-001", "Home College", "Mysuru", "true"],
            ["INS-002", "Outside College", "Bengaluru", "true"],
            ["INS-003", "Unrecognised College", "Bengaluru", "false"],
        ]
        self.fees: list[list[object]] = [
            ["INS-001", "BSC", "30000.00"],
            ["INS-002", "BSC", "30000.00"],
            ["INS-002", "BE", "100000.00"],
            ["INS-002", "BCOM", "35000.00"],
            ["INS-003", "BSC", "30000.00"],
        ]
        self.applications: list[list[object]] = []
        self.banks: list[list[object]] = []
        self.attendance: list[list[object]] = []
        self.renewals: list[list[object]] = []
        self.commands: list[str] = [
            "RUN_SCREENING|2026-08-20 10:00:00",
            "RUN_SELECTION|2026-08-25 10:00:00",
            "DISBURSE|RUN-1|2026-09-15",
            "DISBURSE|RUN-2|2027-02-01",
            "DISBURSE|RUN-3|2027-05-31",
        ]

    def add_app(
        self,
        app_id: str,
        name: str = "Student One",
        dob: str = "2006-01-10",
        gender: str = "M",
        parent: str = "Parent One",
        category: str = "GEN",
        minority: str = "false",
        disability: str = "false",
        district: str = "Mysuru",
        course: str = "BSC",
        year: int = 1,
        inst: str = "INS-001",
        pct: str = "75.00",
        income: str = "90000.00",
        cert_date: str = "2026-05-01",
        scheme_applied: str = "SCH-01",
        ts: str = "2026-07-05 10:00:00",
        central: str = "false",
        central_amt: str = "0.00",
        holder_name: str | None = None,
        holder_rel: str = "SELF",
        aadhaar: str = "true",
        att2: str = "85.00",
        att3: str = "85.00",
    ) -> None:
        self.applications.append(
            [
                app_id,
                name,
                dob,
                gender,
                parent,
                category,
                minority,
                disability,
                district,
                course,
                str(year),
                inst,
                pct,
                income,
                cert_date,
                scheme_applied,
                ts,
                central,
                central_amt,
            ]
        )
        self.banks.append(
            [
                app_id,
                holder_name or name,
                holder_rel,
                "SBIN0000001",
                "1234",
                aadhaar,
            ]
        )
        self.attendance.append(["RUN-2", app_id, att2])
        self.attendance.append(["RUN-3", app_id, att3])

    def build(self) -> ScholarshipEngine:
        write_csv(
            self.dir / "schemes.csv",
            [
                "scheme_code",
                "scheme_name",
                "scheme_type",
                "income_ceiling",
                "merit_cutoff_pct",
                "eligible_courses",
                "tuition_cap",
                "maintenance_per_month",
                "book_grant",
                "seats_per_district",
                "renewal_min_marks_pct",
                "renewal_min_marks_sc_st_pct",
            ],
            self.schemes,
        )
        write_csv(
            self.dir / "institutions.csv",
            ["institution_code", "institution_name", "district", "recognised"],
            self.institutions,
        )
        write_csv(
            self.dir / "fee_structure.csv",
            ["institution_code", "course", "annual_tuition"],
            self.fees,
        )
        write_csv(
            self.dir / "applications.csv",
            [
                "application_id",
                "applicant_name",
                "date_of_birth",
                "gender",
                "parent_name",
                "category",
                "minority",
                "disability",
                "home_district",
                "course",
                "year_of_study",
                "institution_code",
                "previous_exam_pct",
                "family_income",
                "income_cert_date",
                "scheme_applied",
                "application_ts",
                "central_scholarship",
                "central_tuition_component",
            ],
            self.applications,
        )
        write_csv(
            self.dir / "bank_accounts.csv",
            [
                "application_id",
                "account_holder_name",
                "holder_relation",
                "ifsc",
                "account_no_last4",
                "aadhaar_seeded",
            ],
            self.banks,
        )
        write_csv(
            self.dir / "attendance_confirmations.csv",
            ["run_id", "application_id", "attendance_pct"],
            self.attendance,
        )
        write_csv(
            self.dir / "renewals.csv",
            [
                "application_id",
                "academic_year",
                "promoted",
                "prev_year_marks_pct",
                "income_cert_date",
                "submitted_date",
            ],
            self.renewals,
        )
        (self.dir / "commands.txt").write_text(
            "\n".join(self.commands) + "\n", encoding="utf-8"
        )
        return ScholarshipEngine(self.dir, quiet=True)


class TestBusinessRulesAndEdgeCases(unittest.TestCase):
    """Unit & scenario tests for BR-01..BR-12 and EC-01..EC-08."""

    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="ps069_test_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_ec01_income_slab_boundaries_and_cert_expiry(self) -> None:
        fb = FixtureBuilder(self.tmp_dir)
        # Exactly 1,00,000 -> 100% factor
        fb.add_app("APL-0001", name="A", inst="INS-002", income="100000.00")
        # Exactly 2,50,001 -> 50% factor and ineligible for SCH-01 (ceiling 2,50,000)
        fb.add_app("APL-0002", name="B", inst="INS-002", income="250001.00")
        # Exactly 12 months old cert (2025-07-10 on 2026-07-10) -> INVALID_CERT
        fb.add_app(
            "APL-0003",
            name="C",
            cert_date="2025-07-10",
            ts="2026-07-10 11:00:00",
        )
        eng = fb.build()
        eng.run_commands_file()

        s1 = eng.sanctions["APL-0001"]
        self.assertEqual(s1.income_factor_pct, 100.0)
        self.assertEqual(s1.tuition, 30000.0)
        self.assertEqual(s1.maintenance, 15000.0)
        self.assertEqual(s1.award_total, 50000.0)

        s2 = eng.sanctions["APL-0002"]
        self.assertEqual(s2.scheme_code, "SCH-02")
        self.assertEqual(s2.income_factor_pct, 50.0)
        self.assertEqual(s2.tuition, 15000.0)
        self.assertEqual(s2.maintenance, 5000.0)
        self.assertEqual(s2.award_total, 25000.0)

        s3 = eng.sanctions["APL-0003"]
        self.assertEqual(s3.status, "INELIGIBLE")
        sch1_res = [
            r
            for r in eng.eligibility_by_app["APL-0003"]
            if r.scheme_code == "SCH-01"
        ][0]
        self.assertIn("BR-01_INVALID_CERT", sch1_res.rule_ids_failed)

    def test_ec02_sc_plus_disability_merit_relaxation_cap(self) -> None:
        fb = FixtureBuilder(self.tmp_dir)
        # SCH-01 cutoff = 60. SC (5) + disability (3) must NOT stack beyond 5 -> 55.00
        fb.add_app("APL-0001", name="Pass", category="SC", disability="true", pct="55.00")
        fb.add_app("APL-0002", name="Fail", category="SC", disability="true", pct="54.99")
        eng = fb.build()
        eng.run_commands_file()

        r1 = [r for r in eng.eligibility_by_app["APL-0001"] if r.scheme_code == "SCH-01"][0]
        r2 = [r for r in eng.eligibility_by_app["APL-0002"] if r.scheme_code == "SCH-01"][0]
        self.assertTrue(r1.eligible)
        self.assertFalse(r2.eligible)
        self.assertIn("BR-02_MERIT_CUTOFF", r2.rule_ids_failed)

    def test_ec03_tie_break_and_central_reduction_and_year2_book_grant(self) -> None:
        fb = FixtureBuilder(self.tmp_dir)
        # Same district (no maintenance), tuition 30k below caps -> SCH-01 & SCH-02 tie at 35k
        fb.add_app("APL-0001", name="Tie", inst="INS-001", pct="65.00", income="90000.00")
        # Year 2 with central scholarship Rs 10,000 -> book_grant=0, reduced by 10,000
        fb.add_app(
            "APL-0002",
            name="Central",
            inst="INS-001",
            year=2,
            pct="65.00",
            income="90000.00",
            central="true",
            central_amt="10000.00",
        )
        # Unrecognised institution -> INELIGIBLE
        fb.add_app("APL-0003", name="Unrec", inst="INS-003", pct="90.00")
        eng = fb.build()
        eng.run_commands_file()

        self.assertEqual(eng.sanctions["APL-0001"].scheme_code, "SCH-01")
        self.assertEqual(eng.sanctions["APL-0001"].award_total, 35000.0)

        s2 = eng.sanctions["APL-0002"]
        self.assertEqual(s2.book_grant, 0.0)
        self.assertEqual(s2.central_reduction, 10000.0)
        self.assertEqual(s2.award_total, 20000.0)

        self.assertEqual(eng.sanctions["APL-0003"].status, "INELIGIBLE")

    def test_ec04_district_seat_reservations_with_7_seats(self) -> None:
        fb = FixtureBuilder(self.tmp_dir)
        # 10 applicants in Mysuru for SCH-01 (7 seats -> 30%=2.1->2 women, 5%=0.35->0 dis)
        # Top 7 are all M; ranks 8 and 9 are F -> F at 8 and 9 take the 2 WOMEN seats!
        for i in range(1, 8):
            fb.add_app(
                f"APL-000{i}",
                name=f"Male {i}",
                gender="M",
                pct=f"{95 - i}.00",
                ts=f"2026-07-0{i} 10:00:00",
            )
        fb.add_app("APL-0008", name="Woman 1", gender="F", pct="80.00")
        fb.add_app("APL-0009", name="Woman 2", gender="F", pct="79.00")
        fb.add_app("APL-0010", name="Male 10", gender="M", pct="78.00")
        eng = fb.build()
        eng.run_commands_file()

        self.assertEqual(eng.sanctions["APL-0008"].status, "SELECTED")
        self.assertEqual(eng.sanctions["APL-0008"].reserved_category, "WOMEN")
        self.assertEqual(eng.sanctions["APL-0009"].status, "SELECTED")
        self.assertEqual(eng.sanctions["APL-0009"].reserved_category, "WOMEN")
        # Ranks 6 and 7 pushed to WAITLISTED because women seats filled first
        self.assertEqual(eng.sanctions["APL-0006"].status, "WAITLISTED")
        self.assertEqual(eng.sanctions["APL-0007"].status, "WAITLISTED")
        self.assertEqual(eng.sanctions["APL-0010"].status, "WAITLISTED")

    def test_ec05_bank_update_counter_reset_and_double_deferral(self) -> None:
        fb = FixtureBuilder(self.tmp_dir)
        # Exactly 75.00% attendance at RUN-2 passes
        fb.add_app("APL-0001", name="Exact75", att2="75.00", att3="80.00")
        # Adult with PARENT account fails RUN-1, fixed by BANK_UPDATE, passes RUN-2, fails att3
        fb.add_app(
            "APL-0002",
            name="BankFix",
            dob="2005-01-01",
            parent="Dad Two",
            holder_name="Dad Two",
            holder_rel="PARENT",
            att2="85.00",
            att3="60.00",
        )
        # Fails bank at RUN-1 and attendance at RUN-2 -> 2 consecutive deferrals -> CANCELLED
        fb.add_app("APL-0003", name="TwoFail", aadhaar="false", att2="65.00", att3="90.00")
        # Under 18 at RUN-1 (2008-11-01 -> 18 on 2026-11-01), PARENT valid RUN-1, invalid RUN-2
        fb.add_app(
            "APL-0004",
            name="Turns18",
            dob="2008-11-01",
            parent="Dad Four",
            holder_name="Dad Four",
            holder_rel="PARENT",
            att2="90.00",
            att3="90.00",
        )
        fb.commands = [
            "RUN_SCREENING|2026-08-20 10:00:00",
            "RUN_SELECTION|2026-08-25 10:00:00",
            "DISBURSE|RUN-1|2026-09-15",
            "BANK_UPDATE|APL-0002|BankFix|SELF|true|2027-01-20 10:00:00",
            "DISBURSE|RUN-2|2027-02-01",
            "DISBURSE|RUN-3|2027-05-31",
        ]
        eng = fb.build()
        eng.run_commands_file()

        l1 = [e for e in eng.ledger if e.application_id == "APL-0001"]
        self.assertEqual([e.status for e in l1], ["PAID", "PAID", "PAID"])

        l2 = [e for e in eng.ledger if e.application_id == "APL-0002"]
        self.assertEqual(l2[0].gate_result, "DEFER_BANK")
        self.assertEqual(l2[1].gate_result, "PASS")
        self.assertEqual(l2[1].instalment_pct, 80.0)
        # Consecutive deferral counter reset at RUN-2, so RUN-3 is DEFERRED (not CANCELLED)
        self.assertEqual(l2[2].gate_result, "DEFER_ATTENDANCE")
        self.assertEqual(l2[2].status, "DEFERRED")

        l3 = [e for e in eng.ledger if e.application_id == "APL-0003"]
        self.assertEqual(l3[0].status, "DEFERRED")
        self.assertEqual(l3[1].status, "CANCELLED")
        self.assertEqual(eng.sanctions["APL-0003"].status, "CANCELLED")

        l4 = [e for e in eng.ledger if e.application_id == "APL-0004"]
        self.assertEqual(l4[0].status, "PAID")  # Under 18 at RUN-1
        self.assertEqual(l4[1].gate_result, "DEFER_BANK")  # 18+ at RUN-2
        self.assertEqual(l4[2].status, "CANCELLED")  # 2nd deferral at RUN-3

    def test_ec06_dropout_day_30_vs_day_31(self) -> None:
        fb = FixtureBuilder(self.tmp_dir)
        fb.add_app("APL-0001", name="Day30")
        fb.add_app("APL-0002", name="Day31")
        fb.commands = [
            "RUN_SCREENING|2026-08-20 10:00:00",
            "RUN_SELECTION|2026-08-25 10:00:00",
            "DISBURSE|RUN-1|2026-09-15",
            "DROPOUT|APL-0001|2026-10-15|2026-10-15 16:00:00",
            "DROPOUT|APL-0002|2026-10-16|2026-10-16 16:00:00",
            "DISBURSE|RUN-2|2027-02-01",
            "DISBURSE|RUN-3|2027-05-31",
        ]
        eng = fb.build()
        eng.run_commands_file()

        l1 = [e for e in eng.ledger if e.application_id == "APL-0001"]
        l2 = [e for e in eng.ledger if e.application_id == "APL-0002"]
        self.assertEqual([e.status for e in l1], ["RECOVERABLE", "CANCELLED", "CANCELLED"])
        self.assertEqual([e.status for e in l2], ["PAID", "CANCELLED", "CANCELLED"])

    def test_ec07_renewals_50pct_24mo_cert_probation_and_termination(self) -> None:
        fb = FixtureBuilder(self.tmp_dir)
        fb.add_app("APL-0001", name="ExpiredCert", category="GEN", cert_date="2025-07-15", ts="2026-07-10 10:00:00")
        fb.add_app("APL-0002", name="Exact50", category="GEN")
        fb.add_app("APL-0003", name="ProbationTwice", category="GEN")
        fb.add_app("APL-0004", name="SC45", category="SC")
        fb.add_app("APL-0005", name="NotPromoted", category="GEN")
        fb.renewals = [
            ["APL-0001", "2027-28", "true", "50.00", "2025-07-15", "2027-07-15"],
            ["APL-0002", "2027-28", "true", "50.00", "2026-06-01", "2027-07-15"],
            ["APL-0003", "2027-28", "true", "47.50", "2026-06-01", "2027-07-15"],
            ["APL-0003", "2028-29", "true", "48.00", "2027-06-01", "2028-07-15"],
            ["APL-0004", "2027-28", "true", "45.00", "2026-06-01", "2027-07-15"],
            ["APL-0005", "2027-28", "false", "80.00", "2026-06-01", "2027-07-15"],
        ]
        fb.commands = [
            "RUN_SCREENING|2026-08-20 10:00:00",
            "RUN_SELECTION|2026-08-25 10:00:00",
            "RUN_RENEWALS|2027-28|2027-07-20",
            "RUN_RENEWALS|2028-29|2028-07-20",
        ]
        eng = fb.build()
        eng.run_commands_file()

        by_key = {(d.application_id, d.academic_year): d for d in eng.renewal_decisions}
        self.assertEqual(by_key[("APL-0001", "2027-28")].decision, "REJECTED_CERT")
        self.assertEqual(by_key[("APL-0002", "2027-28")].decision, "RENEWED")
        self.assertEqual(by_key[("APL-0002", "2027-28")].maintenance_pct, 100.0)
        self.assertEqual(by_key[("APL-0003", "2027-28")].decision, "ON_PROBATION")
        self.assertEqual(by_key[("APL-0003", "2027-28")].maintenance_pct, 50.0)
        self.assertEqual(by_key[("APL-0003", "2028-29")].decision, "TERMINATED")
        self.assertEqual(by_key[("APL-0004", "2027-28")].decision, "RENEWED")
        self.assertEqual(by_key[("APL-0005", "2027-28")].decision, "TERMINATED")

    def test_ec08_waitlist_movement_prorated_maintenance_full_tuition(self) -> None:
        fb = FixtureBuilder(self.tmp_dir)
        # 8 applicants at INS-002 (outside Mysuru -> 1500/mo * 10 = 15000 maint, 30000 tuition)
        for i in range(1, 9):
            fb.add_app(
                f"APL-000{i}",
                name=f"Stu {i}",
                gender="F" if i <= 3 else "M",
                inst="INS-002",
                pct=f"{95 - i}.00",
                income="80000.00",
            )
        fb.commands = [
            "RUN_SCREENING|2026-08-20 10:00:00",
            "RUN_SELECTION|2026-08-25 10:00:00",
            "DISBURSE|RUN-1|2026-09-15",
            "CANCEL_AWARD|APL-0001|2027-01-28 11:00:00|ADMISSION_CANCELLED",
            "DISBURSE|RUN-2|2027-02-01",
            "DISBURSE|RUN-3|2027-05-31",
        ]
        eng = fb.build()
        eng.run_commands_file()

        promoted = eng.sanctions["APL-0008"]
        self.assertEqual(promoted.status, "SELECTED")
        self.assertEqual(promoted.tuition, 30000.0)  # Paid in full
        self.assertEqual(promoted.maintenance, 6000.0)  # 4/10 of 15000
        self.assertEqual(promoted.book_grant, 0.0)  # Missed RUN-1
        self.assertEqual(promoted.award_total, 36000.0)

        l8 = [e for e in eng.ledger if e.application_id == "APL-0008"]
        self.assertEqual(len(l8), 2)
        self.assertEqual(l8[0].run_id, "RUN-2")
        self.assertEqual(l8[0].amount_paid, 21600.0)  # 60% of 36000
        self.assertEqual(l8[1].run_id, "RUN-3")
        self.assertEqual(l8[1].amount_paid, 14400.0)  # 40% of 36000

    def test_br12_duplicate_detection(self) -> None:
        fb = FixtureBuilder(self.tmp_dir)
        fb.add_app("APL-0001", name="Sowmya", dob="2007-03-14", parent="Rahul", scheme_applied="SCH-01", ts="2026-07-05 11:00:00")
        fb.add_app("APL-0002", name="Sowmya", dob="2007-03-14", parent="Rahul", scheme_applied="SCH-02", ts="2026-07-08 12:00:00")
        fb.add_app("APL-0003", name="Sowmya", dob="2007-03-14", parent="Rahul", scheme_applied="SCH-02", ts="2026-07-20 18:30:00")
        eng = fb.build()
        eng.run_commands_file()

        self.assertEqual(eng.sanctions["APL-0001"].status, "SELECTED")
        self.assertEqual(eng.sanctions["APL-0002"].status, "DUPLICATE")
        self.assertEqual(eng.sanctions["APL-0003"].status, "DUPLICATE")

    def test_stretch_goals_budget_cap_and_dbt_return(self) -> None:
        fb = FixtureBuilder(self.tmp_dir)
        # Set budget cap on SCH-01 (index 0) to 50000 -> only 1 applicant (award 50k) fits
        fb.schemes[0].append("50000.00")
        fb.add_app("APL-0001", name="Top", inst="INS-002", pct="90.00", income="80000.00")
        fb.add_app("APL-0002", name="Second", inst="INS-002", pct="80.00", income="80000.00")
        fb.commands = [
            "RUN_SCREENING|2026-08-20 10:00:00",
            "RUN_SELECTION|2026-08-25 10:00:00",
            "DISBURSE|RUN-1|2026-09-15",
            "DBT_RETURN|RUN-1|APL-0001",
            "DISBURSE|RUN-2|2027-02-01",
            "DISBURSE|RUN-3|2027-05-31",
        ]
        # Write schemes.csv with optional budget_cap column
        eng = fb.build()
        write_csv(
            self.tmp_dir / "schemes.csv",
            [
                "scheme_code",
                "scheme_name",
                "scheme_type",
                "income_ceiling",
                "merit_cutoff_pct",
                "eligible_courses",
                "tuition_cap",
                "maintenance_per_month",
                "book_grant",
                "seats_per_district",
                "renewal_min_marks_pct",
                "renewal_min_marks_sc_st_pct",
                "budget_cap",
            ],
            [fb.schemes[0], fb.schemes[1] + [""], fb.schemes[2] + [""], fb.schemes[3] + [""]],
        )
        eng = ScholarshipEngine(self.tmp_dir, quiet=True)
        eng.run_commands_file()

        self.assertEqual(eng.sanctions["APL-0001"].status, "SELECTED")
        self.assertEqual(eng.sanctions["APL-0002"].status, "WAITLISTED")
        l1 = [e for e in eng.ledger if e.application_id == "APL-0001"]
        self.assertEqual(l1[0].status, "DEFERRED")  # Returned DBT credit at RUN-1
        self.assertEqual(l1[1].amount_paid, 41000.0)  # RUN-1 (27500) + RUN-2 (13500) paid together


class TestSampleDataEndToEnd(unittest.TestCase):
    """End-to-end validation against the provided T043-PS-069-sample-data pack."""

    def test_sample_data_full_run_and_outputs(self) -> None:
        tmp_out = Path(tempfile.mkdtemp(prefix="ps069_out_"))
        try:
            eng = ScholarshipEngine(SAMPLE_DATA_DIR, quiet=True)
            eng.run_commands_file()
            eng.write_outputs(tmp_out)

            # Check all 5 CSV outputs exist and have expected row counts
            expected_files = [
                "eligibility_matrix.csv",
                "sanction.csv",
                "disbursement_ledger.csv",
                "renewal_decisions.csv",
                "utilisation.csv",
            ]
            for name in expected_files:
                self.assertTrue((tmp_out / name).exists(), f"Missing {name}")

            with open(tmp_out / "eligibility_matrix.csv", encoding="utf-8") as f:
                self.assertEqual(sum(1 for _ in f) - 1, 3000)  # 500 * 6
            with open(tmp_out / "sanction.csv", encoding="utf-8") as f:
                self.assertEqual(sum(1 for _ in f) - 1, 500)
            with open(tmp_out / "renewal_decisions.csv", encoding="utf-8") as f:
                self.assertEqual(sum(1 for _ in f) - 1, 63)
            with open(tmp_out / "utilisation.csv", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), 6)
                for row in rows:
                    self.assertGreaterEqual(
                        float(row["sanctioned_amount"]),
                        float(row["disbursed_amount"]),
                    )

            # Verify key planted scenarios
            self.assertEqual(eng.sanctions["APL-0374"].income_factor_pct, 100.0)
            self.assertEqual(eng.sanctions["APL-0464"].income_factor_pct, 50.0)
            self.assertEqual(eng.sanctions["APL-0107"].scheme_code, "SCH-01")
            self.assertEqual(eng.sanctions["APL-0147"].status, "INELIGIBLE")
            self.assertEqual(eng.sanctions["APL-0223"].status, "INELIGIBLE")
            self.assertEqual(eng.sanctions["APL-0109"].status, "DUPLICATE")
            self.assertEqual(eng.sanctions["APL-0326"].status, "DUPLICATE")
            self.assertEqual(eng.sanctions["APL-0428"].central_reduction, 20000.0)
            self.assertEqual(eng.sanctions["APL-0428"].award_total, 60000.0)
            self.assertEqual(eng.sanctions["APL-0120"].status, "CANCELLED")
            self.assertEqual(eng.sanctions["APL-0357"].status, "SELECTED")
            self.assertEqual(eng.sanctions["APL-0378"].status, "CANCELLED")

            ren = {d.application_id: d for d in eng.renewal_decisions}
            self.assertEqual(ren["APL-0150"].decision, "REJECTED_CERT")
            self.assertEqual(ren["APL-0266"].decision, "ON_PROBATION")
            self.assertEqual(ren["APL-0055"].decision, "RENEWED")
        finally:
            shutil.rmtree(tmp_out, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
