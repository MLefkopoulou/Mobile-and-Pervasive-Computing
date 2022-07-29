import socket
import argparse
import pickle
import time
import matplotlib.pyplot as plt
from numpy import random

#global variables for cahce hit and cache miss
cache_valid_hit =0
cache_invalid_hit =0
cache_miss=0

def parse_args():
	parser = argparse.ArgumentParser()
	parser.add_argument('-a',action = "store",nargs = "+",dest = "addr",help = "Server's IP address")
	parser.add_argument('-p',action = "store",nargs = "+",dest = "port",help = "Server's port")
	parser.add_argument('-r',action = "store",nargs = "+",dest = "policy",help = "Replacement Policy , 1:LRU / 3-4:OUR (offline-online) / 5-6: PIX (offline-online)")
	parser.add_argument('-s',action = "store",nargs = "+",dest = "size",help = "Cache size")
	parser.add_argument('-ds',action = "store",nargs = "+",dest = "data_size",help = "Enter 1 if the data sizes are the same else enter 0")

	args = parser.parse_args()
	address = args.addr[0]
	port = args.port[0]
	policy = args.policy[0]
	size = args.size[0]
	data_size = int(args.data_size[0]);
	if(data_size == 1):
		data_size = False;
	else:
		data_size = True;


	return address,int(port),int(policy),int(size),data_size;




address,port,policy,size,data_size = parse_args()

local_update = False;

#In the online algorithms, for access mean and update mean, we will use
# the function : mi[data_item] = K/(T- Tk), were K is a number indicating 
# the K last accessed or updated times , and Tk is the time were the K most
# recent update or access happened.
#items_access_window, is a dictionary that shows the times of the last K accesses of 
# an item. The same holds with update.
_items_access_window = {};
_items_update_window = {};
K = 3;
### This is a dictionary that holds the update rates of 
# the items by :u[i] = alpha / (tserver - tlast_upd) + (1-alpha)*u[i] 
u = {};
alpha = 0.1;

LOGICAL_TIME = 0;

_DATA_ITEMS = 500

replacement = 0;
used_space = 0;
_Cache = []
_freq_in_cache = {}
_timeStamps = {}
_item_accesses = {};
_actual_update_time = {}
_mi_for_request = {}
_li_for_request = {}
cost_function={}
policy_dict = {}
latency = 0;
data_downloaded = 0;
policy_dict[1] = "LRU"
policy_dict[3] = "OUR_offline"
policy_dict[4] = "OUR_online"
policy_dict[5] = "PIX_offline"
policy_dict[6] = "PIX_online"


for i in range(1,_DATA_ITEMS+1):
	u[i] = [0,0];




def create_stream(DATA_ITEMS,stream_size):
	random.seed(8);
	counter = 0;
	hot_data = [];
	stream = []
	data = [i+1 for i in range(DATA_ITEMS)];
	
	while(counter != int(0.2*DATA_ITEMS)):
		i = random.randint(0,DATA_ITEMS-counter)
		hot_data.append(data[i]);
		data.pop(i)
		counter += 1;

	for i in range(stream_size):
		if(random.random()>0.3):
			stream.append(hot_data[random.randint(0,len(hot_data))])
		else:
			stream.append(data[random.randint(0,len(data))]);

	return stream

#Check if there no data_id registered and create the data structures
# Else if window is full, remove the first element and append the new
# otherwise append the new value.
def update_access_window(data_id):
	global LOGICAL_TIME;
	global _items_access_window;
	global _items_update_window;
	global K;
	if(data_id not in _item_accesses):
		_item_accesses[data_id] = 0;
	
	_item_accesses[data_id] = _item_accesses[data_id] + 1;
	

	if(data_id not in _items_access_window):
		_items_access_window[data_id] = [LOGICAL_TIME];
		_items_update_window[data_id] = [LOGICAL_TIME];
	else:
		if(len(_items_access_window[data_id]) == K):
			_items_access_window[data_id].pop(0);
			_items_access_window[data_id].append(LOGICAL_TIME);
		else:
			_items_access_window[data_id].append(LOGICAL_TIME);


