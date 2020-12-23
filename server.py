import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
import os
import re
import time
import json
import traceback
from tornado.options import define, options
with open('config.json') as f:
    config_dict = json.load(f)
ip = config_dict['ip']
port = config_dict['port']
rootfile = config_dict['rootfile']
prefixstr = config_dict['prefixstr']
protocol = config_dict['protocol']
static_file = config_dict["static_file"]


def writelog(content, path='log/log.txt', logtime=True, breakline=True, ip='',prefixstr=prefixstr):
    '''
    I think the logging module is difficult to use
    '''
    if logtime:
        if ip:
            content = prefixstr+' [' + time.strftime('%Y-%m-%d %H:%M:%S') + ', ip = %s ]'%ip + content
        else:
            content = prefixstr + ' [' + time.strftime('%Y-%m-%d %H:%M:%S') + ']' + content
    if breakline:
        content += '\n'
    with open(path, 'a') as f:
        f.write(content)
        
        
def content(filename):
    with open(filename) as f:
        data = f.read()
    if filename.find("htm") >= 0 or filename.find("txt") >= 0:
        #Here I cannot use the template system of tornado, because {{}} conflicts with Vue.
        data = data.replace('var ip = "127.0.0.1";', 'var protocol = "%s";\n\t\t var ip = "%s";'%(protocol, ip))
        data = data.replace('port = 0', 'port = %s'%port)
    return data


    
class MainHandler(tornado.web.RequestHandler):
    '''
    Return index.txt (or index.html)
    '''
    
    def get(self):
        with open(rootfile) as f:
            self.write(content(rootfile))
            
            
class HelloworldHandler(tornado.web.RequestHandler):
    '''
    Enable users to ping the server.
    '''    
    def get(self):
        self.action()
      
    def post(self):
        self.action()
        
    def action(self, log=True):
        if self.request.uri.lower().find("ping") >= 0:
            self.write("pong")
        elif self.request.uri.lower().find("hello") >= 0:
            self.write("helloworld!")
        if log:
            writelog(json.dumps({"uri":self.request.uri, "method":self.request.method, "handler":self.__class__.__name__}), ip=self.request.remote_ip) 

                        
class WebSocketHandler(tornado.websocket.WebSocketHandler):
    cache = None
    
    def check_origin(self, origin):  
        return True 
    
    def open(self):
        WebSocketHandler.cache = self
        
    def on_close(self):
        WebSocketHandler.cache = None
        
    @classmethod
    def send_updates(cls, message=None):
        #print(WebSocketHandler.cache)
        if WebSocketHandler.cache:
            if not message:
                WebSocketHandler.cache.write_message("Hello, world! from %s:%s"%(ip, port))
            else:
                WebSocketHandler.cache.write_message(message)
            

class GPUInfoHandler(tornado.web.RequestHandler):
    def post(self):
        try:
            info = self.get_argument('gpuinfo', 'NAK')
            if info == 'NAK':
                WebSocketHandler.send_updates({'status':'False', 'message':info})
            else:
                WebSocketHandler.send_updates({'status':'True', 'message':info})
            self.write("ACK")
        except:
            self.write("NAK: " + traceback.format_exc())
            
            
def main():
    tornado.options.parse_command_line()
    application = tornado.web.Application(
        [("/", MainHandler), (r"/(?i)ping|/(?i)hello", HelloworldHandler),('/websocket', WebSocketHandler), ('/gpu', GPUInfoHandler)],static_path=os.path.join(os.path.dirname(__file__), "static")
        )
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(port)
    http_server.start(num_processes=0)
    tornado.ioloop.IOLoop.current().start()

    
if __name__ == "__main__":
    main()