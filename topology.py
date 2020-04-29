import json
from types import SimpleNamespace 
from tabulate import tabulate
import itertools
from collections import namedtuple

__topology_map = None

def print_map():
    map = []
    for i, node1 in enumerate(__topology_map.nodes):
        row = []
        for j, node2 in enumerate(__topology_map.nodes):
            if j < i:
                state = next((link 
                for link in __topology_map.links 
                if(node1.index in link.link and node2.index in link.link))
                , None)
                if state is None:
                    row.append('∞')
                else:
                    row.append(state.cost)
            elif j == i:
                row.append('0')
            else:
                row.append('')
        map.append(row)
    table = tabulate(map, headers=range(1, len(__topology_map.nodes)+1)
    , showindex=range(1, len(__topology_map.nodes)+1))
    print('===========================Topology Map===================================')
    print(table)
    print('===========================Topology Map===================================')

# initialize the topology from a config file
def create_map(file='topology.json'):
    global __topology_map
    if __topology_map == None:
        with open(file, 'r') as f:
            __topology_map = json.load(f, object_hook=lambda d: SimpleNamespace(**d))
    print_map()

def static_edges():
    edges = set() # set of frozenset
    for link in __topology_map.links:
        indexes = link.link
        ips = []
        for index in indexes:
            node = next((node for node in __topology_map.nodes if node.index == index), None)
            if node is not None:
                ips.append(node.ip)
            else:
                break
        if len(ips) == 2:
            edges.add(frozenset(ips))
    return frozenset(edges)

def node_identifier(ip):
    node = next((node for node in __topology_map.nodes if (node.ip == ip)), None)
    if node is not None:
        return node.index
    else:
        return -1

# return a set of namedtuple(['TargetIp', 'Cost'])
def static_adjacents(src):
    srcnode = next((node for node in __topology_map.nodes if(node.ip == src)), None)
    if(srcnode is None):
        return []
    IndexAdjacent = namedtuple('IndexAdjacent', ['index', 'cost'])
    adjacents = map(lambda link: IndexAdjacent(
        index=next(index for index in link.link if index != srcnode.index)
        , cost=link.cost)
        , [link for link in __topology_map.links if(srcnode.index in link.link)])
    AdjacentState = namedtuple('AdjacentState', ['TargetIp', 'Cost'])
    return set(map(lambda adjacent: AdjacentState(
        TargetIp = next(node for node in __topology_map.nodes if node.index==adjacent.index).ip,
        Cost = adjacent.cost)
        , adjacents))

def is_adjacent(src, dest):
    (srcnode,  destnode)= next((
        (node1, node2) 
        for node1 in __topology_map.nodes if(node1.ip == src) 
        for node2 in __topology_map.nodes if(node2.ip == dest))
        , (None, None))
    if srcnode is None or destnode is None:
        return False

    return any(link for link in __topology_map.links 
    if(frozenset((srcnode.index, destnode.index)) == frozenset(link.link)))

if __name__ == "__main__":
    create_map()
    for node in __topology_map.nodes:
        print("srouce:", node.ip, "adjacents:"
        , ",".join(list(map(lambda adj: "(" + adj.TargetIp + "-" + str(adj.Cost) + ")", static_adjacents(node.ip)))))
    for link in __topology_map.links:
        print(link.link[0], link.link[1], link.cost, sep="-")

    print(is_adjacent("10.0.0.1", "10.0.0.7"))
    print(is_adjacent("10.0.0.11", "10.0.0.1"))
    print(is_adjacent("10.0.0.1", "10.0.0.16"))
    print(is_adjacent("10.0.0.1", "10.0.0.255"))