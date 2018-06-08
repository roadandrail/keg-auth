# Using unicode_literals instead of adding 'u' prefix to all stings that go to SA.
from __future__ import unicode_literals

import arrow
import flask
import pytest
from freezegun import freeze_time
import sqlalchemy as sa

from keg_auth.model import entity_registry, utils
from keg_auth_ta.model import entities as ents
import mock


class TestUser(object):
    def setup(self):
        ents.User.delete_cascaded()
        ents.Permission.delete_cascaded()

    def test_email_case_insensitive(self):
        ents.User.testing_create(email='foo@BAR.com')

        assert ents.User.get_by(email='foo@bar.com')

    def test_is_verified_default(self):
        # testing_create() overrides the is_enabled default to make testing easier.  So, make sure
        # that we have set enabled to False when not used in a testing environment.
        user = ents.User.add(email='foo', password='bar')
        assert not user.is_verified
        assert user.password == 'bar'

    def test_is_active_python_attribute(self):
        # By default, user is inactive because email has not been verified.
        user = ents.User.testing_create(is_verified=False)
        assert user.is_enabled
        assert not user.is_verified
        assert not user.is_active

        # Once email has been verified, user should be active.
        user = ents.User.testing_create()
        assert user.is_active

        # Verified but disabled is also inactive.
        user = ents.User.testing_create(is_verified=True, is_enabled=False)
        assert not user.is_active

    def test_is_active_sql_expression(self):
        ents.User.testing_create(email='1', is_verified=False, is_enabled=True)
        ents.User.testing_create(email='2', is_verified=True, is_enabled=True)
        ents.User.testing_create(email='3', is_verified=True, is_enabled=False)

        assert ents.User.query.filter_by(email='1', is_active=False).one()
        assert ents.User.query.filter_by(email='2', is_active=True).one()
        assert ents.User.query.filter_by(email='3', is_active=False).one()

    def test_token_validation_null_fields(self):
        # Make sure verification doesn't fail when both token related fields are NULL.
        user = ents.User.add(email='f', password='p')
        assert not user.token_verify('foo')

    def test_token_validation(self):
        user = ents.User.testing_create(token_created_utc=None)

        assert user.token is None
        assert not user.token_verify(None)

        token = user.token_generate()
        assert token
        assert user.token is not None
        assert not user.token_verify('foo')
        assert user.token_verify(token)
        assert user.token_verify(token)

    def test_token_expiration(self):
        user = ents.User.add(email='foo', password='bar')
        assert user.token_created_utc is None
        token = user.token_generate()
        now = arrow.get()
        assert user.token_created_utc <= now

        with mock.patch.dict(flask.current_app.config, KEGAUTH_TOKEN_EXPIRE_MINS=10):
            plus_9_58 = now.shift(minutes=9, seconds=58).datetime
            with freeze_time(plus_9_58):
                assert user.token_verify(token)
            plus_10 = now.shift(minutes=10).datetime
            with freeze_time(plus_10):
                assert not user.token_verify(token)

    def test_change_password(self):
        user = ents.User.testing_create(is_verified=False)
        token = user.token_generate()
        user.change_password(token, 'abc123')
        assert not user.token_verify(token)
        assert user.password == 'abc123'
        assert user.is_verified

    def test_permissions_mapping(self):
        perm1 = ents.Permission.testing_create()
        perm2 = ents.Permission.testing_create()
        perm3 = ents.Permission.testing_create()
        perm4 = ents.Permission.testing_create()
        perm5 = ents.Permission.testing_create()

        bundle1 = ents.Bundle.testing_create()
        bundle2 = ents.Bundle.testing_create()
        bundle3 = ents.Bundle.testing_create()

        group1 = ents.Group.testing_create()
        group2 = ents.Group.testing_create()
        group3 = ents.Group.testing_create()

        user1 = ents.User.testing_create()
        user2 = ents.User.testing_create()

        # Directly assigned
        user1.permissions = [perm1]

        # Assigned via user bundle
        bundle1.permissions = [perm2]
        user1.bundles = [bundle1]

        # Assigned via group
        group1.permissions = [perm3]

        # Assigned via group bundle
        bundle2.permissions = [perm4]
        group1.bundles = [bundle2]
        user1.groups = [group1, group2]

        assert user1.get_all_permissions() == {perm1, perm2, perm3, perm4}
        assert user2.get_all_permissions() == set()

        user2.permissions = [perm1, perm2]
        group3.permissions = [perm2, perm3]
        bundle3.permissions = [perm1, perm5]
        group3.bundles = [bundle3]
        user2.groups = [group3]

        assert user1.get_all_permissions() == {perm1, perm2, perm3, perm4}
        assert user2.get_all_permissions() == {perm1, perm2, perm3, perm5}

        user1.is_superuser = True
        assert user1.get_all_permissions() == {perm1, perm2, perm3, perm4, perm5}

    def test_get_all_permission_tokens(self):
        ents.Permission.delete_cascaded()
        perm1 = ents.Permission.testing_create(token='perm-1')
        perm2 = ents.Permission.testing_create(token='perm-2')
        perm3 = ents.Permission.testing_create(token='perm-3')

        user = ents.User.testing_create(permissions=[perm1, perm2, perm3])

        assert user.get_all_permission_tokens() == {'perm-1', 'perm-2', 'perm-3'}

    def test_has_all_permissions(self):
        ents.Permission.delete_cascaded()
        perm1 = ents.Permission.testing_create(token='perm-1')
        perm2 = ents.Permission.testing_create(token='perm-2')
        ents.Permission.testing_create(token='perm-3')

        user = ents.User.testing_create(permissions=[perm1, perm2])

        assert user.has_all_permissions('perm-1', 'perm-2') is True
        assert user.has_all_permissions('perm-1', 'perm-3') is False
        assert user.has_all_permissions('perm-1') is True
        assert user.has_all_permissions('perm-3') is False

    def test_has_any_permission(self):
        ents.Permission.delete_cascaded()
        perm1 = ents.Permission.testing_create(token='perm-1')
        perm2 = ents.Permission.testing_create(token='perm-2')
        ents.Permission.testing_create(token='perm-3')

        user = ents.User.testing_create(permissions=[perm1, perm2])

        assert user.has_any_permission('perm-1', 'perm-2') is True
        assert user.has_any_permission('perm-1', 'perm-3') is True
        assert user.has_any_permission('perm-1') is True
        assert user.has_any_permission('perm-3') is False


