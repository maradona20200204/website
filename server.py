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
log_file = config_dict['log_file']
data_latest_file = config_dict['data_latest_file']
data_cache_file = config_dict['data_cache_file']
gpu_latest_file = config_dict['gpu_latest_file']
use_websocket = True if config_dict['use_websocket'] == 'True' else False


def writelog(content, path=log_file, logtime=True, breakline=True, ip='',prefixstr=prefixstr):
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
    
    def open(self):
        WebSocketHandler.cache = self
        
    def on_close(self):
        WebSocketHandler.cache = None
        
    @classmethod
    def send_updates(cls, message=None):
        #print(time.strftime('%Y-%m-%d %H:%M:%S'), WebSocketHandler.cache, message)
        if WebSocketHandler.cache and use_websocket:
            if not message:
                WebSocketHandler.cache.write_message("Hello, world! from %s:%s"%(ip, port))
            else:
                WebSocketHandler.cache.write_message(message)
            

class GPUInfoHandler(tornado.web.RequestHandler):
    def post(self):
        try:
            info = self.get_argument('gpuinfo', 'NAK')
            if info == 'NAK':
                data = {'status':'False', 'message':info, 'type':'GPU'}
            else:
                data = {'status':'True', 'message':info, 'type':'GPU'}
            WebSocketHandler.send_updates(data)
            with open(gpu_latest_file, 'w') as f:
                json.dump(data, f)
            self.write("ACK")
        except:
            #print(traceback.format_exc())
            self.write("NAK: " + traceback.format_exc())
            
            
class InfoHandler(tornado.web.RequestHandler):
    def post(self):
        try:
            epoch = self.get_argument('epoch', 'NAK')
            project = self.get_argument('project', 'NAK')
            data = self.get_argument('data', 'NAK')
            dataid = self.get_argument('dataid', 'NAK')
            if epoch != 'NAK':
                try:
                    epoch = int(epoch)
                except:
                    epoch = 'NAK'
            if epoch == 'NAK' or project == 'NAK' or data == 'NAK' or dataid == 'NAK':
                message = {'content': 'NAK', 'latest': 'NAK'}
                senddata = {'status':'False', 'message': message, 'type':'Info', 'protocol':'websocket'}
                with open(data_latest_file, 'w') as f:
                    json.dump(senddata, f)
                WebSocketHandler.send_updates(senddata)
            else:
                latest = 'Latest news (dataid=%s): project %s, epoch %s, data %s'%(dataid, project, epoch, data)
                print(latest)
                contentjson = {'epoch': epoch, 'project': project, 'data':data, 'dataid':dataid, 'time':time.strftime('%Y-%m-%d %H:%M:%S')}
                message =  {'content': contentjson, 'latest': latest}
                senddata = {'status':'True', 'message': message,'type':'Info', 'protocol':'websocket'}
                with open(data_latest_file, 'w') as f:
                    json.dump(senddata, f)
                WebSocketHandler.send_updates(senddata)  
            self.write("ACK")
        except:
            print(traceback.format_exc())
            self.write("NAK: " + traceback.format_exc())

            
class QueryHandler(tornado.web.RequestHandler):
    def post(self):
        try:
            datatype = self.get_argument('type', 'NAK')
            assert datatype in ['NAK', 'GPU', 'Info']
            if datatype == 'NAK':
                self.write({'type':'NAK', 'result':'', 'cache':'None', 'status':'False', 'protocol':'http/https'})
                return
            else:
                if datatype == 'GPU':
                    file = gpu_latest_file
                else:
                    file = data_latest_file
                cache_file_exists = False
                response = ''
                if os.path.isfile(file):
                    with open(file, 'r') as f:
                        response = f.read()
                    cache_file_exists = True
                self.write({'type':datatype, 'response':response, 'cache':str(cache_file_exists), 'status':'True', 'protocol':'http/https'})
        except:
            self.write("NAK: " + traceback.format_exc())
            
            
def main():
    tornado.options.parse_command_line()
    application = tornado.web.Application(
        [("/", MainHandler), (r"/(?i)ping|/(?i)hello", HelloworldHandler),('/websocket', WebSocketHandler), ('/gpu', GPUInfoHandler), ('/info', InfoHandler), ('/query', QueryHandler)], static_path=os.path.join(os.path.dirname(__file__), "static")
        )
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(port)
    http_server.start(num_processes=0)
    tornado.ioloop.IOLoop.current().start()

    
if __name__ == "__main__":
    main()