def update_update_window(data_id):
	global LOGICAL_TIME;
	global _items_update_window;
	global K;
	if(len(_items_update_window) == K):
		_items_update_window[data_id].pop(0);
		_items_update_window[data_id].append(LOGICAL_TIME);
	else:
		_items_update_window[data_id].append(LOGICAL_TIME);

def get_mean_access(data_id,default = True):
	global K;
	global LOGICAL_TIME;
	if(default):
		return K/(LOGICAL_TIME + 1 - _items_access_window[data_id][0]);
	else:
		return _item_accesses[data_id]/(10*(LOGICAL_TIME-1))

def get_mean_update(data_id):
	global K;
	global LOGICAL_TIME;
	return K/(LOGICAL_TIME + 1 - _items_update_window[data_id][0]);

def get_OUR_cost(data_id):
	global u;
	return (get_mean_access(data_id,False)**2)/(get_mean_access(data_id,False)+u[data_id][1]);

def get_PIX_cost(data_id):
	return get_mean_access(data_id,False)/data_lengths[data_id-1];


def refresh_mean_update(data_id,updated,remote_mean_update,updates = 0):
	global u;
	global alpha;
	global LOGICAL_TIME;
	global local_update;
	if(local_update):
		if(updated):
			if(data_id not in u):
				u[data_id] = [1,1/(10*LOGICAL_TIME)];
			else:
				u[data_id] = [u[data_id][0]+ updates,(u[data_id][0]+ updates)/(10*LOGICAL_TIME)];
		#for item in u:
		#	u[item] = [u[item][0],u[item][0]/LOGICAL_TIME]
	else:
		u[data_id] = remote_mean_update;			 

#################################################################

def get_item(data_id):
	sockfd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sockfd.connect((address,port))
	sockfd.sendall(pickle.dumps([1,data_id]))
	data = pickle.loads(sockfd.recv(1024))
	sockfd.close()
	#print("data:")
	#print(data)
	return data

def get_li(data_id):
	sockfd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sockfd.connect((address,port))
	sockfd.sendall(pickle.dumps([3,data_id]))
	data = pickle.loads(sockfd.recv(1024))
	sockfd.close()
	return data

def check_validity(data_id,timestamp):
	sockfd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sockfd.connect((address,port))
	sockfd.sendall(pickle.dumps([2,data_id,timestamp]))
	data = pickle.loads(sockfd.recv(1024))
	sockfd.close()
	return data

		


########### Here you can write cache API and replacement policies ########

def get_from_cache(data_id):
	if(data_id in _Cache):
		if(policy_dict[policy] == "LRU"):
			_Cache.remove(data_id)
			_Cache.insert(0,data_id)
		if(policy_dict[policy] == "LFU"):
			_freq_in_cache[data_id] = _freq_in_cache[data_id] +1

		return data_id
	else:
		return None