class TestPermission(object):
    def setup(self):
        ents.Permission.delete_cascaded()

    def test_token_unique(self):
        ents.Permission.testing_create(token='some-permission')
        with pytest.raises(sa.exc.IntegrityError) as exc:
            # use `add` here instead of `testing_create`, because it is more helpful for the
            #   `testing_create` method to return the existing permission if there is a match
            ents.Permission.add(token='some-permission')

        assert 'unique' in str(exc.value).lower()


class TestBundle(object):
    def setup(self):
        ents.Bundle.delete_cascaded()

    def test_name_unique(self):
        ents.Bundle.testing_create(name='Bundle 1')
        with pytest.raises(sa.exc.IntegrityError) as exc:
            ents.Bundle.testing_create(name='Bundle 1')

        assert 'unique' in str(exc.value).lower()


class TestGroup(object):
    def setup(self):
        ents.Group.delete_cascaded()

    def test_name_unique(self):
        ents.Group.testing_create(name='Group 1')
        with pytest.raises(sa.exc.IntegrityError) as exc:
            ents.Group.testing_create(name='Group 1')

        assert 'unique' in str(exc.value).lower()

    def test_get_all_permissions(self):
        perm1 = ents.Permission.testing_create()
        perm2 = ents.Permission.testing_create()
        perm3 = ents.Permission.testing_create()

        bundle = ents.Bundle.testing_create()

        group1 = ents.Group.testing_create()
        group2 = ents.Group.testing_create()

        # Assigned directly
        group1.permissions = [perm1]

        # Assigned via bundle
        bundle.permissions = [perm2]
        group1.bundles = [bundle]

        assert group1.get_all_permissions() == {perm1, perm2}
        assert group2.get_all_permissions() == set()

        group2.bundles = [bundle]
        group2.permissions = [perm2, perm3]

        assert group1.get_all_permissions() == {perm1, perm2}
        assert group2.get_all_permissions() == {perm2, perm3}


