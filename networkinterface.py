import topology
import threading
from queue import Queue, Empty
from messages import Ping, Pong, Unicast, Broadcast, NodeAdjacentsDatabase

class NetworkInterface:
    # edges: frozenset of edges which is a frozenset of the two adjacent nodes
    def __init__(self, edges:frozenset):
        self.__message_queue = Queue()
        self.__linkdatabase = {edge:True for edge in edges}
        self.__nodes = {} # dict with key as the ip and value as the Router object
        self.__thread = None
        self.__process_event = threading.Event()
        self.__is_opened = False

    def open(self):
        self.__is_opened = True
        self._thread = threading.Thread(target = self.__process_messages)
        self._thread.daemon = True
        self._thread.start()

    def IsOpen(self):
        return self.__is_opened

    def close(self):
        self.__is_opened = False
        self.__process_event.set()
        self._thread.join()
    
    def faillink(self, ip1, ip2):
        key = frozenset([ip1, ip2])
        if key in self.__linkdatabase:
            self.__linkdatabase[key] = False
    
    def recoverlink(self, ip1, ip2):
        key = frozenset([ip1, ip2])
        if key in self.__linkdatabase:
            self.__linkdatabase[key] = True

    def __process_messages(self):
        while self.__is_opened:
            try:
                self.__process_event.wait(0.1) # timeout 100ms
                while self.__message_queue.qsize() > 0:
                    message = self.__message_queue.get_nowait()
                    if message.src not in self.__nodes:
                        continue # ignore the messages from unknown source       
                    if isinstance(message, Unicast):
                        if frozenset([message.src, message.dest]) not in self.__linkdatabase:
                            continue
                        if not self.__linkdatabase[frozenset([message.src, message.dest])]:
                            continue # link is down
                        dest = self.__nodes.get(message.dest, None)
                        if dest is None:
                            continue # unknown destination, ignore
                        if isinstance(message, Ping):
                            dest.on_hello(message.src)
                        elif isinstance(message, Pong):
                            dest.on_hello_back(message.src)
                    elif isinstance(message, Broadcast):
                        for dest in self.__nodes.values():
                            if dest.ip in message.dests and \
                            frozenset([message.src, dest.ip]) in self.__linkdatabase and \
                            self.__linkdatabase[frozenset([message.src, dest.ip])]:
                                dest.on_broadcast_message(message)
            except Empty:
                raise
            finally:
                self.__process_event.clear()

    def register(self, router):
        self.__nodes[router.ip] = router

    def sendhello(self, src_ip, dest_ip):
        self.sendto(Ping(src_ip, dest_ip))
    
    def sendhelloback(self, src_ip, dest_ip):
        self.sendto(Pong(src_ip, dest_ip))

    def sendto(self, msg:Unicast):
        if not self.__is_opened:
            raise RuntimeError("message pipe is closed.")
        # only the adjacent routers can exchange hello messages
        # otherwise, the hello message is discarded
        if frozenset([msg.src, msg.dest]) in self.__linkdatabase and \
        self.__linkdatabase[frozenset([msg.src, msg.dest])]:
            self.__message_queue.put_nowait(msg)
            self.__process_event.set()
    
    # broadcast message to all the routuers on the connected path
    def broadcast(self, message:Broadcast):
        if not self.__is_opened:
            raise RuntimeError("message pipe is closed.")
        self.__message_queue.put_nowait(message)
        self.__process_event.set()

if __name__ == "__main__":
    topology.create_map()
    net = NetworkInterface(topology.static_edges())
    pass
