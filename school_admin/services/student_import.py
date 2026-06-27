"""
StudentImportService
====================
Handles parsing, validation, and database writes for bulk student
CSV / Excel imports.

Design goals
------------
* All business logic here — views are thin wrappers.
* Pre-load all lookup data once to avoid N+1 queries.
* Each student row runs inside its own transaction.atomic() so that
  a single bad row does not block the rest of the file.
* Supports files with up to 5,000+ rows efficiently.
"""
import csv
import io
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class RowError:
    row: int
    column: str
    message: str


@dataclass
class ImportResult:
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[RowError] = field(default_factory=list)
    execution_time: float = 0.0

    def add_error(self, row: int, column: str, message: str):
        self.errors.append(RowError(row=row, column=column, message=message))
        self.failed += 1

    def to_dict(self):
        return {
            'total': self.total,
            'success': self.success,
            'failed': self.failed,
            'skipped': self.skipped,
            'execution_time': round(self.execution_time, 2),
            'errors': [
                {'row': e.row, 'column': e.column, 'message': e.message}
                for e in self.errors
            ],
        }


# ---------------------------------------------------------------------------
# Column header → internal key mapping
# ---------------------------------------------------------------------------

COLUMN_MAP = {
    # required
    'first name':           'first_name',
    'last name':            'last_name',
    'gender':               'gender',
    'date of birth':        'date_of_birth',
    'mobile number':        'mobile_number',
    'admission number':     'admission_number',
    'admission date':       'admission_date',
    'academic year':        'academic_year',
    'class':                'class_name',
    'section':              'section',
    'medium':               'medium',
    # optional personal
    'middle name':          'middle_name',
    'blood group':          'blood_group',
    'aadhaar number':       'aadhaar_number',
    # optional contact
    'alternate mobile':     'alternate_mobile',
    'email':                'email',
    'city':                 'city',
    'state':                'state',
    'address line 1':       'address_line1',
    'address line 2':       'address_line2',
    'pincode':              'pincode',
    # optional academic
    'roll number':          'roll_number',
    'udise number':         'udise_number',
    # optional demographics
    'category':             'category',
    'category (general/obc/sc/st)': 'category',
    'religion':             'religion',
    'caste':                'caste',
    'nationality':          'nationality',
    # optional parent / guardian
    'father name':          'father_name',
    'father mobile':        'father_mobile',
    'father occupation':    'father_occupation',
    'mother name':          'mother_name',
    'mother mobile':        'mother_mobile',
    'guardian name':        'guardian_name',
    'guardian mobile':      'guardian_mobile',
    'guardian relation':    'guardian_relation',
}

REQUIRED_COLUMNS = [
    'first_name', 'last_name', 'gender', 'date_of_birth',
    'mobile_number', 'admission_number', 'admission_date',
    'academic_year', 'class_name', 'section', 'medium',
]

