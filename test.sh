#!/bin/bash
cd assignment1
source ven/bin/activate
#python gen.py http://ece1779-a2-load-balancer-1781096346.us-east-1.elb.amazonaws.com:5000/api/upload liu liu 1 ./photos/ 100
#python gen.py http://1779test-1788742950.us-east-1.elb.amazonaws.com:5000/api/upload tester 123456 1 ./photos/ 100
python gen.py http://ece1779alb-1664248623.us-east-1.elb.amazonaws.com:5000/api/upload tester 123456 1 ./files/ 100