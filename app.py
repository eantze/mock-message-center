import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, g, redirect, render_template, url_for

app = Flask(__name__)
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app.db")
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "docs")

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            subject TEXT NOT NULL,
            preview TEXT NOT NULL,
            body_html TEXT NOT NULL,
            received_at TEXT NOT NULL,
            folder TEXT NOT NULL DEFAULT 'inbox',
            is_read INTEGER NOT NULL DEFAULT 0,
            claim_id INTEGER,
            appointment_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            display_name TEXT NOT NULL,
            mime_type TEXT NOT NULL DEFAULT 'application/pdf',
            FOREIGN KEY (message_id) REFERENCES messages(id)
        );
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor TEXT NOT NULL,
            specialty TEXT NOT NULL,
            location TEXT NOT NULL,
            starts_at TEXT NOT NULL,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            service_date TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Received'
        );
    """)
    db.commit()
    row = db.execute("SELECT COUNT(*) as c FROM messages").fetchone()
    if row["c"] == 0:
        seed_data(db)
    db.close()


# ---------------------------------------------------------------------------
# PDF generation (reportlab)
# ---------------------------------------------------------------------------

def generate_pdfs():
    os.makedirs(DOCS_DIR, exist_ok=True)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
    except ImportError:
        return

    pdfs = {
        "1095-B_2025.pdf": {
            "title": "Form 1095-B - Health Coverage",
            "lines": [
                "Form 1095-B  |  Tax Year 2025", "",
                "Health Coverage Statement", "",
                "Part I - Responsible Individual",
                "Name: Sample Member",
                "SSN: XXX-XX-1234", "",
                "Part II - Employer-Sponsored Coverage",
                "Insurance Company Health Plan",
                "Policy Number: HCP-2025-00412", "",
                "Part III - Covered Individuals",
                "Sample Member - All 12 months", "",
                "This form is provided for informational purposes.",
            ],
        },
        "1099-HC_2025.pdf": {
            "title": "Form 1099-HC - Individual Health Coverage",
            "lines": [
                "Form 1099-HC  |  Tax Year 2025", "",
                "Individual Mandate Health Insurance Coverage", "",
                "Subscriber: Sample Member",
                "Insurance Carrier: Insurance Company",
                "Policy Number: HCP-2025-00412", "",
                "Months of Coverage: January - December 2025",
                "Minimum Creditable Coverage: Yes", "",
                "This form certifies that you maintained minimum",
                "creditable health insurance coverage for the tax year.",
            ],
        },
        "1095-B_2024.pdf": {
            "title": "Form 1095-B - Health Coverage (2024)",
            "lines": [
                "Form 1095-B  |  Tax Year 2024", "",
                "Health Coverage Statement", "",
                "Part I - Responsible Individual",
                "Name: Sample Member",
                "SSN: XXX-XX-1234", "",
                "Part II - Employer-Sponsored Coverage",
                "Insurance Company Health Plan",
                "Policy Number: HCP-2024-00398", "",
                "Part III - Covered Individuals",
                "Sample Member - All 12 months",
            ],
        },
        "1099-HC_2024.pdf": {
            "title": "Form 1099-HC - Individual Health Coverage (2024)",
            "lines": [
                "Form 1099-HC  |  Tax Year 2024", "",
                "Individual Mandate Health Insurance Coverage", "",
                "Subscriber: Sample Member",
                "Insurance Carrier: Insurance Company",
                "Policy Number: HCP-2024-00398", "",
                "Months of Coverage: January - December 2024",
                "Minimum Creditable Coverage: Yes",
            ],
        },
        "privacy_notice_2025.pdf": {
            "title": "Privacy Practices Notice 2025",
            "lines": [
                "NOTICE OF PRIVACY PRACTICES", "",
                "Insurance Company",
                "Effective Date: January 1, 2025", "",
                "THIS NOTICE DESCRIBES HOW MEDICAL INFORMATION",
                "ABOUT YOU MAY BE USED AND DISCLOSED.", "",
                "Your Rights:",
                "- Right to inspect and copy your health information",
                "- Right to request amendment of records",
                "- Right to an accounting of disclosures",
                "- Right to request restrictions", "",
                "Contact: Privacy Officer, 1-800-555-0100",
            ],
        },
        "plan_changes_2026.pdf": {
            "title": "Plan Changes Effective 2026",
            "lines": [
                "PLAN AMENDMENT NOTICE", "",
                "Insurance Company Health Plan",
                "Effective: January 1, 2026", "",
                "Summary of Plan Changes:", "",
                "1. Telehealth copay reduced to $10",
                "2. Mental health visits - no prior auth required",
                "3. Preventive care expanded to include additional",
                "   screenings for members age 40+",
                "4. Out-of-pocket maximum adjusted to $6,500", "",
                "Please review your updated benefits summary.",
            ],
        },
    }

    for filename, info in pdfs.items():
        path = os.path.join(DOCS_DIR, filename)
        if os.path.exists(path):
            continue
        c = canvas.Canvas(path, pagesize=letter)
        width, height = letter
        c.setFont("Helvetica-Bold", 16)
        c.drawString(1 * inch, height - 1 * inch, info["title"])
        c.setFont("Helvetica", 11)
        y = height - 1.5 * inch
        for line in info["lines"]:
            if line == "":
                y -= 14
                continue
            c.drawString(1 * inch, y, line)
            y -= 16
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(1 * inch, 0.75 * inch, "Insurance Company  |  Confidential")
        c.save()


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

def seed_data(db):
    now = datetime.now()

    # --- Appointments ---
    appointments = [
        ("Dr. Sarah Chen", "Primary Care", "Riverside Medical Center, Suite 200",
         (now + timedelta(days=14)).strftime("%Y-%m-%d 09:00"),
         "Annual physical exam. Please fast for 12 hours before the appointment."),
        ("Dr. Michael Torres", "Dermatology", "Westside Dermatology Clinic",
         (now + timedelta(days=30)).strftime("%Y-%m-%d 14:30"),
         "Skin check follow-up. Bring previous biopsy results."),
        ("Dr. Emily Park", "Ophthalmology", "Vision Care Associates",
         (now + timedelta(days=7)).strftime("%Y-%m-%d 11:00"),
         "Annual eye exam. Bring current glasses or contacts."),
        ("Dr. James Wilson", "Cardiology", "Heart Health Center, Floor 3",
         (now + timedelta(days=45)).strftime("%Y-%m-%d 10:15"),
         "Routine cardiac checkup. Wear comfortable clothing for stress test."),
    ]
    appt_ids = []
    for a in appointments:
        cur = db.execute(
            "INSERT INTO appointments (doctor, specialty, location, starts_at, notes) VALUES (?,?,?,?,?)", a)
        appt_ids.append(cur.lastrowid)

    # --- Claims ---
    claims_data = [
        ("Riverside Medical Center", (now - timedelta(days=20)).strftime("%Y-%m-%d"), 245.00, "Payment Sent"),
        ("Westside Pharmacy", (now - timedelta(days=10)).strftime("%Y-%m-%d"), 85.50, "Approved"),
        ("City Imaging Lab", (now - timedelta(days=5)).strftime("%Y-%m-%d"), 1250.00, "Under Review"),
        ("Dr. Sarah Chen", (now - timedelta(days=35)).strftime("%Y-%m-%d"), 175.00, "Payment Sent"),
        ("Summit Physical Therapy", (now - timedelta(days=3)).strftime("%Y-%m-%d"), 320.00, "Received"),
    ]
    claim_ids = []
    for c in claims_data:
        cur = db.execute(
            "INSERT INTO claims (provider, service_date, amount, status) VALUES (?,?,?,?)", c)
        claim_ids.append(cur.lastrowid)

    # --- Messages ---
    messages = []

    # 4 Tax form messages
    messages.append((
        "Tax", "Your 2025 Form 1095-B is available",
        "Your 2025 tax form 1095-B is now available for download.",
        """<p>Dear Member,</p>
        <p>Your <strong>Form 1095-B</strong> for tax year 2025 is now available. This form confirms that you had qualifying health coverage during 2025.</p>
        <p>You can download your form using the attachment below. You may need this form when filing your federal tax return.</p>
        <p>If you have questions about this form, please contact our Member Services at 1-800-555-0100.</p>
        <p>Sincerely,<br>Insurance Company Tax Documents Team</p>""",
        (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"), "inbox", 0, None, None,
        [("1095-B_2025.pdf", "Form 1095-B (2025)")]
    ))
    messages.append((
        "Tax", "Your 2025 Form 1099-HC is available",
        "Your 2025 tax form 1099-HC is ready to view and download.",
        """<p>Dear Member,</p>
        <p>Your <strong>Form 1099-HC</strong> for tax year 2025 is now available. This form certifies that you maintained minimum creditable health insurance coverage.</p>
        <p>Please download and keep this form for your state tax filing records.</p>
        <p>Sincerely,<br>Insurance Company Tax Documents Team</p>""",
        (now - timedelta(days=2, hours=1)).strftime("%Y-%m-%d %H:%M"), "inbox", 0, None, None,
        [("1099-HC_2025.pdf", "Form 1099-HC (2025)")]
    ))
    messages.append((
        "Tax", "Your 2024 Form 1095-B is available",
        "Your 2024 tax form 1095-B is available for download.",
        """<p>Dear Member,</p>
        <p>Your <strong>Form 1095-B</strong> for tax year 2024 is available. This form was previously mailed to you and is now also available digitally.</p>
        <p>Sincerely,<br>Insurance Company Tax Documents Team</p>""",
        (now - timedelta(days=365)).strftime("%Y-%m-%d %H:%M"), "inbox", 1, None, None,
        [("1095-B_2024.pdf", "Form 1095-B (2024)")]
    ))
    messages.append((
        "Tax", "Your 2024 Form 1099-HC is available",
        "Your 2024 tax form 1099-HC is ready to view.",
        """<p>Dear Member,</p>
        <p>Your <strong>Form 1099-HC</strong> for tax year 2024 is available for download.</p>
        <p>Sincerely,<br>Insurance Company Tax Documents Team</p>""",
        (now - timedelta(days=365, hours=1)).strftime("%Y-%m-%d %H:%M"), "inbox", 1, None, None,
        [("1099-HC_2024.pdf", "Form 1099-HC (2024)")]
    ))

    # 5 Claim messages
    messages.append((
        "Claims", "Claim Payment Sent - Riverside Medical Center",
        "Your claim for Riverside Medical Center has been processed and payment sent.",
        f"""<p>Dear Member,</p>
        <p>We have completed processing your claim and payment has been sent.</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Provider:</td><td>Riverside Medical Center</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Service Date:</td><td>{(now - timedelta(days=20)).strftime('%B %d, %Y')}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Billed Amount:</td><td>$245.00</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Your Responsibility:</td><td>$30.00 (copay)</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Plan Paid:</td><td>$215.00</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Status:</td><td><span style="color:#2e7d32;">Payment Sent</span></td></tr>
        </table>
        <p>If you have questions, call Member Services at 1-800-555-0100.</p>""",
        (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"), "inbox", 0, claim_ids[0], None, []
    ))
    messages.append((
        "Claims", "Claim Approved - Westside Pharmacy",
        "Your pharmacy claim has been approved.",
        f"""<p>Dear Member,</p>
        <p>Your claim for prescription services has been approved.</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Provider:</td><td>Westside Pharmacy</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Service Date:</td><td>{(now - timedelta(days=10)).strftime('%B %d, %Y')}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Amount:</td><td>$85.50</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Status:</td><td><span style="color:#2e7d32;">Approved</span></td></tr>
        </table>""",
        (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M"), "inbox", 0, claim_ids[1], None, []
    ))
    messages.append((
        "Claims", "Claim Under Review - City Imaging Lab",
        "Your claim for City Imaging Lab is currently under review.",
        f"""<p>Dear Member,</p>
        <p>We have received your claim and it is currently under review.</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Provider:</td><td>City Imaging Lab</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Service Date:</td><td>{(now - timedelta(days=5)).strftime('%B %d, %Y')}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Amount:</td><td>$1,250.00</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Status:</td><td><span style="color:#e65100;">Under Review</span></td></tr>
        </table>
        <p>We typically complete reviews within 15 business days.</p>""",
        (now - timedelta(hours=18)).strftime("%Y-%m-%d %H:%M"), "inbox", 0, claim_ids[2], None, []
    ))
    messages.append((
        "Claims", "Claim Payment Sent - Dr. Sarah Chen",
        "Your claim for Dr. Sarah Chen has been paid.",
        f"""<p>Dear Member,</p>
        <p>Payment has been sent for your recent visit.</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Provider:</td><td>Dr. Sarah Chen</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Service Date:</td><td>{(now - timedelta(days=35)).strftime('%B %d, %Y')}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Amount:</td><td>$175.00</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Your Responsibility:</td><td>$25.00 (copay)</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Status:</td><td><span style="color:#2e7d32;">Payment Sent</span></td></tr>
        </table>""",
        (now - timedelta(days=15)).strftime("%Y-%m-%d %H:%M"), "inbox", 1, claim_ids[3], None, []
    ))
    messages.append((
        "Claims", "New Claim Received - Summit Physical Therapy",
        "We have received a new claim from Summit Physical Therapy.",
        f"""<p>Dear Member,</p>
        <p>We have received a new claim on your behalf.</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Provider:</td><td>Summit Physical Therapy</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Service Date:</td><td>{(now - timedelta(days=3)).strftime('%B %d, %Y')}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Amount:</td><td>$320.00</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Status:</td><td><span style="color:#1565c0;">Received</span></td></tr>
        </table>
        <p>We will process this claim and notify you of the outcome.</p>""",
        (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M"), "inbox", 0, claim_ids[4], None, []
    ))

    # 3 Legal/policy messages
    messages.append((
        "Legal", "Updated Privacy Practices Notice",
        "Important: Updated Notice of Privacy Practices for 2025.",
        """<p>Dear Member,</p>
        <p>We are writing to inform you of updates to our <strong>Notice of Privacy Practices</strong>, effective January 1, 2025.</p>
        <p>Key updates include:</p>
        <ul>
        <li>Enhanced protections for electronic health information</li>
        <li>Updated disclosure policies for telehealth services</li>
        <li>New rights regarding access to digital health records</li>
        </ul>
        <p>Please review the attached document for complete details.</p>
        <p>Sincerely,<br>Insurance Company Compliance Department</p>""",
        (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M"), "inbox", 1, None, None,
        [("privacy_notice_2025.pdf", "Privacy Practices Notice 2025")]
    ))
    messages.append((
        "Legal", "Important Plan Changes for 2026",
        "Review the upcoming changes to your health plan effective 2026.",
        """<p>Dear Member,</p>
        <p>We want to make you aware of important changes to your health plan benefits, effective <strong>January 1, 2026</strong>.</p>
        <p>Highlights include:</p>
        <ul>
        <li>Reduced telehealth copay ($10)</li>
        <li>Expanded mental health coverage with no prior authorization</li>
        <li>Additional preventive screenings for members 40+</li>
        <li>Updated out-of-pocket maximum</li>
        </ul>
        <p>Please review the attached plan amendment for full details.</p>
        <p>Sincerely,<br>Insurance Company Benefits Team</p>""",
        (now - timedelta(days=60)).strftime("%Y-%m-%d %H:%M"), "inbox", 1, None, None,
        [("plan_changes_2026.pdf", "Plan Amendment Notice 2026")]
    ))
    messages.append((
        "Legal", "Annual Rights & Responsibilities Notice",
        "Your annual member rights and responsibilities statement.",
        """<p>Dear Member,</p>
        <p>As part of our commitment to transparency, we are providing your annual <strong>Member Rights &amp; Responsibilities</strong> statement.</p>
        <p><strong>Your Rights:</strong></p>
        <ul>
        <li>Receive information about your plan, services, and providers</li>
        <li>Be treated with respect and dignity</li>
        <li>Privacy of your personal health information</li>
        <li>Voice complaints or appeals about coverage decisions</li>
        </ul>
        <p><strong>Your Responsibilities:</strong></p>
        <ul>
        <li>Provide accurate information for care and claims</li>
        <li>Understand your plan benefits and coverage</li>
        <li>Follow plan procedures for referrals and prior authorization</li>
        </ul>
        <p>Thank you for being a valued member.</p>""",
        (now - timedelta(days=90)).strftime("%Y-%m-%d %H:%M"), "inbox", 1, None, None, []
    ))

    # 4 Appointment messages
    messages.append((
        "Appointments", "Appointment Confirmation - Dr. Sarah Chen",
        "Your appointment with Dr. Sarah Chen has been confirmed.",
        f"""<p>Dear Member,</p>
        <p>Your upcoming appointment has been confirmed:</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Doctor:</td><td>Dr. Sarah Chen</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Specialty:</td><td>Primary Care</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Date/Time:</td><td>{(now + timedelta(days=14)).strftime('%B %d, %Y at 9:00 AM')}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Location:</td><td>Riverside Medical Center, Suite 200</td></tr>
        </table>
        <p><strong>Preparation:</strong> Please fast for 12 hours before the appointment. Bring your insurance card and photo ID.</p>
        <p>To reschedule or cancel, please call 1-800-555-0100 at least 24 hours in advance.</p>""",
        (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M"), "inbox", 0, None, appt_ids[0], []
    ))
    messages.append((
        "Appointments", "Appointment Reminder - Dr. Emily Park",
        "Reminder: You have an upcoming appointment with Dr. Emily Park.",
        f"""<p>Dear Member,</p>
        <p>This is a reminder about your upcoming appointment:</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Doctor:</td><td>Dr. Emily Park</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Specialty:</td><td>Ophthalmology</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Date/Time:</td><td>{(now + timedelta(days=7)).strftime('%B %d, %Y at 11:00 AM')}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Location:</td><td>Vision Care Associates</td></tr>
        </table>
        <p>Please bring your current glasses or contact lenses to this appointment.</p>""",
        (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M"), "inbox", 0, None, appt_ids[2], []
    ))
    messages.append((
        "Appointments", "Appointment Confirmation - Dr. Michael Torres",
        "Your appointment with Dr. Torres has been scheduled.",
        f"""<p>Dear Member,</p>
        <p>Your appointment has been confirmed:</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Doctor:</td><td>Dr. Michael Torres</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Specialty:</td><td>Dermatology</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Date/Time:</td><td>{(now + timedelta(days=30)).strftime('%B %d, %Y at 2:30 PM')}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Location:</td><td>Westside Dermatology Clinic</td></tr>
        </table>
        <p>Please bring any previous biopsy results to this appointment.</p>""",
        (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M"), "inbox", 1, None, appt_ids[1], []
    ))
    messages.append((
        "Appointments", "Appointment Scheduled - Dr. James Wilson",
        "Your cardiology appointment has been scheduled.",
        f"""<p>Dear Member,</p>
        <p>Your appointment has been confirmed:</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Doctor:</td><td>Dr. James Wilson</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Specialty:</td><td>Cardiology</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Date/Time:</td><td>{(now + timedelta(days=45)).strftime('%B %d, %Y at 10:15 AM')}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Location:</td><td>Heart Health Center, Floor 3</td></tr>
        </table>
        <p>Please wear comfortable clothing as a stress test may be performed.</p>""",
        (now - timedelta(days=12)).strftime("%Y-%m-%d %H:%M"), "inbox", 1, None, appt_ids[3], []
    ))

    # 4 General billing messages
    messages.append((
        "Billing", "Monthly Premium Payment Received",
        "Your April 2026 premium payment has been received.",
        """<p>Dear Member,</p>
        <p>We have received your premium payment for <strong>April 2026</strong>.</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Payment Amount:</td><td>$485.00</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Payment Method:</td><td>Auto-pay (Visa ending 4821)</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Coverage Period:</td><td>April 1 - April 30, 2026</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Next Payment Due:</td><td>May 1, 2026</td></tr>
        </table>
        <p>Thank you for your timely payment.</p>""",
        (now - timedelta(days=4)).strftime("%Y-%m-%d %H:%M"), "inbox", 0, None, None, []
    ))
    messages.append((
        "Billing", "Explanation of Benefits Available",
        "A new Explanation of Benefits (EOB) is available for review.",
        """<p>Dear Member,</p>
        <p>A new <strong>Explanation of Benefits (EOB)</strong> is available for your recent healthcare services.</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Service Date:</td><td>March 15, 2026</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Provider:</td><td>Riverside Medical Center</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Total Charges:</td><td>$245.00</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Plan Discount:</td><td>-$65.00</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Plan Paid:</td><td>$150.00</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Your Responsibility:</td><td>$30.00</td></tr>
        </table>
        <p>This is not a bill. If you owe a balance, you will receive a bill from your provider.</p>""",
        (now - timedelta(days=8)).strftime("%Y-%m-%d %H:%M"), "inbox", 1, None, None, []
    ))
    messages.append((
        "Billing", "Auto-Pay Enrollment Confirmation",
        "You have been successfully enrolled in automatic payments.",
        """<p>Dear Member,</p>
        <p>This confirms your enrollment in <strong>automatic premium payments</strong>.</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Payment Method:</td><td>Visa ending 4821</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Monthly Amount:</td><td>$485.00</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Payment Date:</td><td>1st of each month</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Effective:</td><td>January 1, 2026</td></tr>
        </table>
        <p>You can manage your auto-pay settings in your account at any time.</p>""",
        (now - timedelta(days=100)).strftime("%Y-%m-%d %H:%M"), "inbox", 1, None, None, []
    ))
    messages.append((
        "Billing", "Annual Deductible Status Update",
        "Your annual deductible progress for 2026.",
        """<p>Dear Member,</p>
        <p>Here is your year-to-date deductible status for <strong>2026</strong>:</p>
        <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Annual Deductible:</td><td>$1,500.00</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Amount Met:</td><td>$875.00</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Remaining:</td><td>$625.00</td></tr>
        </table>
        <div style="background:#e3f2fd;border-radius:4px;padding:12px;margin:16px 0;">
        <strong>Out-of-Pocket Maximum:</strong> $6,500.00<br>
        <strong>Amount Applied:</strong> $1,230.00<br>
        <strong>Remaining:</strong> $5,270.00
        </div>
        <p>Once your deductible is met, your plan will pay a larger portion of covered services.</p>""",
        (now - timedelta(days=6)).strftime("%Y-%m-%d %H:%M"), "inbox", 0, None, None, []
    ))

    # Insert all messages
    for m in messages:
        attachments_list = m[9] if len(m) > 9 else []
        cur = db.execute(
            """INSERT INTO messages (category, subject, preview, body_html, received_at, folder, is_read, claim_id, appointment_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            m[:9],
        )
        msg_id = cur.lastrowid
        for fname, display in attachments_list:
            db.execute(
                "INSERT INTO attachments (message_id, filename, display_name, mime_type) VALUES (?,?,?,?)",
                (msg_id, fname, display, "application/pdf"),
            )
    db.commit()


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

