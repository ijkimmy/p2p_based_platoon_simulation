#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar  6 17:06:22 2019

@author: vra24 & ivk5077

Readme as follows:
    ---------------------------------------Sets Up Simulation---------------------------------------
    1. place car2.png, client.py, server.py under current directory
    2. run following command to set up server connection 
        python3 server.py
    * Note: server must be established in order to accept any client connection
    3. run following command to set up client connection
        python3 client.py NAMEOFSERVERMACHINE <default to PSU SUN lab machines>
    * Note: client ID received from server if successfully connect; if timed out (15 sec) before receiving ID, must quit all process (including server) and start over 
    * Note: first client has following functionalities
        - press 'c' or 'C' to add one more client
        - press 's' or 'S' to start simulation (no more client accepted from this point)
    * Note: clients and server may ssh into any machines in SUN lab
    * Note: maximum number of cars is 9
    ---------------------------------------Simulation Began---------------------------------------
    4. Each client has following functionalities
        - press 'd' or 'D' to accelerate
        - press 'a' or 'A' to decelerate
        - press 's' or 'S' to stop
        - press 'q' or 'Q' to quit
    * Note: acceleration and deceleration of non-lead car may not affect the speed of platoon due to conflicts (front car priority)
    * Note: maximum speed of platoon is 1.1
    * Note: all failures handled properly (quit or failure of one or more client immediately stop and quits entire system)
    * Note: no action is taken from server side but only visualization
    * Note: when all program exits, server outputs 3 records (speed, position, headways) of simulation into text files