def put_cache(data_id):
	global replacement;
	global used_space;
	global data_lengths;
	temp_relief = 0;

	replacement_victims = [];

	if(policy_dict[policy] == "LRU"):
		if(used_space + data_lengths[data_id-1] <= size):
			_Cache.insert(0,data_id)
			used_space += data_lengths[data_id-1];
		else:
			#for each iteration remove the least recently used item and 
			# check if there is enough space for replacement. If there is
			# not, then continue else stop.
			while(True):
				#print("Used space : " + str(used_space) + " , size : " + str(size) + " , data_length : " + str(data_lengths[data_id-1]) + " for replacement: " + str(data_lengths[len(_Cache)-1]))
				used_space -= data_lengths[_Cache[len(_Cache)-1]-1];
				_Cache.pop(len(_Cache) - 1);
				if(used_space + data_lengths[data_id-1] <= size):
					_Cache.insert(0,data_id);
					used_space += data_lengths[data_id-1];
					break;

	elif(policy_dict[policy] == "P"):
		if(len(_Cache) < size):
			cost_function[data_id] = _mi_for_request[data_id];
			_Cache.append(data_id);
			used_space += data_lengths[data_id-1];
		else:
			while(True):
				id_for_replace = data_id
				min_pf = _mi_for_request[data_id];
				for x in range(len(_Cache)):
					if(cost_function[_Cache[x]]<min_pf and _Cache[x] not in replacement_victims):
						min_pf = cost_function[_Cache[x]]
						id_for_replace= _Cache[x]

				if(id_for_replace != data_id):
					#print("Used space : " + str(used_space) + " , size : " + str(size) + " , data_length : " + str(data_lengths[data_id-1]) + " for replacement: " + str(data_lengths[id_for_replace-1]))				
					replacement_victims.append(id_for_replace);
					temp_relief += data_lengths[id_for_replace-1];
					#In case space is available for the replacement 
					if(used_space - temp_relief + data_lengths[data_id-1] <= size):
						replacement+=1;
						for victim in replacement_victims:
							_Cache.remove(victim)
							cost_function.pop(victim);
							
						_Cache.append(data_id)
						cost_function[data_id] = _mi_for_request[data_id];
						used_space = used_space - temp_relief + data_lengths[data_id-1];	
						break;
				else:
					return;
	
	elif(policy_dict[policy] == "PIX_offline"):
		if(data_id not in _Cache):
			if(used_space + data_lengths[data_id-1] <= size):
				cost_function[data_id] = (_mi_for_request[data_id]/data_lengths[data_id-1]);
				_Cache.append(data_id);
				used_space += data_lengths[data_id-1];
			else:
				#For each iteration find a replacement victim, which is the data item with the smallest 
				# cost in cache and is not in replacement_victim list.
				while(True):
					id_for_replace = data_id
					min_pf = (_mi_for_request[data_id]/data_lengths[data_id-1]);
					for x in range(len(_Cache)):
						if(cost_function[_Cache[x]]<min_pf and _Cache[x] not in replacement_victims):
							min_pf = cost_function[_Cache[x]]
							id_for_replace= _Cache[x]

					if(id_for_replace != data_id):
						replacement_victims.append(id_for_replace);
						temp_relief += data_lengths[id_for_replace-1];
						#In case space is available for the replacement 
						if(used_space - temp_relief + data_lengths[data_id-1] <= size):
							replacement+=1;
							for victim in replacement_victims:
								_Cache.remove(victim)
								cost_function.pop(victim);
							
							_Cache.append(data_id)
							cost_function[data_id] = (_mi_for_request[data_id]/data_lengths[data_id-1]);
							used_space = used_space - temp_relief + data_lengths[data_id-1];	
							break;
					else:
						return;

	elif(policy_dict[policy] == "PIX_online"):
		if(data_id not in _Cache):
			if(used_space + data_lengths[data_id-1] <= size):
				_Cache.append(data_id);
				used_space += data_lengths[data_id-1];
			else:
				#For each iteration find a replacement victim, which is the data item with the smallest 
				# cost in cache and is not in replacement_victim list.
				while(True):
					id_for_replace = data_id
					min_pf = get_PIX_cost(data_id);
					for x in range(len(_Cache)):
						item_cost = get_PIX_cost(_Cache[x]);
						if(item_cost < min_pf and _Cache[x] not in replacement_victims):
							min_pf = item_cost;
							id_for_replace = _Cache[x]
							
					if(id_for_replace != data_id):
						#print("Used space : " + str(used_space) + " , size : " + str(size) + " , data_length : " + str(data_lengths[data_id-1]) + " for replacement: " + str(data_lengths[id_for_replace-1]))				
						replacement_victims.append(id_for_replace);
						temp_relief += data_lengths[id_for_replace-1];
						#In case space is available for the replacement 
						if(used_space - temp_relief + data_lengths[data_id-1] <= size):
							replacement+=1;
							#print(min_pf);
							#print(get_OUR_cost(data_id))
							for victim in replacement_victims:
							#	print(replacement_victims)
								_Cache.remove(victim)
							
							_Cache.append(data_id)
							used_space = used_space - temp_relief + data_lengths[data_id-1]
							break;

					else:
						return;
					

	elif(policy_dict[policy] == "OUR_offline"):
		if(data_id not in _Cache):
			if(used_space + data_lengths[data_id-1] <= size):
				cost_function[data_id] = (_mi_for_request[data_id]**2)/(_mi_for_request[data_id]+_actual_update_time[data_id])
				_Cache.append(data_id)
				used_space += data_lengths[data_id-1];
			else:
				#For each iteration find a replacement victim, which is the data item with the smallest 
				# cost in cache and is not in replacement_victim list.
				while(True):
					id_for_replace = data_id
					min_pf = (_mi_for_request[data_id]**2)/(_mi_for_request[data_id]+_actual_update_time[data_id])
					for x in range(len(_Cache)):
						if(cost_function[_Cache[x]]<min_pf and _Cache[x] not in replacement_victims):
							min_pf = cost_function[_Cache[x]]
							id_for_replace= _Cache[x]

					if(id_for_replace != data_id):
						#print("Used space : " + str(used_space) + " , size : " + str(size) + " , data_length : " + str(data_lengths[data_id-1]) + " for replacement: " + str(data_lengths[id_for_replace-1]))				
						replacement_victims.append(id_for_replace);
						temp_relief += data_lengths[id_for_replace-1];
						#In case space is available for the replacement 
						if(used_space - temp_relief + data_lengths[data_id-1] <= size):
							replacement+=1;
							for victim in replacement_victims:
								_Cache.remove(victim)
								cost_function.pop(victim);
							
							_Cache.append(data_id)
							cost_function[data_id] = (_mi_for_request[data_id]**2)/(_mi_for_request[data_id]+_actual_update_time[data_id])
							used_space = used_space - temp_relief + data_lengths[data_id-1];	
							break;
					else:
						return;
					
	elif(policy_dict[policy] == "OUR_online"):
		if(data_id not in _Cache):
			if(used_space + data_lengths[data_id-1] <= size):
				_Cache.append(data_id)
				used_space += data_lengths[data_id-1];
			else:
				#For each iteration check if there is a data item 
				# available for replacement. If there is put it in 
				# a replacement_victims list until the space is 
				# cleared for the insertion of the new item. If there
				# is not free space, then leave without removing something
				# in the cache
				while(True):
					id_for_replace = data_id
					min_pf = get_OUR_cost(data_id);
					for x in range(len(_Cache)):
						item_cost = get_OUR_cost(_Cache[x]);
						if(item_cost < min_pf and _Cache[x] not in replacement_victims):
							min_pf = item_cost;
							id_for_replace = _Cache[x]
							
					if(id_for_replace != data_id):
						#print("Used space : " + str(used_space) + " , size : " + str(size) + " , data_length : " + str(data_lengths[data_id-1]) + " for replacement: " + str(data_lengths[id_for_replace-1]))				
						replacement_victims.append(id_for_replace);
						temp_relief += data_lengths[id_for_replace-1];
						#In case space is available for the replacement 
						if(used_space - temp_relief + data_lengths[data_id-1] <= size):
							replacement+=1;
							#print(min_pf);
							#print(get_OUR_cost(data_id))
							for victim in replacement_victims:
							#	print(replacement_victims)
								_Cache.remove(victim)
							
							_Cache.append(data_id)
							used_space = used_space - temp_relief + data_lengths[data_id-1]
							break;

					else:
						return;

	
					


