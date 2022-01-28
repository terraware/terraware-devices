FROM python:3.8.5-buster AS build

RUN apt-get update \
    && apt-get install -y \
        cmake \
        curl \
        g++ \
        gcc \
        libglib2.0-0 \
        make \
        pkg-config \
        wget \
        xz-utils

WORKDIR /app

# Download the latest entrypoint script from Balena. This will set up the
# udev daemon and correctly mount devices into the container.
RUN wget -q https://raw.githubusercontent.com/balena-io-library/base-images/master/balena-base-images/aarch64/debian/buster/run/entry.sh

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

FROM python:3.8.5-slim-buster

WORKDIR /app

RUN apt-get update \
    && apt-get install -y \
        libglib2.0-0 \
        ssh \
        udev \
        nut \
    && apt-get clean \
    && rm -rf /var/cache/apt/lists

COPY --from=build /app/entry.sh /app/entry.sh

# /usr/local contains Python libraries
COPY --from=build /usr/local /usr/local
RUN ldconfig

COPY balena-config.yaml config.yaml *.py /app/
COPY specs /app/specs
COPY devices /app/devices
COPY automations /app/automations

COPY ups.conf nut.conf /etc/nut/

# Uncomment these two lines to push a local site JSON file to the Pi for testing in local dev mode.
#COPY sample_local.yaml /app/local.yaml
#COPY sample-site.json /app/sample-site.json

# Uncomment and set these for local mode development within Balena (which doesn't use the variables specified in the web interface)
#ENV LOCAL_CONFIG_FILE_OVERRIDE=sample-site.json
#ENV KEYCLOAK_API_CLIENT_ID=api
#ENV DIAGNOSTIC_MODE=1
#ENV OFFLINE_REFRESH_TOKEN=
#ENV ACCESS_TOKEN_REQUEST_URL=
#ENV SERVER=
#ENV FACILITIES=1,2,3

ENTRYPOINT ["/bin/bash", "/app/entry.sh"]
CMD ["/usr/local/bin/python3", "main.py"]
