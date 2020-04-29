from messages import Broadcast, NodeAdjacentsDatabase
from collections import namedtuple
from networkinterface import NetworkInterface
from tabulate import tabulate
import threading
import topology
import time
import scheduler
import copy
import math

class RouterFactory:
    def __init__(self, nodeips, net:NetworkInterface):
        self.__routers = {}
        for ip in nodeips:  
            self.__routers[ip]=Router(ip,  net, topology.static_adjacents(ip))
    
    def GetRouters(self):
        return self.__routers.values()

    def GetRouter(self, ip):
        return self.__routers.get(ip, None)

class RouterFactoryBuilder:
    def __init__(self, net:NetworkInterface):
        self.__node_ips = []
        self.__net = net

    def AddNode(self, ip):
        self.__node_ips.append(ip)

    def Build(self):
        return RouterFactory(self.__node_ips, self.__net)

class RouterAdjacentState:
    # state: namedtuple{TargetIp, Cost}
    def __init__(self, state):
        self.State = state
        self.Online = True
        self.LastPingIn = time.monotonic()
        self.LastPingOut = time.monotonic()
    
    def OnPing(self):
        self.LastPingIn = time.monotonic()
        self.Online = True

    def Ping(self):
        self.LastPingOut = time.monotonic()

class Router:
    # adjacents: set of namedtuple{TargetIp, Cost}
    def __init__(self, ip:str, net:NetworkInterface, adjacents:set):
        self.ip = ip
        self.__activate = False
        self.__net = net
        self.__link_state_database=LinkStateDatabase()
        self.__adjacents = {state.TargetIp: RouterAdjacentState(state) for state in adjacents}
        self.__link_state_database.UpdateLinkState(
            NodeAdjacentsDatabase(ip, adjacents))
        self.__state_lock = threading.RLock()
        self.__last_broadcast = time.monotonic()
        scheduler.Instance.Scheule(self.OnTick, None, 2)
        self.__forwarding_table = {} # distance map, key:dest ip; value: tuple(set(Precedents), Cost)
        self.__calculate_forwarding_table()

    def OnTick(self, state):
        if not self.__activate:
            return
        for adjacent in self.__adjacents.values():
            if adjacent.LastPingOut + scheduler.PingInterval <= time.monotonic():
                self.hello(adjacent.State.TargetIp)
            if adjacent.LastPingIn + scheduler.PingInterval * 2 <= time.monotonic():
                adjacent.Online = False
        with self.__state_lock:
            payload = NodeAdjacentsDatabase(self.ip, set(map(lambda state: state.State
                , [adjacent for adjacent in self.__adjacents.values() if adjacent.Online])))
            updated = self.__link_state_database.UpdateLinkState(payload)
        if updated:
            self.__calculate_forwarding_table()
        if updated or \
        self.__last_broadcast + scheduler.BroadcastInterval <= time.monotonic():
            self.broadcast()

    # broadcast link state changes.
    def broadcast(self):
        if not self.__activate:
            return
        payload = NodeAdjacentsDatabase(self.ip, set(map(lambda state: state.State
        , [adjacent for adjacent in self.__adjacents.values() if adjacent.Online])))
        dests = set(self.__adjacents.keys())
        audiences = dests.copy()
        audiences.add(self.ip)
        message = Broadcast(self.ip, dests, audiences, payload) 
        self.__net.broadcast(message)
    
        # broadcast link state changes.
    def broadcastmessage(self, message:Broadcast):
        if not self.__activate:
            return
        self.__net.broadcast(message)
        self.__last_broadcast = time.monotonic()

    # callback of a broadcast message
    def on_broadcast_message(self, message:Broadcast):
        if not self.__activate:
            return
        updated = False
        with self.__state_lock:
            if message.src != self.ip:
                payload = NodeAdjacentsDatabase(self.ip, set(map(lambda state: state.State
                    , [adjacent for adjacent in self.__adjacents.values() if adjacent.Online])))
                updated |= self.__link_state_database.UpdateLinkState(payload)
                updated |= self.__link_state_database.UpdateLinkState(message.payload)
                adjacent_node = self.__adjacents.get(message.src, None)
                if adjacent_node is not None:
                    adjacent_node.OnPing()
        if updated:
            self.__calculate_forwarding_table()
        dests = set(self.__adjacents.keys()) - message.audiences
        if len(dests) > 0:
            new_message = copy.copy(message)
            new_message.src = self.ip
            new_message.dests = dests
            new_message.audiences = copy.copy(message.audiences)
            new_message.audiences |= dests
            new_message.audiences.add(self.ip)
            self.broadcastmessage(new_message)

    # send a hello message to the neighbor
    #receiver: the destination ip
    def hello(self, receiver):
        if not self.__activate:
            return
        adjacent_node = self.__adjacents.get(receiver, None)
        if adjacent_node is not None:
            self.__net.sendhello(self.ip, receiver)
            adjacent_node.Ping()

    # callback of hello message from neighbor
    def on_hello(self, sender):
        if not self.__activate:
            return
        adjacent_node = self.__adjacents.get(sender, None)
        if adjacent_node is not None:
            adjacent_node.OnPing()
            self.on_hello_back(adjacent_node)
            payload = NodeAdjacentsDatabase(self.ip, set(map(lambda state: state.State
                , [adjacent for adjacent in self.__adjacents.values() if adjacent.Online])))
            updated = self.__link_state_database.UpdateLinkState(payload)
            if updated:
                self.__calculate_forwarding_table()
    
    # send a hello back message to the neighbor
    #receiver: the destination ip
    def hello_back(self, receiver):
        if not self.__activate:
            return
        adjacent_node = self.__adjacents.get(receiver, None)
        if adjacent_node is not None:
            self.__net.sendhelloback(self.ip, receiver)
            adjacent_node.Ping()
    
        # callback of hello message from neighbor
    def on_hello_back(self, sender):
        if not self.__activate:
            return
        adjacent_node = self.__adjacents.get(sender, None)
        if adjacent_node is not None:
            adjacent_node.OnPing()
            payload = NodeAdjacentsDatabase(self.ip, set(map(lambda state: state.State
                , [adjacent for adjacent in self.__adjacents.values() if adjacent.Online])))
            updated = self.__link_state_database.UpdateLinkState(payload)
            if updated:
                self.__calculate_forwarding_table()
    
    def fail(self):
        self.__activate = False

    def recover(self):
        if not self.__activate:
            self.__activate = True
            self.broadcast()

    # Dijsktra’s Algorithm with multi path routing
    def __calculate_forwarding_table(self):
        N = set([self.ip])
        D = {} # distance map, key:dest ip; value: tuple(set(Precedents), Cost)
        PathLink = namedtuple('PathLink', ['Precedents', 'Cost'])
        with self.__state_lock:
            # Initialize the distance map
            for v in self.__link_state_database.link_states:
                if v == self.ip:
                    continue
                if v in self.__adjacents and self.__adjacents[v].Online:
                    D[v] =  PathLink(
                        Precedents = set([self.ip]),
                        Cost = self.__adjacents[v].State.Cost)
                else:
                    D[v] = PathLink(
                        Precedents = set(),
                        Cost = math.inf)
            
            while len(N) < len(self.__link_state_database.link_states):
                w = None
                for v in self.__link_state_database.link_states:
                    if v in N:
                        continue;
                    if w is None:
                        w = v
                    elif D[w].Cost > D[v].Cost:
                        w = v
                N.add(w)
                for v in self.__link_state_database.link_states[w]:
                    if v.TargetIp in N:
                        continue
                    if D[v.TargetIp].Cost > D[w].Cost + v.Cost:
                        D[v.TargetIp] = PathLink(
                            Precedents =  set([w]),
                            Cost = D[w].Cost + v.Cost)
                    elif D[v.TargetIp].Cost == D[w].Cost + v.Cost:
                        D[v.TargetIp].Precedents.add(w)
        self.__forwarding_table = D 

    def print_forwardtable(self):
        forwardlist = []
        for k, v in self.__forwarding_table.items():
            if k == self.ip:
                continue
            if v.Cost == math.inf:
                continue
            row = [k]
            row.append(list(v.Precedents))
            row.append(v.Cost)
            forwardlist.append(row)
        table = tabulate(forwardlist, headers=['dest', 'precedents', 'cost'])
        print(table)

# The link state database maintained by per router
class LinkStateDatabase:
    def __init__(self):
        self.link_states = {} # key: the ip of node; value: set of namedtuple{TargetIp, Cost}

    def UpdateLinkState(self, node_data:NodeAdjacentsDatabase):
        AdjacentLink = namedtuple('AdjacentLink', ['TargetIp', 'Cost'])
        if node_data.NodeIp not in self.link_states:
            self.link_states[node_data.NodeIp] = node_data.Adjacents
            for node in node_data.Adjacents:
                if node.TargetIp not in self.link_states:
                    self.link_states[node.TargetIp] = set(
                        [AdjacentLink(TargetIp=node_data.NodeIp, Cost=node.Cost)])
            return True

        linktates = self.link_states[node_data.NodeIp]
        # only update is there is changes
        diff = linktates ^ node_data.Adjacents
        if len(diff) > 0 :
            self.link_states[node_data.NodeIp] = node_data.Adjacents
            for node in node_data.Adjacents:
                if node.TargetIp not in self.link_states:
                    self.link_states[node.TargetIp] = set(
                        [AdjacentLink(TargetIp=node_data.NodeIp, Cost=node.Cost)])
            return True
        return False