####################################################

# Here you should check if the data is in the cache. If it is then check validity with check_validity and if 
# it is out of date replace it (just replace timestamp) else do nothing 
# If it is not in cache send  get_item and take use the replacement policy to replace data.
def get_from_server(data_id):
	reply = get_item(data_id)
	_actual_update_time[reply[0]] = reply[2];
	if(reply[0] not in _timeStamps):
		_timeStamps[reply[0]] = reply[1] - 1;
	refresh_mean_update(data_id,True,reply[3],reply[1]-_timeStamps[reply[0]]);
	_timeStamps[reply[0]] = reply[1];
	

def access_data(data_id):
	global cache_miss
	global cache_invalid_hit
	global cache_valid_hit
	global data_downloaded;
	
	#First of all, check if file is in cache
	cache_return = get_from_cache(data_id)
	
	if(cache_return == None):
		#If the file is not in cache, take it from the server and then put it in cache
		#print("Cache Miss on "+str(data_id)+" !")
		get_from_server(data_id)
		
		put_cache(data_id)
		cache_miss =  cache_miss+1
		data_downloaded += data_lengths[data_id-1]
		return False;
	else:#if the item is in cache 
		reply  = check_validity(data_id,_timeStamps[data_id])
		#print(reply)
		if(reply[0] == -1):#the timestamp is alright
		#	print("Cache Hit on "+str(data_id)+" !")
			cache_valid_hit =  cache_valid_hit+1
			refresh_mean_update(data_id,False,reply[3]);
			return True;
		else:#the timestamp is wrong
		#	print("Item updated at : "+str(data_id)+" !")
			update_update_window(data_id);
			refresh_mean_update(data_id,True,reply[3],reply[1] - _timeStamps[reply[0]]);
			_timeStamps[reply[0]] = reply[1] 
			cache_invalid_hit =  cache_invalid_hit+1
			data_downloaded += data_lengths[data_id-1]
			return False;



			
