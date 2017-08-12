import logging

import flask
import flask_login
from kegauth.views import AuthBaseView, make_blueprint

log = logging.getLogger(__name__)

public_bp = flask.Blueprint('public', __name__,)
private_bp = flask.Blueprint('private', __name__,)
auth_bp = make_blueprint(__name__)

blueprints = public_bp, private_bp, auth_bp


@public_bp.route('/', methods=['GET', 'POST'])
def home():
    return 'home'


# @private_bp.route('/secret1')
# @flask_login.login_required
# def secret1():
#     return 'secret1'


# class Secret2(AuthBaseView):
#     blueprint = private_bp

#     def get(self):
#         return 'secret2'