class TestEntityRegistry(object):
    def test_register_entities(self):
        registry = entity_registry.EntityRegistry()

        @registry.register_user
        class TestingUser(object):
            pass

        @registry.register_permission
        class TestingPermission(object):
            pass

        @registry.register_bundle
        class TestingBundle(object):
            pass

        @registry.register_group
        class TestingGroup(object):
            pass

        assert registry.user_cls is TestingUser
        assert registry.permission_cls is TestingPermission
        assert registry.bundle_cls is TestingBundle
        assert registry.group_cls is TestingGroup

    def test_duplicate_registration(self):
        registry = entity_registry.EntityRegistry()

        @registry.register_user
        class TestingUser1(object):
            pass

        with pytest.raises(entity_registry.RegistryError) as exc:
            @registry.register_user
            class TestingUser2(object):
                pass

        assert str(exc.value) == 'Entity class already registered for user'

    def test_register_unknown_type(self):
        registry = entity_registry.EntityRegistry()

        class Foo(object):
            pass

        with pytest.raises(entity_registry.RegistryError) as exc:
            registry.register_entity('foo', Foo)

        assert str(exc.value) == 'Attempting to register unknown type foo'

    def test_register_nonclass(self):
        registry = entity_registry.EntityRegistry()

        with pytest.raises(entity_registry.RegistryError) as exc:
            @registry.register_user
            def testing_user():
                pass

        assert str(exc.value) == 'Entity must be a class'

        with pytest.raises(entity_registry.RegistryError) as exc:
            registry.register_user(ents.User.testing_create())

        assert str(exc.value) == 'Entity must be a class'

    def test_is_registered(self):
        registry = entity_registry.EntityRegistry()

        @registry.register_user
        class TestingUser(object):
            pass

        @registry.register_permission
        class TestingPermission(object):
            pass

        assert registry.is_registered('user') is True
        assert registry.is_registered('permission') is True
        assert registry.is_registered('bundle') is False
        assert registry.is_registered('group') is False


class TestPermissionsConditions:
    def setup(self):
        ents.Permission.delete_cascaded()
        ents.User.delete_cascaded()

    def test_simple_string(self):
        user = ents.User.testing_create(
            permissions=[ents.Permission.testing_create(token='perm1')]
        )
        ents.Permission.testing_create(token='perm2')

        assert utils.has_any('perm1').check(user) is True
        assert utils.has_all('perm1').check(user) is True

        assert utils.has_any('perm2').check(user) is False
        assert utils.has_all('perm2').check(user) is False

    def test_callable(self):
        user1 = ents.User.testing_create(email='foo@bar.com')
        user2 = ents.User.testing_create(email='abc@123.com')

        def func(usr):
            return usr.email.endswith('@bar.com')

        assert utils.has_any(func).check(user1) is True
        assert utils.has_all(func).check(user1) is True

        assert utils.has_any(func).check(user2) is False
        assert utils.has_all(func).check(user2) is False

    def test_all(self):
        user = ents.User.testing_create(
            permissions=[
                ents.Permission.testing_create(token='perm1'),
                ents.Permission.testing_create(token='perm2'),
                ents.Permission.testing_create(token='perm3'),
            ]
        )
        ents.Permission.testing_create(token='perm4')

        assert utils.has_all('perm1').check(user) is True
        assert utils.has_all('perm1', 'perm2').check(user) is True
        assert utils.has_all('perm1', 'perm2', 'perm3').check(user) is True

        assert utils.has_all('perm4').check(user) is False
        assert utils.has_all('perm1', 'perm4').check(user) is False
        assert utils.has_all('perm1', 'perm2', 'perm4').check(user) is False

    def test_any(self):
        user = ents.User.testing_create(
            permissions=[ents.Permission.testing_create(token='perm1')]
        )
        ents.Permission.testing_create(token='perm2'),
        ents.Permission.testing_create(token='perm3'),
        ents.Permission.testing_create(token='perm4')

        assert utils.has_any('perm1').check(user) is True
        assert utils.has_any('perm1', 'perm2').check(user) is True
        assert utils.has_any('perm1', 'perm2', 'perm3').check(user) is True

        assert utils.has_any('perm2').check(user) is False
        assert utils.has_any('perm2', 'perm3').check(user) is False
        assert utils.has_any('perm2', 'perm3', 'perm4').check(user) is False

    def test_nested(self):
        user = ents.User.testing_create(
            permissions=[
                ents.Permission.testing_create(token='perm1'),
                ents.Permission.testing_create(token='perm2'),
                ents.Permission.testing_create(token='perm3'),
            ]
        )
        ents.Permission.testing_create(token='perm4')

        condition = utils.has_any('perm4', utils.has_all('perm1', 'perm2'))
        assert condition.check(user) is True

        condition = utils.has_all(utils.has_any('perm1', 'perm2'), 'perm4')
        assert condition.check(user) is False

        condition = utils.has_all(utils.has_any('perm4', lambda _: True), 'perm1')
        assert condition.check(user) is True

        condition = utils.has_all(utils.has_any('perm4', lambda _: False), 'perm1')
        assert condition.check(user) is False
