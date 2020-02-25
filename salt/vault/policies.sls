{% from 'vault/map.jinja' import vault with context %}

{% for name, policy in vault.get('policies', {}).items() %}
vault-policy-{{ name }}:
    vault.policy_present:
        - name: {{ name }}
        - rules: '{{ policy | json }}'
{% endfor %}