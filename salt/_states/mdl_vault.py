from __future__ import absolute_import

# Based on https://github.com/mitodl/vault-formula/blob/master/_states/vault.py (BSD 3-clause)

import logging
import os

import salt.config
import salt.syspaths
import salt.utils
import salt.exceptions

log = logging.getLogger(__name__)

try:
    import requests
    DEPS_INSTALLED = True
except ImportError:
    log.debug('Unable to import the requests library.')
    DEPS_INSTALLED = False

__all__ = ['initialize']


def __virtual__():
    return DEPS_INSTALLED


def auth_backend_enabled(name, backend_type, description='', mount_point=None):
    """
    Ensure that the named backend has been enabled

    :param name: ID for state definition
    :param backend_type: The type of authentication backend to enable
    :param description: The description to set for the backend
    :param mount_point: The root path at which the backend will be mounted
    :returns: The result of the state execution
    :rtype: dict
    """
    backends = __salt__['mdl_vault.list_auth_backends']()
    setting_dict = {'type': backend_type, 'description': description}
    backend_enabled = False
    ret = {'name': name,
           'comment': '',
           'result': '',
           'changes': {'old': backends}}

    for path, settings in __salt__['mdl_vault.list_auth_backends']().get('data', {}).items():
        if (path.strip('/') == mount_point or backend_type and
            settings['type'] == backend_type):
            backend_enabled = True

    if backend_enabled:
        ret['comment'] = ('The {auth_type} backend mounted at {mount} is already'
                          ' enabled.'.format(auth_type=backend_type,
                                             mount=mount_point))
        ret['result'] = True
    elif __opts__['test']:
        ret['result'] = None
    else:
        try:
            __salt__['mdl_vault.enable_auth_backend'](backend_type,
                                                  description=description,
                                                  mount_point=mount_point)
            ret['result'] = True
            ret['changes']['new'] = __salt__[
                'mdl_vault.list_auth_backends']()
        except __utils__['mdl_vault.vault_error']() as e:
            ret['result'] = False
            log.exception(e)
        ret['comment'] = ('The {backend} has been successfully mounted at '
                          '{mount}.'.format(backend=backend_type,
                                            mount=mount_point))
    return ret


def audit_backend_enabled(name, backend_type, description='', options=None,
                          backend_name=None):
    if not backend_name:
        backend_name = backend_type
    backends = __salt__['mdl_vault.list_audit_backends']().get('data', {})
    setting_dict = {'type': backend_type, 'description': description}
    backend_enabled = False
    ret = {'name': name,
           'comment': '',
           'result': '',
           'changes': {'old': backends}}

    for path, settings in __salt__['mdl_vault.list_audit_backends']().items():
        if (path.strip('/') == backend_type and
            settings['type'] == backend_type):
            backend_enabled = True

    if backend_enabled:
        ret['comment'] = ('The {audit_type} backend is already enabled.'
                          .format(audit_type=backend_type))
        ret['result'] = True
    elif __opts__['test']:
        ret['result'] = None
    else:
        try:
            __salt__['mdl_vault.enable_audit_backend'](backend_type,
                                                   description=description,
                                                   name=backend_name)
            ret['result'] = True
            ret['changes']['new'] = __salt__[
                'mdl_vault.list_audit_backends']()
            ret['comment'] = ('The {backend} audit backend has been '
                              'successfully enabled.'.format(
                                  backend=backend_type))
        except __utils__['mdl_vault.vault_error']() as e:
            ret['result'] = False
            log.exception(e)
    return ret


