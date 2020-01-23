FROM python:3.8-slim-buster

RUN pip install flywheel-sdk==10.7.0 glob2

ENV FLYWHEEL /flywheel/v0
WORKDIR ${FLYWHEEL}

COPY manifest.json \
    run.py \
    ${FLYWHEEL}/
RUN chmod +x run.py

ENTRYPOINT ${FLYWHEEL}/run.py
