"""
Routes: API Thesis Flask
Struktur URL:
  /api/auth/...      → autentikasi
  /api/master/...    → CRUD data master (admin only)
  /api/content/...   → aksi kandidat
  /api/report/...    → laporan & hasil seleksi (admin)
"""
from flask import Blueprint, jsonify
import datetime

api_bp = Blueprint('api', __name__)

# Health check — tidak butuh database
@api_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "success": True,
        "message": "API is running",
        "service": "Psychoposition API",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }), 200

# Info — informasi umum API (tidak ada data sensitif)
@api_bp.route('/info', methods=['GET'])
def api_info():
    return jsonify({
        "success": True,
        "api": {
            "name": "Psychoposition API",
            "version": "1.0.0",
            "description": (
                "REST API untuk sistem seleksi kandidat berbasis psikologi "
                "menggunakan metode AHP dan machine learning."
            ),
            "language": "Python",
            "framework": "Flask",
            "status": "active",
        },
        "endpoints": {
            "auth":    "/api/auth/*    — autentikasi (login, register, token)",
            "master":  "/api/master/*  — manajemen data master (admin)",
            "content": "/api/content/* — aksi kandidat (profil, lamaran, asesmen)",
            "report":  "/api/report/*  — laporan & hasil seleksi (admin)",
            "health":  "/api/health    — cek status API",
            "info":    "/api/info      — informasi umum API (halaman ini)",
        },
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }), 200

# Auth
from app.controllers.auth_controller import login, register, me, refresh, logout, logout_all
api_bp.add_url_rule('/auth/login',      view_func=login,      methods=['POST'], endpoint='auth_login')
api_bp.add_url_rule('/auth/register',   view_func=register,   methods=['POST'], endpoint='auth_register')
api_bp.add_url_rule('/auth/me',         view_func=me,         methods=['GET'],  endpoint='auth_me')
api_bp.add_url_rule('/auth/refresh',    view_func=refresh,    methods=['POST'], endpoint='auth_refresh')
api_bp.add_url_rule('/auth/logout',     view_func=logout,     methods=['POST'], endpoint='auth_logout')
api_bp.add_url_rule('/auth/logout-all', view_func=logout_all, methods=['POST'], endpoint='auth_logout_all')

# Master: Users & Roles
from app.controllers.user_controller import index as u_index, store as u_store, show as u_show, update as u_update, destroy as u_destroy
from app.controllers.role_controller import index as r_index, store as r_store, show as r_show, update as r_update, destroy as r_destroy
api_bp.add_url_rule('/master/users',          view_func=u_index,   methods=['GET'],    endpoint='master_user_index')
api_bp.add_url_rule('/master/users',          view_func=u_store,   methods=['POST'],   endpoint='master_user_store')
api_bp.add_url_rule('/master/users/<int:id>', view_func=u_show,    methods=['GET'],    endpoint='master_user_show')
api_bp.add_url_rule('/master/users/<int:id>', view_func=u_update,  methods=['PUT'],    endpoint='master_user_update')
api_bp.add_url_rule('/master/users/<int:id>', view_func=u_destroy, methods=['DELETE'], endpoint='master_user_destroy')
api_bp.add_url_rule('/master/roles',          view_func=r_index,   methods=['GET'],    endpoint='master_role_index')
api_bp.add_url_rule('/master/roles',          view_func=r_store,   methods=['POST'],   endpoint='master_role_store')
api_bp.add_url_rule('/master/roles/<int:id>', view_func=r_show,    methods=['GET'],    endpoint='master_role_show')
api_bp.add_url_rule('/master/roles/<int:id>', view_func=r_update,  methods=['PUT'],    endpoint='master_role_update')
api_bp.add_url_rule('/master/roles/<int:id>', view_func=r_destroy, methods=['DELETE'], endpoint='master_role_destroy')

