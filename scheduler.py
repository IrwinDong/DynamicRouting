import threading, time

PingInterval = float(5) # 5 seconds
BroadcastInterval = float(10)

class FutureCallback:
    def __init__(self, callback:None, interval:float, state:None):
        self.Callback = callback
        self.Interval = interval
        self.State = state

class TickScheduler:
    def __init__(self):
        self.__schedule_thread = threading.Thread(target=self.__TickCallback)
        self.__schedule_thread.daemon = True
        self.__running = False
        self.__schedule_signal = threading.Event()
        self.__callbacks = {}
        self.__callbacks_lock = threading.RLock()
   
    def Start(self):
        self.__running = True
        self.__schedule_thread.start()
    
    def Stop(self):
        self.__running = False
        self.__schedule_signal.set()
    
    def __TickCallback(self):
        while self.__running:
            with self.__callbacks_lock:
                currenttick = time.monotonic()
                futurestamp = currenttick
                for nexttick in [key for key in self.__callbacks.keys() if key <= currenttick]:
                    for futurecall in self.__callbacks.pop(nexttick):
                        futurecall.Callback(futurecall.State)
                        self.Scheule(futurecall.Callback, futurecall.State, futurecall.Interval)
                futurestamp = min(self.__callbacks.keys(), default=-1)
            currenttick = time.monotonic()
            self.__schedule_signal.wait(futurestamp-currenttick if futurestamp-currenttick> 0 else float(500))
            self.__schedule_signal.clear()

    # callback: function
    # interval: in fractional seconds
    def Scheule(self, callback:None, state:None, interval:float):
        with self.__callbacks_lock:
            # take precision to 100ms
            timestamp = round(time.monotonic()+interval, 1)
            callbacks:list = self.__callbacks.get(timestamp, None)
            future = FutureCallback(callback, interval, state)
            if callbacks is None:
                callbacks = [future]
                self.__callbacks[timestamp] = callbacks
            else:
                callbacks.append(future)
        self.__schedule_signal.set()

    def CancelSchedule(self, callback:None):
        with self.__callbacks_lock:
            for k, v in self.__callbacks:
                if callback in v:
                    v.remove(callback)
                if not v:
                    self.__callbacks.pop(k)

Instance = TickScheduler()

if __name__ == "__main__":
    scheduler = TickScheduler()
    scheduler.Start()
    test_callback = lambda state: print("state:" + str(state) + ":" + str(time.time() % 1000) + "\n")
    scheduler.Scheule(test_callback, 5, 5)
    time.sleep(6)
    scheduler.Scheule(test_callback, 2, 2)
    input()
    scheduler.Stop()

