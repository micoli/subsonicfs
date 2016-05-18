import re,copy,pprint
import functools

'''[{    
    'rgx'     : 'ortp-message-New PulseAudio context state: (?<state>.*)',
    'handler' : repr,
    'vars'    : {'type' : 'pulseAudioContext'}
}]'''
class Matcher():
    rules=[]
    
    def __init__(self,arg_rules=None):
        if arg_rules:
            self.init(arg_rules)
            
    def init(self,arg_rules):
        self.rules=arg_rules
        self.compile_rules()
        
    def add_rule(self,rule):
        self.rules.append(rule)
        self.compile_rule(rule)
        
    def compile_rules(self):    
        for k,rule in enumerate(self.rules):
            self.compile_rule(rule)
                
    def compile_rule(self,rule):    
        if('rgxvars' not in rule):
            rule['rgxvars']=[]
        m = re.findall('(\?P<(.*?)>)',rule['rgx'])
        if(m):
            for a in m:
                rule['rgxvars'].append(a[1]);
            
    
    def route(self,route,datas=None,method=None):
        for rule in self.rules:
            if(re.search(rule['rgx'],route)):
                found_rule=copy.deepcopy(rule)
                match = re.match(found_rule['rgx'],route)
                for var in found_rule['rgxvars']:
                    found_rule['vars'][var]=match.groupdict()[var]
                found_rule['handler'](found_rule['vars'],datas);
                return True
        return False

def route(method=None,matcher=None,regex=None, vars={}):
    if not callable(method):
        return functools.partial(route, matcher=matcher,regex=regex, vars=vars)
    method.gw_method = matcher or method.__name__
    matcher.add_rule({
        'rgx'     : regex,
        'vars'    : vars,
        'handler' : method
    })
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        method(*args, **kwargs)
    return wrapper