"""
#-----------------------------------------------------------------------------
# IMPORT PACKAGES
import socket, sys, json, pygame, time, os, errno
from threading import Thread, Lock

#-----------------------------------------------------------------------------
# DECLARE GLOBAL VARIABLES
clientList = {}         # LIST TO MAINTAIN CLIENT ADDRESSES
clientSockList = {}     # LIST TO MAINTAIN CLIENT SOCKETS
dataList = {}           # LIST TO MAINTAIN POSITION INFORMATION OF CLIENTS
lock = Lock()           # INITIALIZE LOCK VARIABLE
prev = 0                # VARIABLE TO REFERENCE POSITION OF LEAD CAR
                        # FOR MAINTAINING PLATOON ON THE SCREEN
speed = {}              # LIST TO MAINTAIN SPEED INFORMATION OF CLIENTS
simulationExit = False  # BOOL VARIABLE TO CHECK IF SIMULATION IF RUNNING

############################ FUNCTION DEFINITIONS ############################

#-----------------------------------------------------------------------------
# Function to start server
#-----------------------------------------------------------------------------
def initialize():
    os.system('clear')
    server_connect()

#-----------------------------------------------------------------------------
# Function to accept client connections and start pygame simulation
#-----------------------------------------------------------------------------
def server_connect():
    local_hostname = socket.gethostname()       # GET LOCAL HOST NAME
    host = socket.gethostbyname(local_hostname) # TRANSLATE HOST NAME
    port = 6789                                 # DEFINE PORT NUMBER
    sockfd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)      # CREATE SERVER SOCKET
    sockfd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # SO_REUSEADDR flag tells the kernel to reuse a local socket in TIME_WAIT
    # state, without waiting for its natural timeout to expire
    try:
        sockfd.bind((host, port))               # TRY TO BIND SOCKET
    except:
        print("Bind failed. Error : " + str(sys.exc_info()))
        sys.exit()

    print("SYSTEM: Server is ready to accept connections.")
    sockfd.listen(10)                           # BACKLOG IS 10
    clientID = 0                                # ASSIGN CLIENT ID TO ACCEPT CONNECTIONS
    
    leadConn, leadAdd = sockfd.accept()         # ACCEPT FIRST CLIENT
    clientID += 1                               # ASSIGN CLIENT ID
    print("SYSTEM: Connection received from CLIENT " + str(clientID) + " with address " + str(leadAdd[0]) + ":" + str(leadAdd[1]))
    add_client_to_list(leadConn, clientID, leadAdd)     # ADDING CLIENT INFORMATION TO A LSIT
    recvOpt = leadConn.recv(1).decode("utf-8")          
    if recvOpt == "0":
        send_client_ID(leadConn, clientID)              # CALL FUNCTION TO SEND FIRST CLIENT ITS ID

    while True:
        menu = leadConn.recv(1).decode("utf-8")         # CHECK WHETHER TO ACCEPT MORE CLIENT CONNECTIONS
        if menu == "c":
            clientConn, clientAdd = sockfd.accept()     # ACCEPT ADDITIONAL CLIENT CONNECTIONS
            clientID += 1                               # ASSIGN CLIENT ID
            add_client_to_list(clientConn, clientID, clientAdd)     # ADD CLIENT INFORMATION TO LIST
            clientIP = str(clientAdd[0])                # GET CLIENT IP
            clientPort = str(clientAdd[1])              # GET CLIENT PORT
            print("SYSTEM: Connection received from CLIENT " + str(clientID) + " with address " + clientIP + ":" + clientPort)
            recvOpt = clientConn.recv(1).decode("utf-8")    # RECEIVE CLIENT REQUEST TO SEND ID
            if recvOpt == "0":
                send_client_ID(clientConn, clientID)        # CALL FUNCTION TO SEND CLIENT ID
        elif menu == "s":                                   # CHECK IF FIRST CLIENT WANTS TO CHECK SIMULATION
            print("SYSTEM: Sending client list to all clients.")
            send_client_list(clientList, clientSockList)    # SEND CLIENT INFORMATION LIST TO ALL CLIENTS
            break
        
    start_simulation(clientList, clientSockList)            # CALL FUNCTION START SIMULATION

    sockfd.close()                                          # CLOSE SOCKET CONNECTION ONCE SIMULATION EXITS
    
            
#-----------------------------------------------------------------------------
# Function to send client ID when appropriate request is received
#-----------------------------------------------------------------------------
def send_client_ID(clientConn, clientID):
    clientConn.sendall(str(clientID).encode("utf-8"))
    
#-----------------------------------------------------------------------------
# Function to add a client connection and information to list
#-----------------------------------------------------------------------------
def add_client_to_list(clientConn, clientID, clientAdd):
    global clientList, clientSockList       # REFERENCING GLOBAL VARIABLES
    # USE OF LOCKS TO ENSURE CONCURRENCY
    lock.acquire()
    clientList[clientID] = clientAdd        # ADDING CLIENT ADDRESS TO LIST
    clientSockList[clientID] = clientConn   # ADDING CLIENT SOCKET TO LIST
    lock.release()

#-----------------------------------------------------------------------------    
# Function to send cliend list when appropriate request is received
#-----------------------------------------------------------------------------
def send_client_list(clientList, clientSockList):
    jsonList = json.dumps(clientList)       # PACK CLIENT LIST TO STRING BEFORE SENDING
    for client in clientSockList:           # SENDING PACKED LIST TO ALL CLIENTS
        clientSockList[client].sendall(str(jsonList).encode("utf-8"))

#-----------------------------------------------------------------------------
# Function to start pygame simulation
#-----------------------------------------------------------------------------
def start_simulation(clientList, clientSockList, BUFSIZE = 4096):
    global dataList, lock, prev, speed, simulationExit      # REFERENCING GLOBAL VARIABLES
    print("\nSYSTEM: STARTING THE PLATOON SIMULATION.")
    # CODE TO ADD RECEIVED INFORMATION TO TEXT FILE FOR VISUALIZATION PURPOSE
    fileprefix = "demo1_"
    positionFile = open(fileprefix + "positionFile.txt", "w")
    headwayFile = open(fileprefix + "headwayFile.txt", "w")
    speedFile = open(fileprefix + "speedFile.txt", "w")
    
    # CALCULATE START POSITION OF ALL CARS BASED ON NUMEBR OF CLIENTS
    start_x = list(range(1,len(clientList)+1))
    start_x = [item*150 - 50 for item in start_x]
    start_x.reverse()
    
    # Send initial positions to all clients
    for key, value in clientSockList.items():           # LOOP TO SEND START POSITION TO ALL CLIENTS
        try:
            qqq = value.recv(BUFSIZE).decode("utf-8")   # RECEIVE REQUEST FROM CLIENT TO SEND START POSITION
            if qqq == "xpos":
                value.sendall(str(start_x[key-1]).encode("utf-8"))  # SENDING START POSITION
            else:
                print(key, qqq)                         # ELSE BLOCK JUST TO CHECK IF SERVER RECEIVED CORRECT REQUEST
        except:
            print("Could not send the position to client")
            sys.exit()
            
    pygame.init()                                   # INITIALIZE PYGAME WINDOW
    pygame.font.init()                              # INITIALIZE FONTS IN PYGAME WINDOW
    
    infoObject = pygame.display.Info()              # PYGAME OBJECT TO GET SCREEN SIZE
    
    display_width = infoObject.current_w            # GET SCREEN WIDTH
    display_height = infoObject.current_h           # GET SCREEN HEIGHT
    
    start_y = display_height/2                      # INITIALIZE HEIGHT OF PLATOON TO CENTRE OF SCREEN
    
    white = (255, 255, 255)
    black = (0,0,0)
    font = pygame.font.SysFont('courier new', 20)   # DEFINING FONT FOR PYGAME WINDOW
    
    carImg = pygame.image.load('car2.png')          # LOADING CAR IMAGE
    carImg = pygame.transform.scale(carImg, (100,50))   # SCALING CAR IMAGE TO DISPLAY ON SCREEN
    carRect = carImg.get_rect()                         # GETTING CAR RECT FOR MANIPULAING POSITION ON SCREEN
    
    print(infoObject.current_w, infoObject.current_h)   # PRINTING CURRENT SCREEN SIZE
    # DEFINING PYGAME DISPLAY WINDOW
    gameDisplay = pygame.display.set_mode((display_width, display_height), pygame.RESIZABLE) 
    # SETTING PYGAME DISPLAY CAPTION
    pygame.display.set_caption('P2P based Platton Simulator')
    # FILL PYGAME WINDOW WITH WHITE
    gameDisplay.fill(white)
    # INITIALIZE PYGAME CLOCK
    clock = pygame.time.Clock()
    
    treeSep = 240                                   # DEFINING TREE (GREEN CIRCLES) SEPARATION
    tree = [treeSep*(i+1) for i in range(display_width//treeSep)]   # CALCULATE INITIAL POSITION OF ALL TREES
    bushSep = 240                                   # DEFINING BUSH (SMALL DARK GREEN CIRCLES) SEPARATION
    bush = [bushSep*(i+1) - 100 for i in range(display_width//treeSep)] # CALCULATE INITIAL POSITION OF ALL BUSHES
    treeSpeed = 0                                   # INITIALIZING TREE SPEED
    y1 = int(display_height/2 - 150)                # INITIALIZE POSITION FOR TREES AND BUSHES
    y2 = int(display_height/2 + 150)
    d = display_width*7/10                          # VARIABLE TO MAINTAIN PLATOON IN CENTRE OF SCREEN

    startOfGame = True                              # VARIABLE TO CHECK IF SIMULATION IS RUNNING
    threadList = []                                 # LIST TO MAINTAIN THREADS ON SERVER
    threadName = "receive position thread "
    for key, value in clientSockList.items():       # LOOP TO INITIALIZE ONE THREAD PER CLIENT
        # APPEND THREADS TO THREAD LSIT AND SET DAEMON TO TRUE SO THREADS TERMINATE WHEN MAIN THREAD TERMINATES
        threadList.append(Thread(target = receivePos, name = threadName + str(key),args = (value,key), daemon = True))
        dataList[key-1] = ""
    for i in range(len(clientList)):                # LOOP TO START ALL THREADS
        threadList[i].start()
    
    while True:                                      # RUN SIMULATION FOREVER 
        if simulationExit == True:                   # AND CHECK IF SIMULATION SHOULD QUIT
            break
        # CALL FUNCTION TO DRAW BACKGROUND OF SIMULATION WINDOW (DISPLAYS ROAD, TREES, BUSHES ETC)             
        draw_background(gameDisplay, display_width, display_height, black, tree, bush, y1, y2)
        
        # DISPLAYING INITIAL POSITION OF ALL CARS
        if startOfGame == True:
            for i in range(len(clientList)):            # FOR EACH CLIENT
                carRect.center = (start_x[i], start_y)  # CALCULATE CENTRE OF CAR BASED ON CURRENT POSITION
                gameDisplay.blit(carImg, carRect)       # DRAW CAR IN THE SCREEN
                pygame.display.flip()                   # UPDATE SCREEN DISPLAY FOR EACH CAR
            pygame.display.update()                     # UPDATE THE WHOLE SCREEN
            startOfGame = False
        
        # FUNCTION TO CALCULATE TREE SPEED BASED ON PLATOON SPEED
        treeSpeed = calcTreeSpeed(speed)
        
        # LOOP TO MAKE SURE THAT TREES APPEAR AGAIN AT THE RIGHT END OF THE SCREEN ONCE THEY MOVE
        # OUT OF THE SCREEN FROM THE LEFT
        for j in range(len(tree)):
            if tree[j] + 13 < 0:
                tree[j] = display_width
        
        # LOOP TO MAKE SURE THAT BUSHES APPEAR AGAIN AT THE RIGHT END OF THE SCREEN ONCE THEY MOVE
        # OUT OF THE SCREEN FROM THE LEFT
        for j in range(len(bush)):
            if bush[j] + 5 < 0:
                bush[j] = display_width
        
        # CHANGING TREE SPEED BASED ON SPEED OF PLATOON
        for i in range(len(tree)):
            tree[i] -= treeSpeed
            bush[i] -= treeSpeed
            
        # CONDITION TO CHECK IF PLATOON HAS REACHED A CERTAIN DISTANCE ON THE SCREEN OR WHETHER
        if prev < d:    # IF POSITION OF FIRST CAR IS LESS THAN 'd' THEN DISPLAY USING THIS LOOP
            for i in range(len(dataList)):
                po = float(dataList[i])
                carRect.center = (po, start_y)
                gameDisplay.blit(carImg, carRect)
        else:
            # IF POSITION OF FIRST CAR IS GREATER THAN 'd' THEN DISPLAY USING THIS LOOP
            for p in range(len(dataList)):
                headway = []                    # LOCAL LIST TO CALCULATE HEADWAY OF CARS
                headway.append(float(0))        # HEADWAY OF LEAD CAR IS 0.0
                # LOOP TO CALCULATE HEADWAY OF NON-LEAD CARS BASED ON THE POSITIONS
                # SAY POSITION OF CAR IS 2300. THE PLATOON NEEDS TO BE MAINTAINED WITH LEAD CAR
                # AT POSITION OF 700. SO FIRST WE NEED TO CALCULATE HEADWAY AND THEN CALCULATE
                # POSITION TO DISPLAY ON THE SCREEN
                for o in range(len(dataList) - 1):  
                    # APPEND HEADWAY TO LIST
                    headway.append((float(dataList[o]) - float(dataList[o+1])))
                xp = []
                f = 0
                # LOOP TO CALCULATE AT WHAT POSITION SHOULD THE PLATOON BE DISPLAYED
                # THAT IS CALCULATE X COORDINATE TO DISPLAY PLATOON IN THE CENTRE
                # OF THE SCREEN
                for o in range(len(dataList)):
                    # APPEND COORESPONSING POSITION
                    f += headway[o]
                    xp.append(f)            # APPEND HEADWAY TO LIST
                # CALCULATE CENTRE OF CAR TO DISPLAY ON SCREEN
                carRect.center = (d - xp[p], start_y)
                # DRAW CAR IMGAE ON THE SCREEN
                gameDisplay.blit(carImg, carRect)
            
        # LOOP TO DISPLAY POSITION INFORMATION OF PLATOON AT THE TOP LEFT CORNER OF THE SCREEN
        for i in range(len(speed)):
            text = font.render("Position {}: ".format(i+1), True, white)
            textSurf_pos = font.render(str(round(dataList[i])), True, white)
            textRect_text = text.get_rect()
            textRect_pos = textSurf_pos.get_rect()
            textRect_text.center = (display_width/240 + 100, 25*(i+1))
            textRect_pos.center = (display_width/240 + 190, 25*(i+1))
            gameDisplay.blit(textSurf_pos, textRect_pos)
            gameDisplay.blit(text, textRect_text)
        
        # DISPLAYING SPEED OF PLATOON AT CENTRE OF THE SCREEN
        textSurf_speed = font.render("Platoon Speed: " + str(round(speed[0],1)), True, white)
        textRect_speed = textSurf_speed.get_rect()
        textRect_speed.center = (display_width/2 - 40, 25)
        gameDisplay.blit(textSurf_speed, textRect_speed)
        
        headway = []                    # LOCAL LIST TO CALCULATE HEADWAY OF ALL CARS
        headway.append(float(0))        # HEADWAY OF LEAD CAR IS 0
        for o in range(len(dataList) - 1):
            # CALCULATE HEADWAY OF NON-LEAD CARS BASED ON POSITION
            headway.append((float(dataList[o]) - float(dataList[o+1])))
        
        # LOOP TO DISPLAY HEADWAY OF ALL CARS AT THE TOP RIGHT CORNER OF THE SCREEN
        for i in range(len(headway)):
            headway_text = font.render("Headway {}: ".format(i+1), True, white)
            headway_value = font.render(str(round(headway[i])), True, white)
            headway_text_rect = headway_text.get_rect()
            headway_value_rect = headway_value.get_rect()
            headway_text_rect.center = (display_width-220, 25*(i+1))
            headway_value_rect.center = (display_width-120, 25*(i+1))
            gameDisplay.blit(headway_text, headway_text_rect)
            gameDisplay.blit(headway_value, headway_value_rect)

        # PRINT POSITION INFORMATION RECEIVED BY SERVER
        print("POSITIONS RECEIVED: {}".format([float(value) for key, value in dataList.items()]))

        # LOOP TO WRITE POSITION INFORMATION OF CLIENTS IN A TEXT FILE
        for key, value in dataList.items():
            positionFile.write("%f "%float(value))
        positionFile.write("\n")
        
        # LOOP TO WRITE SPEED INFORMATION OF CLIENTS IN A TEXT FILE
        for key, value in speed.items():
            speedFile.write("%f "%float(value))
        speedFile.write("\n")
        
        # LOOP TO WRITE HEADWAY INFORMATION OF CLIENTS INA  TEXT FILE
        for item in headway:
            headwayFile.write("%f "%float(item))
        headwayFile.write("\n")
        
        pygame.display.flip()           # UPDATE WHOLE SCREEN AFTER ALL CARS HAVE BEEN DRAWN ON THE SCREEN
        clock.tick(120)                 # FRAME RATE
        gameDisplay.fill(white)         # FILL SCREEN WITH WHITE TO UPDATE THE NEXT FRAME
        
#-----------------------------------------------------------------------------
# Function to receive position and speed information from clients
# This function is running for each client in a thread
#-----------------------------------------------------------------------------
def receivePos(client_sock,key, BUFSIZE = 8196):        # client_sock is the client socket connection variables
    global lock, dataList, prev, speed, simulationExit  # REFERENCE GLOBAL VARIABLES
    localList = {}          # LOCAL LIST TO COPY INFORMATION RECEIVED BY CLIENTS
    while True:             # LOOP TO RECEIVE INFORMATION UNTIL SIMULATION QUITS
        try:                # RECEIVE 
            jsonPosList = client_sock.recv(BUFSIZE).decode("utf-8")
        except socket.error as e:           # CHECK IF THERE WAS AN ERROR WHILE RECEIVING INFORMATION
            if detectfailure(e):            # IF THERE WAS A FAILURE/ERROR THEN
                with lock:                  # EXIT SIMULATION LOOP
                    simulationExit = True
                sys.exit()
        if jsonPosList:                     # IF INFORMATION RECEIVED BY CLIENT EXISTS THEN...
            try:
                speedPosList = json.loads(jsonPosList)  # UNPACK FROM STRING TO DICTIONARY USING JSON INTO A LOCAL VARIABLE
            except:                         # IF SERVER COULD NOT UNPACK INFORMATION THEN QUIT SIMULATION
                with lock:
                    simulationExit = True
                sys.exit()
            
            # LOOP TO COPT RECIVED INFORMATION TO LOST LIST
            for i, j in speedPosList.items():
                localList[i] = float(j)
            
            lock.acquire()
            dataList[key-1] = localList['0']        # GET POSITION OF LEAD CAR
            speed[key-1] = localList['1']           # GET SPEED OF PLATOON
            prev = float(dataList[0])           
            lock.release()
            # BLOCK TO SEND ACK TO CLIENT ON RECEIVING INFORMATION
            try:
                client_sock.send("ACK".encode("utf-8"))
            except socket.error as e:
                if detectfailure(e):                # DETECT SOCKET FAILURE TO SEND INFORMATION AND QUIT SIMULATION
                    with lock:
                        simulationExit = True
                    sys.exit()
            except:                                 # DETECT ANY OTHER ERROR AND QUIT SIMULATION
                with lock:
                    simulationExit = True
                sys.exit()                          
            # CHECK IF USER QUIT SIMULATION ON CLIENT SIDE, THEN QUIT SIMULATION ON SERVER SIDE
            if dataList[key-1] < 0 and speed[key-1] < 0:
                with lock:
                    simulationExit = True
                break
            time.sleep(0.001) 
        else:
            print("SYSTEM: Failure detected, quiting now...\r")
            with lock:
                simulationExit = True
            break
                
#-----------------------------------------------------------------------------
# DETECT FAILURE (BROKEN PIPE ERROR), Function to detect socket failure
#-----------------------------------------------------------------------------
def detectfailure(e):
    if isinstance(e.args, tuple):
        if e== errno.EPIPE or e == errno.ECONNRESET:
            print("SYSTEM: Failure detected, quiting now...\r")
            return True
        else:
            return False

#-----------------------------------------------------------------------------
# Function to return tree speed based on platoon speed
#-----------------------------------------------------------------------------
def calcTreeSpeed(speed):
    if sum(speed.values()) == 0:
        return 0
    else:
        leadCarSpeed = round(float(speed[0]),1)
        # switcher IS SYNONYMOUS TO A SWITCH CASE IN C++
        # IT RETURNS THE TREE SPEED FROM A DICTIONARY BASED ON PLATOON SPEED
        switcher={
            0.1:2, 
            0.2:3,
            0.3:4,
            0.4:6,
            0.5:7,
            0.6:8, 
            0.7:9,
            0.8:10,
            0.9:11,
            1.0:12,
            1.1:13,
            1.2:14,
            1.3:15,
            1.4:16,
            1.5:16,
            1.6:17,
            1.7:18,
            1.8:19,
            1.9:20
            }
        return switcher.get(leadCarSpeed,0)
        
#-----------------------------------------------------------------------------
# Function to start pygame simulation
#-----------------------------------------------------------------------------
def draw_background(gameDisplay, display_width, display_height, black, tree, bush, y1, y2):
    # DEFINE ROAD RGB COLORS
    road_1 = (120, 120, 120)
    road_2 = (128, 128, 128)    
    road_3 = (136, 136, 136)
    road_4 = (144, 144, 144)
    road_5 = (152, 152, 152)
    road_6 = (160, 160, 160)
    road_7 = (168, 168, 168)
    road_8 = (176, 176, 176)
    road_9 = (184, 184, 184)
    road_10 = (192, 192, 192)
    
    # DEFINE GROUND RGB COLORS
    ground_1 = (0, 176, 0)
    ground_2 = (0, 192, 0)
    
    # DEFINE TREE AND BUSH COLORS
    green = (0, 125, 0)
    darkGreen = (0, 100, 0)
    
    # DRAW ROAD ON THE SCREEN
    pygame.draw.rect(gameDisplay, road_1, (0, display_height/2 - 100, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_2, (0, display_height/2 - 90, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_3, (0, display_height/2 - 80, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_4, (0, display_height/2 - 70, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_5, (0, display_height/2 - 60, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_6, (0, display_height/2 - 50, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_7, (0, display_height/2 - 40, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_8, (0, display_height/2 - 30, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_9, (0, display_height/2 - 20, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_10, (0, display_height/2 - 10, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_10, (0, display_height/2, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_9, (0, display_height/2 + 10, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_8, (0, display_height/2 + 20, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_7, (0, display_height/2 + 30, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_6, (0, display_height/2 + 40, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_5, (0, display_height/2 + 50, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_4, (0, display_height/2 + 60, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_3, (0, display_height/2 + 70, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_2, (0, display_height/2 + 80, display_width, 10), 0)
    pygame.draw.rect(gameDisplay, road_1, (0, display_height/2 + 90, display_width, 10), 0)
    
    # DRAW GROUND ON THE SCREEN
    pygame.draw.rect(gameDisplay, black, (0, display_height/2 - 600, display_width, 100), 0)
    pygame.draw.rect(gameDisplay, black, (0, display_height/2 - 500, display_width, 100), 0)
    pygame.draw.rect(gameDisplay, black, (0, display_height/2 - 400, display_width, 100), 0)
    pygame.draw.rect(gameDisplay, ground_2, (0, display_height/2 - 300, display_width, 100), 0)
    pygame.draw.rect(gameDisplay, ground_1, (0, display_height/2 - 200, display_width, 100), 0)
    pygame.draw.rect(gameDisplay, ground_1, (0, display_height/2 + 100, display_width, 100), 0)
    pygame.draw.rect(gameDisplay, ground_2, (0, display_height/2 + 200, display_width, 100), 0)
    pygame.draw.rect(gameDisplay, black, (0, display_height/2 + 300, display_width, 100), 0)
    pygame.draw.rect(gameDisplay, black, (0, display_height/2 + 400, display_width, 100), 0)
    pygame.draw.rect(gameDisplay, black, (0, display_height/2 + 500, display_width, 100), 0)

    # DRAW SIDE LINES OF THE ROAD
    pygame.draw.line(gameDisplay,black, (0,display_height/2 - 100),(display_width,display_height/2 - 100), 4)
    pygame.draw.line(gameDisplay,black, (0,display_height/2 + 100),(display_width,display_height/2 + 100), 4)
    
    # DRAW TREE ON THE SCREEN
    for j in range(len(tree)):
        pygame.draw.circle(gameDisplay, green, (tree[j],y1), 25, 0)
        pygame.draw.circle(gameDisplay, green, (tree[j],y2), 25, 0)
    
    # DRAW BUSH ON THE SCREEN
    for j in range(len(bush)):
        pygame.draw.circle(gameDisplay, darkGreen, (bush[j],y1-100), 20, 0)
        pygame.draw.circle(gameDisplay, darkGreen, (bush[j],y2+100), 20, 0)

#-----------------------------------------------------------------------------
################################ MAIN FUNCTION ###############################
if __name__ == "__main__":
    initialize()
