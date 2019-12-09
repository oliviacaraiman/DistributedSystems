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

from bottle import Bottle, run, request, template
import requests
# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()
    board = {}
    timestamp = 0
    history = {}

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):
        """
            Add a new element to the board

            :param entry_sequence: Id unique on the board and one by element
            :param element: An element 
            :type entry_sequence: String
            :type element: String
            :return: the entry sequence number 
        """
        print "I am in the add_new_element_to_store function"
        global board, node_id
        success = False
        try:
            # generate an id for an entry if it is None
            if entry_sequence is None:                 
                entry_sequence = 0
                while (str(entry_sequence) in board):
                    entry_sequence += 1
            board[str(entry_sequence)] = element
                
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

    def add_to_history(element_id, action, element, timestamp, node_id): 
        """
            Add an element to the queue, to be processed later
            
            :param element_id: Id unique on the board and one by element
            :param action: action to be performed on the element (add/modify/delete)

        """
        global history,board
        print "I'm in add_to_history function \n \n"
        try:
            # add new entry in the history
            if action == 'add' or (element_id not in history) :
                history[element_id] = [action, element, timestamp, node_id]
            else:
                if (history[element_id][2] < timestamp) or (history[element_id][2] == timestamp and history[element_id][3] > node_id):
                    #update history with a more recent action
                    history[element_id] = [action, element, timestamp, node_id]
                    # execute action
                    if (action == 'modify'):
                        # if the last received action was 'delete' although a concurrent action was 'modify' keep the modify instead of delete
                        if history[element_id][0] == 'delete':
                            add_new_element_to_store(element_id, element)
                        else:
                            modify_element_in_store(element_id, element)
                    elif (action == 'delete'):
                        delete_element_from_store(element_id)
            print "History: "
            print history
        except Exception as e:
            print e
        pass

    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def contact_vessel(vessel_ip, path, payload = None, req='POST'):
        # Try to contact another server (vessel) through a POST or GET, once
        # print "I am in contact_vessel function"
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(vessel_ip, path))
            else:
                print 'Non implemented feature!'
            print(res.text)
            if res.status_code == 200:
                success = True
        except Exception as e:
            print e
        return success

    def propagate_to_vessels(path, payload = None, req = 'POST'):
        print "I am in propagate_to_vessels function"
        global vessel_list, node_id
        # add a sleep to simulate inconcistency
        # time.sleep(10)
        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "Could not contact vessel {}".format(vessel_id)


    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    @app.route('/')
    def index():
        global board, node_id
        # sort by timestamp then node_id 
        sorted_board = sorted(board.iteritems(), key=lambda item:(int(item[0].split('-')[0]), int(item[0].split('-')[1])) );
        return template('server/index.tpl', board_title='Vessel {}'.format(node_id), board_dict=sorted_board, members_name_string='Lucas BERNEL & Olivia CARAIMAN')

    @app.get('/board')
    def get_board():
        global board, node_id
        # sort by timestamp then node_id 
        sorted_board = sorted(board.iteritems(), key=lambda item:(int(item[0].split('-')[0]), int(item[0].split('-')[1])) );
        return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(node_id), board_dict=sorted_board)
    # ------------------------------------------------------------------------------------------------------
    @app.post('/board')
    def client_add_received():
        print "I am in client_add_received"
        """
        Adds a new element to the board
        Called directly when a user is doing a POST request on /board
        :return: boolean
        """
        global board, node_id, timestamp
        try:
            new_entry = request.forms.get('entry')
            timestamp += 1;
            entry_sequence = str(timestamp) + "-" + str(node_id)
            add_new_element_to_store(entry_sequence, new_entry) 
            add_to_history(entry_sequence, "add", new_entry, timestamp, node_id)
            to_send = {"element" : new_entry, 'timestamp' : timestamp, "id" : node_id }

            thread = Thread(target=propagate_to_vessels, args=('/propagate/add/'+str(entry_sequence), json.dumps(to_send)))
            thread.daemon = True
            thread.start()
            return True
        except Exception as e:
            print e
        return False

    @app.post('/board/<element_id>/')
    def client_action_received(element_id):
        """
            Receive the choosen action from the user. 
            Execute this one and propagate to other vessels using propagate_to_vessel function
            Called directly when a user is doing a POST request on /board/<element_id:int>/
            :param element_id:Id of the element in the board to apply the action 
        """
        global timestamp, node_id
        print "I am in client_action_received function"
        element = request.forms.get('entry')
        # calls delete or modify methods depending on the action sent in request
        # update the timestamp
        timestamp += 1
        action = "modify"
        if request.forms.get('delete') == str(1):
            action = "delete"
            #delete_element_from_store(element_id)
            add_to_history(element_id, "delete", None, timestamp, node_id)
        elif action == "modify":
            #modify_element_in_store(element_id, element)
            add_to_history(element_id, "modify", element, timestamp, node_id)

        to_send = {'element' : element, 'timestamp': timestamp, 'id' : node_id}
        
        thread = Thread(target=propagate_to_vessels, args=('/propagate/' + action + '/' + str(element_id), json.dumps(to_send)))
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
        """
        global board, history, timestamp
        print "I am in propagation_received function"

        msg = json.loads(request.body.read())
        element = msg["element"]
        ts = msg["timestamp"]

        # update the timestamp, should be the maximum between received and local
        timestamp = max(timestamp, ts) + 1
        server = msg["id"]

        # calls add/modify/delete method depending on the parameter "action"
        if str(action) == "add":
            add_new_element_to_store(element_id, element)
            add_to_history(element_id, "add", element, ts, server)
        elif str(action) == "modify":
            add_to_history(element_id, "modify", element, ts, server)
        elif str(action) == "delete":
            add_to_history(element_id, "delete", None, ts, server)
        pass
        
    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    def main():
        global vessel_list, node_id, app, timestamp

        port = 80
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int, help='The total number of vessels present in the system')
        args = parser.parse_args()
        node_id = args.nid
        vessel_list = dict()
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
