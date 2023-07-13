FROM docker.io/python:3-alpine

COPY backup.py backup.yml requirements.txt /opt/app/

RUN apk fix && \
	apk add --no-cache \
		ca-certificates \
		duplicity \
		openssh \
		rsync &&\
	pip install -r /opt/app/requirements.txt
# install dev version of duplicity change URL or comment out
RUN pip install setuptools_scm boto3 python-gettext &&\
	apk add gettext &&\
	apk add -t .build-deps gcc musl-dev librsync-dev git &&\
	pip install git+https://gitlab.com/duplicity/duplicity.git@2f0ce69f4b089f6b819d283a87a76616b9ca0d25 &&\
	apk del --purge .build-deps

RUN	addgroup -S app &&\
	adduser -S app -G app &&\
	mkdir -p \
		~app/.cache/duplicity \
		~app/.gnupg && \
	chown -R app:app ~app && \
	chown -R root:root /opt/app && \
	find /opt/app -type d -exec chmod 755 {} + && \
	find /opt/app -type f -exec chmod 644 {} +;

USER app

ENTRYPOINT ["python3", "-u", "/opt/app/backup.py"]
