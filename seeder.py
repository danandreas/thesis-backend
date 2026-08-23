"""
Database Seeder - Psychoposition Thesis
Jalankan: python seeder.py

Akan membuat:
  - 2 roles: admin, candidate
  - 2 admin + 20 kandidat
  - 10 kriteria + 5 jenis syarat
  - 1 rekrutmen aktif REC-2025-001
  - 2 posisi: Backend Developer, Frontend Developer
  - Syarat: IPK 10%, TOEFL 5%, Sertifikat 3%
  - 10 kriteria per posisi dengan bobot berbeda
  - 6 pertanyaan + 5 opsi Likert per kriteria-posisi
  - 10 kandidat per posisi, semua sudah submitted
"""
import os
import sys
import random
from datetime import datetime, date

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
random.seed(42)

from app import create_app, db
from app.models.role import Role
from app.models.user import User


def seed():
    app = create_app()
    with app.app_context():
        print("\n" + "=" * 60)
        print("  PSYCHOPOSITION — DATABASE SEEDER")
        print("=" * 60)

        db.create_all()
        print("\n✅ Tables created / verified.\n")

        # ── Roles ────────────────────────────────────────────────────
        print("📦 Seeding roles...")
        roles = {}
        for r in [{'code': 'admin', 'name': 'Administrator'},
                  {'code': 'candidate', 'name': 'Kandidat'}]:
            obj = Role.query.filter_by(code=r['code']).first()
            if not obj:
                obj = Role(code=r['code'], name=r['name'])
                db.session.add(obj)
                db.session.commit()
                print(f"  ➕ Role '{r['code']}' created.")
            else:
                print(f"  ⏭️  Role '{r['code']}' exists.")
            roles[r['code']] = obj

        # ── Admin users ──────────────────────────────────────────────
        print("\n📦 Seeding admin users...")
        for a in [{'name': 'Super Admin',  'email': 'admin@company.com', 'phone': '08111111111'},
                  {'name': 'HR Manager',   'email': 'hr@company.com',    'phone': '08222222222'}]:
            if not User.query.filter_by(email=a['email']).first():
                u = User(role_id=roles['admin'].id, name=a['name'],
                         email=a['email'], phone=a['phone'], password='')
                u.set_password('password')
                u.save()
                print(f"  ➕ Admin '{a['email']}' created.")
            else:
                print(f"  ⏭️  Admin '{a['email']}' exists.")

        # ── Candidate users ──────────────────────────────────────────
        print("\n📦 Seeding candidates (20)...")
        candidate_data = [
            ('Budi Utomo',      'budi@email.com'),
            ('Rina Wijaya',       'rina@email.com'),
            ('Eko Prasetyo',      'eko@email.com'),
            ('Dewi Lestari',      'dewi@email.com'),
            ('Ahmad Fauzi',       'ahmad@email.com'),
            ('Siti Rahayu',       'siti@email.com'),
            ('Hendra Gunawan',    'hendra@email.com'),
            ('Maya Putri',        'maya@email.com'),
            ('Dian Kurniawan',    'dian@email.com'),
            ('Nining Suryani',    'nining@email.com'),
            ('Rizky Firmansyah',  'rizky@email.com'),
            ('Lina Marlina',      'lina@email.com'),
            ('Teguh Wibowo',      'teguh@email.com'),
            ('Fitri Handayani',   'fitri@email.com'),
            ('Bagas Nugroho',     'bagas@email.com'),
            ('Retno Puspitasari', 'retno@email.com'),
            ('Arif Rahman',       'arif@email.com'),
            ('Wulan Sari',        'wulan@email.com'),
            ('Yoga Pratama',      'yoga@email.com'),
            ('Cantika Dewi',      'cantika@email.com'),
        ]
        candidate_users = []
        for name, email in candidate_data:
            u = User.query.filter_by(email=email).first()
            if not u:
                u = User(role_id=roles['candidate'].id, name=name,
                         email=email, phone='0812-0000', password='')
                u.set_password('password')
                u.save()
                print(f"  ➕ {email}")
            else:
                print(f"  ⏭️  {email} exists.")
            candidate_users.append(u)

        # ── Import thesis models ─────────────────────────────────────
        try:
            from app.models.criteria import Criteria, RequirementType
            from app.models.recruitment import (
                Recruitment, RecruitmentPosition, RecruitmentRequirement,
                PositionCriteria, AssessmentQuestion, AssessmentOption
            )
            from app.models.candidate import (
                CandidateProfile, CandidateEducation,
                CandidateApplication, AssessmentAnswer, CandidateRequirement
            )
        except ImportError as e:
            print(f"\n❌ Import error: {e}")
            return

        # ── Criteria ─────────────────────────────────────────────────
        print("\n📦 Seeding criteria...")
        criteria_def = [
            ('LOG', 'Logical Thinking'),
            ('CRE', 'Creativity'),
            ('COM', 'Communication'),
            ('TEC', 'Technical Skill'),
            ('ART', 'Artistic Sense'),
            ('TEM', 'Teamwork'),
            ('ADA', 'Adaptability'),
            ('LED', 'Leadership'),
            ('PRB', 'Problem Solving'),
            ('DET', 'Detail Oriented'),
        ]
        criteria_objs = {}
        for code, name in criteria_def:
            obj = Criteria.query.filter_by(code=code).first()
            if not obj:
                obj = Criteria(code=code, name=name, is_active=True)
                db.session.add(obj)
                db.session.commit()
                print(f"  ➕ Criteria '{code}'")
            criteria_objs[code] = obj

        # ── Requirement Types ────────────────────────────────────────
        print("\n📦 Seeding requirement types...")
        rt_def = [
            ('GPA',   'IPK',             0,    4,    'scale'),
            ('TOEFL', 'TOEFL Score',     310,  677,  'numeric'),
            ('IELTS', 'IELTS Score',     0,    9,    'scale'),
            ('CERT',  'Sertifikat',      0,    10,   'count'),
            ('WORK',  'Pengalaman Kerja',0,    20,   'numeric'),
        ]
        rt_objs = {}
        for code, name, minv, maxv, vtype in rt_def:
            obj = RequirementType.query.filter_by(code=code).first()
            if not obj:
                obj = RequirementType(code=code, name=name,
                                      min_value=minv, max_value=maxv,
                                      value_type=vtype, is_active=True)
                db.session.add(obj)
                db.session.commit()
                print(f"  ➕ RequirementType '{code}'")
            rt_objs[code] = obj

        # ── Recruitment ──────────────────────────────────────────────
        print("\n📦 Seeding recruitment...")
        admin_user = User.query.filter_by(email='admin@company.com').first()
        rec = Recruitment.query.filter_by(code='REC-2025-001').first()
        if not rec:
            rec = Recruitment(
                code='REC-2025-001',
                title='Rekrutmen Teknologi Informasi Batch 2025',
                description='Rekrutmen karyawan baru divisi IT untuk posisi Backend dan Frontend Developer.',
                status='active',
                published_at=datetime.utcnow(),
                created_by=admin_user.id,
            )
            db.session.add(rec)
            db.session.commit()
            print("  ➕ Recruitment 'REC-2025-001' created.")
        else:
            print("  ⏭️  Recruitment exists.")

        # ── Recruitment Requirements (Syarat Tambahan) ───────────────
        print("\n📦 Seeding requirements (IPK, TOEFL, CERT)...")
        req_setup = [('GPA', 10, True), ('TOEFL', 5, False), ('CERT', 3, False)]
        rr_objs = {}  # code → RecruitmentRequirement object
        for code, weight, mandatory in req_setup:
            rr = RecruitmentRequirement.query.filter_by(
                recruitment_id=rec.id,
                requirement_type_id=rt_objs[code].id
            ).first()
            if not rr:
                rr = RecruitmentRequirement(
                    recruitment_id=rec.id,
                    requirement_type_id=rt_objs[code].id,
                    weight=weight,
                    is_mandatory=mandatory,
                    display_order=req_setup.index((code, weight, mandatory)) + 1
                )
                db.session.add(rr)
                db.session.commit()
                print(f"  ➕ Requirement '{code}' {weight}%")
            rr_objs[code] = rr

        # ── Positions + Criteria + Questions ────────────────────────
        print("\n📦 Seeding positions, criteria, questions...")

        positions_cfg = [
            {
                'title': 'Backend Developer',
                'description': 'Membangun dan memelihara sistem server-side yang handal.',
                'quota': 2,
                'criteria': {  # code: (weight_manual, criteria_type)
                    'LOG': (90, 'benefit'), 'TEC': (85, 'benefit'),
                    'PRB': (88, 'benefit'), 'DET': (82, 'benefit'),
                    'TEM': (65, 'benefit'), 'ADA': (70, 'benefit'),
                    'COM': (60, 'benefit'), 'CRE': (50, 'benefit'),
                    'LED': (40, 'benefit'), 'ART': (20, 'benefit'),
                },
            },
            {
                'title': 'Frontend Developer',
                'description': 'Membangun antarmuka pengguna yang menarik dan responsif.',
                'quota': 2,
                'criteria': {
                    'ART': (90, 'benefit'), 'CRE': (88, 'benefit'),
                    'DET': (85, 'benefit'), 'COM': (78, 'benefit'),
                    'TEC': (75, 'benefit'), 'ADA': (72, 'benefit'),
                    'TEM': (70, 'benefit'), 'PRB': (68, 'benefit'),
                    'LOG': (60, 'benefit'), 'LED': (35, 'benefit'),
                },
            },
        ]

        questions_map = {
            'LOG': ["Seberapa sering Anda menyelesaikan masalah teknis secara mandiri?",
                    "Seberapa mudah Anda menganalisis data dan menarik kesimpulan?",
                    "Seberapa sering Anda menggunakan pendekatan sistematis dalam pemecahan masalah?",
                    "Seberapa baik Anda memahami alur logika sebuah program?",
                    "Seberapa cepat Anda dapat mengidentifikasi akar masalah?",
                    "Seberapa sering Anda menggunakan diagram atau flowchart saat merancang solusi?"],
            'CRE': ["Seberapa sering Anda mengusulkan ide-ide baru di lingkungan kerja?",
                    "Seberapa mudah Anda memikirkan solusi alternatif untuk suatu masalah?",
                    "Seberapa sering Anda mencari inspirasi dari luar bidang Anda?",
                    "Seberapa besar rasa ingin tahu Anda terhadap hal-hal baru?",
                    "Seberapa sering Anda bereksperimen dengan metode baru?",
                    "Seberapa mudah Anda beradaptasi saat menghadapi tantangan tidak biasa?"],
            'COM': ["Seberapa mudah Anda menjelaskan ide teknis kepada orang non-teknis?",
                    "Seberapa sering Anda aktif berkomunikasi dalam rapat?",
                    "Seberapa baik Anda dalam menulis laporan atau dokumentasi?",
                    "Seberapa sering Anda memberikan feedback konstruktif kepada rekan?",
                    "Seberapa mudah Anda memahami instruksi yang diberikan secara lisan?",
                    "Seberapa baik kemampuan presentasi Anda di depan audiens?"],
            'TEC': ["Seberapa baik penguasaan Anda terhadap bahasa pemrograman utama Anda?",
                    "Seberapa sering Anda mempelajari teknologi atau framework baru?",
                    "Seberapa cepat Anda memahami codebase yang belum pernah dilihat?",
                    "Seberapa baik kemampuan Anda dalam debugging dan testing?",
                    "Seberapa sering Anda mengikuti best practices dalam pengembangan?",
                    "Seberapa familiar Anda dengan konsep database dan query optimization?"],
            'ART': ["Seberapa baik intuisi estetika Anda dalam menilai sebuah desain?",
                    "Seberapa sering Anda memperhatikan detail visual pada antarmuka?",
                    "Seberapa mudah Anda memilih kombinasi warna yang harmonis?",
                    "Seberapa baik Anda dalam membuat layout yang bersih dan rapi?",
                    "Seberapa sering Anda mengikuti tren desain UI/UX terkini?",
                    "Seberapa baik pemahaman Anda tentang prinsip tipografi?"],
            'TEM': ["Seberapa mudah Anda berkolaborasi dengan rekan yang berbeda gaya kerja?",
                    "Seberapa sering Anda membantu rekan tim yang mengalami kesulitan?",
                    "Seberapa baik Anda dalam berbagi pengetahuan dengan tim?",
                    "Seberapa sering Anda mengutamakan kepentingan tim di atas pribadi?",
                    "Seberapa mudah Anda menyesuaikan diri dengan budaya tim?",
                    "Seberapa sering Anda menginisiasi sesi knowledge sharing?"],
            'ADA': ["Seberapa cepat Anda menyesuaikan diri dengan perubahan prioritas proyek?",
                    "Seberapa mudah Anda belajar menggunakan alat atau sistem baru?",
                    "Seberapa tenang Anda saat menghadapi ketidakpastian dalam pekerjaan?",
                    "Seberapa sering Anda mengubah pendekatan kerja berdasarkan feedback?",
                    "Seberapa cepat Anda pulih setelah menghadapi kegagalan?",
                    "Seberapa mudah Anda menerima dan menerapkan kritik yang membangun?"],
            'LED': ["Seberapa sering Anda mengambil inisiatif dalam proyek tanpa diminta?",
                    "Seberapa mudah Anda memotivasi rekan yang kehilangan semangat?",
                    "Seberapa sering Anda mendelegasikan tugas dengan efektif?",
                    "Seberapa baik Anda membuat keputusan di bawah tekanan?",
                    "Seberapa sering Anda memberikan arahan yang jelas kepada tim?",
                    "Seberapa mudah Anda mengelola konflik antar anggota tim?"],
            'PRB': ["Seberapa cepat Anda mengidentifikasi penyebab utama sebuah masalah?",
                    "Seberapa sering Anda menggunakan data untuk mendukung solusi?",
                    "Seberapa mudah Anda memecah masalah besar menjadi langkah-langkah kecil?",
                    "Seberapa sering Anda mencari solusi jangka panjang daripada hanya patch?",
                    "Seberapa baik Anda mengevaluasi dampak dari solusi yang diterapkan?",
                    "Seberapa sering Anda mendokumentasikan solusi untuk referensi mendatang?"],
            'DET': ["Seberapa teliti Anda dalam memeriksa pekerjaan sebelum diserahkan?",
                    "Seberapa sering Anda menemukan kesalahan kecil yang luput dari orang lain?",
                    "Seberapa konsisten Anda dalam mengikuti standar yang berlaku?",
                    "Seberapa baik Anda menjaga kerapian dan organisasi file/kode?",
                    "Seberapa sering Anda membuat catatan saat mengerjakan sesuatu?",
                    "Seberapa teliti Anda membaca dan memahami spesifikasi requirement?"],
        }

        likert_opts = [
            ('Tidak Pernah / Sangat Tidak Setuju', 1),
            ('Jarang / Tidak Setuju',              2),
            ('Kadang-kadang / Netral',             3),
            ('Sering / Setuju',                    4),
            ('Selalu / Sangat Setuju',             5),
        ]

        position_objs = []
        for pcfg in positions_cfg:
            pos = RecruitmentPosition.query.filter_by(
                recruitment_id=rec.id, title=pcfg['title']
            ).first()
            if not pos:
                pos = RecruitmentPosition(
                    recruitment_id=rec.id,
                    title=pcfg['title'],
                    description=pcfg['description'],
                    quota=pcfg['quota'],
                    status='active',
                )
                db.session.add(pos)
                db.session.commit()
                print(f"  ➕ Position '{pcfg['title']}' created.")
            else:
                print(f"  ⏭️  Position '{pcfg['title']}' exists.")

            # PositionCriteria + Questions + Options
            pc_objs = {}
            for order, (ccode, (weight, ctype)) in enumerate(pcfg['criteria'].items(), 1):
                crit = criteria_objs[ccode]
                pc = PositionCriteria.query.filter_by(
                    position_id=pos.id, criteria_id=crit.id
                ).first()
                if not pc:
                    pc = PositionCriteria(
                        position_id=pos.id,
                        criteria_id=crit.id,
                        weight_manual=weight,
                        criteria_type=ctype,
                        fuzzy_low=1, fuzzy_mid=3, fuzzy_high=5,
                        display_order=order * 10,
                    )
                    db.session.add(pc)
                    db.session.commit()
                pc_objs[ccode] = pc

                # Questions
                q_texts = questions_map.get(ccode, [])
                for qorder, qtext in enumerate(q_texts, 1):
                    q = AssessmentQuestion.query.filter_by(
                        position_criteria_id=pc.id, display_order=qorder * 10
                    ).first()
                    if not q:
                        q = AssessmentQuestion(
                            position_criteria_id=pc.id,
                            question_text=qtext,
                            display_order=qorder * 10,
                            is_active=True,
                        )
                        db.session.add(q)
                        db.session.commit()
                        for otext, oval in likert_opts:
                            opt = AssessmentOption(
                                question_id=q.id,
                                option_text=otext,
                                option_value=oval,
                                display_order=oval,
                            )
                            db.session.add(opt)
                        db.session.commit()

            print(f"  ✅ Criteria + questions ready for '{pcfg['title']}'.")
            position_objs.append((pos, pc_objs))

        # ── Candidates: Profile, Education, Application, Answers ────
        print("\n📦 Seeding candidate applications (20 kandidat × 1 posisi)...")

        # Backend: kandidat 0-9 | Frontend: kandidat 10-19
        assignments = [
            (position_objs[0], candidate_users[:10]),
            (position_objs[1], candidate_users[10:]),
        ]

        unis = ['Universitas Indonesia', 'Universitas Gadjah Mada', 'ITS',
                'Institut Teknologi Bandung', 'Universitas Brawijaya',
                'Universitas Diponegoro', 'Universitas Telkom',
                'Binus University', 'Universitas Padjadjaran', 'Universitas Airlangga']
        majors = ['Teknik Informatika', 'Sistem Informasi',
                  'Ilmu Komputer', 'Teknik Elektro']

        for (pos, pc_objs), candidates in assignments:
            # Kumpulkan semua question+options untuk posisi ini
            all_q = []
            for ccode, pc in pc_objs.items():
                for q in AssessmentQuestion.query.filter_by(
                    position_criteria_id=pc.id, is_active=True
                ).all():
                    opts = AssessmentOption.query.filter_by(
                        question_id=q.id
                    ).order_by(AssessmentOption.display_order).all()
                    all_q.append((q, opts))

            for cand in candidates:
                # CandidateProfile
                if not CandidateProfile.query.filter_by(user_id=cand.id).first():
                    CandidateProfile(
                        user_id=cand.id,
                        gender=random.choice(['male', 'female']),
                    ).save()

                # CandidateEducation (graduation_year & is_latest — sesuai model)
                if not CandidateEducation.query.filter_by(user_id=cand.id).first():
                    gpa = round(random.uniform(2.85, 3.95), 2)
                    edu = CandidateEducation(
                        user_id=cand.id,
                        degree='S1',
                        institution=random.choice(unis),
                        major=random.choice(majors),
                        gpa=gpa,
                        gpa_scale=4.00,
                        graduation_year=random.choice([2020, 2021, 2022]),
                        is_latest=True,
                    )
                    db.session.add(edu)
                    db.session.commit()
                else:
                    edu = CandidateEducation.query.filter_by(
                        user_id=cand.id
                    ).first()

                # CandidateApplication
                app_obj = CandidateApplication.query.filter_by(
                    user_id=cand.id, position_id=pos.id
                ).first()
                if app_obj:
                    print(f"  ⏭️  {cand.email} → {pos.title} (exists)")
                    continue

                app_obj = CandidateApplication(
                    user_id=cand.id,
                    position_id=pos.id,
                    status='submitted',
                    submitted_at=datetime.utcnow(),
                )
                db.session.add(app_obj)
                db.session.commit()

                # AssessmentAnswers — distribusi realistis (3-5 lebih sering)
                weights_dist = [5, 15, 30, 30, 20]
                for q, opts in all_q:
                    if not opts:
                        continue
                    w = weights_dist[:len(opts)]
                    chosen = random.choices(opts, weights=w, k=1)[0]
                    ans = AssessmentAnswer(
                        application_id=app_obj.id,
                        question_id=q.id,
                        option_id=chosen.id,
                        answer_value=chosen.option_value,
                    )
                    db.session.add(ans)

                # CandidateRequirement — pakai recruitment_requirement_id (sesuai model)
                gpa_val = float(edu.gpa) if edu and edu.gpa else round(random.uniform(2.85, 3.95), 2)
                toefl   = random.randint(420, 640)
                cert    = random.choices([0, 1, 2, 3], weights=[20, 40, 30, 10], k=1)[0]

                for code, raw_val in [('GPA', gpa_val), ('TOEFL', toefl), ('CERT', cert)]:
                    rr = rr_objs.get(code)
                    if rr:
                        cr = CandidateRequirement(
                            application_id=app_obj.id,
                            recruitment_requirement_id=rr.id,
                            raw_value=raw_val,
                        )
                        db.session.add(cr)

                db.session.commit()
                print(f"  ✅ {cand.email} → {pos.title}")

        print("\n" + "=" * 60)
        print("  ✅ SEEDING COMPLETED!")
        print("=" * 60)
        print()
        print("📋 Akun Login:")
        print("  Admin     → admin@company.com  / password")
        print("  Admin     → hr@company.com     / password")
        print("  Kandidat  → budi@email.com     / password")
        print("  Kandidat  → rizky@email.com    / password")
        print("  (semua 20 kandidat password = 'password')")
        print()
        print("🌐 Jalankan server: python run.py")
        print("   API: http://localhost:5100/api")
        print()


if __name__ == '__main__':
    seed()
