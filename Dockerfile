FROM python:3.6

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
            build-essential \
            default-libmysqlclient-dev \
            gettext \
            git \
            libffi-dev \
            libjpeg-dev \
            libmemcached-dev \
            libpq-dev \
            libssl-dev \
            libxml2-dev \
            libxslt1-dev \
            locales \
            nginx \
            python-dev \
            python-virtualenv \
            python3-dev \
            sudo \
            supervisor \
            zlib1g-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    dpkg-reconfigure locales && \
	locale-gen C.UTF-8 && \
	/usr/sbin/update-locale LANG=C.UTF-8 && \
    mkdir /etc/pretalx && \
    mkdir /data && \
    useradd -ms /bin/bash -d /pretalx -u 999 pretalxuser && \
    echo 'pretalxuser ALL=(ALL) NOPASSWD: /usr/bin/supervisord' >> /etc/sudoers && \
    mkdir /static

ENV LC_ALL=C.UTF-8 \
    DJANGO_SETTINGS_MODULE=production_settings

COPY src /pretalx/src
COPY deployment/docker/pretalx.bash /usr/local/bin/pretalx
COPY deployment/docker/supervisord.conf /etc/supervisord.conf
COPY deployment/docker/nginx.conf /etc/nginx/nginx.conf

RUN pip3 install -U pip setuptools wheel typing && \
    pip3 install -e /pretalx/src/ && \
    pip3 install django-redis pylibmc mysqlclient psycopg2 && \
    pip3 install gunicorn && \
    chmod +x /usr/local/bin/pretalx




RUN chmod +x /usr/local/bin/pretalx && \
    rm /etc/nginx/sites-enabled/default && \
    cd /pretalx/src && \
    rm -f pretalx.cfg && \
	mkdir -p data && \
    chown -R pretalxuser:pretalxuser /pretalx /data data 



USER pretalxuser

RUN cd /pretalx/src && python3 -m pretalx makemigrations
RUN cd /pretalx/src && python3 -m pretalx migrate && python3 -m pretalx rebuild

VOLUME ["/etc/pretalx", "/data"]
EXPOSE 80
ENTRYPOINT ["pretalx"]
CMD ["all"]
