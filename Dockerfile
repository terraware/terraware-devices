FROM python:3.8.5-buster AS build

WORKDIR /app

RUN apt-get update \
    && apt-get install -y libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/cache/apt/lists

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

FROM python:3.8.5-slim-buster

WORKDIR /app

RUN apt-get update \
    && apt-get install -y libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/cache/apt/lists

COPY --from=build /usr/local/lib/python3.8 /usr/local/lib/python3.8

COPY balena-config.yaml config.yaml main.py /app/
COPY specs /app/specs
COPY terraware_devices /app/terraware_devices

CMD ["python3", "main.py"]
