from flask import Blueprint

club_portal = Blueprint('club_portal', __name__, template_folder='../templates/club')

from . import routes
