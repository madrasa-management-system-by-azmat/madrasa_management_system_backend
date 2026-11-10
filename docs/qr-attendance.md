# QR attendance

## Operator setup

1. Sign in with an active tenant staff account with `attendance.manage`.
2. Open Dashboard → Attendance → **QR scan attendance — open in new tab**.
3. Connect a **2D QR-capable** USB/Bluetooth scanner in keyboard/HID mode.
4. Enter/Tab suffix is optional: either submits immediately; without a suffix, the page automatically submits after **500ms without another character**.
5. Keep the scanner tab active and the Student ID input focused. Scan a card and wait for the saved confirmation before the next student.

No Save button is required. Input resets after a successful scan and focus returns to the scanner field. If entering an ID manually, paste the complete ID to avoid pauses submitting partial input. Wait for the saved confirmation before scanning the next card.

This implementation accepts keyboard/HID scanners. It does not use a phone/webcam, run in a background browser tab, or queue offline attendance.

## Daily policy

Each student's sequence resets on the server's institution-local date (`Asia/Karachi` in this installation):

| Scan | Movement |
| ---- | -------- |
| 1    | Entry    |
| 2    | Exit     |
| 3    | Entry    |
| 4    | Exit     |

A fifth scan is rejected. A new scan within 10 seconds of the preceding event is rejected to protect against accidental double reads. These are a maximum of four events, not four automatically generated records. A missed scan needs operational review; the system cannot infer an unrecorded exit.

The first scan marks daily attendance as present. An existing late mark is retained. Movement history is separate: exit does not make a student absent. Each accepted event records server timestamp, local date, sequence, direction, student, tenant and recording operator.

## Reliability and security

- QR content is the exact saved registration number, not a URL or full profile.
- The QR is an identifier, not authentication: supervise the scanner because a copied QR can identify the same student.
- Only active students in the operator's tenant are accepted. Guardians and platform superusers cannot operate this endpoint.
- Scan and daily attendance update commit in a single database transaction.
- Reusing the same UUID returns the original event without advancing the sequence. On uncertain network/server results, use **Retry this scan** before continuing. Do not refresh the page to retry an uncertain scan.
- Concurrent scans serialize through a write lock before reading the daily sequence. SQLite lock timeouts return 503; retries must retain the UUID.
- The live history displays the newest 100 events today; all events remain in the database and tenant backup registry.
- Scans cannot be edited or deleted through this API. Existing manual daily-attendance tools do not modify movement history.

## Endpoints

- `GET /api/v1/student-attendance/scanner/`: today's recent movement history.
- `POST /api/v1/student-attendance/scanner/`: `student_id` (registration string), `request_id` (UUID). No client-supplied date or direction is used.

Tests: `manage.py test apps.students.test_scanner`.
