import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'database.db')

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screenings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT UNIQUE NOT NULL,
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
        )
    """)
    conn.commit()

    # Dynamic migration check for existing databases
    cursor.execute("PRAGMA table_info(screenings)")
    existing_cols = [r['name'] for r in cursor.fetchall()]
    if 'seg_overlay_path' not in existing_cols:
        cursor.execute("ALTER TABLE screenings ADD COLUMN seg_overlay_path TEXT DEFAULT ''")
    if 'seg_mask_path' not in existing_cols:
        cursor.execute("ALTER TABLE screenings ADD COLUMN seg_mask_path TEXT DEFAULT ''")
    if 'detected_lesions' not in existing_cols:
        cursor.execute("ALTER TABLE screenings ADD COLUMN detected_lesions TEXT DEFAULT ''")
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) as count FROM screenings")
    row = cursor.fetchone()
    if row['count'] == 0:
        seed_demo_data(conn)
    conn.close()

def seed_demo_data(conn):
    demo_screenings = [
        (
            'RXT-1001',
            'static/samples/sample_no_dr.jpg',
            'static/samples/sample_no_dr_heatmap.jpg',
            'static/samples/sample_no_dr_overlay.jpg',
            'No Diabetic Retinopathy',
            0,
            96.8,
            json.dumps([96.8, 2.1, 0.7, 0.3, 0.1]),
            'Routine annual screening recommended. Retinal architecture within normal limits.',
            'Fundus clear. Normal foveal avascular zone and optic disc margins. Routine 12-month follow-up.',
            0,
            1,
            '2026-08-28 10:15:22'
        ),
        (
            'RXT-1002',
            'static/samples/sample_mild.jpg',
            'static/samples/sample_mild_heatmap.jpg',
            'static/samples/sample_mild_overlay.jpg',
            'Mild Diabetic Retinopathy',
            1,
            88.4,
            json.dumps([6.2, 88.4, 4.1, 1.0, 0.3]),
            'Early screening observation: Microaneurysms detected. Monitor closely in 6-12 months.',
            'Isolated microaneurysms present in inferior temporal arcade. Blood glucose counseling recommended.',
            0,
            1,
            '2026-08-29 11:42:05'
        ),
        (
            'RXT-1003',
            'static/samples/sample_moderate.jpg',
            'static/samples/sample_moderate_heatmap.jpg',
            'static/samples/sample_moderate_overlay.jpg',
            'Moderate Diabetic Retinopathy',
            2,
            91.2,
            json.dumps([2.0, 4.3, 91.2, 2.1, 0.4]),
            'Refer for ophthalmic evaluation. Multiple lesions and microaneurysms observed.',
            'Dot and blot hemorrhages visible in macula periphery. Hard exudates noted. Tele-ophthalmology referral initiated.',
            1,
            1,
            '2026-08-30 14:08:49'
        ),
        (
            'RXT-1004',
            'static/samples/sample_severe.jpg',
            'static/samples/sample_severe_heatmap.jpg',
            'static/samples/sample_severe_overlay.jpg',
            'Severe Diabetic Retinopathy',
            3,
            94.6,
            json.dumps([0.4, 1.2, 3.1, 94.6, 0.7]),
            'Urgent ophthalmic referral required. Extensive intraretinal hemorrhages and vascular changes.',
            'Severe 4-quadrant hemorrhages with venous beading. High risk of progression to PDR. Fast-tracked to district hospital.',
            1,
            1,
            '2026-09-01 09:25:30'
        ),
        (
            'RXT-1005',
            'static/samples/sample_proliferative.jpg',
            'static/samples/sample_proliferative_heatmap.jpg',
            'static/samples/sample_proliferative_overlay.jpg',
            'Proliferative Diabetic Retinopathy',
            4,
            97.1,
            json.dumps([0.1, 0.3, 0.8, 1.7, 97.1]),
            'Critical ophthalmic referral. Neovascularization and elevated risk of retinal detachment.',
            'Neovascularization at disc (NVD) with fibrous proliferation. Urgent tertiary eye center referral issued.',
            1,
            1,
            '2026-09-02 16:50:12'
        )
    ]
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO screenings (
            patient_id, image_path, heatmap_path, overlay_path,
            prediction, class_id, confidence, probabilities,
            risk_status, notes, referral_required, is_demo, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, demo_screenings)
    conn.commit()

def add_screening(patient_id, image_path, heatmap_path, overlay_path, prediction, class_id, confidence, probabilities, risk_status, notes='', referral_required=0, is_demo=0, seg_overlay_path='', seg_mask_path='', detected_lesions=''):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    prob_str = json.dumps(probabilities) if isinstance(probabilities, list) else str(probabilities)
    lesions_str = json.dumps(detected_lesions) if isinstance(detected_lesions, (list, dict)) else str(detected_lesions)
    cursor.execute("""
        INSERT INTO screenings (
            patient_id, image_path, heatmap_path, overlay_path,
            prediction, class_id, confidence, probabilities,
            risk_status, notes, referral_required, is_demo,
            seg_overlay_path, seg_mask_path, detected_lesions, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (patient_id, image_path, heatmap_path, overlay_path, prediction, class_id, confidence, prob_str, risk_status, notes, referral_required, is_demo, seg_overlay_path, seg_mask_path, lesions_str, now_str))
    conn.commit()
    screening_id = cursor.lastrowid
    conn.close()
    return screening_id