FOLDER_SIDEBAR = [
    ("inbox", "Inbox", "folder_view"),
    ("appointments", "Appointments", "appointments_page"),
    ("benefits", "Benefits", "benefits_page"),
    ("billing", "Billing", "billing_page"),
    ("claims", "Claims", "claims_page"),
    ("health", "Health Awareness", None),
    ("pharmacy", "Pharmacy", None),
    ("sent", "Sent", "folder_view"),
    ("archive", "Archive", "folder_view"),
    ("trash", "Trash", "folder_view"),
]

CATEGORIES = ["All", "Billing", "Claims", "Legal", "Appointments", "Tax"]


@app.context_processor
def inject_globals():
    return dict(
        folder_sidebar=FOLDER_SIDEBAR,
        categories=CATEGORIES,
    )


@app.template_filter("datefmt")
def datefmt_filter(value):
    """Format a datetime string for display."""
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return value
    now = datetime.now()
    if dt.date() == now.date():
        return dt.strftime("Today %I:%M %p")
    elif dt.year == now.year:
        return dt.strftime("%b %d")
    else:
        return dt.strftime("%b %d, %Y")


@app.template_filter("fulldatefmt")
def fulldatefmt_filter(value):
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return value
    return dt.strftime("%B %d, %Y at %I:%M %p")


