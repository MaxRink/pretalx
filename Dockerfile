FROM python:3.6

RUN apt-get update && \
    apt-get install -y git gettext libmariadbclient-dev libpq-dev locales libmemcached-dev build-essential \
            nginx \
            supervisor \
            sudo \
            --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    dpkg-reconfigure locales && \
	locale-gen C.UTF-8 && \
	/usr/sbin/update-locale LANG=C.UTF-8 && \
    mkdir /etc/pretalx && \
    mkdir /data && \
    useradd -r -ms /bin/bash -d /pretalx -u 999 pretalxuser && \
    echo 'pretalxuser ALL=(ALL) NOPASSWD: /usr/bin/supervisord' >> /etc/sudoers && \
    mkdir /static

ENV LC_ALL=C.UTF-8


COPY src /pretalx/src
COPY deployment/docker/pretalx.bash /usr/local/bin/pretalx
COPY deployment/docker/supervisord.conf /etc/supervisord.conf
COPY deployment/docker/nginx.conf /etc/nginx/nginx.conf

RUN pip3 install -U pip setuptools wheel typing && \
    pip3 install -e /pretalx/src/ && \
    pip3 install django-redis pylibmc mysqlclient psycopg2-binary redis==2.10.6 && \
    pip3 install gunicorn 




RUN chmod +x /usr/local/bin/pretalx && \
    rm /etc/nginx/sites-enabled/default && \
    cd /pretalx/src && \
    rm -f pretalx.cfg && \
    chown -R pretalxuser:pretalxuser /pretalx /data  



USER pretalxuser

RUN cd /pretalx/src && python3 -m pretalx makemigrations
RUN cd /pretalx/src && python3 -m pretalx migrate && python3 -m pretalx rebuild

VOLUME ["/etc/pretalx", "/data"]
EXPOSE 80
ENTRYPOINT ["pretalx"]
CMD ["all"]
