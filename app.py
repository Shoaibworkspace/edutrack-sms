import sqlite3, os, json
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'sms_secret_key_college_2024'
DATABASE = os.path.join(os.path.dirname(__file__), 'instance', 'sms.db')
os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
app.jinja_env.globals['enumerate'] = enumerate

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None: db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall(); cur.close()
    return (rv[0] if rv else None) if one else rv

def modify_db(query, args=()):
    db = get_db(); cur = db.execute(query, args); db.commit(); return cur.lastrowid

def init_db():
    with app.app_context():
        db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'student',
                student_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, roll_no TEXT UNIQUE NOT NULL,
                email TEXT, course TEXT NOT NULL, year INTEGER NOT NULL,
                contact TEXT, address TEXT, dob TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL, date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Present',
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE(student_id, date)
            );
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL, subject TEXT NOT NULL,
                marks INTEGER NOT NULL, max_marks INTEGER NOT NULL DEFAULT 100,
                exam_type TEXT DEFAULT 'Final', semester INTEGER DEFAULT 1,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );
        """)
        db.commit()

        if not db.execute("SELECT id FROM users WHERE email='admin@college.edu'").fetchone():
            db.execute("INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
                ('Administrator','admin@college.edu',generate_password_hash('admin123'),'admin'))

        sample = [
            ('Arjun Sharma','CS2024001','arjun@student.edu','B.Tech CSE',2,'9876543210','Delhi','2003-05-15'),
            ('Priya Patel','CS2024002','priya@student.edu','B.Tech CSE',2,'9876543211','Mumbai','2003-08-22'),
            ('Rahul Verma','CS2024003','rahul@student.edu','B.Tech ECE',1,'9876543212','Bangalore','2004-01-10'),
            ('Sneha Gupta','ME2024001','sneha@student.edu','B.Tech ME',3,'9876543213','Chennai','2002-11-30'),
            ('Vikram Singh','CS2024004','vikram@student.edu','B.Tech CSE',2,'9876543214','Pune','2003-07-18'),
            ('Ananya Roy','EC2024001','ananya@student.edu','B.Tech ECE',2,'9876543215','Kolkata','2003-03-25'),
            ('Karan Mehta','ME2024002','karan@student.edu','B.Tech ME',1,'9876543216','Jaipur','2004-06-12'),
            ('Divya Nair','CS2024005','divya@student.edu','B.Tech CSE',3,'9876543217','Kochi','2002-09-08'),
        ]
        for s in sample:
            if not db.execute("SELECT id FROM students WHERE roll_no=?",(s[1],)).fetchone():
                db.execute("INSERT INTO students (name,roll_no,email,course,year,contact,address,dob) VALUES (?,?,?,?,?,?,?,?)",s)
        db.commit()

        for st in db.execute("SELECT id,name,email FROM students").fetchall():
            if st['email'] and not db.execute("SELECT id FROM users WHERE email=?",(st['email'],)).fetchone():
                db.execute("INSERT INTO users (name,email,password,role,student_id) VALUES (?,?,?,?,?)",
                    (st['name'],st['email'],generate_password_hash('student123'),'student',st['id']))

        from datetime import timedelta; import random; random.seed(42)
        subjects_map = {
            'B.Tech CSE':['Data Structures','Algorithms','DBMS','OS','Networks'],
            'B.Tech ECE':['Signals','Electronics','VLSI','Microprocessors','Communications'],
            'B.Tech ME':['Thermodynamics','Fluid Mechanics','Machine Design','Manufacturing','Dynamics'],
        }
        for st in db.execute("SELECT id,course FROM students").fetchall():
            for i in range(30):
                d=(date.today()-timedelta(days=i)).isoformat()
                status='Present' if random.random()>0.2 else 'Absent'
                try: db.execute("INSERT INTO attendance (student_id,date,status) VALUES (?,?,?)",(st['id'],d,status))
                except: pass
            for subj in subjects_map.get(st['course'],subjects_map['B.Tech CSE']):
                if not db.execute("SELECT id FROM results WHERE student_id=? AND subject=?",(st['id'],subj)).fetchone():
                    db.execute("INSERT INTO results (student_id,subject,marks,max_marks) VALUES (?,?,?,?)",
                               (st['id'],subj,random.randint(45,98),100))
        db.commit(); db.close()

def login_required(f):
    @wraps(f)
    def dec(*a,**kw):
        if 'user_id' not in session: flash('Please login.','warning'); return redirect(url_for('login'))
        return f(*a,**kw)
    return dec

def admin_required(f):
    @wraps(f)
    def dec(*a,**kw):
        if 'user_id' not in session: flash('Please login.','warning'); return redirect(url_for('login'))
        if session.get('role')!='admin': flash('Admins only.','danger'); return redirect(url_for('student_dashboard'))
        return f(*a,**kw)
    return dec

def calculate_grade(p):
    if p>=90: return 'A+'
    elif p>=80: return 'A'
    elif p>=70: return 'B'
    elif p>=60: return 'C'
    elif p>=50: return 'D'
    else: return 'F'

def get_att_stats(sid):
    rows=query_db("SELECT status FROM attendance WHERE student_id=?",(sid,))
    total=len(rows); present=sum(1 for r in rows if r['status']=='Present')
    return {'total':total,'present':present,'absent':total-present,'percentage':round(present/total*100,1) if total else 0}

def get_res_stats(sid):
    rows=query_db("SELECT marks,max_marks FROM results WHERE student_id=?",(sid,))
    if not rows: return {'total_marks':0,'max_marks':0,'percentage':0,'grade':'N/A','subjects':0}
    t=sum(r['marks'] for r in rows); m=sum(r['max_marks'] for r in rows)
    p=round(t/m*100,1) if m else 0
    return {'total_marks':t,'max_marks':m,'percentage':p,'grade':calculate_grade(p),'subjects':len(rows)}

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('role')=='admin' else 'student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login',methods=['GET','POST'])
def login():
    if 'user_id' in session: return redirect(url_for('index'))
    if request.method=='POST':
        email=request.form.get('email','').strip(); pw=request.form.get('password','')
        user=query_db("SELECT * FROM users WHERE email=?",(email,),one=True)
        if user and check_password_hash(user['password'],pw):
            session.update({'user_id':user['id'],'user_name':user['name'],'role':user['role'],'student_id':user['student_id']})
            flash(f'Welcome back, {user["name"]}!','success')
            return redirect(url_for('admin_dashboard' if user['role']=='admin' else 'student_dashboard'))
        flash('Invalid email or password.','danger')
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.clear(); flash('Logged out.','info'); return redirect(url_for('login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_students=query_db("SELECT COUNT(*) as c FROM students",one=True)['c']
    total_courses=query_db("SELECT COUNT(DISTINCT course) as c FROM students",one=True)['c']
    today=date.today().isoformat()
    att_map={r['status']:r['c'] for r in query_db("SELECT status,COUNT(*) as c FROM attendance WHERE date=? GROUP BY status",(today,))}
    all_att=query_db("SELECT status FROM attendance")
    tp=sum(1 for r in all_att if r['status']=='Present'); ta=len(all_att)
    grade_dist={'A+':0,'A':0,'B':0,'C':0,'D':0,'F':0}
    for s in query_db("SELECT id FROM students"):
        g=get_res_stats(s['id'])['grade']
        if g in grade_dist: grade_dist[g]+=1
    from datetime import timedelta
    att_trend=[{'date':(date.today()-timedelta(days=i)).isoformat(),'total':0,'present':0} for i in range(6,-1,-1)]
    for item in att_trend:
        row=query_db("SELECT COUNT(*) as t,SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as p FROM attendance WHERE date=?",(item['date'],),one=True)
        item['total']=row['t'] or 0; item['present']=row['p'] or 0
    return render_template('admin/dashboard.html',
        total_students=total_students,total_courses=total_courses,
        present_today=att_map.get('Present',0),absent_today=att_map.get('Absent',0),
        overall_att_pct=round(tp/ta*100,1) if ta else 0,
        grade_dist=json.dumps(grade_dist),
        recent_students=query_db("SELECT * FROM students ORDER BY created_at DESC LIMIT 5"),
        course_dist=json.dumps([{'course':r['course'],'count':r['count']} for r in query_db("SELECT course,COUNT(*) as count FROM students GROUP BY course")]),
        att_trend=json.dumps(att_trend))

@app.route('/admin/students')
@admin_required
def admin_students():
    search=request.args.get('search','').strip(); cf=request.args.get('course',''); yf=request.args.get('year','')
    page=int(request.args.get('page',1)); per=10
    q="SELECT * FROM students WHERE 1=1"; cq="SELECT COUNT(*) as c FROM students WHERE 1=1"; args=[]
    if search:
        cl=" AND (name LIKE ? OR roll_no LIKE ?)"; q+=cl; cq+=cl; args+=[f'%{search}%',f'%{search}%']
    if cf:
        cl=" AND course=?"; q+=cl; cq+=cl; args.append(cf)
    if yf:
        cl=" AND year=?"; q+=cl; cq+=cl; args.append(yf)
    total=query_db(cq,args,one=True)['c']
    students=query_db(q+f" ORDER BY created_at DESC LIMIT {per} OFFSET {(page-1)*per}",args)
    return render_template('admin/students.html',students=students,
        courses=query_db("SELECT DISTINCT course FROM students ORDER BY course"),
        years=query_db("SELECT DISTINCT year FROM students ORDER BY year"),
        search=search,course_filter=cf,year_filter=yf,
        page=page,total_pages=(total+per-1)//per,total=total)

@app.route('/admin/students/add',methods=['GET','POST'])
@admin_required
def add_student():
    if request.method=='POST':
        n,r,e,c,y,co,a,d=request.form.get('name','').strip(),request.form.get('roll_no','').strip(),\
            request.form.get('email','').strip(),request.form.get('course','').strip(),\
            request.form.get('year','1'),request.form.get('contact','').strip(),\
            request.form.get('address','').strip(),request.form.get('dob','').strip()
        if not all([n,r,c,y]): flash('Name, Roll No, Course, Year required.','danger'); return redirect(url_for('add_student'))
        if query_db("SELECT id FROM students WHERE roll_no=?",(r,),one=True): flash(f'Roll {r} exists.','danger'); return redirect(url_for('add_student'))
        sid=modify_db("INSERT INTO students (name,roll_no,email,course,year,contact,address,dob) VALUES (?,?,?,?,?,?,?,?)",(n,r,e,c,int(y),co,a,d))
        if e: modify_db("INSERT OR IGNORE INTO users (name,email,password,role,student_id) VALUES (?,?,?,?,?)",(n,e,generate_password_hash('student123'),'student',sid))
        flash(f'{n} added!','success'); return redirect(url_for('admin_students'))
    return render_template('admin/student_form.html',student=None,action='Add')

@app.route('/admin/students/edit/<int:sid>',methods=['GET','POST'])
@admin_required
def edit_student(sid):
    student=query_db("SELECT * FROM students WHERE id=?",(sid,),one=True)
    if not student: flash('Not found.','danger'); return redirect(url_for('admin_students'))
    if request.method=='POST':
        n,r,e,c,y,co,a,d=request.form.get('name','').strip(),request.form.get('roll_no','').strip(),\
            request.form.get('email','').strip(),request.form.get('course','').strip(),\
            request.form.get('year','1'),request.form.get('contact','').strip(),\
            request.form.get('address','').strip(),request.form.get('dob','').strip()
        if query_db("SELECT id FROM students WHERE roll_no=? AND id!=?",(r,sid),one=True): flash(f'Roll {r} exists.','danger'); return redirect(url_for('edit_student',sid=sid))
        modify_db("UPDATE students SET name=?,roll_no=?,email=?,course=?,year=?,contact=?,address=?,dob=? WHERE id=?",(n,r,e,c,int(y),co,a,d,sid))
        flash(f'{n} updated!','success'); return redirect(url_for('admin_students'))
    return render_template('admin/student_form.html',student=student,action='Edit')

@app.route('/admin/students/delete/<int:sid>',methods=['POST'])
@admin_required
def delete_student(sid):
    s=query_db("SELECT name FROM students WHERE id=?",(sid,),one=True)
    if s:
        modify_db("DELETE FROM users WHERE student_id=?",(sid,))
        modify_db("DELETE FROM students WHERE id=?",(sid,))
        flash(f'{s["name"]} deleted.','success')
    return redirect(url_for('admin_students'))

@app.route('/admin/students/view/<int:sid>')
@admin_required
def view_student(sid):
    student=query_db("SELECT * FROM students WHERE id=?",(sid,),one=True)
    if not student: flash('Not found.','danger'); return redirect(url_for('admin_students'))
    raw=query_db("SELECT * FROM results WHERE student_id=? ORDER BY subject",(sid,))
    results=[{'subject':r['subject'],'marks':r['marks'],'max_marks':r['max_marks'],
              'percentage':round(r['marks']/r['max_marks']*100,1) if r['max_marks'] else 0,
              'grade':calculate_grade(round(r['marks']/r['max_marks']*100,1) if r['max_marks'] else 0)} for r in raw]
    return render_template('admin/student_detail.html',student=student,att_stats=get_att_stats(sid),
        result_stats=get_res_stats(sid),results=results,
        attendance=query_db("SELECT * FROM attendance WHERE student_id=? ORDER BY date DESC LIMIT 30",(sid,)))

@app.route('/admin/attendance',methods=['GET','POST'])
@admin_required
def admin_attendance():
    sel=request.args.get('date',date.today().isoformat()); cf=request.args.get('course','')
    q="SELECT * FROM students WHERE 1=1"; args=[]
    if cf: q+=" AND course=?"; args.append(cf)
    students=query_db(q+" ORDER BY roll_no",args)
    att_records={r['student_id']:r['status'] for r in query_db("SELECT student_id,status FROM attendance WHERE date=?",(sel,))}
    if request.method=='POST':
        d=request.form.get('att_date',date.today().isoformat())
        for s in query_db("SELECT id FROM students"):
            modify_db("INSERT OR REPLACE INTO attendance (student_id,date,status) VALUES (?,?,?)",
                (s['id'],d,'Present' if request.form.get(f'att_{s["id"]}') else 'Absent'))
        flash(f'Attendance saved for {d}!','success'); return redirect(url_for('admin_attendance',date=d))
    return render_template('admin/attendance.html',students=students,att_records=att_records,
        selected_date=sel,courses=query_db("SELECT DISTINCT course FROM students ORDER BY course"),course_filter=cf)

@app.route('/admin/attendance/report')
@admin_required
def attendance_report():
    report=[{'id':s['id'],'name':s['name'],'roll_no':s['roll_no'],'course':s['course'],'year':s['year'],**get_att_stats(s['id'])}
            for s in query_db("SELECT * FROM students ORDER BY roll_no")]
    return render_template('admin/attendance_report.html',report=report)

@app.route('/admin/results')
@admin_required
def admin_results():
    sr=[{'id':s['id'],'name':s['name'],'roll_no':s['roll_no'],'course':s['course'],'year':s['year'],**get_res_stats(s['id'])}
        for s in query_db("SELECT * FROM students ORDER BY course,roll_no")]
    return render_template('admin/results.html',student_results=sr)

@app.route('/admin/results/manage/<int:sid>',methods=['GET','POST'])
@admin_required
def manage_results(sid):
    student=query_db("SELECT * FROM students WHERE id=?",(sid,),one=True)
    if not student: flash('Not found.','danger'); return redirect(url_for('admin_results'))
    if request.method=='POST':
        act=request.form.get('action')
        if act=='add':
            subj,marks,mm,et,sem=request.form.get('subject','').strip(),request.form.get('marks','0'),\
                request.form.get('max_marks','100'),request.form.get('exam_type','Final'),request.form.get('semester','1')
            if subj and marks:
                if query_db("SELECT id FROM results WHERE student_id=? AND subject=?",(sid,subj),one=True):
                    modify_db("UPDATE results SET marks=?,max_marks=?,exam_type=?,semester=? WHERE student_id=? AND subject=?",(int(marks),int(mm),et,int(sem),sid,subj))
                    flash(f'Updated {subj}.','success')
                else:
                    modify_db("INSERT INTO results (student_id,subject,marks,max_marks,exam_type,semester) VALUES (?,?,?,?,?,?)",(sid,subj,int(marks),int(mm),et,int(sem)))
                    flash(f'Added {subj}.','success')
        elif act=='delete':
            modify_db("DELETE FROM results WHERE id=? AND student_id=?",(request.form.get('result_id'),sid))
            flash('Deleted.','info')
        return redirect(url_for('manage_results',sid=sid))
    raw=query_db("SELECT * FROM results WHERE student_id=? ORDER BY subject",(sid,))
    results=[{'id':r['id'],'subject':r['subject'],'marks':r['marks'],'max_marks':r['max_marks'],
              'percentage':round(r['marks']/r['max_marks']*100,1) if r['max_marks'] else 0,
              'grade':calculate_grade(round(r['marks']/r['max_marks']*100,1) if r['max_marks'] else 0),
              'exam_type':r['exam_type'],'semester':r['semester']} for r in raw]
    return render_template('admin/manage_results.html',student=student,results=results,overall=get_res_stats(sid))

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if session.get('role')=='admin': return redirect(url_for('admin_dashboard'))
    sid=session.get('student_id')
    if not sid: flash('No student record.','danger'); return redirect(url_for('logout'))
    student=query_db("SELECT * FROM students WHERE id=?",(sid,),one=True)
    raw=query_db("SELECT * FROM results WHERE student_id=? ORDER BY subject",(sid,))
    results=[{'subject':r['subject'],'marks':r['marks'],'max_marks':r['max_marks'],
              'percentage':round(r['marks']/r['max_marks']*100,1) if r['max_marks'] else 0,
              'grade':calculate_grade(round(r['marks']/r['max_marks']*100,1) if r['max_marks'] else 0)} for r in raw]
    return render_template('student/dashboard.html',student=student,att_stats=get_att_stats(sid),
        result_stats=get_res_stats(sid),results=results,
        recent_att=query_db("SELECT * FROM attendance WHERE student_id=? ORDER BY date DESC LIMIT 7",(sid,)))

@app.route('/student/profile')
@login_required
def student_profile():
    return render_template('student/profile.html',student=query_db("SELECT * FROM students WHERE id=?",(session.get('student_id'),),one=True))

@app.route('/student/attendance')
@login_required
def student_attendance():
    sid=session.get('student_id')
    return render_template('student/attendance.html',
        student=query_db("SELECT * FROM students WHERE id=?",(sid,),one=True),
        att_stats=get_att_stats(sid),
        attendance=query_db("SELECT * FROM attendance WHERE student_id=? ORDER BY date DESC",(sid,)))

@app.route('/student/results')
@login_required
def student_results():
    sid=session.get('student_id')
    raw=query_db("SELECT * FROM results WHERE student_id=? ORDER BY subject",(sid,))
    results=[{'subject':r['subject'],'marks':r['marks'],'max_marks':r['max_marks'],
              'percentage':round(r['marks']/r['max_marks']*100,1) if r['max_marks'] else 0,
              'grade':calculate_grade(round(r['marks']/r['max_marks']*100,1) if r['max_marks'] else 0),
              'exam_type':r['exam_type']} for r in raw]
    return render_template('student/results.html',
        student=query_db("SELECT * FROM students WHERE id=?",(sid,),one=True),
        results=results,overall=get_res_stats(sid))

if __name__=='__main__':
    init_db()
    app.run(debug=True,port=5000)
