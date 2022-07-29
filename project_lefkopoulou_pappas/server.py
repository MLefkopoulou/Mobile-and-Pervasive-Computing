import socket
import pickle 
import threading 
from numpy import random
import matplotlib.pyplot as plt
import time
import math
import argparse



objects_cardinarity = 500;
_lambda = {}
_lambda_calculated = {}
last_update = {};
freq = {};
alpha = 0.25; 

for i in range(1,objects_cardinarity+1):
	freq[i] = 0;

clock = 1;	
## The packets are formed in [REQUEST_DATA (1), data_id] and [CHECK_VALIDITY (pid = 2),data_id,timestamp] and [give λ (pid=3) ,data_id]
def process_request(packet):
	global last_update;
	global freq;
	data = pickle.loads(packet)
	pid = data[0]
	#print(data)
	global clock 
	if(pid == 1):
		return [data[1],last_update[data[1]],freq[data[1]],_lambda_calculated[data[1]]]
	elif(pid == 2):
		if(data[2] == last_update[data[1]]):
			return [-1,last_update[data[1]],clock,_lambda_calculated[data[1]]]
		return [data[1],last_update[data[1]],clock,_lambda_calculated[data[1]]]
	#elif(pid == 3):''' ti li na stelnoume'''
	#	return[data[1],li]
########################################################
######## GENERATE THE FILES AND UPDATE TRACES ##########

def update_lambda(data_id,last_update):
	global _lambda_calculated;
	global _lambda;
	global clock;
	if(data_id not in _lambda_calculated):
		_lambda_calculated[data_id] = [1,1/clock];
	else:
		_lambda_calculated[data_id] = [_lambda_calculated[data_id][0]+1,(_lambda_calculated[data_id][0]+1)/clock]; 
	
	for items in _lambda_calculated:
		_lambda_calculated[items] = [_lambda_calculated[items][0],_lambda_calculated[items][0]/clock];
	
	#print(_lambda_calculated);
	#print(_lambda)

def update_daemon(items,updates):
	global clock 
	global last_update;
	i = 0;
	clock = 0;
	for i in range(1,items+1):
		last_update[i] = 0
		#_lambda_calculated[i] = [1,0.001]
		_lambda_calculated[i] = [0,0]
	
	while(True and len(updates)!=0):
		s_time = random.random();
		time.sleep(s_time)
		clock += s_time;
		if(updates[i]==0):
			updates[i] = 1;
		update_lambda(updates[i],last_update[updates[i]]);
		last_update[updates[i]] = last_update[updates[i]] + 1
		i+=1;
		


def find_frequences(x,items):
	object_dic = {}
	for i in range(1,items+1):
		counter = 0
		for j in range(len(x)):
			if(x[j] == i):
				counter += 1
		if(counter == 0):
			object_dic[i] = 1
		else:
			object_dic[i] = counter
	
	for item in object_dic:
		object_dic[item] = object_dic[item]/100000;
	return object_dic	


def find_mi(freq,items):
	expected = {}
	base = 3*freq[1]
	print ("base : ",base)
	for i in range(1,items+1):
		expected[i] = base/freq[i]
	return expected


def add_noise(noise_ratio,means_table,items):
	table = [i+1 for i in range(items)]
	
	for i in range(items-1):
		if(random.random() < noise_ratio):
			j = random.randint(0,items-2)
			table[i],table[j] = table[j],table[i]
	new_means = {}
	_lambda = {}
	
	for i in range(1,items+1):
		new_means[table[i-1]] = means_table[i]

	for item in new_means:
		_lambda[item] =  1/new_means[item];	

	return new_means,_lambda;

def initialize_update_data(objects_cardinarity):
	global _lambda;
	global freq;
	global readonly;
	updates = [];
	random.seed(8)
	counter =  random.randint(0,10);
	if(readonly == False):
		updates = (random.zipf(a=2, size=100000) + [counter for i in range(100000)])%(objects_cardinarity+1)
	print(updates)
	freq = find_frequences(updates,objects_cardinarity)
	print(freq)
	

	#exponential_expected, _lambda = add_noise(0.60,find_mi(freq,objects_cardinarity),objects_cardinarity)
	#print(_lambda)
	print("Server is ready! ")
	update_daemon(objects_cardinarity,updates)



###################################################################3


def parse_args():
	parser = argparse.ArgumentParser()
	parser.add_argument('-a',action = "store",nargs = "+",dest = "addr",help = "Server's IP address")
	parser.add_argument('-p',action = "store",nargs = "+",dest = "port",help = "Server's port")
	parser.add_argument('-r',action = "store",nargs = "+",dest = "readonly",help = "Enter 0 if data are not readonly else enter 1")
	
	args = parser.parse_args()
	address = args.addr[0]
	port = args.port[0]
	readonly = args.readonly[0]
	if(readonly == 1):
		readonly = True;
	else:
		readonly = False;

	
	return address,int(port),readonly;

address,port,readonly = parse_args()
print("Waitting for the server to begin...")
# Initialize data and update patterns
# In initialization, a thread is been created, which runs every 1 sec (you can change that)
# and updates with exponential distribution the data
updates_daemon = threading.Thread(target = initialize_update_data, args = [objects_cardinarity])
updates_daemon.start()


# Create sockfd , listen for any request and send back the answer
sockfd = socket.socket(socket.AF_INET,socket.SOCK_STREAM)

sockfd.bind((address,port))
sockfd.listen()

while(True):
	conn, addr = sockfd.accept()
	request = conn.recv(1024)
	reply = process_request(request)
	conn.sendall(pickle.dumps(reply))
	conn.close()


