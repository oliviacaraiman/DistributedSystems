#!/bin/bash

curl -X POST -F 'entry=vessel1' http://10.1.0.1:80/board && echo "done1" &
curl -X POST -F 'entry=vessel2' http://10.1.0.2:80/board && echo "done2" &

wait
