from keg_elements.forms import Form, ModelForm, FieldMeta
from keg_elements.forms.validators import ValidateUnique
from sqlalchemy_utils import EmailType
from webhelpers2.html.tags import link_to
from wtforms.fields import (
    HiddenField,
    PasswordField,
    StringField,
    SelectMultipleField)
from wtforms import ValidationError, validators
from wtforms_components.widgets import EmailInput

from keg_auth.model import entity_registry


def login_form(config):
    login_id_label = u'User ID'
    login_id_validators = [validators.DataRequired()]

    if isinstance(
        getattr(entity_registry.registry.user_cls, config.get('KEGAUTH_USER_IDENT_FIELD')).type,
        EmailType
    ):
        login_id_label = u'Email'
        login_id_validators.append(validators.Email())

    class Login(Form):
        next = HiddenField()

        login_id = StringField(login_id_label, validators=login_id_validators)
        password = PasswordField('Password', validators=[
            validators.DataRequired(),
        ])

    return Login


class ForgotPassword(Form):
    email = StringField(u'Email', validators=[
        validators.DataRequired(),
        validators.Email(),
    ])


class SetPassword(Form):
    password = PasswordField('New Password', validators=[
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Confirm Password')


def get_permission_options():
    perm_cls = entity_registry.registry.permission_cls
    return [(str(perm.id), perm.description) for perm in perm_cls.query.order_by('description')]


def get_bundle_options():
    bundle_cls = entity_registry.registry.bundle_cls
    return [(str(bundle.id), bundle.name) for bundle in bundle_cls.query.order_by('name')]


def get_group_options():
    group_cls = entity_registry.registry.group_cls
    return [(str(group.id), group.name) for group in group_cls.query.order_by('name')]


def entities_from_ids(cls, ids):
    if not ids:
        return []
    return cls.query.filter(cls.id.in_(ids)).all()


class PermissionsMixin(object):
    permission_ids = SelectMultipleField('Permissions')

    def get_selected_permissions(self):
        return entities_from_ids(entity_registry.registry.permission_cls, self.permission_ids.data)


class BundlesMixin(object):
    bundle_ids = SelectMultipleField('Bundles')

    def get_selected_bundles(self):
        return entities_from_ids(entity_registry.registry.bundle_cls, self.bundle_ids.data)


class _ValidatePasswordRequired(object):
    def __call__(self, form, field):
        if not form.obj and not field.data:
            raise ValidationError('This field is required.')
        return True


def user_form(config, allow_superuser=False, endpoint='', fields=['is_enabled']):
    user_cls = entity_registry.registry.user_cls

    # create a copy of fields for internal use. In python 2, if we use this as a static method,
    #   the kwarg value would get modified in the wrong scope
    _fields = [config.get('KEGAUTH_USER_IDENT_FIELD')] + fields[:]
    if allow_superuser and 'is_superuser' not in _fields:
        _fields.append('is_superuser')

    def html_link(obj):
        import flask
        return link_to(
            getattr(obj, config.get('KEGAUTH_USER_IDENT_FIELD')),
            flask.url_for(endpoint, objid=obj.id)
        )

    class User(ModelForm, PermissionsMixin, BundlesMixin):
        class Meta:
            model = user_cls
            only = _fields

        class FieldsMeta:
            is_enabled = FieldMeta('Enabled')
            is_superuser = FieldMeta('Superuser')
            __default__ = FieldMeta

        field_order = tuple(_fields + ['group_ids', 'bundle_ids', 'permission_ids'])

        setattr(FieldsMeta, config.get('KEGAUTH_USER_IDENT_FIELD'), FieldMeta(
            extra_validators=[validators.data_required(),
                              ValidateUnique(html_link)]
        ))

        if isinstance(
            getattr(entity_registry.registry.user_cls, config.get('KEGAUTH_USER_IDENT_FIELD')).type,
            EmailType
        ):
            meta_field = getattr(FieldsMeta, config.get('KEGAUTH_USER_IDENT_FIELD'))
            meta_field.widget = EmailInput()

        if not config.get('KEGAUTH_EMAIL_OPS_ENABLED'):
            reset_password = PasswordField('New Password', validators=[
                _ValidatePasswordRequired(),
                validators.EqualTo('confirm', message='Passwords must match')
            ])
            confirm = PasswordField('Confirm Password')
            field_order = field_order + ('reset_password', 'confirm')

        group_ids = SelectMultipleField('Groups')

        def after_init(self, args, kwargs):
            self.permission_ids.choices = get_permission_options()
            self.bundle_ids.choices = get_bundle_options()
            self.group_ids.choices = get_group_options()

        def get_selected_groups(self):
            return entities_from_ids(entity_registry.registry.group_cls, self.group_ids.data)

        def get_object_by_field(self, field):
            return user_cls.get_by(**{config.get('KEGAUTH_USER_IDENT_FIELD'): field.data})

        @property
        def obj(self):
            return self._obj

        def __iter__(self):
            order = ('csrf_token', ) + self.field_order
            return (getattr(self, field_id) for field_id in order)

    return User


def group_form(endpoint):
    group_cls = entity_registry.registry.group_cls

    def html_link(obj):
        import flask
        return link_to(obj.name, flask.url_for(endpoint, objid=obj.id))

    class Group(ModelForm, PermissionsMixin, BundlesMixin):
        class Meta:
            model = group_cls

        class FieldsMeta:
            name = FieldMeta(extra_validators=[ValidateUnique(html_link)])

        def after_init(self, args, kwargs):
            self.permission_ids.choices = get_permission_options()
            self.bundle_ids.choices = get_bundle_options()

        def get_object_by_field(self, field):
            return group_cls.get_by(name=field.data)

        @property
        def obj(self):
            return self._obj

    return Group


def bundle_form(endpoint):
    bundle_cls = entity_registry.registry.bundle_cls

    def html_link(obj):
        import flask
        return link_to(obj.name, flask.url_for(endpoint, objid=obj.id))

    class Bundle(ModelForm, PermissionsMixin):
        class Meta:
            model = bundle_cls

        class FieldsMeta:
            name = FieldMeta(extra_validators=[ValidateUnique(html_link)])

        def after_init(self, args, kwargs):
            self.permission_ids.choices = get_permission_options()

        def get_object_by_field(self, field):
            return bundle_cls.get_by(name=field.data)

        @property
        def obj(self):
            return self._obj

    return Bundle
