FROM python:3

WORKDIR /usr/src/app

RUN pip install --no-cache-dir bluepy==1.2.0 prometheus_client

COPY . .

CMD python ./waveplus_exporter.py --serialnumber $WAVEPLUS_SERIALNUM
