import sqlite3
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger('retina_xai.database')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'database', 'database.db')

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

def is_postgres():
    return bool(DATABASE_URL and DATABASE_URL.startswith('postgresql://'))

def get_db_connection():
    """
    Returns a database connection.
    Uses PostgreSQL if DATABASE_URL is configured and psycopg2 is available;
    otherwise falls back cleanly to local SQLite.
    """
    if is_postgres():
        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = False
            return conn
        except Exception as e:
            logger.warning(f"Failed connecting to PostgreSQL via DATABASE_URL: {e}. Falling back to SQLite.")

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=(), fetchone=False, fetchall=False, commit=False, return_id=False):
    """
    Database-agnostic query executor handling parameter markers:
    - Automatically converts '?' markers to '%s' for PostgreSQL.
    - Uniformly returns dict or list of dicts.
    """
    conn = get_db_connection()
    use_pg = is_postgres() and hasattr(conn, 'cursor_factory')

    if use_pg:
        # Translate '?' placeholders to '%s' for psycopg2
        pg_query = query.replace('?', '%s')
        if return_id and 'INSERT INTO' in pg_query.upper() and 'RETURNING id' not in pg_query.upper():
            pg_query = pg_query.rstrip().rstrip(';') + ' RETURNING id;'

        import psycopg2.extras
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cursor.execute(pg_query, params)
            last_id = None
            if return_id:
                ret = cursor.fetchone()
                last_id = ret['id'] if ret else None
            if commit:
                conn.commit()
            if fetchone:
                row = cursor.fetchone()
                return dict(row) if row else None
            if fetchall:
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
            return last_id
        finally:
            cursor.close()
            conn.close()
    else:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            last_id = cursor.lastrowid if return_id else None
            if commit:
                conn.commit()
            if fetchone:
                row = cursor.fetchone()
                return dict(row) if row else None
            if fetchall:
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
            return last_id
        finally:
            cursor.close()
            conn.close()

