# coding=utf-8
# ------------------------------------------------------------------------------------------------------
# TDA596 - Lab 1
# server/server.py
# Input: Node_ID total_number_of_ID
# Student: Olivia CARAIMAN & Lucas BERNEL
# ------------------------------------------------------------------------------------------------------
import traceback
import sys
import time
import json
import argparse
from threading import Thread
from random import randint

from bottle import Bottle, run, request, template
import requests
# ------------------------------------------------------------------------------------------------------
try:
    board = {}

    def init_app():
        def on_startup():
            global leader
            time.sleep(3)
            elect_leader("election")
            print "leader_call" + str(leader)
            pass
        app = Bottle()
        t = Thread(target=on_startup)
        t.daemon = True
        t.start()
        return app
    app = init_app()

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):
        print "I am in the add_new_element_to_store function"
        global board, node_id
        success = False
        try:
            # generate an id for an entry, by checking if the id doesn't already exist
            if entry_sequence is None:                 
                entry_sequence = 0
                while (str(entry_sequence) in board):
                    entry_sequence += 1
            board[str(entry_sequence)] = element
            print element            
            success = True
        except Exception as e:
            print e
        return entry_sequence

    def modify_element_in_store(entry_sequence, modified_element, is_propagated_call = False):
        global board, node_id
        success = False
        try:
            board[str(entry_sequence)] = modified_element
            success = True
        except Exception as e:
            print e
        return success

    def delete_element_from_store(entry_sequence, is_propagated_call = False):
        global board, node_id
        success = False
        try:
            del board[str(entry_sequence)]
            success = True
        except Exception as e:
            print e
        return success

    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def contact_vessel(vessel_ip, path, payload = None, req='POST'):
        # Try to contact another server (vessel) through a POST or GET, once
        print "I am in contact_vessel function"
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(vessel_ip, path))
            else:
                print 'Non implemented feature!'
            # result is in res.text or res.json()
            # print(res.text)
            if res.status_code == 200:
                success = True
        except Exception as e:
            print e
        return success

    def propagate_to_vessels(path, payload = None, req = 'POST'):
        print "I am in propagate_to_vessels function"
        global vessel_list, node_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    @app.route('/')
    def index():
        global board, node_id, leader, leader_random
        return template('server/index.tpl', leader=str(leader)+'; random id = '+str(leader_random), board_title='Vessel {}'.format(node_id)+' random_id: '+str(random_id), board_dict=sorted(board.iteritems()), members_name_string='Lucas BERNEL & Olivia CARAIMAN')

    @app.get('/board')
    def get_board():
        global board, node_id, leader, leader_random
        print board
        return template('server/boardcontents_template.tpl',leader=str(leader)+'; random id = '+str(leader_random),board_title='Vessel {}'.format(node_id)+' random_id: '+str(random_id), board_dict=sorted(board.iteritems()))
    # ------------------------------------------------------------------------------------------------------
    @app.post('/board')
    def client_add_received():
        print "I am in client_add_received"
        '''Adds a new element to the board
        Called directly when a user is doing a POST request on /board'''
        global board, node_id
        try:
            new_entry = request.forms.get('entry')
            last_id = add_new_element_to_store(None, new_entry) 
            
            thread = Thread(target=propagate_to_vessels, args=('/propagate/add/'+str(last_id), json.dumps(new_entry)))
            thread.daemon = True
            thread.start()
            return True
        except Exception as e:
            print e
        return False

    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        print "I am in client_action_received function"
        element = request.forms.get('entry')
        # calls delete or modify methods depending on the action sent in request
        action = "modify"
        if request.forms.get('delete') == str(1):
            action = "delete"
            delete_element_from_store(element_id)
        elif action == "modify":
            modify_element_in_store(element_id, element)
        
        thread = Thread(target=propagate_to_vessels, args=('/propagate/' + action + '/' + str(element_id), json.dumps(element)))
        thread.daemon = True
        thread.start()
        pass

    @app.post('/propagate/<action>/<element_id>')
    def propagation_received(action, element_id):
        print "I am in propagation_received function"
        element=json.loads(request.body.read())
        # calls add/modify/delete method depending on the parameter "action"
        if str(action) == "add":
            add_new_element_to_store(element_id, element)
        elif str(action) == "modify":
            modify_element_in_store(element_id, element)
        elif str(action) == "delete":
            delete_element_from_store(element_id)
        pass

    @app.post('/propagate/<action>')
    def elect_leader(action):
        print "I am in the elect_leader function"
        global election_msg, node_id, vessel_list, random_id, coordination_msg, leader_random, leader
        try:

            # determine the successor ip by choosing the next neighbour in the vessel list
            vessel_ip = vessel_list[str((node_id % len(vessel_list)+1))]

            if (action == "election"): 
                print "in election"

                action_todo = "election"
                # initialize election message with its random_id and node_id
                if election_msg is None:
                    election_msg = {"leader_random":random_id, "leader":node_id}
                else:
                    # change the leader in the election message only if the received random id is greater than the current leader random id
                    received_id_random = int(json.loads(request.body.read())["leader_random"])
                    received_id = int(json.loads(request.body.read())["leader"])
                    
                    if received_id_random > election_msg["leader_random"]:
                        election_msg = {"leader_random":received_id_random, "leader":received_id}
                    
                    # we did a full loop and we found the greatest value of random_id. This node has the greatest value
                    # update leader_random and leader with the node's values
                    # do the coordination step     
                    elif received_id_random == random_id:
                        leader_random = random_id
                        leader = node_id
                        action_todo = "coordination"
                # propagate election message to successor
                thread = Thread(target=contact_vessel, args=(vessel_ip,'/propagate/' + action_todo, json.dumps(election_msg)))
                thread.daemon = True
                thread.start()

            elif (action == "coordination"): 
                received_id_random = int(json.loads(request.body.read())["leader_random"])
                # if receive random id is greater than random_id, update leader_random and leader 
                # propagate to successor
                if (received_id_random > leader_random):
                    leader_random = received_id_random
                    leader = int(json.loads(request.body.read())["leader"])
                    coordination_msg = {"leader_random" : leader_random, "leader":leader}
                    thread = Thread(target=contact_vessel, args=(vessel_ip,'/propagate/coordination', json.dumps(coordination_msg)))
                    thread.daemon = True
                    thread.start()
  
        except Exception as e:
            print e
        return True

    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------

    def main():
        global vessel_list, node_id, app, random_id, leader, leader_random, election_msg, coordination_msg
        port = 80
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int, help='The total number of vessels present in the system')
        args = parser.parse_args()
        node_id = args.nid
        vessel_list = dict()
        random_id = randint(0,1000)
        leader = 1 #by default server 1 will be the leader
        leader_random = None
        election_msg = None
        coordination_msg = None
        # We need to write the other vessels IP, based on the knowledge of their number
        for i in range(1, args.nbv):
            vessel_list[str(i)] = '10.1.0.{}'.format(str(i))

        try:

            run(app, host=vessel_list[str(node_id)], port=port)
        except Exception as e:
            print e

    # ------------------------------------------------------------------------------------------------------
    if __name__ == '__main__':
        main()
except Exception as e:
        traceback.print_exc()
        while True:
            time.sleep(60.)
