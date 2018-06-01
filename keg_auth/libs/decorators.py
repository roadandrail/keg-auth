import inspect

import flask
import flask_login

from keg_auth.model import utils as model_utils


class RequiresUser:
    def __init__(self, on_authentication_failure=None, on_authorization_failure=None):
        self._on_authentication_failure = on_authentication_failure
        self._on_authorization_failure = on_authorization_failure

    def __call__(self, class_or_function):
        if inspect.isclass(class_or_function):
            return self.decorate_class(class_or_function)
        return self.decorate_function(class_or_function)

    def decorate_class(self, cls):
        old_check_auth = getattr(cls, 'check_auth', lambda: None)

        def new_check_auth(*args, **kwargs):
            self.check_auth()
            return old_check_auth(*args, **kwargs)
        cls.check_auth = new_check_auth

    def decorate_function(self, func):
        def wrapper(*args, **kwargs):
            self.check_auth()
            return func(*args, **kwargs)
        wrapper.__name__ = getattr(func, '__name__', 'wrapper')
        return wrapper

    def on_authentication_failure(self):
        if self._on_authentication_failure:
            self._on_authentication_failure()
        redirect_resp = flask.current_app.login_manager.unauthorized()
        flask.abort(redirect_resp)

    def on_authorization_failure(self):
        if self._on_authorization_failure:
            self._on_authorization_failure()
        flask.abort(403)

    def check_auth(self):
        user = flask_login.current_user
        if not user or not user.is_authenticated:
            self.on_authentication_failure()


class RequiresPermissions(RequiresUser):
    """ Require a user to be conditionally authorized before proceeding to decorated target. May be
        used as a class decorator or method decorator.

        Usage: @requires_permissions(condition)

        Note: if using along with a route decorator (e.g. Blueprint.route), requires_permissions
            should be the closest decorator to the method

        Examples:
        - @requires_permissions(('token1', 'token2'))
        - @requires_permissions(has_any('token1', 'token2'))
        - @requires_permissions(has_all('token1', 'token2'))
        - @requires_permissions(has_all(has_any('token1', 'token2'), 'token3'))
        - @requires_permissions(custom_authorization_callable that takes user arg)
    """
    def __init__(self, condition, on_authentication_failure=None, on_authorization_failure=None):
        super(RequiresPermissions, self).__init__(
            on_authentication_failure=on_authentication_failure,
            on_authorization_failure=on_authorization_failure,
        )
        self.condition = condition

    def check_auth(self):
        super(RequiresPermissions, self).check_auth()

        user = flask_login.current_user
        if not model_utils.has_permissions(self.condition, user):
            self.on_authorization_failure()


def requires_user(arg=None, *args, **kwargs):
    """ Require a user to be authenticated before proceeding to decorated target. May be used as
        a class decorator or method decorator.

        Usage: @requires_user OR @requires_user()
        Note: both usage forms are identical
    """
    if arg is None:
        return RequiresUser(*args, **kwargs)
    if inspect.isclass(arg):
        return RequiresUser().decorate_class(arg)
    return RequiresUser().decorate_function(arg)


requires_permissions = RequiresPermissions