@app.template_filter("apptdatefmt")
def apptdatefmt_filter(value):
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return value
    return dt.strftime("%B %d, %Y at %I:%M %p")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("folder_view", folder="inbox"))


@app.route("/folder/<folder>")
def folder_view(folder):
    db = get_db()
    messages = db.execute(
        "SELECT * FROM messages WHERE folder = ? ORDER BY received_at DESC", (folder,)
    ).fetchall()
    selected = messages[0] if messages else None
    attachments = []
    claim = None
    appointment = None
    if selected:
        attachments = db.execute(
            "SELECT * FROM attachments WHERE message_id = ?", (selected["id"],)
        ).fetchall()
        if selected["claim_id"]:
            claim = db.execute("SELECT * FROM claims WHERE id = ?", (selected["claim_id"],)).fetchone()
        if selected["appointment_id"]:
            appointment = db.execute("SELECT * FROM appointments WHERE id = ?", (selected["appointment_id"],)).fetchone()
    unread_count = db.execute(
        "SELECT COUNT(*) as c FROM messages WHERE folder = 'inbox' AND is_read = 0"
    ).fetchone()["c"]
    return render_template(
        "inbox.html",
        messages=messages, selected=selected, attachments=attachments,
        claim=claim, appointment=appointment,
        current_folder=folder, unread_count=unread_count, filter_category=None,
    )