# Master: Criteria & Requirement Types
from app.controllers.master.criteria_controller import (
    criteria_index, criteria_store, criteria_show, criteria_update, criteria_destroy,
    reqtype_index, reqtype_store, reqtype_show, reqtype_update, reqtype_destroy,
)
api_bp.add_url_rule('/master/criteria',          view_func=criteria_index,   methods=['GET'],    endpoint='criteria_index')
api_bp.add_url_rule('/master/criteria',          view_func=criteria_store,   methods=['POST'],   endpoint='criteria_store')
api_bp.add_url_rule('/master/criteria/<int:id>', view_func=criteria_show,    methods=['GET'],    endpoint='criteria_show')
api_bp.add_url_rule('/master/criteria/<int:id>', view_func=criteria_update,  methods=['PUT'],    endpoint='criteria_update')
api_bp.add_url_rule('/master/criteria/<int:id>', view_func=criteria_destroy, methods=['DELETE'], endpoint='criteria_destroy')
api_bp.add_url_rule('/master/requirement-types',          view_func=reqtype_index,   methods=['GET'],    endpoint='reqtype_index')
api_bp.add_url_rule('/master/requirement-types',          view_func=reqtype_store,   methods=['POST'],   endpoint='reqtype_store')
api_bp.add_url_rule('/master/requirement-types/<int:id>', view_func=reqtype_show,    methods=['GET'],    endpoint='reqtype_show')
api_bp.add_url_rule('/master/requirement-types/<int:id>', view_func=reqtype_update,  methods=['PUT'],    endpoint='reqtype_update')
api_bp.add_url_rule('/master/requirement-types/<int:id>', view_func=reqtype_destroy, methods=['DELETE'], endpoint='reqtype_destroy')

# Master: Recruitment
from app.controllers.master.recruitment_controller import (
    recruitment_index, recruitment_store, recruitment_show,
    recruitment_update, recruitment_publish, recruitment_close, recruitment_destroy,
    requirement_setup,
    position_index, position_store, position_show, position_update, position_destroy,
    position_criteria_setup,
    question_index, question_store, question_update, question_destroy,
    option_store, option_update, option_destroy,
)
api_bp.add_url_rule('/master/recruitments',                  view_func=recruitment_index,   methods=['GET'],    endpoint='recruitment_index')
api_bp.add_url_rule('/master/recruitments',                  view_func=recruitment_store,   methods=['POST'],   endpoint='recruitment_store')
api_bp.add_url_rule('/master/recruitments/<int:id>',         view_func=recruitment_show,    methods=['GET'],    endpoint='recruitment_show')
api_bp.add_url_rule('/master/recruitments/<int:id>',         view_func=recruitment_update,  methods=['PUT'],    endpoint='recruitment_update')
api_bp.add_url_rule('/master/recruitments/<int:id>/publish', view_func=recruitment_publish, methods=['POST'],   endpoint='recruitment_publish')
api_bp.add_url_rule('/master/recruitments/<int:id>/close',   view_func=recruitment_close,   methods=['POST'],   endpoint='recruitment_close')
api_bp.add_url_rule('/master/recruitments/<int:id>',         view_func=recruitment_destroy, methods=['DELETE'], endpoint='recruitment_destroy')
api_bp.add_url_rule('/master/recruitments/<int:recruitment_id>/requirements', view_func=requirement_setup, methods=['POST'], endpoint='requirement_setup')
api_bp.add_url_rule('/master/recruitments/<int:recruitment_id>/positions',                            view_func=position_index,          methods=['GET'],    endpoint='position_index')
api_bp.add_url_rule('/master/recruitments/<int:recruitment_id>/positions',                            view_func=position_store,          methods=['POST'],   endpoint='position_store')
api_bp.add_url_rule('/master/recruitments/<int:recruitment_id>/positions/<int:position_id>',          view_func=position_show,           methods=['GET'],    endpoint='position_show')
api_bp.add_url_rule('/master/recruitments/<int:recruitment_id>/positions/<int:position_id>',          view_func=position_update,         methods=['PUT'],    endpoint='position_update')
api_bp.add_url_rule('/master/recruitments/<int:recruitment_id>/positions/<int:position_id>',          view_func=position_destroy,        methods=['DELETE'], endpoint='position_destroy')
api_bp.add_url_rule('/master/recruitments/<int:recruitment_id>/positions/<int:position_id>/criteria', view_func=position_criteria_setup, methods=['POST'],   endpoint='position_criteria_setup')
api_bp.add_url_rule('/master/position-criteria/<int:position_criteria_id>/questions',                 view_func=question_index,          methods=['GET'],    endpoint='question_index')
api_bp.add_url_rule('/master/position-criteria/<int:position_criteria_id>/questions',                 view_func=question_store,          methods=['POST'],   endpoint='question_store')
api_bp.add_url_rule('/master/position-criteria/<int:position_criteria_id>/questions/<int:question_id>', view_func=question_update,       methods=['PUT'],    endpoint='question_update')
api_bp.add_url_rule('/master/position-criteria/<int:position_criteria_id>/questions/<int:question_id>', view_func=question_destroy,      methods=['DELETE'], endpoint='question_destroy')
api_bp.add_url_rule('/master/questions/<int:question_id>/options',               view_func=option_store,   methods=['POST'],   endpoint='option_store')
api_bp.add_url_rule('/master/questions/<int:question_id>/options/<int:option_id>', view_func=option_update, methods=['PUT'],   endpoint='option_update')
api_bp.add_url_rule('/master/questions/<int:question_id>/options/<int:option_id>', view_func=option_destroy,methods=['DELETE'],endpoint='option_destroy')