def secret_backend_enabled(name, backend_type, description='', mount_point=None,
                           connection_config_path=None, connection_config=None,
                           lease_max=None, lease_default=None, ttl_max=None,
                           ttl_default=None, override=False):
    """

    :param name: The ID for the state definition
    :param backend_type: The type of the backend to be enabled (e.g. MySQL)
    :param description: The description to set for the enabled backend
    :param mount_point: The root path for the backend
    :param connection_config_path: The full path to the endpoint used for
                                   configuring the connection (needed for
                                   e.g. Consul)
    :param connection_config: The configuration settings for the backend
                              connection
    :param lease_max: The maximum allowed lease for credentials retrieved from
                      the backend
    :param lease_default: The default allowed lease for credentials retrieved from
                          the backend
    :param ttl_max: The maximum TTL for a lease generated by the backend. Uses
                    the mounts/<mount_point>/tune endpoint.
    :param ttl_default: The default TTL for a lease generated by the backend.
                        Uses the mounts/<mount_point>/tune endpoint.
    :param override: Specifies whether to override the settings for an existing mount
    :returns: The result of the execution
    :rtype: dict

    """
    backends = __salt__['mdl_vault.list_secret_backends']().get('data', {})
    backend_enabled = False
    ret = {'name': name,
           'comment': '',
           'result': '',
           'changes': {'old': backends}}

    for path, settings in __salt__['mdl_vault.list_secret_backends']().get('data', {}).items():
        if (path.strip('/') == mount_point and
            settings['type'] == backend_type):
            backend_enabled = True

    if backend_enabled and not override:
        ret['comment'] = ('The {secret_type} backend mounted at {mount} is already'
                          ' enabled.'.format(secret_type=backend_type,
                                             mount=mount_point))
        ret['result'] = True
    elif __opts__['test']:
        ret['result'] = None
    else:
        try:
            __salt__['mdl_vault.enable_secret_backend'](backend_type,
                                                    description=description,
                                                    mount_point=mount_point)
            ret['result'] = True
            ret['changes']['new'] = __salt__[
                'mdl_vault.list_secret_backends']()
        except __utils__['mdl_vault.vault_error']() as e:
            ret['result'] = False
            log.exception(e)
        if connection_config:
            if not connection_config_path:
                connection_config_path = '{mount}/config/connection'.format(
                    mount=mount_point)
            try:
                __salt__['mdl_vault.write'](connection_config_path,
                                        **connection_config)
            except __utils__['mdl_vault.vault_error']() as e:
                ret['comment'] += ('The backend was enabled but the connection '
                                  'could not be configured\n')
                log.exception(e)
                raise salt.exceptions.CommandExecutionError(str(e))
        if ttl_max or ttl_default:
            ttl_config_path = 'sys/mounts/{mount}/tune'.format(
                mount=mount_point)
            if ttl_default > ttl_max:
                raise salt.exceptions.SaltInvocationError(
                    'The specified default ttl is longer than the maximum')
            if ttl_max and not ttl_default:
                ttl_default = ttl_max
            if ttl_default and not ttl_max:
                ttl_max = ttl_default
            try:
                log.debug('Tuning the mount ttl to be: Max={ttl_max}, '
                          'Default={ttl_default}'.format(
                              ttl_max=ttl_max, ttl_default=ttl_default))
                __salt__['mdl_vault.write'](ttl_config_path,
                                        default_lease_ttl=ttl_default,
                                        max_lease_ttl=ttl_max)
            except __utils__['mdl_vault.vault_error']() as e:
                ret['comment'] += ('The backend was enabled but the connection '
                                  'ttl could not be tuned\n'.format(e))
                log.exception(e)
                raise salt.exceptions.CommandExecutionError(str(e))
        if lease_max or lease_default:
            lease_config_path = '{mount}/config/lease'.format(
                mount=mount_point)
            if lease_default > lease_max:
                raise salt.exceptions.SaltInvocationError(
                    'The specified default lease is longer than the maximum')
            if lease_max and not lease_default:
                lease_default = lease_max
            if lease_default and not lease_max:
                lease_max = lease_default
            try:
                log.debug('Tuning the lease config to be: Max={lease_max}, '
                          'Default={lease_default}'.format(
                              lease_max=lease_max, lease_default=lease_default))
                __salt__['mdl_vault.write'](lease_config_path,
                                        ttl=lease_default,
                                        max_ttl=lease_max)
            except __utils__['mdl_vault.vault_error']() as e:
                ret['comment'] += ('The backend was enabled but the lease '
                                  'length could not be configured\n'.format(e))
                log.exception(e)
                raise salt.exceptions.CommandExecutionError(str(e))
        ret['comment'] += ('The {backend} has been successfully mounted at '
                          '{mount}.'.format(backend=backend_type,
                                            mount=mount_point))
    return ret


def policy_present(name, rules):
    """
    Ensure that the named policy exists and has the defined rules set

    :param name: The name of the policy
    :param rules: The rules to set on the policy
    :returns: The result of the state execution
    :rtype: dict
    """
    current_policy = __salt__['mdl_vault.get_policy'](name, parse=True)
    ret = {'name': name,
           'comment': '',
           'result': False,
           'changes': {}}
    if current_policy == rules:
        ret['result'] = True
        ret['comment'] = ('The {policy_name} policy already exists with the '
                          'given rules.'.format(policy_name=name))
    elif __opts__['test']:
        ret['result'] = None
        if current_policy:
            ret['changes']['old'] = current_policy
            ret['changes']['new'] = rules
        ret['comment'] = ('The {policy_name} policy will be {suffix}.'.format(
            policy_name=name,
            suffix='updated' if current_policy else 'created'))
    else:
        try:
            __salt__['mdl_vault.set_policy'](name, rules)
            ret['result'] = True
            ret['comment'] = ('The {policy_name} policy was successfully '
                              'created/updated.'.format(policy_name=name))
            ret['changes']['old'] = current_policy
            ret['changes']['new'] = rules
        except __utils__['mdl_vault.vault_error']() as e:
            log.exception(e)
            ret['comment'] = ('The {policy_name} policy failed to be '
                              'created/updated'.format(policy_name=name))
    return ret