###########################################################################

random.seed(11)
#request stream
request_stream = create_stream(_DATA_ITEMS,5000);
for i in range(len(request_stream)):
	if(request_stream[i] == 0):
		request_stream[i] = 1;

for i in range(1,_DATA_ITEMS+1):
	_timeStamps[i] = 0 
#print(_timeStamps)
#if the replacement policy is LFU init  _freq_in_cache

if(policy_dict[policy] == "LFU"): 
	for i in range(1,_DATA_ITEMS+1):
		_freq_in_cache[i] = 0 
#	print(_freq_in_cache)
#if the replacement policy is OUR init  _mi_for_request  (and _pf_for_request ,_li_for_request with 0 )
if(policy_dict[policy] == "OUR_offline" or policy_dict[policy] == "PIX_offline" or policy_dict[policy] == "P"): 
	for i in range(1,_DATA_ITEMS+1):
		_mi_for_request[i] = 0
	for i in range(1,_DATA_ITEMS+1):
		_li_for_request[i] = 0		
	
	for i in range(len(request_stream)):
		if(request_stream[i] == 0):
			request_stream[i] = 1;
		_mi_for_request[request_stream[i]] = _mi_for_request[request_stream[i]]+1
	for i in range(1,_DATA_ITEMS+1):
		_mi_for_request[i] = _mi_for_request[i]/len(request_stream)

#	print (_mi_for_request)

if(policy_dict[policy] == "OUR_online" or policy_dict[policy] == "PIX_online"): 
	for i in range(1,_DATA_ITEMS+1):
		_mi_for_request[i] = 0
	for i in range(1,_DATA_ITEMS+1):
		_li_for_request[i] = 0		
	

#print(data_size)
if(data_size):
	random.seed(10);
	data_lengths = [random.randint(1,11) for i in range(_DATA_ITEMS)];
else:
	data_lengths = [1 for i in range(_DATA_ITEMS)];

#print(data_lengths)

LOGICAL_TIME = 1;
for i in range(len(request_stream)):
	time.sleep(0.1)
	LOGICAL_TIME+= 0.1;
	update_access_window(request_stream[i]);
	start = time.time();
	#check if the item is in cache
	if(access_data(request_stream[i])):
		end = time.time();
		print("Cache Hit!, data item : "+str(request_stream[i]) + " , time elapsed :" + str(end - start))
	else:
		end = time.time();
		print("Cache Miss, data item  : "+str(request_stream[i]) + " , time elapsed :" + str(end - start))

	
	#print(_Cache)
	#print(u)
#calculate rate %
cache_valid_hit_rate= (cache_valid_hit*100)/len(request_stream)
cache_invalid_hit_rate= (cache_invalid_hit*100)/len(request_stream)
cache_miss_rate= (cache_miss*100)/len(request_stream)

print(cache_valid_hit_rate)
print(cache_invalid_hit_rate)
print(cache_miss_rate)
print(data_downloaded)

print("==========")
#plot
names = ['cache_valid_hit','cache_invalid_hit', 'cache_miss']
values = [cache_valid_hit_rate,cache_invalid_hit_rate, cache_miss_rate]

#print(replacement)
#plt.axis(ymin=0, ymax=100)
#plt.bar(names, values)
#plt.show()
