import bliss.scanner 
import os
import simplejson

def test_search():
    f = os.path.join(os.path.dirname(__file__),
                     '..',
                     '..',
                     'resources',
                     'scanner.txt')
    for line in open(f, 'r'):
        if line.startswith("#"):
            continue
        tokens = line.strip().split(' | ')
        yield check_search, tokens
    #    return
    
def check_search(tokens):
    name, year = bliss.scanner.parse_name(tokens[1])
    d = bliss.scanner.get_duration(tokens[1])
    m = bliss.scanner.search(name, year, d)
    assert m is not None, "no result for: %s" % (tokens[1])
    assert m['id'] == tokens[0], "got: %s (%f) expected: %s for %s" % (m['id'], m['score_value'], tokens[0], tokens[1])
        
                
