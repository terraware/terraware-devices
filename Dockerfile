FROM python:3.8.5-buster AS build

WORKDIR /app

RUN apt-get update \
    && apt-get install -y libglib2.0-0 wget

# Download the latest entrypoint script from Balena. This will set up the
# udev daemon and correctly mount devices into the container.
RUN wget https://raw.githubusercontent.com/balena-io-library/base-images/master/balena-base-images/aarch64/debian/buster/run/entry.sh

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

FROM python:3.8.5-slim-buster

WORKDIR /app

RUN apt-get update \
    && apt-get install -y libglib2.0-0 ssh udev \
    && apt-get clean \
    && rm -rf /var/cache/apt/lists

COPY --from=build /usr/local/lib/python3.8 /usr/local/lib/python3.8
COPY --from=build /app/entry.sh /app/entry.sh

COPY balena-config.yaml config.yaml main.py /app/
COPY specs /app/specs
COPY terraware_devices /app/terraware_devices

ENTRYPOINT ["/bin/bash", "/app/entry.sh"]
CMD ["/usr/local/bin/python3", "main.py"]
