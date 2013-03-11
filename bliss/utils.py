import re

def escape_generic(s):
    return re.sub(r"[^\w-]", "_", s, flags=re.IGNORECASE+re.UNICODE)

class Unbuffered:
    def __init__(self, stream):
        self.stream = stream
        
    def write(self, data):
        self.stream.write(data)
        self.stream.flush()
        
    def __getattr__(self, attr):
        return getattr(self.stream, attr)
       