def policy_absent(name):
    """
    Ensure that the named policy is not present

    :param name: The name of the policy to be deleted
    :returns: The result of the state execution
    :rtype: dict
    """
    current_policy = __salt__['mdl_vault.get_policy'](name, parse=True)
    ret = {'name': name,
           'comment': '',
           'result': False,
           'changes': {}}
    if not current_policy:
        ret['result'] = True
        ret['comment'] = ('The {policy_name} policy is not present.'.format(
            policy_name=name))
    elif __opts__['test']:
        ret['result'] = None
        if current_policy:
            ret['changes']['old'] = current_policy
            ret['changes']['new'] = {}
        ret['comment'] = ('The {policy_name} policy {suffix}.'.format(
            policy_name=name,
            suffix='will be deleted' if current_policy else 'is not present'))
    else:
        try:
            __salt__['mdl_vault.delete_policy'](name)
            ret['result'] = True
            ret['comment'] = ('The {policy_name} policy was successfully '
                              'deleted.')
            ret['changes']['old'] = current_policy
            ret['changes']['new'] = {}
        except __utils__['mdl_vault.vault_error']() as e:
            log.exception(e)
            ret['comment'] = ('The {policy_name} policy failed to be '
                              'created/updated'.format(policy_name=name))
    return ret


def role_present(name, mount_point, options, override=False):
    """
    Ensure that the named role exists. If it does not already exist then it
    will be created with the specified options.

    :param name: The name of the role
    :param mount_point: The mount point of the target backend
    :param options: A dictionary of the configuration options for the role
    :param override: Write the role definition even if there is already one
                     present. Useful if the existing role doesn't match the
                     desired state.
    :returns: Result of executing the state
    :rtype: dict
    """
    current_role = __salt__['mdl_vault.read']('{mount}/roles/{name}'.format(
        mount=mount_point, name=name))
    ret = {'name': name,
           'comment': '',
           'result': False,
           'changes': {}}
    if current_role and not override:
        ret['result'] = True
        ret['comment'] = ('The {role} role already exists with the '
                          'given rules.'.format(role=name))
    elif __opts__['test']:
        ret['result'] = None
        if current_role:
            ret['changes']['old'] = current_role
            ret['changes']['new'] = None
        ret['comment'] = ('The {role} role {suffix}.'.format(
            role=name,
            suffix='already exists' if current_role else 'will be created'))
    else:
        try:
            response = __salt__['mdl_vault.write']('{mount}/roles/{role}'.format(
                mount=mount_point, role=name), **options)
            ret['result'] = True
            ret['comment'] = ('The {role} role was successfully '
                              'created.'.format(role=name))
            ret['changes']['old'] = current_role
            ret['changes']['new'] = response
        except __utils__['mdl_vault.vault_error']() as e:
            log.exception(e)
            ret['comment'] = ('The {role} role failed to be '
                              'created'.format(role=name))
    return ret


def role_absent(name, mount_point):
    """
    Ensure that the named role does not exist.

    :param name: The name of the role to be deleted if present
    :param mount_point: The mount point of the target backend
    :returns: The result of the stae execution
    :rtype: dict
    """
    current_role = __salt__['mdl_vault.read']('{mount}/roles/{name}'.format(
        mount=mount_point, name=name))
    ret = {'name': name,
           'comment': '',
           'result': False,
           'changes': {}}
    if current_role:
        ret['changes']['old'] = current_role
        ret['changes']['new'] = None
    else:
        ret['changes'] = None
        ret['result'] = True
    if __opts__['test']:
        ret['result'] = None
        return ret
    try:
        __salt__['mdl_vault.delete']('{mount}/roles/{name}'.format(
            mount=mount_point, name=name))
        ret['result'] = True
    except __utils__['mdl_vault.vault_error']() as e:
        log.exception(e)
        raise salt.exceptions.SaltInvocationError(e)
    return ret