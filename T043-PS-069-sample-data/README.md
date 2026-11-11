# PS-069 – Scholarship Eligibility and Disbursement Engine — Sample Data Pack

Prepared by 10 SECONDS for Team T043.

## Files

| File | What it holds | Row count |
|---|---|---|
| `schemes.csv` | 6 state schemes with ceilings, cut-offs, components and seats | 6 data rows |
| `institutions.csv` | 40 institutions across 10 districts with recognition flag | 40 data rows |
| `fee_structure.csv` | Annual tuition per institution per course | 73 data rows |
| `applications.csv` | 500 applications (one row per application; a person may appear more than once) | 500 data rows |
| `bank_accounts.csv` | Bank account details per application at the start | 500 data rows |
| `attendance_confirmations.csv` | Institution attendance confirmations for disbursement runs 2 and 3 | 1000 data rows |
| `renewals.csv` | Renewal file for 2027-28 | 63 data rows |
| `commands.txt` | Screening, selection, 3 disbursement runs, dropouts, cancellations, bank updates, renewals and prints | 28 command lines (excluding comments) |

Row numbers quoted below are 1-based data-row numbers (the header is row 0). Line numbers for `commands.txt` are physical line numbers including comment lines.

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with 2 places (no commas, no symbol); percentages as plain numbers (12.5 means 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix. An empty cell means "not applicable / not supplied" and only occurs in columns whose notes say so.

### `schemes.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| scheme_code | string | SCH-nn | — | — |
| scheme_name | string | — | — | — |
| scheme_type | enum | — | MERIT, MEANS, MERIT_CUM_MEANS, MINORITY | MINORITY needs minority = true |
| income_ceiling | decimal | Rs / year | — | above → INELIGIBLE_INCOME |
| merit_cutoff_pct | decimal | % | — | 0 = no merit test |
| eligible_courses | string | `;`-separated | — | — |
| tuition_cap | decimal | Rs / year | — | — |
| maintenance_per_month | decimal | Rs | — | x 10 months |
| book_grant | decimal | Rs | — | first year only |
| seats_per_district | int | — | — | empty = no seat limit |
| renewal_min_marks_pct | decimal | % | — | — |
| renewal_min_marks_sc_st_pct | decimal | % | — | — |

### `institutions.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| institution_code | string | INS-nnn | — | — |
| institution_name | string | — | — | — |
| district | string | — | — | maintenance only if != home_district |
| recognised | bool | — | — | — |

### `fee_structure.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| institution_code | string | — | institutions.csv | — |
| course | string | — | — | — |
| annual_tuition | decimal | Rs | — | — |

### `applications.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| application_id | string | APL-nnnn | — | numbered by application_ts |
| applicant_name | string | — | — | — |
| date_of_birth | date | — | — | under 18 on the run date → parent's account allowed |
| gender | enum | — | M, F | — |
| parent_name | string | — | — | identity key = name + DOB + parent name |
| category | enum | — | GEN, OBC, SC, ST | — |
| minority | bool | — | — | — |
| disability | bool | — | — | — |
| home_district | string | — | — | seat district |
| course | string | — | — | — |
| year_of_study | int | — | 1–5 | — |
| institution_code | string | — | institutions.csv | — |
| previous_exam_pct | decimal | % | — | — |
| family_income | decimal | Rs / year | — | — |
| income_cert_date | date | — | — | valid if <= 12 months old at application |
| scheme_applied | string | — | schemes.csv | screening still runs against every scheme |
| application_ts | timestamp | — | — | ranking tie-break |
| central_scholarship | bool | — | — | — |
| central_tuition_component | decimal | Rs | — | 0.00 if none |

### `bank_accounts.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| application_id | string | — | applications.csv | — |
| account_holder_name | string | — | — | — |
| holder_relation | enum | — | SELF, PARENT | — |
| ifsc | string | 11 chars | — | — |
| account_no_last4 | string | 4 digits | — | — |
| aadhaar_seeded | bool | — | — | — |

### `attendance_confirmations.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| run_id | string | — | RUN-2, RUN-3 | attendance for the period before the run |
| application_id | string | — | applications.csv | — |
| attendance_pct | decimal | % | — | gate: >= 75 |

### `renewals.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| application_id | string | — | applications.csv | — |
| academic_year | string | YYYY-YY | — | — |
| promoted | bool | — | — | — |
| prev_year_marks_pct | decimal | % | — | — |
| income_cert_date | date | — | — | certificate on file at renewal |
| submitted_date | date | — | — | — |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. An empty argument (two adjacent `|`) means "not supplied". Every command used in this pack:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `RUN_SCREENING` | `ts` | screen every application against every scheme |
| `RUN_SELECTION` | `ts` | final scheme per applicant, district ranking, selected / waitlisted lists, sanction |
| `PRINT_SANCTION` | `scheme_code` | sanction list (ALL = every scheme) |
| `DISBURSE` | `run_id|run_date` | RUN-1 = 50% at sanction (with book grant), RUN-2 = 30%, RUN-3 = 20%; gates per BR-06/07 |
| `DROPOUT` | `application_id|dropout_date|reported_ts` | institution reports a dropout |
| `CANCEL_AWARD` | `application_id|ts|reason` | award cancelled (waitlist moves) |
| `BANK_UPDATE` | `application_id|account_holder_name|holder_relation|aadhaar_seeded|ts` | corrected bank record |
| `RUN_RENEWALS` | `academic_year|run_date` | evaluate renewals.csv |
| `PRINT_UTILISATION` | `` | scheme utilisation report |
| `PRINT_LEDGER` | `application_id` | disbursement ledger for the applicant |

## Planted scenarios

Every edge case in the brief, mapped to the exact record where it occurs, followed by extra traps.

- **EC-01 Family income exactly Rs 1,00,000 and exactly Rs 2,50,001**
  - APL-0374: family income Rs 1,00,000.00 exactly → full means award; APL-0464: Rs 2,50,001.00 → 50% band (also above SCH-01's Rs 2,50,000 ceiling) — `applications.csv rows 374, 464`
- **EC-02 SC applicant with a disability flag and marks exactly 5 points below the cut-off**
  - APL-0433: SC with disability flag, previous exam 55.00% for SCH-01 (cut-off 60) — relaxations do not stack beyond 5 points, so 55.00 is exactly at the relaxed cut-off (eligible) — `applications.csv row 433`
- **EC-03 Two schemes with identical total award**
  - APL-0107: BSC at INS-015 in the home district (no maintenance), tuition below both caps, income < 1 L — SCH-01 (MERIT_CUM_MEANS) and SCH-02 (MEANS) give the same total (tuition + Rs 5,000 book grant); tie → MERIT_CUM_MEANS wins — `applications.csv row 107`
- **EC-04 District where 30% of 7 seats is non-integer**
  - Belagavi: 12 eligible SCH-01 applicants for 7 seats — 30% women = 2.1 seats and 5% disability = 0.35 seats (round as you document); unfilled reserved seats revert to open; ranks 8+ WAITLISTED — `applications.csv rows 78, 138, 217, 248, 262, 275 … 491 (12 rows)`
- **EC-05 Attendance confirmation exactly 75%**
  - APL-0496: institution confirms exactly 75.00% attendance for RUN-2 — meets '>= 75%', the 30% instalment is released — `attendance_confirmations.csv row 496`
- **EC-06 Dropout reported on day 30 after an instalment**
  - APL-0492 drops out on 2026-10-15 — exactly 30 days after the 2026-09-15 instalment → that instalment is RECOVERABLE; APL-0253 drops out on day 31 → not recoverable; future instalments cancelled for both — `commands.txt line 5 and line 6`
- **EC-07 Renewal with marks exactly 50% and income certificate dated 24 months ago**
  - APL-0150: application on 2026-07-10 with an income certificate of 2025-07-15 (valid, < 12 months); its 2027-28 renewal is submitted 2027-07-15 with previous-year marks exactly 50.00% (meets >= 50) and the same certificate — now exactly 24 months old: decide whether 'a new certificate every 2 years' is already due — `renewals.csv row 22`
- **EC-08 Waitlisted applicant selected with 4 months left in the year**
  - Tumakuru: 9 SCH-01 applicants for 7 seats; the top-ranked APL-0120 is cancelled on 2027-01-28, before the 2027-02-01 second instalment — the first waitlisted applicant is selected with 4 months (Feb–May) left: maintenance pro-rated to 4 months, tuition paid in full — `applications.csv rows 114, 120, 126, 280, 288, 357 … 478 (9 rows); commands.txt line 8`
- **Extra traps (not in the brief, but realistic):**
  - APL-0147: income certificate dated 2025-07-10 — older than 12 months at the July 2026 application → INVALID_CERT — `applications.csv row 147`
  - APL-0223 studies at INS-018 (not recognised) — ineligible for every scheme — `applications.csv row 223`
  - Same applicant (name, DOB, parent name) submits APL-0061 (SCH-01), APL-0109 (SCH-02) and APL-0326 (SCH-02 again) — screened once; the later SCH-02 application is discarded — `applications.csv rows 61, 109, 326`
  - APL-0428 holds a central scholarship with a Rs 20,000 tuition component — the state award is reduced by Rs 20,000 — `applications.csv row 428`
  - APL-0425 is 21 but the account is in the parent's name → DEFER_BANK at RUN-1; corrected by BANK_UPDATE before RUN-2, so RUN-2 pays the deferred and the due instalment (check your 'two consecutive deferrals' counter is reset) — `bank_accounts.csv row 425; commands.txt line 7`
  - APL-0378: bank not Aadhaar-seeded at RUN-1 (DEFER_BANK) and attendance 61.50% at RUN-2 (deferred again) — two consecutive deferrals cancel the remaining award — `attendance_confirmations.csv row 378`
  - Renewals: APL-0266 (GEN) 47.50% → ON_PROBATION with 50% maintenance; APL-0055 (SC) exactly 45.00% → meets the SC/ST threshold — `renewals.csv rows 7, 34`

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these CSV files (header row, same conventions as above, rows sorted as stated). Where the brief is silent on a format detail the choice below is binding for evaluation.

### `eligibility_matrix.csv`

One row per application per scheme.

Columns, in order: `application_id`, `scheme_code`, `eligible`, `rule_ids_failed`, `award_total`

### `sanction.csv`

One row per applicant (identity) with the final decision.

Columns, in order: `application_id`, `scheme_code`, `status`, `district`, `rank`, `reserved_category`, `tuition`, `maintenance`, `book_grant`, `central_reduction`, `income_factor_pct`, `award_total`

### `disbursement_ledger.csv`

One row per instalment attempt.

Columns, in order: `application_id`, `run_id`, `run_date`, `instalment_pct`, `amount_due`, `gate_result`, `amount_paid`, `status`

### `renewal_decisions.csv`

One row per renewal.

Columns, in order: `application_id`, `academic_year`, `decision`, `reason_code`, `maintenance_pct`

### `utilisation.csv`

One row per scheme.

Columns, in order: `scheme_code`, `selected`, `waitlisted`, `sanctioned_amount`, `disbursed_amount`, `recoverable_amount`

Binding choices: sanction `status` SELECTED, WAITLISTED, INELIGIBLE, DUPLICATE or CANCELLED; `gate_result` PASS, DEFER_BANK, DEFER_ATTENDANCE, CANCELLED; ledger `status` PAID, DEFERRED, CANCELLED, RECOVERABLE; renewal `decision` RENEWED, ON_PROBATION, TERMINATED, REJECTED_CERT. Amounts in Rs, 2 dp.
