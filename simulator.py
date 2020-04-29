from networkinterface import NetworkInterface
from router import Router, RouterFactory, RouterFactoryBuilder
import topology
from signal import signal, SIGINT
from sys import exit
import atexit
import scheduler
import re
from threading import Timer

routerFactory = None
network = None

def CreateRouterFactory(net:NetworkInterface):
    builder = RouterFactoryBuilder(net)
    for node in topology.__topology_map.nodes:
        builder.AddNode(node.ip)
    return builder.Build()

def Initialize(net:NetworkInterface):
    global routerFactory
    routerFactory = CreateRouterFactory(net)
    for router in routerFactory.GetRouters():
        net.register(router)
    net.open()

def TearDown(net):
    if net.IsOpen():
        net.close()

def printhelp():
    print('Instructions:')
    print('* Type "print [ip]" to print the forwarding table of router with specified ip')
    print('* Type "fail [ip]" to shutdown the router with specified ip')
    print('* Type "recover [ip]" to recover the router with specified ip')
    print('* Type "fail [ip]-[ip]" to shutdown the link between the two routers')
    print('* Type "recover [ip 1]-[ip 2]" to recover the link between the two routers')
    print('* type "help" for the instructions')
    print('* type "CTRL-C" to exit')

def InterpretCommand(command:str):
    ip_pattern = '(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])'
    print_pattern =  r"^\s*print\s+(" + ip_pattern + ")\s*$"
    recover_router_pattern = r"^\s*recover\s+(" + ip_pattern + ")\s*$"
    fail_router_pattern = r"^\s*fail\s+(" + ip_pattern + ")\s*$"
    recover_link_pattern = r"^\s*recover\s+(?P<ip1>" + ip_pattern + ")-(?P<ip2>" + ip_pattern + ")\s*$"
    fail_link_pattern = r"^\s*fail\s+(?P<ip1>" + ip_pattern + ")-(?P<ip2>" + ip_pattern  + ")\s*$"
    help_patter = r"^\s*help\s*$"
    while True:
        m = re.match(print_pattern, command, re.IGNORECASE)
        if m:
            r = routerFactory.GetRouter(m.group(1))
            if r:
                r.print_forwardtable()
                print('\trequest done.')
            else:
                print("router '" + m.group(0) + "' does not exist")
            break
        m = re.match(recover_router_pattern, command, re.IGNORECASE)
        if m:
            routerFactory.GetRouter(m.group(1)).recover()
            print('\trequest done. wait for 10s for route path refresh...')
            Timer(10, lambda : print('\troute path refreshed')).start()
            break
        m = re.match(fail_router_pattern, command, re.IGNORECASE)
        if m:
            routerFactory.GetRouter(m.group(1)).fail()
            print('\trequest done. wait for 10s for route path refresh...')
            Timer(10, lambda : print('\troute path refreshed')).start()
            break
        m = re.match(recover_link_pattern, command, re.IGNORECASE)
        if m:
            network.recoverlink(m.group('ip1'), m.group('ip2'))
            print('\trequest done. wait for 10s for route path refresh...')
            Timer(10, lambda : print('\troute path refreshed')).start()
            break
        m = re.match(fail_link_pattern, command, re.IGNORECASE)
        if m:
            network.faillink(m.group('ip1'), m.group('ip2'))
            print('\trequest done. wait for 10s for route path refresh...')
            Timer(10, lambda : print('\troute path refreshed')).start()
            break
        m = re.match(help_patter, command, re.IGNORECASE)
        if m:
            printhelp()
            break
        print("Unknown command. Type 'help' for more information")
        break

def exithandler(signal_received, frame):
    exit(0)

def Run():
    signal(SIGINT, exithandler)
    topology.create_map()
    global network
    network = NetworkInterface(topology.static_edges())
    atexit.register(TearDown, network)
    try:
        Initialize(network)
        scheduler.Instance.Start()
        for router in routerFactory.GetRouters():
            router.recover()
        printhelp()
        while True:
            command = input()
            if command:
                InterpretCommand(command)
    finally:
        scheduler.Instance.Stop()
        if network.IsOpen():
            network.close()    

if __name__ == "__main__":
    Run()