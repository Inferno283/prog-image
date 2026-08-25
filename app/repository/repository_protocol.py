from typing import Protocol


class Repository(Protocol):
    def store(self):
        pass
    
    def retrieve(self):
        pass