def update_screening_notes(screening_id, notes, referral_required):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE screenings SET notes = ?, referral_required = ? WHERE id = ? OR patient_id = ?', (notes, referral_required, screening_id, str(screening_id)))
    conn.commit()
    conn.close()

def get_screening_by_id(screening_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM screenings WHERE id = ? OR patient_id = ?', (screening_id, str(screening_id)))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        try:
            d['probabilities'] = json.loads(d['probabilities'])
        except Exception:
            pass
        try:
            if 'detected_lesions' in d and d['detected_lesions']:
                if isinstance(d['detected_lesions'], str):
                    d['detected_lesions'] = json.loads(d['detected_lesions'])
            else:
                d['detected_lesions'] = {}
        except Exception:
            d['detected_lesions'] = {}
        return d
    return None

def get_all_screenings(filter_class=None, search_query=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = 'SELECT * FROM screenings WHERE 1=1'
    params = []
    if filter_class is not None and filter_class != 'all' and str(filter_class) != '':
        query += ' AND class_id = ?'
        params.append(int(filter_class))
    if search_query:
        query += ' AND (patient_id LIKE ? OR notes LIKE ? OR prediction LIKE ?)'
        like_str = f'%{search_query}%'
        params.extend([like_str, like_str, like_str])
    query += ' ORDER BY created_at DESC'
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d['probabilities'] = json.loads(d['probabilities'])
        except Exception:
            pass
        results.append(d)
    return results

def get_dashboard_statistics():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as total FROM screenings')
    total = cursor.fetchone()['total']
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    cursor.execute('SELECT class_id, COUNT(*) as cnt FROM screenings GROUP BY class_id')
    for row in cursor.fetchall():
        counts[row['class_id']] = row['cnt']
    cursor.execute('SELECT COUNT(*) as refs FROM screenings WHERE referral_required = 1')
    referrals = cursor.fetchone()['refs']
    cursor.execute('SELECT created_at, class_id, confidence, prediction FROM screenings ORDER BY created_at ASC')
    timeline_rows = cursor.fetchall()
    conn.close()
    return {
        'total': total,
        'no_dr': counts[0],
        'mild': counts[1],
        'moderate': counts[2],
        'severe': counts[3],
        'proliferative': counts[4],
        'referrals_needed': referrals,
        'referral_rate': round((referrals / total * 100) if total > 0 else 0, 1),
        'timeline': [dict(r) for r in timeline_rows]
    }
