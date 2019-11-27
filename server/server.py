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

from bottle import Bottle, run, request, template, response
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
        """
            Add a new element to the board

            :param entry_sequence: Id unique on the board and one by element
            :param element: An element 
            :type entry_sequence: integer
            :type element: String
            :return: the entry sequence number 
        """
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
        """
           Modify an element in the board
            
            :param entry_sequence: Id unique on the board and one by element
            :param element: An element 
            :type entry_sequence: integer
            :type element: String
            :return: boolean success 
        """
        global board, node_id
        success = False
        try:
            board[str(entry_sequence)] = modified_element
            success = True
        except Exception as e:
            print e
        return success

    def delete_element_from_store(entry_sequence, is_propagated_call = False):
        """
            Delete an element in the board
            
            :param entry_sequence: Id unique on the board and one by element
            :type entry_sequence: Integer
            :return: boolean success 
        """
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
            success = True
            if res.status_code == 200:
                success = True
        except requests.ConnectionError:
            print "OOOOOOOOOOOOOKKK"
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
        return template('server/index.tpl', leader=str(leader)+'; random id = '+str(leader_random), 
            board_title='Vessel {}'.format(node_id)+' random_id: '+str(random_id), board_dict=sorted(board.iteritems()), 
            members_name_string='Lucas BERNEL & Olivia CARAIMAN')

    @app.get('/board')
    def get_board():
        global board, node_id, leader, leader_random
        print board
        return template('server/boardcontents_template.tpl',leader=str(leader)+'; random id = '+str(leader_random),
            board_title='Vessel {}'.format(node_id)+' random_id: '+str(random_id), board_dict=sorted(board.iteritems()))
    # ------------------------------------------------------------------------------------------------------
    @app.post('/board')
    def client_add_received():
        print "I am in client_add_received"
        """
        Adds a new element to the board
        Called directly when a user is doing a POST request on /board
        :return: boolean
        """
        global board, node_id, leader, vessel_list
        try:
            if node_id == leader:
                #The leader add an entry, so it adds it and progate
                new_entry = request.forms.get('entry')
                last_id = add_new_element_to_store(None, new_entry) 
                
                thread = Thread(target=propagate_to_vessels, args=('/propagate/add/'+str(last_id), json.dumps(new_entry)))
                thread.daemon = True
                thread.start()
                return HTTPResponse(status=200)
            else:
                #An other vessel add an entry, ride up the entry to the leader
                new_entry = request.forms.get('entry')
                leader_ip = vessel_list[str(leader)]
                thread = Thread(target=contact_vessel, args=(leader_ip,'/board/update/add', json.dumps(new_entry)))
                thread.daemon = True
                thread.start()
                return HTTPResponse(status=200)
        except Exception as e:
            print e
        return False
    @app.post('/board/update/<action>')
    def receive_update_from_vessel(action):
        """
            Receive all the update from other vessel and treat them 
            This function is used only by the leader 
            :param action: Could be "add", "modify" and "delete". Correspond to the action we have to apply on the board
            :type action: String
            :return: boolean
        """
        if action == "add":
            new_entry = json.loads(request.body.read())
            last_id = add_new_element_to_store(None, new_entry) 
            thread = Thread(target=propagate_to_vessels, args=('/propagate/add/'+str(last_id), json.dumps(new_entry)))
            thread.daemon = True
            thread.start()
            return True
        elif action == "modify":
            #Here we need in the request body a String like "element_id,element" to be split beneath
            jsonObject = json.loads(request.body.read())
            element_id, element = jsonObject.split(',')
            modify_element_in_store(element_id,element)
            thread = Thread(target=propagate_to_vessels, args=('/propagate/modify/'+str(element_id), json.dumps(element)))
            thread.daemon = True
            thread.start()
            return True
        elif action == "delete":
            id_element = json.loads(request.body.read())
            delete_element_from_store(id_element)
            thread = Thread(target=propagate_to_vessels, args=('/propagate/delete/'+str(id_element), json.dumps(id_element)))
            thread.daemon = True
            thread.start()
            return True


    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        """
            Receive the choosen action from the user. 
            Execute this one and propagate to other vessels using propagate_to_vessel function
            Called directly when a user is doing a POST request on /board/<element_id:int>/
            :param element_id:Id of the element in the board to apply the action 
            :type element_id: Int
        """
        print "I am in client_action_received function"
        global leader, vessel_list, node_id
        element = request.forms.get('entry')
        # calls delete or modify methods depending on the action sent in request
        action = "modify"
        if request.forms.get('delete') == str(1):
            if leader == node_id:
                #The deletion is done on the leader, so directly deleted and propagate
                action = "delete"
                delete_element_from_store(element_id)
                thread = Thread(target=propagate_to_vessels, args=('/propagate/delete/'+str(element_id), json.dumps(element_id)))
                thread.daemon = True
                thread.start()
            else:
                #The deletion is done on an other vessel, so we ride up the info to the leader
                action = "delete"
                leader_ip = vessel_list[str(leader)]
                thread = Thread(target=contact_vessel, args=(leader_ip,'/board/update/delete', json.dumps(element_id)))
                thread.daemon = True
                thread.start()
        elif action == "modify":
            if leader == node_id:
                #The modification is done on the leader, so directly deleted and propagate
                modify_element_in_store(element_id, element)
                thread = Thread(target=propagate_to_vessels, args=('/propagate/modify/'+str(element_id), json.dumps(element)))
                thread.daemon = True
                thread.start()
            else:
                #The modification is done on an other vessel, so we ride up the info to the leader
                to_send = str(element_id) + "," + str(element)
                leader_ip = vessel_list[str(leader)]
                thread = Thread(target=contact_vessel, args=(leader_ip,'/board/update/modify', json.dumps(to_send)))
                thread.daemon = True
                thread.start()        
        pass

    @app.post('/propagate/<action>/<element_id>')
    def propagation_received(action, element_id):
        """
            Reception of a modification of the board from an other vessel. 
            Update the board in function of the parameters
            Called directly when a vessel send a POST request on /propagate/<action>/<element_id>
            :param action: The choosen action delete or modify
            :param element_id:Id of the element in the board to apply the action 
            :type action: String
            :type element_id: Int
        """
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
        """
            Allow to elect a leader vessel to manage the centralized blackboard. This function use a ring algorithm to elect the leader.
            The highest number is the leader
            :param action: Could be "election" or "coordination". The first one allow to elect the leader. The second one allow to propagate the leader between every vessels
            :type action: String
        """
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
                
                """print test 
                print vessel_ip
                if test == False:
                    vessel_ip = vessel_list[str((node_id + 1 % len(vessel_list)+1))]
                    print vessel_ip """
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
                    #contact_vessel(vessel_ip,'/propagate/coordination'+ action_todo, json.dumps(coordination_msg))
                    #    vessel_ip = vessel_list[str((node_id + 1 % len(vessel_list)+1))]
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