def init_db():
    """
    Initializes database schema and executes safe, non-destructive migrations.
    Preserves all existing records.
    """
    conn = get_db_connection()
    use_pg = is_postgres() and hasattr(conn, 'cursor_factory')
    cursor = conn.cursor()

    try:
        if use_pg:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    email TEXT,
                    phone_number TEXT UNIQUE,
                    age INTEGER,
                    gender TEXT,
                    role TEXT DEFAULT 'Clinician / Screener',
                    is_active INTEGER DEFAULT 1,
                    last_login TEXT,
                    created_at TEXT NOT NULL
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS screenings (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT UNIQUE NOT NULL,
                    user_id INTEGER,
                    image_path TEXT NOT NULL,
                    heatmap_path TEXT,
                    overlay_path TEXT,
                    seg_overlay_path TEXT DEFAULT '',
                    seg_mask_path TEXT DEFAULT '',
                    detected_lesions TEXT DEFAULT '',
                    prediction TEXT NOT NULL,
                    class_id INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    probabilities TEXT NOT NULL,
                    risk_status TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    referral_required INTEGER DEFAULT 0,
                    is_demo INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_screenings_user_id ON screenings(user_id);")
            conn.commit()
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS screenings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT UNIQUE NOT NULL,
                    user_id INTEGER,
                    image_path TEXT NOT NULL,
                    heatmap_path TEXT,
                    overlay_path TEXT,
                    seg_overlay_path TEXT DEFAULT '',
                    seg_mask_path TEXT DEFAULT '',
                    detected_lesions TEXT DEFAULT '',
                    prediction TEXT NOT NULL,
                    class_id INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    probabilities TEXT NOT NULL,
                    risk_status TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    referral_required INTEGER DEFAULT 0,
                    is_demo INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
            """)
            conn.commit()

            # Non-destructive migration checks for existing SQLite screenings table
            cursor.execute("PRAGMA table_info(screenings)")
            existing_s_cols = [r['name'] if isinstance(r, dict) or hasattr(r, 'keys') else r[1] for r in cursor.fetchall()]
            if 'user_id' not in existing_s_cols:
                cursor.execute("ALTER TABLE screenings ADD COLUMN user_id INTEGER;")
            if 'seg_overlay_path' not in existing_s_cols:
                cursor.execute("ALTER TABLE screenings ADD COLUMN seg_overlay_path TEXT DEFAULT '';")
            if 'seg_mask_path' not in existing_s_cols:
                cursor.execute("ALTER TABLE screenings ADD COLUMN seg_mask_path TEXT DEFAULT '';")
            if 'detected_lesions' not in existing_s_cols:
                cursor.execute("ALTER TABLE screenings ADD COLUMN detected_lesions TEXT DEFAULT '';")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_screenings_user_id ON screenings(user_id);")
            conn.commit()

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT,
                    phone_number TEXT UNIQUE,
                    mobile_number TEXT UNIQUE,
                    age INTEGER,
                    gender TEXT,
                    role TEXT DEFAULT 'Clinician / Screener',
                    is_active INTEGER DEFAULT 1,
                    last_login TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.commit()

            cursor.execute("PRAGMA table_info(users)")
            existing_u_cols = [r['name'] if isinstance(r, dict) or hasattr(r, 'keys') else r[1] for r in cursor.fetchall()]
            if 'phone_number' not in existing_u_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN phone_number TEXT;")
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone_number);")
            if 'mobile_number' not in existing_u_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN mobile_number TEXT;")
                cursor.execute("UPDATE users SET mobile_number = phone_number WHERE mobile_number IS NULL AND phone_number IS NOT NULL;")
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_mobile ON users(mobile_number);")
            if 'updated_at' not in existing_u_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN updated_at TEXT;")
                cursor.execute("UPDATE users SET updated_at = created_at WHERE updated_at IS NULL;")
            if 'last_login' not in existing_u_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN last_login TEXT;")
            conn.commit()

        # Seed Demo User & Demo Screenings if completely empty
        seed_demo_user(conn, use_pg)
        seed_demo_screenings_if_empty(conn, use_pg)
    finally:
        cursor.close()
        conn.close()

def seed_demo_user(conn, use_pg=False):
    cursor = conn.cursor()
    try:
        check_sql = "SELECT COUNT(*) FROM users WHERE phone_number = %s OR mobile_number = %s OR email = %s" if use_pg else "SELECT COUNT(*) FROM users WHERE phone_number = ? OR mobile_number = ? OR email = ?"
        cursor.execute(check_sql, ('+919876543210', '+919876543210', 'demo@drishtiai.org'))
        res = cursor.fetchone()
        count = res[0] if res is not None else 0
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if count == 0:
            insert_sql = """
                INSERT INTO users (full_name, email, phone_number, mobile_number, age, gender, role, is_active, created_at, updated_at, last_login)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s)
            """ if use_pg else """
                INSERT INTO users (full_name, email, phone_number, mobile_number, age, gender, role, is_active, created_at, updated_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """
            cursor.execute(insert_sql, (
                'Dr. Ananya Sharma', 'demo@drishtiai.org', '+919876543210', '+919876543210', 34, 'Female',
                'Consultant Ophthalmologist', now_str, now_str, now_str
            ))
            conn.commit()
        else:
            # If demo user existed from legacy schema without phone_number or mobile_number, populate it
            update_sql = "UPDATE users SET phone_number = %s, mobile_number = %s, updated_at = %s WHERE email = %s AND (phone_number IS NULL OR mobile_number IS NULL)" if use_pg else "UPDATE users SET phone_number = ?, mobile_number = ?, updated_at = ? WHERE email = ? AND (phone_number IS NULL OR mobile_number IS NULL)"
            cursor.execute(update_sql, ('+919876543210', '+919876543210', now_str, 'demo@drishtiai.org'))
            conn.commit()
    finally:
        cursor.close()

def seed_demo_screenings_if_empty(conn, use_pg=False):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM screenings")
        res = cursor.fetchone()
        count = res[0] if res is not None else 0
        if count == 0:
            demo_screenings = [
                (
                    'RXT-1001', 1,
                    'static/samples/sample_no_dr.jpg',
                    'static/samples/sample_no_dr_heatmap.jpg',
                    'static/samples/sample_no_dr_overlay.jpg',
                    'No Diabetic Retinopathy', 0, 96.8,
                    json.dumps([96.8, 2.1, 0.7, 0.3, 0.1]),
                    'Routine annual screening recommended. Retinal architecture within normal limits.',
                    'Fundus clear. Normal foveal avascular zone and optic disc margins. Routine 12-month follow-up.',
                    0, 1, '2026-08-28 10:15:22'
                ),
                (
                    'RXT-1002', 1,
                    'static/samples/sample_mild.jpg',
                    'static/samples/sample_mild_heatmap.jpg',
                    'static/samples/sample_mild_overlay.jpg',
                    'Mild Diabetic Retinopathy', 1, 88.4,
                    json.dumps([6.2, 88.4, 4.1, 1.0, 0.3]),
                    'Early screening observation: Microaneurysms detected. Monitor closely in 6-12 months.',
                    'Isolated microaneurysms present in inferior temporal arcade. Blood glucose counseling recommended.',
                    0, 1, '2026-08-29 11:42:05'
                ),
                (
                    'RXT-1003', 1,
                    'static/samples/sample_moderate.jpg',
                    'static/samples/sample_moderate_heatmap.jpg',
                    'static/samples/sample_moderate_overlay.jpg',
                    'Moderate Diabetic Retinopathy', 2, 91.2,
                    json.dumps([2.0, 4.3, 91.2, 2.1, 0.4]),
                    'Refer for ophthalmic evaluation. Multiple lesions and microaneurysms observed.',
                    'Dot and blot hemorrhages visible in macula periphery. Hard exudates noted. Tele-ophthalmology referral initiated.',
                    1, 1, '2026-08-30 14:08:49'
                ),
                (
                    'RXT-1004', 1,
                    'static/samples/sample_severe.jpg',
                    'static/samples/sample_severe_heatmap.jpg',
                    'static/samples/sample_severe_overlay.jpg',
                    'Severe Diabetic Retinopathy', 3, 94.6,
                    json.dumps([0.4, 1.2, 3.1, 94.6, 0.7]),
                    'Urgent ophthalmic referral required. Extensive intraretinal hemorrhages and vascular changes.',
                    'Severe 4-quadrant hemorrhages with venous beading. High risk of progression to PDR. Fast-tracked to district hospital.',
                    1, 1, '2026-09-01 09:25:30'
                ),
                (
                    'RXT-1005', 1,
                    'static/samples/sample_proliferative.jpg',
                    'static/samples/sample_proliferative_heatmap.jpg',
                    'static/samples/sample_proliferative_overlay.jpg',
                    'Proliferative Diabetic Retinopathy', 4, 97.1,
                    json.dumps([0.1, 0.3, 0.8, 1.7, 97.1]),
                    'Critical ophthalmic referral. Neovascularization and elevated risk of retinal detachment.',
                    'Neovascularization at disc (NVD) with fibrous proliferation. Urgent tertiary eye center referral issued.',
                    1, 1, '2026-09-02 16:50:12'
                )
            ]
            for s in demo_screenings:
                insert_sql = """
                    INSERT INTO screenings (
                        patient_id, user_id, image_path, heatmap_path, overlay_path,
                        prediction, class_id, confidence, probabilities,
                        risk_status, notes, referral_required, is_demo, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                execute_query(insert_sql, s, commit=True)
    finally:
        cursor.close()

# -------------------------------------------------------------------
# User Management Functions
# -------------------------------------------------------------------

def get_or_create_user_by_phone(phone_number, full_name=None, role='Clinician / Screener'):
    """
    Retrieves an existing user by normalized phone number or creates a new one.
    Returns the user dict with integer 'id'.
    """
    user = get_user_by_phone(phone_number)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if user:
        update_user_last_login(user['id'])
        if full_name and (not user.get('full_name') or user['full_name'].startswith('Screener ')):
            execute_query("UPDATE users SET full_name = ?, updated_at = ? WHERE id = ?", (full_name.strip(), now_str, user['id']), commit=True)
            user['full_name'] = full_name.strip()
        return get_user_by_id(user['id'])

    name = full_name.strip() if full_name else f"Screener {phone_number[-4:]}"
    clean_digits = phone_number.replace('+', '')
    email = f"screener_{clean_digits}@drishtiai.local"
    user_id = execute_query(
        """
        INSERT INTO users (full_name, email, phone_number, mobile_number, role, is_active, created_at, updated_at, last_login)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
        """,
        (name, email, phone_number, phone_number, role, now_str, now_str, now_str),
        commit=True,
        return_id=True
    )
    return get_user_by_id(user_id)

def get_user_by_phone(phone_number):
    if not phone_number:
        return None
    p = phone_number.strip()
    return execute_query("SELECT * FROM users WHERE mobile_number = ? OR phone_number = ?", (p, p), fetchone=True)

def get_user_by_id(user_id):
    if not user_id:
        return None
    return execute_query("SELECT * FROM users WHERE id = ?", (int(user_id),), fetchone=True)

def get_user_by_email(email):
    if not email:
        return None
    return execute_query("SELECT * FROM users WHERE email = ?", (email.strip().lower(),), fetchone=True)

def update_user_last_login(user_id):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    execute_query("UPDATE users SET last_login = ?, updated_at = ? WHERE id = ?", (now_str, now_str, int(user_id)), commit=True)

def create_or_update_user(full_name, email=None, age=None, gender=None, role='Clinician / Screener', phone_number=None):
    """
    Legacy compatibility helper supporting both email-based and phone-based user creation.
    """
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    email_clean = email.strip().lower() if email else None

    # Check by email first to prevent email unique collision
    if email_clean:
        user = get_user_by_email(email_clean)
        if user:
            # Only update phone if not already used by someone else
            safe_phone = phone_number
            if safe_phone:
                phone_holder = get_user_by_phone(safe_phone)
                if phone_holder and phone_holder['id'] != user['id']:
                    safe_phone = None
            execute_query("""
                UPDATE users SET full_name = ?, phone_number = COALESCE(?, phone_number),
                                 age = COALESCE(?, age), gender = COALESCE(?, gender),
                                 role = COALESCE(?, role), last_login = ?
                WHERE id = ?
            """, (full_name.strip(), safe_phone, age, gender, role, now_str, user['id']), commit=True)
            return user['id']

    if phone_number:
        user = get_user_by_phone(phone_number)
        if user:
            execute_query("""
                UPDATE users SET full_name = ?, email = COALESCE(?, email),
                                 age = COALESCE(?, age), gender = COALESCE(?, gender),
                                 role = COALESCE(?, role), last_login = ?
                WHERE id = ?
            """, (full_name.strip(), email_clean, age, gender, role, now_str, user['id']), commit=True)
            return user['id']

    eff_email = email_clean or (f"user_{phone_number.replace('+', '')}@drishtiai.local" if phone_number else f"user_{int(time.time()*1000)}@drishtiai.local")
    user_id = execute_query("""
        INSERT INTO users (full_name, email, phone_number, age, gender, role, is_active, created_at, last_login)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (full_name.strip(), eff_email, phone_number, age, gender, role, now_str, now_str),
    commit=True, return_id=True)
    return user_id

# -------------------------------------------------------------------
# Screening Management Functions (User-Isolated)
# -------------------------------------------------------------------

def add_screening(patient_id, image_path, heatmap_path, overlay_path, prediction, class_id,
                  confidence, probabilities, risk_status, notes='', referral_required=0,
                  is_demo=0, seg_overlay_path='', seg_mask_path='', detected_lesions='', user_id=None):
    """
    Persists a new retinal screening. Explicitly associates record with user_id.
    """
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    prob_str = json.dumps(probabilities) if isinstance(probabilities, list) else str(probabilities)
    lesions_str = json.dumps(detected_lesions) if isinstance(detected_lesions, (list, dict)) else str(detected_lesions)

    query = """
        INSERT INTO screenings (
            patient_id, user_id, image_path, heatmap_path, overlay_path,
            prediction, class_id, confidence, probabilities,
            risk_status, notes, referral_required, is_demo,
            seg_overlay_path, seg_mask_path, detected_lesions, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    screening_id = execute_query(
        query,
        (patient_id, user_id, image_path, heatmap_path, overlay_path,
         prediction, class_id, confidence, prob_str,
         risk_status, notes, referral_required, is_demo,
         seg_overlay_path, seg_mask_path, lesions_str, now_str),
        commit=True,
        return_id=True
    )
    return screening_id

def update_screening_notes(screening_id, notes, referral_required, user_id=None):
    """
    Updates screening notes and referral status with strict ownership check.
    """
    if user_id is not None:
        execute_query(
            "UPDATE screenings SET notes = ?, referral_required = ? WHERE (id = ? OR patient_id = ?) AND user_id = ?",
            (notes, referral_required, str(screening_id), str(screening_id), int(user_id)),
            commit=True
        )
    else:
        execute_query(
            "UPDATE screenings SET notes = ?, referral_required = ? WHERE id = ? OR patient_id = ?",
            (notes, referral_required, str(screening_id), str(screening_id)),
            commit=True
        )

def get_screening_by_id(screening_id, user_id=None):
    """
    Retrieves a single screening record.
    If user_id is passed, enforces ownership verification.
    """
    if user_id is not None:
        query = "SELECT * FROM screenings WHERE (id = ? OR patient_id = ?) AND user_id = ?"
        params = (str(screening_id), str(screening_id), int(user_id))
    else:
        query = "SELECT * FROM screenings WHERE id = ? OR patient_id = ?"
        params = (str(screening_id), str(screening_id))

    row = execute_query(query, params, fetchone=True)
    if not row:
        return None

    d = dict(row)
    try:
        d['probabilities'] = json.loads(d['probabilities'])
    except Exception:
        pass
    try:
        if d.get('detected_lesions'):
            if isinstance(d['detected_lesions'], str):
                d['detected_lesions'] = json.loads(d['detected_lesions'])
        else:
            d['detected_lesions'] = {}
    except Exception:
        d['detected_lesions'] = {}
    return d

def get_all_screenings(filter_class=None, search_query=None, user_id=None):
    """
    Retrieves screenings.
    When user_id is provided, returns ONLY records belonging to that user.
    """
    query = 'SELECT * FROM screenings WHERE 1=1'
    params = []

    if user_id is not None:
        query += ' AND user_id = ?'
        params.append(int(user_id))

    if filter_class is not None and str(filter_class) != 'all' and str(filter_class) != '':
        query += ' AND class_id = ?'
        params.append(int(filter_class))

    if search_query:
        query += ' AND (patient_id LIKE ? OR notes LIKE ? OR prediction LIKE ?)'
        like_str = f'%{search_query}%'
        params.extend([like_str, like_str, like_str])

    query += ' ORDER BY created_at DESC'
    rows = execute_query(query, params, fetchall=True)

    results = []
    for r in rows:
        d = dict(r)
        try:
            d['probabilities'] = json.loads(d['probabilities'])
        except Exception:
            pass
        try:
            if d.get('detected_lesions') and isinstance(d['detected_lesions'], str):
                d['detected_lesions'] = json.loads(d['detected_lesions'])
        except Exception:
            d['detected_lesions'] = {}
        results.append(d)
    return results

def get_user_screenings(user_id, filter_class=None, search_query=None):
    """Convenience alias explicitly enforcing user isolation."""
    return get_all_screenings(filter_class=filter_class, search_query=search_query, user_id=user_id)

def get_user_latest_screening(user_id):
    """
    Fetches the most recent screening for the specified user (used by DrishtiAI Assistant).
    """
    if not user_id:
        return None
    rows = execute_query(
        "SELECT * FROM screenings WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (int(user_id),),
        fetchall=True
    )
    if not rows:
        return None
    d = dict(rows[0])
    try:
        d['probabilities'] = json.loads(d['probabilities'])
    except Exception:
        pass
    try:
        if d.get('detected_lesions') and isinstance(d['detected_lesions'], str):
            d['detected_lesions'] = json.loads(d['detected_lesions'])
    except Exception:
        d['detected_lesions'] = {}
    return d

def get_dashboard_statistics(user_id=None):
    """
    Returns screening statistics.
    When user_id is supplied, aggregates ONLY for that specific user.
    """
    user_clause = " WHERE user_id = ?" if user_id is not None else ""
    user_params = (int(user_id),) if user_id is not None else ()

    total_row = execute_query(f"SELECT COUNT(*) as total FROM screenings{user_clause}", user_params, fetchone=True)
    total = total_row['total'] if total_row else 0

    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    group_query = f"SELECT class_id, COUNT(*) as cnt FROM screenings{user_clause} GROUP BY class_id"
    for row in execute_query(group_query, user_params, fetchall=True):
        if row['class_id'] in counts:
            counts[row['class_id']] = row['cnt']

    ref_clause = f"{user_clause} AND referral_required = 1" if user_clause else " WHERE referral_required = 1"
    ref_row = execute_query(f"SELECT COUNT(*) as refs FROM screenings{ref_clause}", user_params, fetchone=True)
    referrals = ref_row['refs'] if ref_row else 0

    timeline_query = f"SELECT created_at, class_id, confidence, prediction FROM screenings{user_clause} ORDER BY created_at ASC"
    timeline_rows = execute_query(timeline_query, user_params, fetchall=True)

    return {
        'total': total,
        'no_dr': counts[0],
        'mild': counts[1],
        'moderate': counts[2],
        'severe': counts[3],
        'proliferative': counts[4],
        'referrals_needed': referrals,
        'referral_rate': round((referrals / total * 100) if total > 0 else 0, 1),
        'timeline': timeline_rows
    }
