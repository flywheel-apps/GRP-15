FROM python:3.8-slim-buster

COPY ["requirements.txt", "/opt/requirements.txt"]
RUN pip install -r /opt/requirements.txt

ENV FLYWHEEL /flywheel/v0
WORKDIR ${FLYWHEEL}

COPY manifest.json \
    run.py \
    ${FLYWHEEL}/
RUN chmod +x run.py

ENTRYPOINT ${FLYWHEEL}/run.py
