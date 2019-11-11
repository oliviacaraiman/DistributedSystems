#!/bin/bash

for i in `seq 1 10`;
do
	curl -X POST -F 'entry=vessel1 at '${i} http://10.1.0.1:80/board &
	curl -X POST -F 'entry=vessel2 at '${i} http://10.1.0.2:80/board &
	curl -X POST -F 'entry=vessel3 at '${i} http://10.1.0.3:80/board &
done 
