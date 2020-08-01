# waveplus_exporter
[Prometheus](https://prometheus.io) exporter for the [Airthings Waveplus](https://www.airthings.com/en/wave-plus) air sensor, based on their [library](https://github.com/Airthings/waveplus-reader)

# Raspberry Pi Setup
This worked for me on a raspberry pi 3.

## System Setup
```
$ sudo systemctl start hciuart
$ sudo bluetoothctl
[bluetooth]# power on
[bluetooth]# show
...
	Powered: yes
...
```

## Python Setup
```
$ sudo apt install python-pip libglib2.0-dev
$ sudo pip2 install bluepy==1.2.0
```

## Prometheus Setup
A raspberry pi has more than enough compute to run a [prometheus instance](https://github.com/prometheus/prometheus/releases), this exporter, and plenty more.  See the [example config file](example_prometheus_config.yml).

```
$ prometheus --config.file example_prometheus_config.yml
```
# Usage
```
usage: waveplus_exporter.py [-h] [--port [PORT]] [--bind [BIND]] [--periodseconds [PERIODSECONDS]] --serialnumber [SERIALNUMBER]

optional arguments:
  -h, --help            show this help message and exit
  --port [PORT]         The TCP port to listen on (default: 9744)
  --bind [BIND]         The interface/IP to bind to (default: 0.0.0.0)
  --periodseconds [PERIODSECONDS] number of seconds to wait between sampling (default: 60)

```

# Dashboard
Grafana [dashboard](https://grafana.com/grafana/dashboards/12310)

# License
The original [reader from Airthings](https://github.com/Airthings/waveplus-reader) uses the [MIT License](LICENSE), and so does this.
