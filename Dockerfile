FROM python:3.11-alpine3.18

RUN apk add --no-cache --update tzdata

COPY requirements.txt /

RUN pip install -r /requirements.txt \
    # remove temporary files
    && rm -rf /root/.cache

COPY ./deluge-exporter.py /deluge-exporter.py

EXPOSE 8011

CMD [ "/usr/local/bin/python", "-u", "/deluge-exporter.py" ]

# Help
#
# Local build
# docker build -t deluge-exporter:custom .
#
# Multi-arch build
# docker buildx create --use
# docker buildx build -t deluge-exporter:custom --platform linux/386,linux/amd64,linux/arm/v6,linux/arm/v7,linux/arm64/v8,linux/ppc64le,linux/s390x .
#
# add --push to publish in DockerHub
