import flask
import flask_login
import webgrid
from webgrid import filters
from webhelpers2.html import literal
from webhelpers2.html.tags import link_to

from keg_auth.model.utils import has_permissions


class ActionColumn(webgrid.Column):
    """Places various action buttons in a Column.

    Since actions can be protected by permissions, this column must reside in a ProtectedGrid.
    """

    def __init__(self,
                 label,
                 key=None,
                 filter=None,
                 can_sort=False,
                 render_in=('html',),
                 has_subtotal=False,
                 edit_endpoint=None,
                 delete_endpoint=None,
                 view_endpoint=None,
                 edit_permission_for=lambda row: None,
                 delete_permission_for=lambda row: None,
                 view_permission_for=lambda row: None,
                 delete_link_class_for=lambda row: 'delete-link confirm-delete',
                 **kwargs):
        """
        :param edit_permission_for: is a function that takes a row and returns the permission
                                    required to open the edit endpoint for that row.
        :param delete_permission_for: is like `edit_permission_for`, but for the delete endpoint.
        :param view_permission_for: is like `edit_permission_for`, but for the view endpoint.
        :param delete_link_class_for: is a function that takes a row and returns the HTML class to
                                      place on the delete link.
        """
        self.edit_endpoint = edit_endpoint
        self.delete_endpoint = delete_endpoint
        self.view_endpoint = view_endpoint
        self.edit_permission_for = edit_permission_for
        self.delete_permission_for = delete_permission_for
        self.view_permission_for = view_permission_for
        self.delete_link_class_for = delete_link_class_for

        super(ActionColumn, self).__init__(label, key=key, filter=filter, can_sort=can_sort,
                                           render_in=render_in, has_subtotal=has_subtotal, **kwargs)

    def extract_and_format_data(self, record):
        view_perm = self.view_permission_for(record)
        edit_perm = self.edit_permission_for(record)
        delete_perm = self.delete_permission_for(record)
        can_edit = has_permissions(edit_perm, flask_login.current_user)
        can_delete = has_permissions(delete_perm, flask_login.current_user)
        can_view = (
            (self.edit_endpoint != self.view_endpoint or not can_edit) and
            has_permissions(view_perm, flask_login.current_user)
        )

        delete_link_class = self.delete_link_class_for(record)
        data = self.extract_data(record)
        return self.format_data(data, can_edit, can_delete, can_view, delete_link_class)

    def format_data(self, value, show_edit, show_delete, show_view, delete_link_class):
        result = literal()
        if self.edit_endpoint and show_edit:
            result += link_to(
                literal('&nbsp;'),
                flask.url_for(self.edit_endpoint, objid=value, session_key=self.grid.session_key),
                **{
                    'aria-label': 'Edit',
                    'class_': 'edit-link',
                    'title': 'Edit'
                }
            )
        if self.delete_endpoint and show_delete:
            result += link_to(
                literal('&nbsp;'),
                flask.url_for(self.delete_endpoint, objid=value, session_key=self.grid.session_key),
                **{
                    'aria-label': 'Delete',
                    'class_': delete_link_class,
                    'title': 'Delete'
                }
            )
        if self.view_endpoint and show_view:
            result += link_to(
                literal('&nbsp;'),
                flask.url_for(self.view_endpoint, objid=value, session_key=self.grid.session_key),
                **{
                    'aria-label': 'View',
                    'class_': 'view-link',
                    'title': 'View'
                }
            )
        return result


def make_user_grid(edit_endpoint, edit_permission, delete_endpoint, delete_permission,
                   grid_cls=None):
    user_cls = flask.current_app.auth_manager.entity_registry.user_cls
    grid_cls = grid_cls or flask.current_app.auth_manager.grid_cls

    class User(grid_cls):
        ActionColumn(
            '',
            user_cls.id,
            edit_endpoint=edit_endpoint,
            delete_endpoint=delete_endpoint,
            edit_permission_for=lambda _: edit_permission,
            delete_permission_for=lambda _: delete_permission
        )
        webgrid.Column('User ID', user_cls.username, filters.TextFilter)
        if flask.current_app.auth_manager.mail_manager and hasattr(user_cls, 'is_verified'):
            webgrid.YesNoColumn('Verified', user_cls.is_verified, filters.YesNoFilter)
        webgrid.YesNoColumn('Superuser', user_cls.is_superuser, filters.YesNoFilter)

        def query_prep(self, query, has_sort, has_filters):
            if not has_sort:
                query = query.order_by(user_cls.username)
            return query
    return User


def make_group_grid(edit_endpoint, edit_permission, delete_endpoint, delete_permission,
                    grid_cls=None):
    group_cls = flask.current_app.auth_manager.entity_registry.group_cls
    grid_cls = grid_cls or flask.current_app.auth_manager.grid_cls

    class Group(grid_cls):
        ActionColumn(
            '',
            group_cls.id,
            edit_endpoint=edit_endpoint,
            delete_endpoint=delete_endpoint,
            edit_permission_for=lambda _: edit_permission,
            delete_permission_for=lambda _: delete_permission
        )
        webgrid.Column('Name', group_cls.name, filters.TextFilter)

        def query_prep(self, query, has_sort, has_filters):
            if not has_sort:
                query = query.order_by(group_cls.name)
            return query
    return Group


def make_bundle_grid(edit_endpoint, edit_permission, delete_endpoint, delete_permission,
                     grid_cls=None):
    bundle_cls = flask.current_app.auth_manager.entity_registry.bundle_cls
    grid_cls = grid_cls or flask.current_app.auth_manager.grid_cls

    class Bundle(grid_cls):
        ActionColumn(
            '',
            bundle_cls.id,
            edit_endpoint=edit_endpoint,
            delete_endpoint=delete_endpoint,
            edit_permission_for=lambda _: edit_permission,
            delete_permission_for=lambda _: delete_permission
        )
        webgrid.Column('Name', bundle_cls.name, filters.TextFilter)

        def query_prep(self, query, has_sort, has_filters):
            if not has_sort:
                query = query.order_by(bundle_cls.name)
            return query
    return Bundle


def make_permission_grid(grid_cls=None):
    permission_cls = flask.current_app.auth_manager.entity_registry.permission_cls
    grid_cls = grid_cls or flask.current_app.auth_manager.grid_cls

    class Permission(grid_cls):
        webgrid.Column('Name', permission_cls.token, filters.TextFilter)
        webgrid.Column('Description', permission_cls.description, filters.TextFilter)

        def query_prep(self, query, has_sort, has_filters):
            if not has_sort:
                query = query.order_by(permission_cls.token)
            return query
    return Permission