@app.route("/folder/<folder>/category/<category>")
def folder_category_view(folder, category):
    db = get_db()
    if category == "All":
        messages = db.execute(
            "SELECT * FROM messages WHERE folder = ? ORDER BY received_at DESC", (folder,)
        ).fetchall()
    else:
        messages = db.execute(
            "SELECT * FROM messages WHERE folder = ? AND category = ? ORDER BY received_at DESC",
            (folder, category),
        ).fetchall()
    selected = messages[0] if messages else None
    attachments = []
    claim = None
    appointment = None
    if selected:
        attachments = db.execute(
            "SELECT * FROM attachments WHERE message_id = ?", (selected["id"],)
        ).fetchall()
        if selected["claim_id"]:
            claim = db.execute("SELECT * FROM claims WHERE id = ?", (selected["claim_id"],)).fetchone()
        if selected["appointment_id"]:
            appointment = db.execute("SELECT * FROM appointments WHERE id = ?", (selected["appointment_id"],)).fetchone()
    unread_count = db.execute(
        "SELECT COUNT(*) as c FROM messages WHERE folder = 'inbox' AND is_read = 0"
    ).fetchone()["c"]
    return render_template(
        "inbox.html",
        messages=messages, selected=selected, attachments=attachments,
        claim=claim, appointment=appointment,
        current_folder=folder, unread_count=unread_count, filter_category=category,
    )


