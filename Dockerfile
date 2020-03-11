FROM python:3.8-slim-buster

RUN pip install \
    flywheel-sdk==11.2.0 \
    glob2

ENV FLYWHEEL /flywheel/v0
WORKDIR ${FLYWHEEL}

COPY manifest.json \
    run.py \
    ${FLYWHEEL}/
RUN chmod +x run.py

ENTRYPOINT ${FLYWHEEL}/run.py
