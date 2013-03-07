import re

def escape_generic(s):
    return re.sub(r"[^\w]", "_", s, flags=re.IGNORECASE+re.UNICODE)