# Content: Kandidat
from app.controllers.content.candidate_controller import (
    profile_show, profile_update,
    education_index, education_store, education_update, education_destroy,
    recruitment_list, recruitment_detail,
    apply, my_applications,
    assessment_questions, assessment_submit,
    my_result,
)
api_bp.add_url_rule('/content/profile',                                     view_func=profile_show,          methods=['GET'],  endpoint='profile_show')
api_bp.add_url_rule('/content/profile',                                     view_func=profile_update,        methods=['PUT'],  endpoint='profile_update')
api_bp.add_url_rule('/content/educations',                                  view_func=education_index,       methods=['GET'],  endpoint='education_index')
api_bp.add_url_rule('/content/educations',                                  view_func=education_store,       methods=['POST'], endpoint='education_store')
api_bp.add_url_rule('/content/educations/<int:id>',                         view_func=education_update,      methods=['PUT'],  endpoint='education_update')
api_bp.add_url_rule('/content/educations/<int:id>',                         view_func=education_destroy,     methods=['DELETE'],endpoint='education_destroy')
api_bp.add_url_rule('/content/recruitments',                                view_func=recruitment_list,      methods=['GET'],  endpoint='content_recruitment_list')
api_bp.add_url_rule('/content/recruitments/<int:recruitment_id>',           view_func=recruitment_detail,    methods=['GET'],  endpoint='content_recruitment_detail')
api_bp.add_url_rule('/content/apply/<int:position_id>',                     view_func=apply,                 methods=['POST'], endpoint='content_apply')
api_bp.add_url_rule('/content/my-applications',                             view_func=my_applications,       methods=['GET'],  endpoint='my_applications')
api_bp.add_url_rule('/content/applications/<int:application_id>/questions', view_func=assessment_questions,  methods=['GET'],  endpoint='assessment_questions')
api_bp.add_url_rule('/content/applications/<int:application_id>/submit',    view_func=assessment_submit,     methods=['POST'], endpoint='assessment_submit')
api_bp.add_url_rule('/content/applications/<int:application_id>/result',    view_func=my_result,             methods=['GET'],  endpoint='my_result')

# Report: Admin
from app.controllers.report.report_controller import (
    generate_ranking, ranking_by_position, ranking_detail,
    choose_ranking_version, finalize_candidate,
    verify_requirements, dashboard, ml_logs,
)
api_bp.add_url_rule('/report/dashboard',                                          view_func=dashboard,              methods=['GET'],  endpoint='dashboard')
api_bp.add_url_rule('/report/generate/<int:position_id>',                         view_func=generate_ranking,       methods=['POST'], endpoint='generate_ranking')
api_bp.add_url_rule('/report/ranking/<int:position_id>',                          view_func=ranking_by_position,    methods=['GET'],  endpoint='ranking_by_position')
api_bp.add_url_rule('/report/ranking/<int:position_id>/detail/<int:application_id>', view_func=ranking_detail,      methods=['GET'],  endpoint='ranking_detail')
api_bp.add_url_rule('/report/ranking/<int:position_id>/choose',                   view_func=choose_ranking_version, methods=['POST'], endpoint='choose_ranking_version')
api_bp.add_url_rule('/report/ranking/<int:position_id>/finalize/<int:application_id>', view_func=finalize_candidate, methods=['POST'],endpoint='finalize_candidate')
api_bp.add_url_rule('/report/applications/<int:application_id>/verify-requirements', view_func=verify_requirements, methods=['PUT'],  endpoint='verify_requirements')
api_bp.add_url_rule('/report/ml-logs/<int:position_id>',                          view_func=ml_logs,                methods=['GET'],  endpoint='ml_logs')
