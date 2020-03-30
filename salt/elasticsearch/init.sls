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
        - pkgs:
            - elasticsearch
        - require:
            - pkgrepo: elasticsearch
        - version: 7.6.1

    # start service and watch the config files for restarting the service
    service.running:
        - watch:
          - file: /etc/elasticsearch/elasticsearch.yml
          - file: /etc/elasticsearch/jvm.options

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