VALID_GENDERS = {'male', 'female', 'other', 'm', 'f', 'o'}
VALID_CATEGORIES = {'general', 'obc', 'sc', 'st', ''}
DATE_FORMATS = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y']
MOBILE_RE = re.compile(r'^\d{10}$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _parse_date(value: str) -> Optional[date]:
    if not value:
        return None
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _clean_mobile(value: str) -> str:
    return re.sub(r'[\s\-\+]', '', value.strip())


def _normalise_header(header: str) -> str:
    return header.strip().lower().lstrip('\ufeff')


def _generate_email(first_name: str, last_name: str, admission_number: str, existing: set) -> str:
    base = f"{first_name.lower().replace(' ', '.')}.{last_name.lower().replace(' ', '.')}.{admission_number.lower().replace(' ', '')}@student.local"
    candidate = base
    counter = 1
    while candidate in existing:
        candidate = f"{base.split('@')[0]}_{counter}@student.local"
        counter += 1
    existing.add(candidate)
    return candidate


def _dob_to_password(dob: date) -> str:
    """Default password: DDMMYYYY"""
    return dob.strftime('%d%m%Y')


# ---------------------------------------------------------------------------
# Cache structure
# ---------------------------------------------------------------------------

def _build_lookup_cache(inst, branches):
    """
    Pre-fetch all lookup data into memory dicts so the import loop
    never issues more than O(1) lookups per row.
    """
    from super_admin.models import AcademicYear, Role
    from school_admin.models import SchoolClass, Medium

    academic_years = {ay.name: ay for ay in AcademicYear.objects.filter(is_active=True)}

    classes = {}
    for sc in SchoolClass.objects.filter(branch__in=branches).select_related('medium'):
        medium_name = sc.medium.name.strip().lower() if sc.medium else ''
        key = (sc.name.strip().lower(), (sc.section or '').strip().lower(), medium_name, sc.branch_id)
        classes[key] = sc

    mediums = {m.name.strip().lower(): m for m in Medium.objects.filter(institution=inst)}

    student_role, _ = Role.objects.get_or_create(role_name='STUDENT')
    user_role_obj, _ = Role.objects.get_or_create(role_name='USER')

    return {
        'academic_years': academic_years,
        'classes': classes,
        'mediums': mediums,
        'student_role': student_role,
        'user_role': user_role_obj,
    }


# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------

class StudentImportService:

    def parse_file(self, uploaded_file) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Parse the uploaded file and return (rows, header_errors).
        Each row is a dict keyed by internal column names.
        """
        name = uploaded_file.name.lower()
        if name.endswith('.csv'):
            return self._parse_csv(uploaded_file)
        elif name.endswith('.xlsx'):
            return self._parse_xlsx(uploaded_file)
        else:
            return [], ['Unsupported file type. Please upload a .csv or .xlsx file.']

    def _parse_csv(self, f) -> Tuple[List[Dict], List[str]]:
        try:
            content = f.read()
            try:
                text = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = content.decode('latin-1')
            reader = csv.DictReader(io.StringIO(text))
            return self._normalise_rows(reader), []
        except Exception as exc:
            logger.exception('CSV parse error')
            return [], [f'Failed to parse CSV: {exc}']

    def _parse_xlsx(self, f) -> Tuple[List[Dict], List[str]]:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
            ws = wb.active
            rows_iter = iter(ws.rows)
            header_row = next(rows_iter, None)
            if header_row is None:
                return [], ['Excel file appears to be empty.']
            headers = [str(c.value or '').strip() for c in header_row]
            dicts = []
            for row in rows_iter:
                d = {headers[i]: (str(row[i].value) if row[i].value is not None else '') for i in range(len(headers))}
                dicts.append(d)
            return self._normalise_rows(dicts), []
        except Exception as exc:
            logger.exception('XLSX parse error')
            return [], [f'Failed to parse Excel file: {exc}']

    def _normalise_rows(self, reader) -> List[Dict]:
        """Convert raw DictReader rows to internal-key dicts."""
        rows = []
        for raw in reader:
            row = {}
            for raw_key, value in raw.items():
                normalised = _normalise_header(raw_key)
                internal = COLUMN_MAP.get(normalised)
                if internal:
                    row[internal] = (value or '').strip()
            rows.append(row)
        return rows

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_row(
        self,
        row_num: int,
        row: Dict,
        cache: Dict,
        result: ImportResult,
        batch_admission_numbers: set,
        batch_aadhaar_numbers: set,
        batch_roll_keys: set,
        generated_emails: set,
    ) -> bool:
        """
        Returns True if row is valid.
        Appends errors to result and returns False otherwise.
        """
        ok = True

        # --- Required fields ---
        for col in REQUIRED_COLUMNS:
            if not row.get(col, '').strip():
                label = col.replace('_', ' ').title()
                result.add_error(row_num, label, f"'{label}' is required.")
                ok = False

        if not ok:
            return False

        # --- Date of Birth ---
        dob = _parse_date(row['date_of_birth'])
        if dob is None:
            result.add_error(row_num, 'Date of Birth', "Invalid date format. Use DD/MM/YYYY or YYYY-MM-DD.")
            ok = False

        # --- Admission Date ---
        adm_date = _parse_date(row['admission_date'])
        if adm_date is None:
            result.add_error(row_num, 'Admission Date', "Invalid date format. Use DD/MM/YYYY or YYYY-MM-DD.")
            ok = False

        # --- Mobile ---
        mobile = _clean_mobile(row['mobile_number'])
        if not MOBILE_RE.match(mobile):
            result.add_error(row_num, 'Mobile Number', "Mobile number must be exactly 10 digits.")
            ok = False

        # --- Email ---
        email = row.get('email', '').strip()
        if email and not EMAIL_RE.match(email):
            result.add_error(row_num, 'Email', "Invalid email format.")
            ok = False

        # --- Gender ---
        if row['gender'].strip().lower() not in VALID_GENDERS:
            result.add_error(row_num, 'Gender', f"Gender must be Male, Female, or Other (got '{row['gender']}').")
            ok = False

        # --- Academic Year ---
        ay_name = row['academic_year'].strip()
        if ay_name not in cache['academic_years']:
            result.add_error(row_num, 'Academic Year', f"Academic Year \"{ay_name}\" does not exist.")
            ok = False

        # --- Class / Section / Medium ---
        class_key = (
            row['class_name'].strip().lower(),
            row['section'].strip().lower(),
            row['medium'].strip().lower(),
        )
        # We need branch_id but don't know it at validate-time (branch determined later by the caller)
        # So we check if *any* matching class exists across any branch the inst has —
        # exact branch match is verified in _import_row.
        any_match = any(
            (k[0], k[1], k[2]) == class_key
            for k in cache['classes'].keys()
        )
        if not any_match:
            result.add_error(
                row_num, 'Class/Section/Medium',
                f"Class \"{row['class_name']}\" / Section \"{row['section']}\" / Medium \"{row['medium']}\" not found."
            )
            ok = False

        # --- Admission Number uniqueness (within this batch) ---
        adm_no = row['admission_number'].strip()
        if adm_no in batch_admission_numbers:
            result.add_error(row_num, 'Admission Number', f"Duplicate Admission Number \"{adm_no}\" in this file.")
            ok = False
        else:
            batch_admission_numbers.add(adm_no)

        # --- Aadhaar uniqueness ---
        aadhaar = row.get('aadhaar_number', '').strip()
        if aadhaar:
            if aadhaar in batch_aadhaar_numbers:
                result.add_error(row_num, 'Aadhaar Number', f"Duplicate Aadhaar Number \"{aadhaar}\" in this file.")
                ok = False
            else:
                batch_aadhaar_numbers.add(aadhaar)

        # --- Roll Number uniqueness within batch (year+class+section) ---
        roll = row.get('roll_number', '').strip()
        if roll:
            roll_key = (ay_name, row['class_name'].strip().lower(), row['section'].strip().lower(), roll)
            if roll_key in batch_roll_keys:
                result.add_error(row_num, 'Roll Number', f"Duplicate Roll Number \"{roll}\" for this class/year in this file.")
                ok = False
            else:
                batch_roll_keys.add(roll_key)

        return ok

    # ------------------------------------------------------------------
    # Single-row import (wrapped in its own atomic block)
    # ------------------------------------------------------------------

    def _import_row(
        self,
        row_num: int,
        row: Dict,
        inst,
        branch,
        cache: Dict,
        result: ImportResult,
        generated_emails: set,
    ) -> bool:
        from django.db import transaction
        from django.contrib.auth import get_user_model
        from school_admin.models import RoleProfile, UserRole, SchoolClass
        from student.models import UserProfile
        from super_admin.models import SchoolRole

        User = get_user_model()

        try:
            with transaction.atomic():
                # ---- Resolve Academic Year ----
                ay = cache['academic_years'][row['academic_year'].strip()]

                # ---- Resolve SchoolClass ----
                class_key = (
                    row['class_name'].strip().lower(),
                    row['section'].strip().lower(),
                    row['medium'].strip().lower(),
                    branch.id,
                )
                school_class = cache['classes'].get(class_key)
                if school_class is None:
                    result.add_error(
                        row_num, 'Class/Section/Medium',
                        f"Class \"{row['class_name']}\" / Section \"{row['section']}\" / Medium \"{row['medium']}\" not found in branch \"{branch.name}\"."
                    )
                    result.failed += 1
                    if row['admission_number'].strip() in {e.message for e in result.errors if e.row < row_num}:
                        pass  # already counted
                    return False

                # ---- DB-level duplicate checks ----
                adm_no = row['admission_number'].strip()
                if RoleProfile.objects.filter(rp_grno=adm_no, institution=inst).exists():
                    result.add_error(row_num, 'Admission Number', f"Admission Number \"{adm_no}\" already exists in the database.")
                    return False

                aadhaar = row.get('aadhaar_number', '').strip()
                if aadhaar and RoleProfile.objects.filter(rp_uid_no=aadhaar, institution=inst).exists():
                    result.add_error(row_num, 'Aadhaar Number', f"Aadhaar Number \"{aadhaar}\" already exists in the database.")
                    return False

                roll = row.get('roll_number', '').strip()
                if roll and RoleProfile.objects.filter(
                    rp_roll_no=roll,
                    rp_school_class=school_class,
                    academic_year=ay,
                    institution=inst,
                ).exists():
                    result.add_error(row_num, 'Roll Number', f"Roll Number \"{roll}\" already used in this class/year.")
                    return False

                # ---- Resolve or create User ----
                dob = _parse_date(row['date_of_birth'])
                email = row.get('email', '').strip()
                if not email:
                    email = _generate_email(
                        row['first_name'], row['last_name'],
                        adm_no, generated_emails,
                    )
                else:
                    generated_emails.add(email)

                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'username': email,
                        'first_name': row['first_name'].strip(),
                        'last_name': row['last_name'].strip(),
                        'middle_name': row.get('middle_name', '').strip() or None,
                        'mobile_no': _clean_mobile(row['mobile_number']),
                        'is_active': True,
                    }
                )
                if created:
                    default_pw = _dob_to_password(dob) if dob else 'student@123'
                    user.set_password(default_pw)
                    user.save()
                else:
                    # Update name fields if user is new to this institution
                    if not RoleProfile.objects.filter(user=user, institution=inst).exists():
                        user.first_name = row['first_name'].strip()
                        user.last_name = row['last_name'].strip()
                        user.middle_name = row.get('middle_name', '').strip() or user.middle_name
                        user.mobile_no = _clean_mobile(row['mobile_number']) or user.mobile_no
                        user.save()

                # ---- Create / update UserProfile ----
                adm_date = _parse_date(row.get('admission_date', ''))
                profile_defaults = {
                    'date_of_birth': dob,
                    'gender': row.get('gender', '').strip() or None,
                    'blood_group': row.get('blood_group', '').strip() or None,
                    'alternate_mobile': _clean_mobile(row.get('alternate_mobile', '')) or None,
                    'admission_date': adm_date,
                    'father_name': row.get('father_name', '').strip() or None,
                    'father_mobile': _clean_mobile(row.get('father_mobile', '')) or None,
                    'father_occupation': row.get('father_occupation', '').strip() or None,
                    'mother_name': row.get('mother_name', '').strip() or None,
                    'mother_mobile': _clean_mobile(row.get('mother_mobile', '')) or None,
                    'parent_full_name': row.get('father_name', '').strip() or None,
                    'parent_mobile_no': _clean_mobile(row.get('father_mobile', '')) or None,
                    'gardian_name': row.get('guardian_name', '').strip() or None,
                    'gardian_mobile_no': _clean_mobile(row.get('guardian_mobile', '')) or None,
                    'guardian_relation': row.get('guardian_relation', '').strip() or None,
                    'category': row.get('category', '').strip() or None,
                    'religion': row.get('religion', '').strip() or None,
                    'caste': row.get('caste', '').strip() or None,
                    'nationality': row.get('nationality', '').strip() or None,
                }
                # Strip None to not overwrite existing data
                profile_defaults_clean = {k: v for k, v in profile_defaults.items() if v is not None}
                UserProfile.objects.update_or_create(user=user, defaults=profile_defaults_clean)

                # ---- Resolve / create Address on RoleProfile ----
                from super_admin.models import Address
                address_line1 = row.get('address_line1', '').strip()
                address_line2 = row.get('address_line2', '').strip()
                city = row.get('city', '').strip()
                state_val = row.get('state', '').strip() or 'Gujarat'
                pincode = row.get('pincode', '').strip()

                address_obj = None
                if address_line1 or city:
                    address_obj = Address.objects.create(
                        addressline1=address_line1,
                        addressline2=address_line2 or None,
                        city=city,
                        state=state_val,
                        pincode=pincode,
                    )

                # ---- Create RoleProfile (Student) ----
                student_role = cache['student_role']
                SchoolRole.objects.get_or_create(role=student_role, school=inst)

                role_profile = RoleProfile.objects.create(
                    user=user,
                    role=student_role,
                    role_name='STUDENT',
                    email_id=email,
                    mobile_no=_clean_mobile(row['mobile_number']),
                    institution=inst,
                    branch=branch,
                    address_record=address_obj,
                    academic_year=ay,
                    rp_school_class=school_class,
                    rp_roll_no=roll or None,
                    rp_grno=adm_no,
                    rp_uid_no=aadhaar or None,
                    rp_udise_no=row.get('udise_number', '').strip() or None,
                )

                # ---- Create UserRole ----
                UserRole.objects.get_or_create(
                    user=user,
                    role=student_role,
                    institution=inst,
                    branch=branch,
                    defaults={'academic_year': ay},
                )

                result.success += 1
                return True

        except Exception as exc:
            logger.exception('Row %d import failed', row_num)
            result.add_error(row_num, 'System', f"Unexpected error: {exc}")
            return False

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, uploaded_file, inst, branch, result: Optional[ImportResult] = None) -> ImportResult:
        """
        Parse the file, validate each row, and import valid rows.
        Returns an ImportResult with full counts and errors.
        """
        if result is None:
            result = ImportResult()

        start = time.perf_counter()

        rows, parse_errors = self.parse_file(uploaded_file)
        if parse_errors:
            for msg in parse_errors:
                result.add_error(0, 'File', msg)
            result.execution_time = time.perf_counter() - start
            return result

        result.total = len(rows)
        if result.total == 0:
            result.add_error(0, 'File', 'The uploaded file contains no data rows.')
            result.execution_time = time.perf_counter() - start
            return result

        cache = _build_lookup_cache(inst, [branch])

        # Batch uniqueness sets (prevent duplicates within the same file)
        batch_admission_numbers = set()
        batch_aadhaar_numbers = set()
        batch_roll_keys = set()
        generated_emails = set()

        for idx, row in enumerate(rows, start=2):  # start=2 because row 1 is header
            # Skip fully empty rows
            if all(not v for v in row.values()):
                result.skipped += 1
                continue

            valid = self._validate_row(
                idx, row, cache, result,
                batch_admission_numbers,
                batch_aadhaar_numbers,
                batch_roll_keys,
                generated_emails,
            )
            if not valid:
                continue

            self._import_row(idx, row, inst, branch, cache, result, generated_emails)

        result.execution_time = time.perf_counter() - start
        logger.info(
            'Import complete: total=%d success=%d failed=%d skipped=%d time=%.2fs',
            result.total, result.success, result.failed, result.skipped, result.execution_time
        )
        return result
