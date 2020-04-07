include:
    - .pillar_check


elasticsearch-deps:
    pkg.installed:
        - name: apt-transport-https


elasticsearch:
    # add repo to managed repositories
    pkgrepo.managed:
        - name: deb https://artifacts.elastic.co/packages/7.x/apt stable main
        - key_url: salt://elasticsearch/release-key
        - require:
            - pkg: elasticsearch-deps
    # install elastic search package
    pkg.installed:
        - name: elasticsearch
        - require:
            - pkgrepo: elasticsearch
        - version: 7.6.2

    # start service and watch the config files for restarting the service
    service.running:
        - require:
            - file: elasticsearch
        - watch:
            - file: elasticsearch-environment-variables
            - file: elasticsearch-jvm-options
            - file: elasticsearch-elasticsearch-yml

    # Created a dedicated temp directory to not conflict with hardening of /tmp
    file.directory:
        - name: /var/lib/elasticsearch-temp
        - makedirs: True
        - user: root
        - group: elasticsearch
        - mode: 775
        - require:
            - pkg: elasticsearch


elasticsearch-environment-variables:
    file.managed:
        - name: /etc/default/elasticsearch
        - source: salt://elasticsearch/default


elasticsearch-jvm-options:
    file.managed:
        - name: /etc/elasticsearch/jvm.options
        - source: salt://elasticsearch/jvm.options
        - template: jinja


elasticsearch-elasticsearch-yml:
    file.managed:
        - name: /etc/elasticsearch/elasticsearch.yml
        - source: salt://elasticsearch/elasticsearch.yml
        - template: jinja


{% for family in ('ipv4', 'ipv6') %}
elasticsearch-outbound-firewall-{{ family }}:
    firewall.append:
        - table: filter
        - chain: OUTPUT
        - family: {{ family }}
        - proto: tcp
        - dport: 9300
        - match:
            - comment
            - owner
        - comment: 'elasticsearch: Allow outgoing traffic for internal comms'
        - uid-owner: elasticsearch
        - jump: ACCEPT
        - require:
            - pkg: elasticsearch


elasticsearch-inbound-firewall-{{ family }}:
    firewall.append:
        - table: filter
        - family: {{ family }}
        - chain: INPUT
        - protocol: tcp
        - dports: 9200,9300
        - match:
            - comment
        - comment: 'elasticsearch: Allow incoming traffic for http and internal comms'
        - jump: ACCEPT
{% endfor %}