@app.route("/message/<int:message_id>")
def message_detail(message_id):
    db = get_db()
    msg = db.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    if not msg:
        return "Message not found", 404
    if not msg["is_read"]:
        db.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (message_id,))
        db.commit()
        msg = db.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    folder = msg["folder"]
    messages = db.execute(
        "SELECT * FROM messages WHERE folder = ? ORDER BY received_at DESC", (folder,)
    ).fetchall()
    attachments = db.execute(
        "SELECT * FROM attachments WHERE message_id = ?", (message_id,)
    ).fetchall()
    claim = None
    appointment = None
    if msg["claim_id"]:
        claim = db.execute("SELECT * FROM claims WHERE id = ?", (msg["claim_id"],)).fetchone()
    if msg["appointment_id"]:
        appointment = db.execute("SELECT * FROM appointments WHERE id = ?", (msg["appointment_id"],)).fetchone()
    unread_count = db.execute(
        "SELECT COUNT(*) as c FROM messages WHERE folder = 'inbox' AND is_read = 0"
    ).fetchone()["c"]
    return render_template(
        "inbox.html",
        messages=messages, selected=msg, attachments=attachments,
        claim=claim, appointment=appointment,
        current_folder=folder, unread_count=unread_count, filter_category=None,
    )


@app.route("/appointments")
def appointments_page():
    db = get_db()
    appointments = db.execute("SELECT * FROM appointments ORDER BY starts_at ASC").fetchall()
    unread_count = db.execute(
        "SELECT COUNT(*) as c FROM messages WHERE folder = 'inbox' AND is_read = 0"
    ).fetchone()["c"]
    return render_template(
        "appointments.html", appointments=appointments,
        current_folder="appointments", unread_count=unread_count,
    )


@app.route("/benefits")
def benefits_page():
    unread_count = get_db().execute(
        "SELECT COUNT(*) as c FROM messages WHERE folder = 'inbox' AND is_read = 0"
    ).fetchone()["c"]
    return render_template("benefits.html", current_folder="benefits", unread_count=unread_count)


@app.route("/billing")
def billing_page():
    unread_count = get_db().execute(
        "SELECT COUNT(*) as c FROM messages WHERE folder = 'inbox' AND is_read = 0"
    ).fetchone()["c"]
    return render_template("billing_page.html", current_folder="billing", unread_count=unread_count)


@app.route("/claims")
def claims_page():
    db = get_db()
    claims = db.execute("SELECT * FROM claims ORDER BY service_date DESC").fetchall()
    unread_count = db.execute(
        "SELECT COUNT(*) as c FROM messages WHERE folder = 'inbox' AND is_read = 0"
    ).fetchone()["c"]
    return render_template(
        "claims_page.html", claims=claims,
        current_folder="claims", unread_count=unread_count,
    )


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

with app.app_context():
    init_db()
    generate_pdfs()

if __name__ == "__main__":
    app.run(debug=True, port=8080)
