# Design Document — PS-069 Scholarship Eligibility and Disbursement Engine (Team T043)

## 1. Architecture Overview

The engine is implemented in beginner-friendly, standard-library Python 3.10+ with no external dependencies:

- `engine/models.py`: Dataclasses for `Scheme`, `Institution`, `Applicant`, `BankAccount`, `RenewalRequest`, `EligibilityResult`, `SanctionRecord`, `LedgerEntry`, and `RenewalDecision`.
- `engine/loader.py`: CSV and command-file parsers plus date/rounding utilities (`add_months`, `round_half_up`, `round_money`).
- `engine/rules.py`: Pure functions implementing each business rule (`BR-01` to `BR-12`).
- `engine/engine.py`: `ScholarshipEngine` class maintaining state across commands and exporting the five CSV reports.
- `main.py`: Command-line entry point (`--data-dir`, `--output-dir`, `--quiet`).

---

## 2. Registered Business Rules (`BR-01` – `BR-12`)

| Rule ID | Name | Implementation & Binding Decisions | Function |
|---|---|---|---|
| **BR-01** | Income Slabs & Certificate Validity | Family income `<= 1,00,000`: 100% factor; `1,00,001–2,50,000`: 75%; `> 2,50,000` up to scheme `income_ceiling`: 50%. Above `income_ceiling` -> `BR-01_INELIGIBLE_INCOME`. Certificate age `>= 12` calendar months (`application_ts.date() >= add_months(income_cert_date, 12)`) -> `BR-01_INVALID_CERT`. Income factor scales `tuition` and `maintenance` across all schemes. | `get_income_factor_pct`, `is_income_cert_valid_at_application`, `screen_application_against_scheme` |
| **BR-02** | Merit Cut-off & Relaxations | When `merit_cutoff_pct > 0`, `previous_exam_pct` must meet `cutoff - min(5, cat_relax + dis_relax)` (`SC/ST = 5`, `OBC = 3`, `disability = 3`, stacked relaxation capped at `5`). `MINORITY` schemes also require `minority == true`. | `get_effective_merit_cutoff`, `screen_application_against_scheme` |
| **BR-03** | Course, Institution & Award Components | Course must be in scheme's `eligible_courses` (`BR-03_INELIGIBLE_COURSE`); institution must have `recognised == true` (`BR-03_UNRECOGNISED_INST`). Tuition = `min(actual_tuition, tuition_cap) * factor`; Maintenance = `(monthly_rate * 10) * factor` only when `institution.district != applicant.home_district`. | `screen_application_against_scheme` |
| **BR-04** | Multiple Schemes, Precedence & Central Offset | Each applicant receives at most one state scheme: highest `award_total`, ties broken by `MERIT_CUM_MEANS > MEANS > MERIT > MINORITY` (then `scheme_code`). Central scholarship reduces state award by `central_tuition_component` (clamped at 0). | `select_best_scheme` |
| **BR-05** | District Seats, Ranking & Reservations | Ranked within `(scheme_code, home_district)` by `previous_exam_pct` desc, `family_income` asc, `application_ts` asc. When `seats_per_district` (`S`) is set: `round_half_up(0.05 * S)` disability seats filled first, `round_half_up(0.30 * S)` women seats filled next, remaining/unfilled seats filled as `OPEN`. Ranks beyond `S` are `WAITLISTED`. | `allocate_district_seats` |
| **BR-06** | Instalments & Gate Deferrals | Disbursed `50%` at sanction (`RUN-1`, plus book grant), `30%` at `RUN-2`, `20%` at `RUN-3`. `RUN-2` and `RUN-3` require institution attendance `>= 75.00%` plus valid bank account. Failed gate defers amount to next run; successful run resets `consecutive_deferrals = 0`; 2 consecutive deferrals cancel remaining award. | `ScholarshipEngine.disburse` |
| **BR-07** | Bank Validation | Requires `aadhaar_seeded == true`, `SELF` matching `applicant_name`, OR `PARENT` matching `parent_name` **only if applicant is under 18 on `run_date`**. Failures defer as `DEFER_BANK`; `BANK_UPDATE` takes effect for subsequent runs. | `validate_bank_account`, `ScholarshipEngine.handle_bank_update` |
| **BR-08** | Fee Refund Guard (Dropout) | `DROPOUT` cancels all future instalments (`CANCELLED`). If `(dropout_date - last_paid_date).days <= 30`, the last `PAID` ledger row becomes `RECOVERABLE`. | `is_dropout_recoverable`, `ScholarshipEngine.handle_dropout` |
| **BR-09** | Annual Renewals | Keeps original sanctioned scheme even if cut-offs change. Requires `promoted == true` (else `TERMINATED`), income certificate `< 24` months old at `submitted_date` (else `REJECTED_CERT`), and marks `>= 50%` (`>= 45%` for `SC/ST`). First marks failure -> `ON_PROBATION` (`50%` maintenance); second marks failure -> `TERMINATED`. | `evaluate_renewal` |
| **BR-10** | Book Grant | One-time `Rs 5,000.00` in `year_of_study == 1` only, paid in full with `RUN-1`, never income-scaled, pro-rated, or renewed. | `screen_application_against_scheme`, `ScholarshipEngine._initialize_instalments` |
| **BR-11** | Waitlist Movement | `CANCEL_AWARD` before `RUN-2` promotes next ranked waitlisted applicant in that district (preserving quota if underfilled). Tuition is paid in full; maintenance is pro-rated to months remaining (`months_left / 10`), split across `RUN-2` (`60%`) and `RUN-3` (`40%`). Book grant is `0.00` since `RUN-1` has passed. | `months_remaining_in_academic_year`, `ScholarshipEngine.cancel_award` |
| **BR-12** | Duplicate Detection | Identity key `(applicant_name, date_of_birth, parent_name)`. Same person + same scheme discards later application; same person across multiple schemes keeps earliest application to screen once across all schemes and marks extra rows `DUPLICATE`. | `deduplicate_applications` |

