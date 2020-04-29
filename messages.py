
import copy

class Unicast:
    def __init__(self, src, dest):
        self.src = src
        self.dest = dest

class Ping(Unicast):
    def __init__(self, src, dest):
        Unicast.__init__(self, src, dest)

class Pong(Unicast):
    def __init__(self, src, dest):
        Unicast.__init__(self, src, dest)

class NodeAdjacentsDatabase:
    # Adjacents: set of namedtuple{TargetIp, Cost}
    def __init__(self, src_ip, adjacents:set):
        self.NodeIp = src_ip
        self.Adjacents = copy.copy(adjacents)

class Broadcast:
    # src: source ip
    # payload: type of NodeAdjacentDatabase
    def __init__(self, src, dests, audiences, payload:NodeAdjacentsDatabase):
        self.orgin = src
        self.src = src
        self.dests = dests
        self.payload = payload
        self.audiences = audiences