---

## 3. Documented Design Choices for Edge Cases

1. **Non-integer reserved seats (`EC-04`)**: We use `round_half_up(x) = int(x + 0.5)`. For `S = 7` (`SCH-01`), `30%` gives `2.1 -> 2` women seats and `5%` gives `0.35 -> 0` disability seats. For `S = 10` (`SCH-03`), `30%` gives `3` women seats and `5%` gives `0.5 -> 1` disability seat.
2. **24-month renewal certificate boundary (`EC-07`)**: "New certificate every 2 years" is enforced when `submitted_date >= add_months(income_cert_date, 24)`. Thus a certificate dated `2025-07-15` submitted on `2027-07-15` (exactly 24 months old) receives `REJECTED_CERT`.
3. **Waitlist pro-ration (`EC-08`)**: In the 10-month Aug–May academic year, `CANCEL_AWARD` on `2027-01-28` leaves 4 full months (`Feb–May`), so maintenance is scaled by `4/10` while tuition is paid `100%` across `RUN-2` (`60%`) and `RUN-3` (`40%`).

---

## 4. Viva Preparation Notes

- **Why scheme precedence runs before district seat allocation**: Applicants are screened against all schemes first (`BR-04`) so each person competes for their highest-value scheme (`MERIT_CUM_MEANS > MEANS > MERIT > MINORITY` on ties) before seats per district (`BR-05`) are ranked.
- **How reservations and ranking interact**: All eligible district applicants for a scheme are first ordered by `(merit % desc, income asc, application_ts asc)`. Reserved disability (`5%`) and women (`30%`) buckets are filled first in merit order, and any unfilled quota seats revert to the `OPEN` pool.
- **Why instalment gates are evaluated at run time rather than at sanction**: Eligibility facts change during the academic year — an applicant who is 17 at `RUN-1` (`2026-09-15`) with a `PARENT` bank account can turn 18 before `RUN-2` (`2027-02-01`) and must switch to a `SELF` account (`BR-07`), and attendance (`>= 75%`) is only known for each preceding period at `RUN-2` and `RUN-3`.
